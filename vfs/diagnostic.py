"""Diagnostic log — append-only JSONL with fcntl.flock for same-UID safety.

Explicitly NOT an audit log: the audited process can also write here.
Same-UID peer locking ensures concurrent appends produce well-formed JSONL,
not interleaved bytes — which is the realistic concurrency case (two
Claude Code sessions writing the same project).

Rotates to `.1` at `VFS_MAX_DIAGNOSTIC_LOG_BYTES` (default 100 MB). Rotation
is not integrity-preserving (consistent with the "diagnostic, not audit"
naming).
"""
import fcntl
import json
import os
from datetime import datetime, timezone


DEFAULT_MAX_BYTES = 100_000_000  # rotate at 100 MB


class DiagnosticLog:
    def __init__(self, path: str) -> None:
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            old_umask = os.umask(0o077)
            try:
                os.makedirs(parent, mode=0o700, exist_ok=True)
            finally:
                os.umask(old_umask)

    def append(self, record: dict) -> None:
        full = dict(record)
        full.setdefault("ts", datetime.now(timezone.utc).isoformat())
        full.setdefault("caller_pid", os.getpid())
        line = json.dumps(full, separators=(",", ":")) + "\n"
        max_bytes = int(os.environ.get(
            "VFS_MAX_DIAGNOSTIC_LOG_BYTES", str(DEFAULT_MAX_BYTES)
        ))
        old_umask = os.umask(0o077)
        try:
            fd = os.open(self.path,
                         os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
                         mode=0o600)
        finally:
            os.umask(old_umask)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                cur_size = os.fstat(fd).st_size
                if cur_size + len(line) > max_bytes:
                    try:
                        os.rename(self.path, self.path + ".1")
                    except OSError:
                        pass
                    os.close(fd)
                    old_umask = os.umask(0o077)
                    try:
                        fd = os.open(self.path,
                                     os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
                                     mode=0o600)
                    finally:
                        os.umask(old_umask)
                    fcntl.flock(fd, fcntl.LOCK_EX)
                os.write(fd, line.encode("utf-8"))
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
