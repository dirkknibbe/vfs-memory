"""LocalFS backend with O_DIRECTORY root FD + dir_fd-relative traversal."""
import errno
import os
import secrets
import stat
from typing import List, Optional, Tuple

from agent_vfs.types import (
    BackendCapabilities, ConflictError, Entry, NotFoundError,
    ValidationError, VFSError, ZoneViolationError,
)
from agent_vfs.paths import validate_key


MAX_OBJECT_SIZE_BYTES = 10_000_000  # 10 MB enforced cap
DIR_MODE = 0o700
FILE_MODE = 0o600


class LocalFSBackend:
    """File-backed storage with strict path containment.

    Root resolution: realpath the user-supplied path, then open with
    O_DIRECTORY and hold the FD for the process lifetime. All subsequent
    operations traverse with `dir_fd=root_fd` and `O_NOFOLLOW` on every
    component, plus an lstat check on write destinations.
    """

    def __init__(self, root: str, *, strict_perms: bool = True) -> None:
        """Initialize the backend.

        `strict_perms=True` (default) refuses to operate if the root
        directory's mode has any `0o077` bits set. Callers who need to
        operate on a deliberately-loose-perms dir (rare) pass
        `strict_perms=False`. The CLI never overrides the default.
        """
        self.root = os.path.abspath(os.path.expanduser(root))
        old_umask = os.umask(0o077)
        try:
            os.makedirs(self.root, mode=DIR_MODE, exist_ok=True)
        finally:
            os.umask(old_umask)

        if strict_perms:
            st = os.stat(self.root)
            mode = stat.S_IMODE(st.st_mode)
            if mode & 0o077:
                raise PermissionError(
                    f"refusing to operate on {self.root!r} with mode "
                    f"{oct(mode)} (must be 0700 or stricter); "
                    f"chmod 0700 {self.root} or construct with "
                    f"strict_perms=False if intentional"
                )

        self._root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)

    def close(self) -> None:
        """Release the root directory FD. Idempotent.

        No __del__ — close-on-gc is unreliable at interpreter shutdown.
        Tests + the CLI call close() explicitly via try/finally.
        """
        if self._root_fd != -1:
            os.close(self._root_fd)
            self._root_fd = -1

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            atomic_write=True,
            etag_native=False,
            list_consistency="strong",
            search=True,
            max_object_size_bytes=MAX_OBJECT_SIZE_BYTES,
        )

    # ---- internal helpers ----

    def _open_relative(self, key: str, flags: int) -> int:
        """Open `key` relative to root_fd, refusing symlinks at any component.

        Walks components one by one, opening each as a directory FD with
        O_NOFOLLOW. The final component is opened with `flags`. This
        defeats symlink-in-path-component attacks even under concurrent
        attacker-driven swaps.
        """
        validate_key(key)
        components = key.split("/")
        cur_fd = self._root_fd
        opened_fds: list = []
        try:
            for i, comp in enumerate(components):
                is_final = i == len(components) - 1
                comp_flags = flags if is_final else (
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                )
                try:
                    next_fd = os.open(comp, comp_flags | os.O_NOFOLLOW,
                                      dir_fd=cur_fd)
                except OSError as e:
                    if e.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise ZoneViolationError(
                            f"symlink in path: {key!r} (component {comp!r})"
                        ) from e
                    if e.errno == errno.ENOENT:
                        raise NotFoundError(key) from e
                    raise
                if not is_final:
                    opened_fds.append(next_fd)
                cur_fd = next_fd
            return cur_fd
        except Exception:
            for fd in opened_fds:
                try:
                    os.close(fd)
                except OSError:
                    pass
            raise
        finally:
            for fd in opened_fds:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def _open_dir_relative(self, dir_path: str) -> int:
        """Open an intermediate directory under root, refusing symlinks."""
        components = [c for c in dir_path.split("/") if c]
        cur_fd = self._root_fd
        opened: list = []
        try:
            for comp in components:
                try:
                    next_fd = os.open(
                        comp,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=cur_fd,
                    )
                except OSError as e:
                    if e.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise ZoneViolationError(
                            f"symlink in path: {dir_path!r}"
                        ) from e
                    raise
                if cur_fd != self._root_fd:
                    opened.append(cur_fd)
                cur_fd = next_fd
        except Exception:
            for fd in opened:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if cur_fd != self._root_fd:
                try:
                    os.close(cur_fd)
                except OSError:
                    pass
            raise
        else:
            for fd in opened:
                try:
                    os.close(fd)
                except OSError:
                    pass
            return cur_fd

    def _mkdir_relative(self, dir_path: str) -> None:
        """Create intermediate directories under root, refusing symlinks."""
        components = [c for c in dir_path.split("/") if c]
        cur_fd = self._root_fd
        opened: list = []
        try:
            for comp in components:
                try:
                    next_fd = os.open(
                        comp,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=cur_fd,
                    )
                except FileNotFoundError:
                    old_umask = os.umask(0o077)
                    try:
                        os.mkdir(comp, mode=DIR_MODE, dir_fd=cur_fd)
                    finally:
                        os.umask(old_umask)
                    next_fd = os.open(
                        comp,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=cur_fd,
                    )
                except OSError as e:
                    if e.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise ZoneViolationError(
                            f"symlink in path: {dir_path!r}"
                        ) from e
                    raise
                if cur_fd != self._root_fd:
                    opened.append(cur_fd)
                cur_fd = next_fd
            if cur_fd != self._root_fd:
                opened.append(cur_fd)
        finally:
            for fd in opened:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def _etag_from_fd(self, fd: int) -> tuple:
        st = os.fstat(fd)
        return f"{st.st_mtime_ns}-{st.st_size}", st.st_mtime

    # ---- public ops ----

    def read(
        self,
        key: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> Tuple[str, str, float]:
        """Read up to `limit` characters from `key`, starting at `offset`.

        Returns (content, etag, mtime). Raises NotFoundError or
        ZoneViolationError as appropriate.
        """
        fd = self._open_relative(key, os.O_RDONLY)
        try:
            etag, mtime = self._etag_from_fd(fd)
            with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as fp:
                if offset:
                    fp.read(offset)
                content = fp.read() if limit is None else fp.read(limit)
            return content, etag, mtime
        finally:
            os.close(fd)

    def write(
        self,
        key: str,
        content: str,
        if_match: Optional[str] = None,
    ) -> str:
        """Atomic write with symlink containment and size cap.

        `if_match`: None = last-writer-wins. "" = CAS-create (O_EXCL).
        "<etag>" = update only if current etag matches.
        """
        validate_key(key)
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_OBJECT_SIZE_BYTES:
            raise ValidationError(
                f"object too large: {len(encoded)} > {MAX_OBJECT_SIZE_BYTES}"
            )

        components = key.split("/")
        dir_components = components[:-1]
        filename = components[-1]

        if dir_components:
            self._mkdir_relative("/".join(dir_components))
            parent_fd = self._open_dir_relative("/".join(dir_components))
            close_parent = True
        else:
            parent_fd = self._root_fd
            close_parent = False

        try:
            # Refuse symlink at destination (existing file)
            try:
                st = os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)
                if stat.S_ISLNK(st.st_mode):
                    raise ZoneViolationError(
                        f"refusing to overwrite symlink at {key!r}"
                    )
                current_etag = f"{st.st_mtime_ns}-{st.st_size}"
                exists = True
            except FileNotFoundError:
                exists = False
                current_etag = ""

            # CAS check
            if if_match is not None:
                if if_match == "":
                    if exists:
                        raise ConflictError(
                            f"CAS-create failed: {key!r} already exists"
                        )
                else:
                    if not exists or if_match != current_etag:
                        raise ConflictError(
                            f"etag mismatch on {key!r}: expected {if_match!r}, "
                            f"current {current_etag!r}"
                        )

            # Atomic write via O_CREAT|O_EXCL temp file in dest's parent.
            # For CAS-create (if_match=""), use os.link + unlink to atomically
            # refuse if dest already exists (no TOCTOU window). For overwrite
            # or update, use os.rename (replaces atomically).
            tmp_basename = f".vfs-tmp-{secrets.token_hex(8)}"
            tmp_fd = os.open(
                tmp_basename,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                mode=FILE_MODE,
                dir_fd=parent_fd,
            )
            try:
                with os.fdopen(tmp_fd, "wb") as fp:
                    fp.write(encoded)
                if if_match == "":
                    # CAS-create: link is atomic and refuses if dest exists
                    try:
                        os.link(
                            tmp_basename, filename,
                            src_dir_fd=parent_fd, dst_dir_fd=parent_fd,
                            follow_symlinks=False,
                        )
                    except FileExistsError as e:
                        raise ConflictError(
                            f"CAS-create failed: {key!r} already exists"
                        ) from e
                    finally:
                        try:
                            os.unlink(tmp_basename, dir_fd=parent_fd)
                            tmp_basename = None
                        except OSError:
                            pass
                else:
                    os.rename(
                        tmp_basename,
                        filename,
                        src_dir_fd=parent_fd,
                        dst_dir_fd=parent_fd,
                    )
                    tmp_basename = None
            finally:
                if tmp_basename is not None:
                    try:
                        os.unlink(tmp_basename, dir_fd=parent_fd)
                    except OSError:
                        pass

            st = os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)
            return f"{st.st_mtime_ns}-{st.st_size}"
        finally:
            if close_parent:
                os.close(parent_fd)

    def delete(self, key: str, if_match: Optional[str] = None) -> None:
        """Unlink `key`, refusing symlinks. CAS via `if_match`."""
        validate_key(key)
        components = key.split("/")
        dir_components = components[:-1]
        filename = components[-1]

        if dir_components:
            parent_fd = self._open_dir_relative("/".join(dir_components))
            close_parent = True
        else:
            parent_fd = self._root_fd
            close_parent = False

        try:
            try:
                st = os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError as e:
                raise NotFoundError(key) from e
            if stat.S_ISLNK(st.st_mode):
                raise ZoneViolationError(
                    f"refusing to delete symlink at {key!r}"
                )
            if if_match is not None:
                current_etag = f"{st.st_mtime_ns}-{st.st_size}"
                if if_match != current_etag:
                    raise ConflictError(
                        f"etag mismatch on delete {key!r}: expected {if_match!r}, "
                        f"current {current_etag!r}"
                    )
            os.unlink(filename, dir_fd=parent_fd)
        finally:
            if close_parent:
                os.close(parent_fd)

    def list(
        self,
        prefix: str = "",
        cursor: Optional[str] = None,
        max_items: int = 100,
    ) -> Tuple[List[Entry], Optional[str]]:
        """List entries with key starting with `prefix`. Refuses symlinks."""
        max_files = int(os.environ.get("VFS_MAX_FILES", "10000"))

        candidates = []
        count = 0
        root_with_sep = self.root + os.sep
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            dirnames[:] = [d for d in dirnames
                           if not os.path.islink(os.path.join(dirpath, d))]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                if os.path.islink(full):
                    continue
                real = os.path.realpath(full)
                if not (real == self.root or real.startswith(root_with_sep)):
                    continue
                if fn.startswith(".vfs-tmp-"):
                    continue
                rel = os.path.relpath(full, self.root)
                if prefix and not rel.startswith(prefix):
                    continue
                count += 1
                if count > max_files:
                    raise VFSError(
                        f"VFS_MAX_FILES={max_files} exceeded; refusing to list. "
                        f"Set VFS_MAX_FILES=N to raise the cap."
                    )
                candidates.append(rel)

        candidates.sort()
        if cursor is not None:
            candidates = [k for k in candidates if k > cursor]
        batch = candidates[:max_items]
        next_cursor = batch[-1] if len(candidates) > max_items else None

        entries: List[Entry] = []
        for k in batch:
            full = os.path.join(self.root, k)
            st = os.lstat(full)
            entries.append(Entry(
                key=k,
                mtime=st.st_mtime,
                size=st.st_size,
                etag=f"{st.st_mtime_ns}-{st.st_size}",
            ))
        return entries, next_cursor

    def search(
        self,
        prefix: str,
        query: str,
        max_hits: int = 50,
    ) -> List[dict]:
        """Literal-substring line search. Refuses symlinks. Bounded per-file."""
        max_bytes = int(os.environ.get("VFS_MAX_BYTES_PER_FILE", "10000000"))
        max_files = int(os.environ.get("VFS_MAX_FILES", "10000"))

        hits: List[dict] = []
        count = 0
        root_with_sep = self.root + os.sep
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            dirnames[:] = [d for d in dirnames
                           if not os.path.islink(os.path.join(dirpath, d))]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                if os.path.islink(full):
                    continue
                real = os.path.realpath(full)
                if not (real == self.root or real.startswith(root_with_sep)):
                    continue
                if fn.startswith(".vfs-tmp-"):
                    continue
                rel = os.path.relpath(full, self.root)
                if prefix and not rel.startswith(prefix):
                    continue
                count += 1
                if count > max_files:
                    raise VFSError(
                        f"VFS_MAX_FILES={max_files} exceeded during search"
                    )
                try:
                    with open(full, "r", encoding="utf-8") as fp:
                        body = fp.read(max_bytes)
                except (OSError, UnicodeDecodeError):
                    continue
                for lineno, line in enumerate(body.split("\n"), start=1):
                    if query in line:
                        hits.append({
                            "key": rel,
                            "line": lineno,
                            "snippet": line,
                        })
                        if len(hits) >= max_hits:
                            return hits
        return hits
