"""Consolidated adversarial tests for security-critical controls."""
import json
import os
import subprocess
import sys
import threading
import time

import pytest

from vfs.backends.localfs import LocalFSBackend
from vfs.types import (
    ConflictError, NotFoundError, ValidationError, VFSError,
    ZoneViolationError,
)


# ----- TOCTOU symlink swap -----

@pytest.mark.timeout(30)
def test_toctou_symlink_swap(tmp_path):
    """Adversary thread swaps a path component between symlink and real dir;
    writer must never land outside root.

    Barrier-synced + N=10_000 to ensure the race actually fires.
    """
    backend = LocalFSBackend(str(tmp_path))
    outside = tmp_path.parent / "outside-sentinel"
    outside.mkdir(exist_ok=True)
    sentinel = outside / "DO_NOT_OVERWRITE.txt"
    sentinel.write_text("INTACT", encoding="utf-8")

    stop = threading.Event()
    barrier = threading.Barrier(2)

    def adversary():
        barrier.wait()
        path = tmp_path / "swappable"
        while not stop.is_set():
            try:
                if path.is_symlink() or path.exists():
                    if path.is_symlink() or path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        try:
                            for child in path.iterdir():
                                child.unlink()
                        except OSError:
                            pass
                        try:
                            path.rmdir()
                        except OSError:
                            pass
                path.symlink_to(outside)
            except OSError:
                pass
            try:
                if path.is_symlink():
                    path.unlink()
                path.mkdir(exist_ok=True)
            except OSError:
                pass

    t = threading.Thread(target=adversary, daemon=True)
    t.start()
    barrier.wait()

    violations = 0
    successes = 0
    N = 10_000
    for _ in range(N):
        try:
            backend.write("swappable/inner.md", "agent-content")
            successes += 1
        except (ZoneViolationError, NotFoundError, OSError):
            violations += 1

    stop.set()
    t.join(timeout=2)
    backend.close()

    assert sentinel.read_text() == "INTACT", \
        "sentinel outside root was overwritten — TOCTOU defense failed"
    assert violations > 0, (
        f"expected at least one race violation across {N} iterations; got 0. "
        f"the adversary may not be running concurrently — re-check thread setup."
    )


# ----- CAS-create concurrency -----

def test_cas_create_concurrent(tmp_path):
    """Many threads racing CAS-create the same key — exactly one wins."""
    backend = LocalFSBackend(str(tmp_path))
    N = 20
    results = []
    barrier = threading.Barrier(N)

    def worker(i):
        barrier.wait()
        try:
            backend.write("racey.md", f"v{i}", if_match="")
            results.append(("ok", i))
        except Exception as e:
            results.append(("err", type(e).__name__))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    backend.close()

    winners = [r for r in results if r[0] == "ok"]
    losers = [r for r in results if r[0] == "err"]
    assert len(winners) == 1, f"expected 1 winner, got {len(winners)}: {results}"
    assert len(losers) == N - 1
    assert all("Conflict" in r[1] for r in losers)


# ----- rate limit DoS shielding -----

def test_rate_limit_blocks_loop(tmp_path):
    """Loop-prompt-injection style: many sequential writes hit the limit."""
    from vfs.ratelimit import WriteRateLimiter
    rl = WriteRateLimiter(str(tmp_path / "rl.state"), limit=10, window_s=60)
    succeeded = 0
    for _ in range(50):
        try:
            rl.check()
            succeeded += 1
        except VFSError:
            break
    assert succeeded == 10


# ----- boundary -----

def test_write_exact_cap(tmp_path):
    """Exactly 10 MB → success."""
    backend = LocalFSBackend(str(tmp_path))
    body = "x" * 10_000_000
    etag = backend.write("at-cap.md", body)
    assert etag
    content, _, _ = backend.read("at-cap.md")
    assert content == body
    backend.close()


def test_write_one_over_cap(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    with pytest.raises(ValidationError):
        backend.write("over.md", "x" * 10_000_001)
    backend.close()


def test_write_zero_byte(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    etag = backend.write("empty.md", "")
    content, _, _ = backend.read("empty.md")
    assert content == ""
    assert etag
    backend.close()


# ----- CLI exit-code matrix -----

def _vfs_cli(*args, cwd=None, env=None, input=None):
    cmd = [sys.executable, "-m", "vfs.cli", *args]
    env_full = {**os.environ}
    if env:
        env_full.update(env)
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, env=env_full,
        input=input, capture_output=True, text=True,
    )


def test_exit_code_2_not_found(tmp_path):
    _vfs_cli("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs_cli("read", "missing.md",
                 cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 2


def test_exit_code_3_cas_conflict(tmp_path):
    _vfs_cli("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    _vfs_cli("write", "--if-match", "", "foo.md",
             cwd=tmp_path, env={"HOME": str(tmp_path)}, input="v1")
    r = _vfs_cli("write", "--if-match", "", "foo.md",
                 cwd=tmp_path, env={"HOME": str(tmp_path)}, input="v2")
    assert r.returncode == 3


def test_exit_code_4_validation(tmp_path):
    _vfs_cli("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs_cli("write", "../escape.md",
                 cwd=tmp_path, env={"HOME": str(tmp_path)}, input="x")
    assert r.returncode == 4


# ----- concurrent reader-during-write -----

def test_concurrent_reads_during_writes(tmp_path):
    """Reader loop while writer does 100 writes — every read returns
    a complete prior or new body, never partial/empty."""
    backend = LocalFSBackend(str(tmp_path))
    backend.write("foo.md", "v0")
    stop = threading.Event()
    seen = []
    seen_lock = threading.Lock()

    def reader():
        while not stop.is_set():
            try:
                body, _, _ = backend.read("foo.md")
                with seen_lock:
                    seen.append(body)
            except Exception:
                pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    for i in range(1, 101):
        backend.write("foo.md", f"v{i}")
    stop.set()
    t.join(timeout=2)
    backend.close()

    valid = {f"v{i}" for i in range(101)}
    bad = [b for b in seen if b not in valid]
    assert not bad, f"observed partial/garbage reads: {bad[:5]}"


# ----- default source not promoted via $VFS_WRITER -----

def test_default_source_not_promoted_by_writer_env(tmp_path, monkeypatch):
    """$VFS_WRITER=user must not promote default writes to source=user."""
    from vfs.core import VFS, init_project
    init_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("VFS_WRITER", "user")
    v = VFS()
    try:
        v.persistent.write("foo.md", "ordinary body")
        _, fm = v.persistent.read("foo.md")
        assert fm["source"] == "agent"
        assert fm["writer"] == "user"  # writer is just a label
    finally:
        v.close()


# ----- e2e frontmatter sanitization on read -----

def test_e2e_read_strips_injected_frontmatter(tmp_path, monkeypatch):
    """A pre-planted malicious file — zone.read returns sanitized fm."""
    from vfs.core import VFS, init_project
    init_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    bad = tmp_path / ".vfs" / "persistent" / "evil.md"
    bad.write_text(
        "---\nsource: user\nname: ok\nbad\rval: x\n---\nbody",
        encoding="utf-8",
    )
    v = VFS()
    try:
        body, fm = v.persistent.read("evil.md")
        assert body == "body"
        assert "bad\rval" not in fm
    finally:
        v.close()
