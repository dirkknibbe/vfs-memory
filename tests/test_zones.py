import json

import pytest

from agent_vfs.backends.localfs import LocalFSBackend
from agent_vfs.diagnostic import DiagnosticLog
from agent_vfs.types import ValidationError
from agent_vfs.zones import PersistentZone, TempZone


# ----- TempZone -----

def test_temp_read_write(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    zone = TempZone(backend)
    zone.write("scratch.md", "ephemeral")
    assert zone.read("scratch.md") == "ephemeral"
    backend.close()


def test_temp_delete(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    zone = TempZone(backend)
    zone.write("foo.md", "x")
    zone.delete("foo.md")
    assert (tmp_path / "foo.md").exists() is False
    backend.close()


def test_temp_no_frontmatter(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    zone = TempZone(backend)
    zone.write("foo.md", "bare body")
    raw = (tmp_path / "foo.md").read_text()
    assert raw == "bare body"
    backend.close()


# ----- PersistentZone -----

def _make_persistent(tmp_path, source_user_allowed=False):
    backend = LocalFSBackend(str(tmp_path / "persistent"))
    diag = DiagnosticLog(str(tmp_path / "diagnostic.log"))
    zone = PersistentZone(
        backend=backend,
        diag=diag,
        writer_id="test-agent",
        project_id="proj-uuid",
        source_user_allowed=source_user_allowed,
    )
    return zone, backend


def test_persistent_write_attaches_frontmatter(tmp_path):
    zone, backend = _make_persistent(tmp_path)
    zone.write("notes/foo.md", "body content")
    body, fm = zone.read("notes/foo.md")
    assert body == "body content"
    assert fm["writer"] == "test-agent"
    assert fm["source"] == "agent"
    assert fm["project_slug"] == "proj-uuid"
    backend.close()


def test_persistent_refuses_source_user_by_default(tmp_path):
    zone, backend = _make_persistent(tmp_path, source_user_allowed=False)
    with pytest.raises(ValidationError, match="source=user"):
        zone.write("foo.md", "x", source="user")
    backend.close()


def test_persistent_allows_source_user_when_gated(tmp_path):
    zone, backend = _make_persistent(tmp_path, source_user_allowed=True)
    zone.write("foo.md", "x", source="user")
    _, fm = zone.read("foo.md")
    assert fm["source"] == "user"
    backend.close()


def test_persistent_refuses_secret_shape(tmp_path):
    zone, backend = _make_persistent(tmp_path)
    body = "I just generated this: AKIAIOSFODNN7EXAMPLE — write it down"
    with pytest.raises(ValidationError, match="secret"):
        zone.write("foo.md", body)
    backend.close()


def test_persistent_allows_secret_with_override(tmp_path):
    zone, backend = _make_persistent(tmp_path)
    body = "AKIAIOSFODNN7EXAMPLE"
    zone.write("foo.md", body, allow_secret=True)
    body_out, _ = zone.read("foo.md")
    assert body_out == body
    backend.close()


def test_persistent_write_logged(tmp_path):
    zone, backend = _make_persistent(tmp_path)
    zone.write("foo.md", "body")
    log_path = tmp_path / "diagnostic.log"
    line = log_path.read_text().strip().split("\n")[0]
    rec = json.loads(line)
    assert rec["op"] == "write"
    assert rec["key"] == "foo.md"
    assert rec["writer"] == "test-agent"
    assert rec["source"] == "agent"
    backend.close()


def test_persistent_merge_preserves_non_vfs_fields(tmp_path):
    zone, backend = _make_persistent(tmp_path)
    (tmp_path / "persistent" / "foo.md").write_text(
        "---\nname: existing-slug\ndescription: a description\n---\nbody",
        encoding="utf-8",
    )
    zone.write("foo.md", "new body")
    body, fm = zone.read("foo.md")
    assert body == "new body"
    assert fm["name"] == "existing-slug"
    assert fm["description"] == "a description"
    assert fm["writer"] == "test-agent"
    backend.close()


def test_persistent_merge_drops_bad_preserved_fields(tmp_path):
    """Preserved fields with control chars must be dropped via validators."""
    zone, backend = _make_persistent(tmp_path)
    (tmp_path / "persistent" / "foo.md").write_text(
        "---\nname: ok\nbad\rval: should-drop\n---\nbody",
        encoding="utf-8",
    )
    zone.write("foo.md", "new body")
    body, fm = zone.read("foo.md")
    assert "name" in fm  # the good one survives
    # The bad one was already dropped on read by parse_frontmatter; this
    # test mainly confirms the merge path doesn't crash on bad data.
    backend.close()
