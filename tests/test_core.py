import pytest

from vfs.core import VFS, init_project
from vfs.types import NotFoundError, ValidationError


def test_init_creates_layout(tmp_path, monkeypatch):
    init_project(tmp_path)
    assert (tmp_path / ".vfs").is_dir()
    assert (tmp_path / ".vfs" / "config.toml").is_file()
    assert (tmp_path / ".vfs" / "persistent").is_dir()
    assert (tmp_path / ".vfs" / "temp").is_dir()


def test_init_refuses_existing(tmp_path):
    (tmp_path / ".vfs").mkdir()
    with pytest.raises(ValidationError, match="already exists"):
        init_project(tmp_path)


def test_vfs_constructs(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VFS_PROJECT_ROOT", raising=False)
    v = VFS()
    try:
        assert v.project_id
        assert v.root == tmp_path
        assert v.persistent is not None
        assert v.temp is not None
    finally:
        v.close()


def test_vfs_writer_id_from_env(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("VFS_WRITER", "my-named-agent")
    v = VFS()
    try:
        assert v.writer_id == "my-named-agent"
    finally:
        v.close()


def test_vfs_writer_id_default(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VFS_WRITER", raising=False)
    v = VFS()
    try:
        assert v.writer_id == "agent"
    finally:
        v.close()


def test_vfs_writer_id_with_control_chars_refused(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("VFS_WRITER", "evil\x1b[31mwriter")
    with pytest.raises(ValidationError, match="VFS_WRITER"):
        VFS()


def test_vfs_explicit_root(tmp_path, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    init_project(other)
    v = VFS(root=str(other))
    try:
        assert v.root == other
    finally:
        v.close()
