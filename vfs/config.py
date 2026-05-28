"""Per-project .vfs/config.toml — schema version and project UUID.

Hand-rolled minimal TOML reader: three known keys, strict shape. Keeps
the stdlib-only claim consistent across Python 3.9, 3.10, 3.11, 3.12
(tomllib only landed in 3.11).
"""
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


CONFIG_FILENAME = "config.toml"
SCHEMA_VERSION = 1

_INT_LINE = re.compile(r'^(\w+)\s*=\s*(\d+)$')
_STR_LINE = re.compile(r'^(\w+)\s*=\s*"([^"\x00-\x1f]*)"$')


def write_config(vfs_dir: Path, project_id: Optional[str] = None) -> str:
    """Write a fresh config.toml. Returns the project_id."""
    pid = project_id or str(uuid.uuid4())
    content = (
        f"schema_version = {SCHEMA_VERSION}\n"
        f'project_id = "{pid}"\n'
        f'created_at = "{datetime.now(timezone.utc).isoformat()}"\n'
    )
    config_path = vfs_dir / CONFIG_FILENAME
    old_umask = os.umask(0o077)
    try:
        config_path.write_text(content, encoding="utf-8")
        os.chmod(config_path, 0o600)
    finally:
        os.umask(old_umask)
    return pid


def read_config(vfs_dir: Path) -> dict:
    """Read .vfs/config.toml. Raises FileNotFoundError if missing,
    ValueError if the file's shape doesn't match the three known keys.
    """
    config_path = vfs_dir / CONFIG_FILENAME
    out: dict = {}
    with open(config_path, "r", encoding="utf-8") as fp:
        for lineno, raw in enumerate(fp, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = _INT_LINE.match(line)
            if m:
                out[m.group(1)] = int(m.group(2))
                continue
            m = _STR_LINE.match(line)
            if m:
                out[m.group(1)] = m.group(2)
                continue
            raise ValueError(
                f"{config_path}:{lineno}: unparseable config line: {line!r}"
            )
    missing = {"schema_version", "project_id", "created_at"} - set(out)
    if missing:
        raise ValueError(
            f"{config_path}: missing required keys {sorted(missing)}"
        )
    return out
