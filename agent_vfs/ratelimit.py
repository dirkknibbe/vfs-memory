"""Rate limiter for write ops — soft cap to defeat loop-prompt-injection DoS."""
import fcntl
import json
import os
import stat as _stat
import time

from agent_vfs.types import VFSError


class WriteRateLimiter:
    def __init__(self, state_path: str, limit: int = 300, window_s: int = 60) -> None:
        self.path = state_path
        self.limit = limit
        self.window_s = window_s

    def check(self) -> None:
        now = time.time()
        old_umask = os.umask(0o077)
        try:
            fd = os.open(self.path,
                         os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                         mode=0o600)
        finally:
            os.umask(old_umask)
        try:
            # fstat the FD: must be a regular file owned by current UID,
            # mode 0600, st_nlink == 1. Defeats a same-UID peer pre-planting
            # a hardlink or world-readable file at this path.
            st = os.fstat(fd)
            if not _stat.S_ISREG(st.st_mode):
                raise VFSError(
                    f"rate-limiter state file {self.path!r} is not a regular file"
                )
            if st.st_uid != os.geteuid():
                raise VFSError(
                    f"rate-limiter state file {self.path!r} has unexpected owner"
                )
            if st.st_nlink != 1:
                raise VFSError(
                    f"rate-limiter state file {self.path!r} has st_nlink != 1 (hardlinked?)"
                )
            mode = _stat.S_IMODE(st.st_mode)
            if mode & 0o077:
                raise VFSError(
                    f"rate-limiter state file {self.path!r} has mode {oct(mode)} (must be 0600)"
                )

            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                raw = os.read(fd, 65536).decode("utf-8")
                if not raw:
                    timestamps = []
                else:
                    try:
                        timestamps = json.loads(raw)
                    except json.JSONDecodeError as e:
                        # Do NOT silent-reset: a malicious peer pre-planting
                        # garbage would otherwise be able to clear the limiter.
                        raise VFSError(
                            f"rate-limiter state file {self.path!r} is corrupted; "
                            f"delete it manually if intentional: {e}"
                        )
                if not isinstance(timestamps, list):
                    raise VFSError(
                        f"rate-limiter state file {self.path!r} has unexpected shape"
                    )
                cutoff = now - self.window_s
                timestamps = [t for t in timestamps
                              if isinstance(t, (int, float)) and t >= cutoff]
                if len(timestamps) >= self.limit:
                    raise VFSError(
                        f"write rate limit exceeded: "
                        f"{len(timestamps)} writes in last {self.window_s}s "
                        f"(limit {self.limit})"
                    )
                timestamps.append(now)
                os.lseek(fd, 0, os.SEEK_SET)
                os.ftruncate(fd, 0)
                os.write(fd, json.dumps(timestamps).encode("utf-8"))
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
