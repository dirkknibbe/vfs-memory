"""TempZone garbage collection — 7-day sweep, symlink-safe."""
import os
import stat as _stat
import time
from pathlib import Path
from typing import List


DEFAULT_CUTOFF_SECONDS = 7 * 86400
STAMP_FILENAME = ".gc-last-run"
STAMP_INTERVAL_SECONDS = 86400  # once per day


def sweep_temp_zone(
    temp_dir: str,
    cutoff_seconds: int = DEFAULT_CUTOFF_SECONDS,
) -> List[str]:
    """Remove regular files in `temp_dir` whose mtime is older than the cutoff.

    Symlinks are explicitly skipped (no following). Subdirs are not
    traversed in v1 — temp is supposed to be flat.

    Returns the list of removed file names (relative to temp_dir).
    """
    removed: List[str] = []
    threshold = time.time() - cutoff_seconds
    try:
        entries = os.listdir(temp_dir)
    except FileNotFoundError:
        return removed
    for name in entries:
        full = os.path.join(temp_dir, name)
        try:
            st = os.lstat(full)
        except OSError:
            continue
        if _stat.S_ISLNK(st.st_mode):
            continue
        if not _stat.S_ISREG(st.st_mode):
            continue
        if st.st_mtime >= threshold:
            continue
        try:
            os.unlink(full)
        except OSError:
            continue
        removed.append(name)
    return removed


def opportunistic_sweep(vfs_dir: Path) -> bool:
    """Run a sweep iff the stamp file says we haven't recently.

    Returns True if the sweep fired, False if it was skipped this call.
    """
    vfs_dir = Path(vfs_dir)
    stamp = vfs_dir / STAMP_FILENAME
    now = time.time()
    try:
        last = stamp.stat().st_mtime
        if now - last < STAMP_INTERVAL_SECONDS:
            return False
    except FileNotFoundError:
        pass
    sweep_temp_zone(str(vfs_dir / "temp"))
    old_umask = os.umask(0o077)
    try:
        stamp.touch(mode=0o600, exist_ok=True)
        os.utime(stamp, (now, now))
    finally:
        os.umask(old_umask)
    return True
