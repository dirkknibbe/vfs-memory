"""Migration from legacy ~/.claude/projects/<slug>/memory/ to .vfs/persistent/.

Symlink-contained walk of the source directory: refuses symlinks at any
component and ensures realpath stays inside the source. Library callers
invoke `run_migration(args, vfs)` directly; the CLI handler wraps it
with the TTY gate.
"""
import os
import stat as _stat
from pathlib import Path

from vfs.backends.localfs import MAX_OBJECT_SIZE_BYTES
from vfs.frontmatter import parse_frontmatter
from vfs.types import ValidationError


def _collect_md_files(src_root: str) -> list:
    md_files = []
    for dirpath, dirnames, filenames in os.walk(src_root, followlinks=False):
        dirnames[:] = [d for d in dirnames
                       if not os.path.islink(os.path.join(dirpath, d))]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            full = os.path.join(dirpath, fn)
            try:
                fst = os.lstat(full)
            except OSError:
                continue
            if _stat.S_ISLNK(fst.st_mode):
                continue
            real = os.path.realpath(full)
            if not (real == src_root or real.startswith(src_root + os.sep)):
                continue
            md_files.append(full)
    return md_files


def run_migration(args, v) -> dict:
    """Migrate .md files from `args.from_dir` into `v.persistent`.

    Returns {"migrated": [keys], "skipped": [(key, reason)]}.
    Raises ValidationError on missing/invalid source dir.
    """
    src_path = Path(args.from_dir).expanduser().resolve()
    if not src_path.is_dir():
        raise ValidationError(f"{src_path} is not a directory")

    md_files = _collect_md_files(str(src_path))
    if not md_files:
        raise ValidationError(f"no .md files in {src_path}")

    skipped: list = []
    migrated: list = []
    old_writer = v.persistent._writer
    v.persistent._writer = "vfs-migrate"
    try:
        for full in sorted(md_files):
            rel = Path(full).relative_to(src_path)
            rel_key = str(rel).replace(os.sep, "/")
            try:
                raw = Path(full).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                skipped.append((rel_key, f"unreadable: {e}"))
                continue
            fm, body = parse_frontmatter(raw)
            for owned in ("source", "writer", "ts", "project_slug", "etag"):
                fm.pop(owned, None)
            if args.dry_run:
                migrated.append(rel_key)
                continue
            if len(body.encode("utf-8")) > MAX_OBJECT_SIZE_BYTES:
                skipped.append((rel_key, "exceeds 10MB cap"))
                continue
            dest_dir = v.root / ".vfs" / "persistent" / Path(rel_key).parent
            dest_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            if fm:
                pre = ("---\n"
                       + "".join(f"{k}: {val}\n" for k, val in fm.items())
                       + "---\n")
                (v.root / ".vfs" / "persistent" / rel_key).write_text(
                    pre, encoding="utf-8"
                )
            try:
                v.persistent.write(rel_key, body, source="agent",
                                   allow_secret=True)
                migrated.append(rel_key)
            except ValidationError as e:
                skipped.append((rel_key, str(e)))
        if args.delete_source:
            for rel_key in migrated:
                (src_path / rel_key).unlink(missing_ok=True)
    finally:
        v.persistent._writer = old_writer
    return {"migrated": migrated, "skipped": skipped}
