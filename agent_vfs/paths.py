"""Path/key grammar validation and root resolution.

Key grammar:
    [A-Za-z0-9._/-]+
    no leading or trailing /
    no `..` or `.` components
    no control chars (including \\n, \\r, \\x00)
    no trailing dot or space (Windows-style traversal defense)
    no leading space
    no backslash (Windows path separator)
    must roundtrip through os.path.normpath unchanged

Root resolution:
    Strictly upward-walk from CWD. No $VFS_PROJECT_ROOT env var —
    that doubles as a cross-project bypass for prompt-injected agents.
"""
import os
import re
from pathlib import Path
from typing import Optional

from agent_vfs.types import NotFoundError, ValidationError


_ALLOWED_CHARSET = re.compile(r"^[A-Za-z0-9._/-]+$")


def validate_key(key: str) -> None:
    """Raise ValidationError if `key` violates the v1 grammar."""
    if not isinstance(key, str):
        raise ValidationError(f"invalid key (not a string): {type(key).__name__}")
    if not key:
        raise ValidationError("invalid key: empty string")
    if key.startswith("/"):
        raise ValidationError(f"invalid key (absolute path): {key!r}")
    if key.endswith("/"):
        raise ValidationError(f"invalid key (trailing slash): {key!r}")
    if not _ALLOWED_CHARSET.match(key):
        raise ValidationError(
            f"invalid key (charset; allowed [A-Za-z0-9._/-]): {key!r}"
        )
    if key.startswith(" ") or key.endswith(" "):
        raise ValidationError(f"invalid key (leading/trailing space): {key!r}")
    if key.endswith("."):
        raise ValidationError(f"invalid key (trailing dot): {key!r}")
    components = key.split("/")
    for comp in components:
        if comp in ("", ".", ".."):
            raise ValidationError(f"invalid key (bad component {comp!r}): {key!r}")
    normalized = os.path.normpath(key)
    if normalized != key:
        raise ValidationError(
            f"invalid key (normpath roundtrip mismatch: {key!r} -> {normalized!r})"
        )


def resolve_project_root(start: Optional[str] = None) -> Path:
    """Discover the project's .vfs/ root.

    Strictly upward-walk from `start` (default CWD). Stops at:
    filesystem root, $HOME, or a `.vfs/` hit.

    No env-var override — an earlier draft honored $VFS_PROJECT_ROOT,
    but that doubled as a cross-project bypass for prompt-injected agents.
    Callers who need a non-CWD root use `VFS(root=...)` directly.

    Raises:
      NotFoundError: no .vfs/ found.
    """
    cwd = Path(start if start is not None else os.getcwd()).resolve()
    home = Path(os.environ.get("HOME", "/")).resolve()
    current = cwd
    while True:
        if (current / ".vfs").is_dir():
            return current
        if current == home or current.parent == current:
            raise NotFoundError(
                f"no .vfs/ found walking up from {cwd}; run `vfs init`"
            )
        current = current.parent
