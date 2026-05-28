import os
import stat
import pytest

from vfs.backends.localfs import LocalFSBackend
from vfs.types import (
    ConflictError, NotFoundError, ValidationError, VFSError,
    ZoneViolationError,
)


# ----- init -----

def test_init_creates_root_dir(tmp_path):
    root = tmp_path / "data"
    backend = LocalFSBackend(str(root))
    assert root.is_dir()
    assert backend.root == str(root)
    assert backend._root_fd >= 0
    backend.close()


def test_init_with_existing_dir(tmp_path):
    root = tmp_path / "data"
    root.mkdir(mode=0o700)
    backend = LocalFSBackend(str(root))
    assert backend._root_fd >= 0
    backend.close()


def test_init_refuses_loose_perms(tmp_path):
    root = tmp_path / "data"
    root.mkdir(mode=0o755)
    with pytest.raises(PermissionError):
        LocalFSBackend(str(root))


def test_init_loose_perms_allowed_when_opted_out(tmp_path):
    root = tmp_path / "data"
    root.mkdir(mode=0o755)
    backend = LocalFSBackend(str(root), strict_perms=False)
    backend.close()


def test_close_releases_fd(tmp_path):
    backend = LocalFSBackend(str(tmp_path / "data"))
    backend.close()
    assert backend._root_fd == -1
    backend.close()  # idempotent


# ----- read -----

