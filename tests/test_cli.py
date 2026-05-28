import json
import os
import subprocess
import sys

import pytest


def _vfs(*args, cwd=None, env=None, input=None):
    cmd = [sys.executable, "-m", "agent_vfs.cli", *args]
    env_full = {**os.environ}
    if env:
        env_full.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env_full,
        input=input,
        capture_output=True,
        text=True,
    )


def test_version(tmp_path):
    r = _vfs("version")
    assert r.returncode == 0
    assert "1.0.0" in r.stdout


def test_init_basic(tmp_path):
    r = _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
    assert (tmp_path / ".vfs").is_dir()
    assert (tmp_path / ".vfs" / "config.toml").is_file()


def test_init_refuses_double(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode != 0
    assert "already" in r.stderr.lower()


def test_whoami(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("whoami",
             cwd=tmp_path,
             env={"HOME": str(tmp_path), "VFS_WRITER": "test-agent"})
    assert r.returncode == 0
    assert "test-agent" in r.stdout


def test_write_and_read(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("write", "notes/foo.md",
             cwd=tmp_path, env={"HOME": str(tmp_path)},
             input="hello world")
    assert r.returncode == 0
    r = _vfs("read", "notes/foo.md",
            cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
    assert r.stdout == "hello world"


def test_write_rejects_source_user(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("write", "--source", "user", "foo.md",
             cwd=tmp_path, env={"HOME": str(tmp_path)},
             input="x")
    assert r.returncode == 4


def test_write_rejects_secret(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("write", "foo.md",
             cwd=tmp_path, env={"HOME": str(tmp_path)},
             input="AKIAIOSFODNN7EXAMPLE")
    assert r.returncode == 4


def test_list_basic(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    _vfs("write", "a.md", cwd=tmp_path, env={"HOME": str(tmp_path)}, input="1")
    _vfs("write", "b.md", cwd=tmp_path, env={"HOME": str(tmp_path)}, input="2")
    r = _vfs("--json", "list", cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
    lines = [json.loads(line) for line in r.stdout.strip().split("\n")]
    assert {line["key"] for line in lines} == {"a.md", "b.md"}


def test_delete(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    _vfs("write", "foo.md", cwd=tmp_path, env={"HOME": str(tmp_path)}, input="x")
    r = _vfs("delete", "foo.md", cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
    r = _vfs("read", "foo.md", cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 2


def test_search(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    _vfs("write", "a.md",
         cwd=tmp_path, env={"HOME": str(tmp_path)},
         input="contains needle here")
    r = _vfs("--json", "search", "needle",
            cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
    lines = [json.loads(line) for line in r.stdout.strip().split("\n")]
    assert any("needle" in line["snippet"] for line in lines)


def test_temp_write_and_read(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("temp", "write", "scratch.md",
             cwd=tmp_path, env={"HOME": str(tmp_path)},
             input="ephemeral")
    assert r.returncode == 0
    r = _vfs("temp", "read", "scratch.md",
             cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
    assert r.stdout == "ephemeral"


def test_remember_as_user_refuses_no_tty(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("remember", "--as-user", "foo.md",
             cwd=tmp_path, env={"HOME": str(tmp_path)},
             input="my fact")
    assert r.returncode == 5


def test_root_without_as_user_refused(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    _vfs("init", cwd=other, env={"HOME": str(tmp_path)})
    r = _vfs("--root", str(other), "read", "x",
             cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 5


def test_vfs_project_root_env_is_ignored(tmp_path):
    """$VFS_PROJECT_ROOT was removed for security; must not redirect resolution."""
    real = tmp_path / "real"
    real.mkdir()
    _vfs("init", cwd=real, env={"HOME": str(tmp_path)})
    fake = tmp_path / "fake"
    fake.mkdir()
    _vfs("init", cwd=fake, env={"HOME": str(tmp_path)})
    _vfs("write", "marker.md",
         cwd=real, env={"HOME": str(tmp_path)}, input="REAL")
    r = _vfs("read", "marker.md",
             cwd=real,
             env={"HOME": str(tmp_path), "VFS_PROJECT_ROOT": str(fake)})
    assert r.returncode == 0
    assert r.stdout == "REAL"


def test_review_shows_diag_entries(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    _vfs("write", "foo.md",
         cwd=tmp_path, env={"HOME": str(tmp_path)}, input="x")
    r = _vfs("--json", "review",
             cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
    lines = [json.loads(line) for line in r.stdout.strip().split("\n")]
    assert any(line.get("op") == "write" and line.get("key") == "foo.md"
               for line in lines)


def test_gc_runs(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("gc", cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
