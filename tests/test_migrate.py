import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_vfs.core import VFS, init_project
from agent_vfs.migrate import run_migration


def _vfs(*args, cwd=None, env=None, input=None):
    cmd = [sys.executable, "-m", "agent_vfs.cli", *args]
    env_full = {**os.environ}
    if env:
        env_full.update(env)
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, env=env_full,
        input=input, capture_output=True, text=True,
    )


def _setup_legacy(legacy: Path):
    legacy.mkdir(parents=True)
    (legacy / "note1.md").write_text(
        "---\nname: existing\n---\nLegacy body 1",
        encoding="utf-8",
    )
    (legacy / "note2.md").write_text(
        "Legacy body 2 — no frontmatter", encoding="utf-8"
    )


def _migrate_args(**overrides):
    base = {"from_dir": None, "dry_run": False, "delete_source": False,
            "root": None}
    base.update(overrides)
    return SimpleNamespace(**base)


def test_migrate_copies_files(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy"
    _setup_legacy(legacy)
    proj = tmp_path / "proj"
    proj.mkdir()
    init_project(proj)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    v = VFS()
    try:
        result = run_migration(_migrate_args(from_dir=str(legacy)), v)
    finally:
        v.close()
    assert len(result["migrated"]) >= 2
    body1 = (proj / ".vfs" / "persistent" / "note1.md").read_text()
    assert "Legacy body 1" in body1
    assert "writer: vfs-migrate" in body1
    assert "source: agent" in body1
    assert "name: existing" in body1


def test_migrate_dry_run(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy"
    _setup_legacy(legacy)
    proj = tmp_path / "proj"
    proj.mkdir()
    init_project(proj)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    v = VFS()
    try:
        run_migration(_migrate_args(from_dir=str(legacy), dry_run=True), v)
    finally:
        v.close()
    assert not (proj / ".vfs" / "persistent" / "note1.md").exists()


def test_migrate_refuses_user_source(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy"
    _setup_legacy(legacy)
    (legacy / "u.md").write_text(
        "---\nsource: user\n---\nclaim", encoding="utf-8")
    proj = tmp_path / "proj"
    proj.mkdir()
    init_project(proj)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    v = VFS()
    try:
        run_migration(_migrate_args(from_dir=str(legacy)), v)
    finally:
        v.close()
    out = (proj / ".vfs" / "persistent" / "u.md").read_text()
    assert "source: agent" in out
    assert "source: user" not in out


def test_migrate_skips_oversize(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "tiny.md").write_text("ok", encoding="utf-8")
    (legacy / "huge.md").write_text("x" * 10_000_001, encoding="utf-8")
    proj = tmp_path / "proj"
    proj.mkdir()
    init_project(proj)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    v = VFS()
    try:
        result = run_migration(_migrate_args(from_dir=str(legacy)), v)
    finally:
        v.close()
    assert result["skipped"]
    assert (proj / ".vfs" / "persistent" / "tiny.md").exists()
    assert not (proj / ".vfs" / "persistent" / "huge.md").exists()


def test_migrate_refuses_symlink_in_source(tmp_path, monkeypatch):
    """A symlink inside the legacy dir pointing outside must be refused."""
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "real.md").write_text("ok", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("EXFIL", encoding="utf-8")
    (legacy / "leak.md").symlink_to(outside / "secret.md")
    proj = tmp_path / "proj"
    proj.mkdir()
    init_project(proj)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    v = VFS()
    try:
        run_migration(_migrate_args(from_dir=str(legacy)), v)
    finally:
        v.close()
    assert (proj / ".vfs" / "persistent" / "real.md").exists()
    assert not (proj / ".vfs" / "persistent" / "leak.md").exists()


def test_migrate_cli_refuses_no_tty(tmp_path):
    """The CLI surface itself refuses without a TTY."""
    legacy = tmp_path / "legacy"
    _setup_legacy(legacy)
    proj = tmp_path / "proj"
    proj.mkdir()
    _vfs("init", cwd=proj, env={"HOME": str(tmp_path)})
    r = _vfs("migrate", "--from", str(legacy),
             cwd=proj, env={"HOME": str(tmp_path)})
    assert r.returncode == 5