def test_read_simple(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    (tmp_path / "foo.md").write_text("hello", encoding="utf-8")
    os.chmod(tmp_path / "foo.md", 0o600)
    content, etag, mtime = backend.read("foo.md")
    assert content == "hello"
    assert etag
    assert mtime > 0
    backend.close()


def test_read_not_found(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    with pytest.raises(NotFoundError):
        backend.read("missing.md")
    backend.close()


def test_read_refuses_symlink_in_dest(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("SECRET", encoding="utf-8")
    (tmp_path / "evil.md").symlink_to(sentinel)
    with pytest.raises(ZoneViolationError):
        backend.read("evil.md")
    backend.close()


def test_read_refuses_symlink_in_path_component(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    (outside / "secret.md").write_text("SECRET", encoding="utf-8")
    (tmp_path / "shortcut").symlink_to(outside)
    with pytest.raises(ZoneViolationError):
        backend.read("shortcut/secret.md")
    backend.close()


def test_read_offset_limit(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("foo.md", "0123456789")
    content, _, _ = backend.read("foo.md", offset=2, limit=4)
    assert content == "2345"
    backend.close()


# ----- write -----

def test_write_simple(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    etag = backend.write("foo.md", "hello")
    assert (tmp_path / "foo.md").read_text() == "hello"
    assert etag
    backend.close()


def test_write_creates_intermediate_dirs(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("notes/foo.md", "x")
    assert (tmp_path / "notes" / "foo.md").read_text() == "x"
    backend.close()


def test_write_refuses_symlink_at_dest(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("ORIGINAL", encoding="utf-8")
    (tmp_path / "evil.md").symlink_to(sentinel)
    with pytest.raises(ZoneViolationError):
        backend.write("evil.md", "OVERWRITE")
    assert sentinel.read_text() == "ORIGINAL"
    backend.close()


def test_write_refuses_symlink_in_path(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    (tmp_path / "shortcut").symlink_to(outside)
    with pytest.raises(ZoneViolationError):
        backend.write("shortcut/foo.md", "x")
    backend.close()


def test_write_enforces_size_cap(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    with pytest.raises(ValidationError):
        backend.write("foo.md", "x" * 10_000_001)
    assert not (tmp_path / "foo.md").exists()
    backend.close()


def test_write_overwrite(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("foo.md", "v1")
    backend.write("foo.md", "v2")
    assert (tmp_path / "foo.md").read_text() == "v2"
    backend.close()


def test_write_sets_0600_perms(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("foo.md", "x")
    mode = stat.S_IMODE((tmp_path / "foo.md").stat().st_mode)
    assert mode == 0o600
    backend.close()


def test_write_intermediate_dirs_0700(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("notes/deep/foo.md", "x")
    mode = stat.S_IMODE((tmp_path / "notes").stat().st_mode)
    assert mode == 0o700
    mode = stat.S_IMODE((tmp_path / "notes" / "deep").stat().st_mode)
    assert mode == 0o700
    backend.close()


# ----- delete + CAS -----

def test_delete_simple(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("foo.md", "x")
    backend.delete("foo.md")
    assert not (tmp_path / "foo.md").exists()
    backend.close()


def test_delete_not_found(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    with pytest.raises(NotFoundError):
        backend.delete("missing.md")
    backend.close()


def test_delete_cas_match(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    etag = backend.write("foo.md", "x")
    backend.delete("foo.md", if_match=etag)
    assert not (tmp_path / "foo.md").exists()
    backend.close()


def test_delete_cas_mismatch(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("foo.md", "x")
    with pytest.raises(ConflictError):
        backend.delete("foo.md", if_match="bogus")
    assert (tmp_path / "foo.md").exists()
    backend.close()


def test_cas_create(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("foo.md", "v1", if_match="")
    with pytest.raises(ConflictError):
        backend.write("foo.md", "v2", if_match="")
    backend.close()


def test_cas_update(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    e1 = backend.write("foo.md", "v1")
    e2 = backend.write("foo.md", "v2", if_match=e1)
    assert e2 != e1
    with pytest.raises(ConflictError):
        backend.write("foo.md", "v3", if_match=e1)
    backend.close()


def test_delete_refuses_symlink_at_dest(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("KEEP", encoding="utf-8")
    (tmp_path / "evil.md").symlink_to(sentinel)
    with pytest.raises(ZoneViolationError):
        backend.delete("evil.md")
    assert sentinel.exists()
    backend.close()


# ----- list -----

def test_list_empty(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    entries, cursor = backend.list()
    assert entries == []
    assert cursor is None
    backend.close()


def test_list_basic(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("a.md", "1")
    backend.write("notes/b.md", "2")
    entries, _ = backend.list()
    keys = sorted(e.key for e in entries)
    assert keys == ["a.md", "notes/b.md"]
    backend.close()


def test_list_prefix(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("notes/a.md", "1")
    backend.write("decisions/b.md", "2")
    entries, _ = backend.list(prefix="notes/")
    assert {e.key for e in entries} == {"notes/a.md"}
    backend.close()


def test_list_pagination(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    for i in range(5):
        backend.write(f"k{i}.md", "x")
    page1, cursor = backend.list(max_items=2)
    assert len(page1) == 2
    assert cursor is not None
    page2, cursor2 = backend.list(cursor=cursor, max_items=2)
    assert len(page2) == 2
    page3, cursor3 = backend.list(cursor=cursor2, max_items=2)
    assert len(page3) == 1
    assert cursor3 is None
    backend.close()


def test_list_excludes_tmp_files(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("real.md", "x")
    (tmp_path / ".vfs-tmp-deadbeef").write_text("garbage")
    entries, _ = backend.list()
    assert all(not e.key.startswith(".vfs-tmp-") for e in entries)
    backend.close()


def test_list_does_not_follow_symlinks(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("real.md", "x")
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    (outside / "secret.md").write_text("SECRET")
    (tmp_path / "shortcut").symlink_to(outside)
    entries, _ = backend.list()
    assert all("secret" not in e.key for e in entries)
    backend.close()


def test_list_max_files_cap(tmp_path, monkeypatch):
    backend = LocalFSBackend(str(tmp_path))
    monkeypatch.setenv("VFS_MAX_FILES", "3")
    for i in range(10):
        backend.write(f"k{i}.md", "x")
    with pytest.raises(VFSError, match="VFS_MAX_FILES"):
        backend.list()
    backend.close()


def test_list_sibling_adjacency(tmp_path):
    """<root>-evil/ should not be surfaced."""
    root = tmp_path / "data"
    root.mkdir(mode=0o700)
    evil = tmp_path / "data-evil"
    evil.mkdir(mode=0o700)
    (evil / "leak.md").write_text("LEAK")
    backend = LocalFSBackend(str(root))
    backend.write("ok.md", "x")
    entries, _ = backend.list()
    assert all("leak" not in e.key for e in entries)
    backend.close()


# ----- search -----

def test_search_hit(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("notes/a.md", "alpha\nbravo\ncharlie\n")
    hits = backend.search("", "bravo")
    assert len(hits) == 1
    assert hits[0]["key"] == "notes/a.md"
    assert hits[0]["snippet"] == "bravo"
    backend.close()


def test_search_no_hit(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("a.md", "alpha")
    hits = backend.search("", "missing")
    assert hits == []
    backend.close()


def test_search_prefix(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("notes/a.md", "needle")
    backend.write("decisions/b.md", "needle")
    hits = backend.search("notes/", "needle")
    assert len(hits) == 1
    assert hits[0]["key"] == "notes/a.md"
    backend.close()


def test_search_does_not_follow_symlinks(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    outside = tmp_path.parent / "outside-search"
    outside.mkdir(exist_ok=True)
    (outside / "leak.md").write_text("needle")
    (tmp_path / "shortcut").symlink_to(outside)
    hits = backend.search("", "needle")
    assert hits == []
    backend.close()


def test_search_max_bytes_per_file(tmp_path, monkeypatch):
    backend = LocalFSBackend(str(tmp_path))
    monkeypatch.setenv("VFS_MAX_BYTES_PER_FILE", "10")
    backend.write("big.md", "this is way more than ten bytes of needle text")
    hits = backend.search("", "needle")
    assert hits == []  # bound applied
    backend.close()
