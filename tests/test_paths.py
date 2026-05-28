import pytest
from pathlib import Path

from agent_vfs.paths import resolve_project_root, validate_key
from agent_vfs.types import NotFoundError, ValidationError


VALID_KEYS = [
    "foo",
    "foo.md",
    "notes/foo.md",
    "decisions/2026-05-27-x.md",
    "a/b/c/d.md",
    "foo-bar_baz.txt",
]

INVALID_KEYS = [
    "",                  # empty
    "/abs",              # leading slash
    "rel/",              # trailing slash
    "a/../b",            # traversal component
    "a/./b",             # dot component
    "..",                # bare dotdot
    ".",                 # bare dot
    "foo\x00bar",        # NUL
    "foo\nbar",          # newline
    "foo\rbar",          # CR
    "foo\\bar",          # backslash
    "foo.",              # trailing dot
    "foo ",              # trailing space
    " foo",              # leading space
    "foo bar",           # internal space
    "foo:bar",           # colon
    "foo;bar",           # semicolon
    "foo|bar",           # pipe
    "foo*bar",           # glob char
    "foo?bar",           # glob char
    "foo[bar",           # bracket
]


@pytest.mark.parametrize("key", VALID_KEYS)
def test_valid_keys(key):
    validate_key(key)


@pytest.mark.parametrize("key", INVALID_KEYS)
def test_invalid_keys(key):
    with pytest.raises(ValidationError):
        validate_key(key)


def _make_project(root: Path) -> Path:
    (root / ".vfs").mkdir(parents=True)
    return root


def test_resolve_from_project_root(tmp_path, monkeypatch):
    proj = _make_project(tmp_path / "myproj")
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VFS_PROJECT_ROOT", raising=False)
    assert resolve_project_root() == proj


def test_resolve_from_subdir(tmp_path, monkeypatch):
    proj = _make_project(tmp_path / "myproj")
    sub = proj / "src" / "nested"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VFS_PROJECT_ROOT", raising=False)
    assert resolve_project_root() == proj


def test_resolve_stops_at_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    sub = home / "myproj" / "src"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("VFS_PROJECT_ROOT", raising=False)
    with pytest.raises(NotFoundError):
        resolve_project_root()


def test_resolve_ignores_vfs_project_root_env(tmp_path, monkeypatch):
    """$VFS_PROJECT_ROOT was removed for security — must not affect resolution."""
    proj = _make_project(tmp_path / "real")
    fake = _make_project(tmp_path / "fake")
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("VFS_PROJECT_ROOT", str(fake))  # ignored
    assert resolve_project_root() == proj


def test_resolve_no_env_var_special_case(tmp_path, monkeypatch):
    """Resolution is strictly upward-walk; no env var override."""
    other = tmp_path / "no-vfs"
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("VFS_PROJECT_ROOT", "/anywhere")  # ignored
    with pytest.raises(NotFoundError):
        resolve_project_root()
