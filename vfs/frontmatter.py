"""Provenance frontmatter — strict on write, sanitizing on read.

Write shape:
    ---
    writer: <agent id>
    source: <"user" | "agent" | "tool:<name>" | "web:<domain>">
    ts: <ISO-8601 UTC>
    project_slug: <project uuid from config.toml>
    etag: <empty at write; reserved for future inline storage>
    ---
    <body>

Field values reject any [\\x00-\\x1f] (control chars, including \\n \\r).
Field keys must match [\\w.-]+. Both checks apply on write AND on read.
Bad fields are dropped on read (the body is unaffected) — defeats injection
attempts via pre-planted file content.
"""
import re
from datetime import datetime, timezone
from typing import Dict, Tuple

from vfs.types import ValidationError


_CONTROL_CHARS = re.compile(r"[\x00-\x1f]")
_FIELD_KEY = re.compile(r"^[\w.-]+$")


def _check_field_value(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise ValidationError(f"frontmatter field {name!r} must be a string")
    if _CONTROL_CHARS.search(value):
        raise ValidationError(
            f"frontmatter field {name!r} contains control char: {value!r}"
        )


def _check_field_key(key: str) -> bool:
    return bool(_FIELD_KEY.match(key))


def make_frontmatter(
    writer: str,
    source: str,
    project_slug: str,
    etag: str = "",
) -> str:
    """Serialize the VFS-v1 provenance block. Strict on values."""
    _check_field_value("writer", writer)
    _check_field_value("source", source)
    _check_field_value("project_slug", project_slug)
    _check_field_value("etag", etag)
    ts = datetime.now(timezone.utc).isoformat()
    return (
        "---\n"
        f"writer: {writer}\n"
        f"source: {source}\n"
        f"ts: {ts}\n"
        f"project_slug: {project_slug}\n"
        f"etag: {etag}\n"
        "---\n"
    )


def parse_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    """Split content into (frontmatter_dict, body).

    Sanitizing: bad-key / bad-value fields are silently dropped from the
    returned dict. The body is unaffected.

    Tolerant: missing / unterminated frontmatter returns ({}, content).
    """
    if not content.startswith("---\n"):
        return {}, content
    end_idx = content.find("\n---\n", 4)
    if end_idx == -1:
        return {}, content
    fm_text = content[4:end_idx]
    body = content[end_idx + len("\n---\n"):]
    fm: Dict[str, str] = {}
    for line in fm_text.split("\n"):
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if not _check_field_key(k):
            continue
        if _CONTROL_CHARS.search(v):
            continue
        fm[k] = v
    return fm, body
