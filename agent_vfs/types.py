"""Core VFS types and error hierarchy."""
from dataclasses import dataclass
from typing import Literal


@dataclass
class Entry:
    """One item returned by list() — key + metadata, no content."""
    key: str
    mtime: float
    size: int
    etag: str


@dataclass
class BackendCapabilities:
    """Declared capabilities of a backend."""
    atomic_write: bool
    etag_native: bool
    list_consistency: Literal["strong", "eventual"]
    search: bool
    max_object_size_bytes: int


class VFSError(Exception):
    """Base class for all VFS errors."""


class NotFoundError(VFSError):
    """Read/delete on a key that does not exist."""


class ConflictError(VFSError):
    """CAS conflict: if_match did not match current etag (or O_EXCL failed)."""


class CapabilityError(VFSError):
    """Backend cannot meet the zone's required capabilities."""


class ZoneViolationError(VFSError):
    """Symlink/path-traversal violation — refuses to operate outside root."""


class ValidationError(VFSError):
    """Bad key grammar, frontmatter, secret refusal, or size cap exceeded."""


class PermissionGateError(VFSError):
    """TTY gate or perms refusal (e.g., --as-user without TTY)."""
