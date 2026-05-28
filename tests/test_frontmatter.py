import pytest

from vfs.frontmatter import make_frontmatter, parse_frontmatter
from vfs.types import ValidationError


def test_make_basic():
    fm = make_frontmatter(writer="agent", source="agent", project_slug="proj-uuid")
    assert fm.startswith("---\n")
    assert fm.endswith("---\n")
    assert "writer: agent" in fm
    assert "source: agent" in fm
    assert "project_slug: proj-uuid" in fm


def test_make_rejects_newline_in_value():
    with pytest.raises(ValidationError):
        make_frontmatter(writer="agent\nsource: user", source="agent", project_slug="x")


def test_make_rejects_cr_in_value():
    with pytest.raises(ValidationError):
        make_frontmatter(writer="agent\r", source="agent", project_slug="x")


def test_make_rejects_control_chars():
    with pytest.raises(ValidationError):
        make_frontmatter(writer="agent\x01", source="agent", project_slug="x")


def test_parse_no_frontmatter():
    fm, body = parse_frontmatter("just a body")
    assert fm == {}
    assert body == "just a body"


def test_parse_unterminated_frontmatter():
    fm, body = parse_frontmatter("---\nwriter: agent\nno close")
    assert fm == {}
    assert body == "---\nwriter: agent\nno close"


def test_parse_basic():
    text = "---\nwriter: agent\nsource: agent\n---\nbody"
    fm, body = parse_frontmatter(text)
    assert fm == {"writer": "agent", "source": "agent"}
    assert body == "body"


def test_parse_strips_invalid_field_keys():
    text = "---\nwriter: agent\nbad key: x\nfoo:bar: y\n---\nbody"
    fm, _ = parse_frontmatter(text)
    assert "writer" in fm
    assert "bad key" not in fm
    assert "foo:bar" not in fm


def test_parse_strips_values_with_control_chars():
    text = "---\nwriter: agent\nname: foo\rbar\n---\nbody"
    fm, _ = parse_frontmatter(text)
    assert fm.get("writer") == "agent"
    assert "name" not in fm


def test_roundtrip_preserves_known_fields():
    fm_text = make_frontmatter(writer="agent", source="agent", project_slug="proj-uuid")
    parsed, body = parse_frontmatter(fm_text + "hello")
    assert parsed["writer"] == "agent"
    assert parsed["source"] == "agent"
    assert parsed["project_slug"] == "proj-uuid"
    assert body == "hello"
