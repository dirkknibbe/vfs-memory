"""Zone wrappers: TempZone (flat, no provenance), PersistentZone (frontmatter)."""
from typing import List, Optional, Tuple

from vfs.backends.localfs import LocalFSBackend
from vfs.frontmatter import (
    _check_field_key, _check_field_value,
    make_frontmatter, parse_frontmatter,
)
from vfs.secrets import looks_like_secret
from vfs.types import Entry, NotFoundError, ValidationError


_VFS_OWNED_FIELDS = {"writer", "source", "ts", "project_slug", "etag"}


class TempZone:
    """Ephemeral scratch. No frontmatter; flat key-value over the backend."""

    def __init__(self, backend: LocalFSBackend) -> None:
        self._backend = backend

    def read(self, key: str, offset: int = 0, limit: Optional[int] = None) -> str:
        content, _etag, _mtime = self._backend.read(key, offset, limit)
        return content

    def write(self, key: str, content: str) -> str:
        return self._backend.write(key, content)

    def delete(self, key: str) -> None:
        self._backend.delete(key)

    def list(
        self,
        prefix: str = "",
        cursor: Optional[str] = None,
        max_items: int = 100,
    ) -> Tuple[List[Entry], Optional[str]]:
        return self._backend.list(prefix, cursor, max_items)

    def search(self, prefix: str, query: str, max_hits: int = 50) -> list:
        return self._backend.search(prefix, query, max_hits)


class PersistentZone:
    """Durable, provenance-tagged storage.

    `source_user_allowed` is set by the CLI layer based on the TTY gate.
    The library default is False — callers cannot upgrade trust without
    going through the gated CLI path.
    """

    def __init__(
        self,
        backend: LocalFSBackend,
        diag,
        writer_id: str,
        project_id: str,
        source_user_allowed: bool = False,
    ) -> None:
        self._backend = backend
        self._diag = diag
        self._writer = writer_id
        self._project = project_id
        self._source_user_allowed = source_user_allowed

    def read(self, key: str) -> Tuple[str, dict]:
        """Read the full file, parse and sanitize frontmatter.

        Returns (body, frontmatter_dict). No offset/limit — use `read_raw()`
        for partial reads, which returns raw bytes without frontmatter parsing.
        """
        content, _etag, _mtime = self._backend.read(key)
        fm, body = parse_frontmatter(content)
        return body, fm

    def read_raw(
        self,
        key: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> str:
        """Raw partial read. Returns file content (frontmatter included)
        without parsing.
        """
        content, _etag, _mtime = self._backend.read(key, offset, limit)
        return content

    def write(
        self,
        key: str,
        content: str,
        source: str = "agent",
        if_match: Optional[str] = None,
        allow_secret: bool = False,
    ) -> str:
        if source == "user" and not self._source_user_allowed:
            raise ValidationError(
                "source=user is not allowed via the agent surface; "
                "use `vfs remember --as-user` (TTY-gated)"
            )
        if not allow_secret and looks_like_secret(content):
            raise ValidationError(
                "refusing to write content matching a known secret shape; "
                "pass --allow-secret (TTY-gated) if intentional"
            )

        # Merge-on-write: preserve non-VFS-owned fields from existing file,
        # but route them through the same validators as VFS-owned fields.
        preserved: dict = {}
        dropped: list = []
        try:
            existing, _e, _m = self._backend.read(key)
            existing_fm, _existing_body = parse_frontmatter(existing)
            for k, v in existing_fm.items():
                if k in _VFS_OWNED_FIELDS:
                    continue
                if not _check_field_key(k):
                    dropped.append((k, "bad-key"))
                    continue
                try:
                    _check_field_value(k, v)
                except ValidationError:
                    dropped.append((k, "bad-value"))
                    continue
                preserved[k] = v
        except NotFoundError:
            pass

        fm = make_frontmatter(
            writer=self._writer,
            source=source,
            project_slug=self._project,
        )
        if preserved:
            closing = fm.rfind("---\n")
            preserved_lines = "".join(
                f"{k}: {v}\n" for k, v in preserved.items()
            )
            fm = fm[:closing] + preserved_lines + fm[closing:]

        etag = self._backend.write(key, fm + content, if_match=if_match)
        self._diag.append({
            "op": "write",
            "key": key,
            "writer": self._writer,
            "source": source,
            "etag": etag,
        })
        for k, reason in dropped:
            self._diag.append({
                "op": "merge-drop-field",
                "key": key,
                "field": k,
                "reason": reason,
            })
        return etag

    def delete(self, key: str, if_match: Optional[str] = None) -> None:
        self._backend.delete(key, if_match=if_match)
        self._diag.append({
            "op": "delete",
            "key": key,
            "writer": self._writer,
        })

    def list(
        self,
        prefix: str = "",
        cursor: Optional[str] = None,
        max_items: int = 100,
    ) -> Tuple[List[Entry], Optional[str]]:
        return self._backend.list(prefix, cursor, max_items)

    def search(self, prefix: str, query: str, max_hits: int = 50) -> list:
        return self._backend.search(prefix, query, max_hits)
