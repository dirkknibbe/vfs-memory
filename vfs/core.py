"""VFS top-level entry point: VFS() and init_project()."""
import os
import re
from pathlib import Path
from typing import Optional

from vfs.backends.localfs import LocalFSBackend
from vfs.config import read_config, write_config
from vfs.diagnostic import DiagnosticLog
from vfs.gc import opportunistic_sweep
from vfs.paths import resolve_project_root
from vfs.types import ValidationError
from vfs.zones import PersistentZone, TempZone


_WRITER_ID_PATTERN = re.compile(r"^[\w.-]+$")


def _validated_writer_id() -> str:
    """Read $VFS_WRITER and validate against [\\w.-]+ (no control chars).

    Closes ANSI-escape injection into `vfs review` output via attacker-
    controlled writer IDs. Refuses on any character outside the allowed
    set rather than sanitizing — sanitization invites future bypass.
    """
    writer = os.environ.get("VFS_WRITER", "agent")
    if not _WRITER_ID_PATTERN.match(writer):
        raise ValidationError(
            f"$VFS_WRITER {writer!r} contains invalid characters; "
            f"allowed: [A-Za-z0-9_.-]+"
        )
    return writer


def init_project(root: Path) -> dict:
    """Create .vfs/ structure at `root`. Refuses if one exists."""
    root = Path(root)
    vfs_dir = root / ".vfs"
    if vfs_dir.exists():
        raise ValidationError(f".vfs/ already exists at {vfs_dir}")
    old_umask = os.umask(0o077)
    try:
        vfs_dir.mkdir(mode=0o700)
        (vfs_dir / "persistent").mkdir(mode=0o700)
        (vfs_dir / "temp").mkdir(mode=0o700)
    finally:
        os.umask(old_umask)
    pid = write_config(vfs_dir)
    return {"project_id": pid, "root": str(root)}


class VFS:
    """Top-level handle. Resolves .vfs/ on construction.

    Construction does NOT accept writer_id — it reads $VFS_WRITER and
    validates it. Cross-project access via VFS(root=...).

    `strict_perms=True` (default) propagates to the LocalFSBackend ctors,
    which refuse to operate on a .vfs/ with loose perms — re-checked
    each session, not just at init.
    """

    def __init__(
        self,
        root: Optional[str] = None,
        *,
        source_user_allowed: bool = False,
        strict_perms: bool = True,
    ) -> None:
        if root is None:
            self.root = resolve_project_root()
        else:
            self.root = Path(root).resolve()
            if not (self.root / ".vfs").is_dir():
                raise ValidationError(f"no .vfs/ at {root!r}")

        config = read_config(self.root / ".vfs")
        self.project_id = config["project_id"]
        self.writer_id = _validated_writer_id()

        self._persistent_backend = LocalFSBackend(
            str(self.root / ".vfs" / "persistent"),
            strict_perms=strict_perms,
        )
        self._temp_backend = LocalFSBackend(
            str(self.root / ".vfs" / "temp"),
            strict_perms=strict_perms,
        )
        self._diag = DiagnosticLog(str(self.root / ".vfs" / "diagnostic.log"))

        try:
            opportunistic_sweep(self.root / ".vfs")
        except Exception:
            # GC failure must not block VFS construction
            pass

        self.persistent = PersistentZone(
            backend=self._persistent_backend,
            diag=self._diag,
            writer_id=self.writer_id,
            project_id=self.project_id,
            source_user_allowed=source_user_allowed,
        )
        self.temp = TempZone(self._temp_backend)

    def close(self) -> None:
        self._persistent_backend.close()
        self._temp_backend.close()
