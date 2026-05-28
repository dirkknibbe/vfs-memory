"""vfs CLI entry point."""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from agent_vfs import __version__
from agent_vfs.core import VFS, init_project
from agent_vfs.ratelimit import WriteRateLimiter
from agent_vfs.types import (
    ConflictError, NotFoundError, PermissionGateError,
    ValidationError, VFSError, ZoneViolationError,
)


# Exit codes
EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_NOT_FOUND = 2
EXIT_CONFLICT = 3
EXIT_VALIDATION = 4
EXIT_PERMISSION = 5


_REVIEW_STRIP = re.compile(r"[\x00-\x1f\x7f]")


def _exit_for(exc: Exception) -> int:
    if isinstance(exc, NotFoundError):
        return EXIT_NOT_FOUND
    if isinstance(exc, ConflictError):
        return EXIT_CONFLICT
    if isinstance(exc, (ValidationError, ZoneViolationError)):
        return EXIT_VALIDATION
    if isinstance(exc, PermissionGateError):
        return EXIT_PERMISSION
    return EXIT_GENERIC


def _require_tty():
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise PermissionGateError(
            "this command requires an interactive TTY on both stdin and stdout"
        )


def _vfs_for(args, *, source_user_allowed: bool = False) -> "VFS":
    """Construct a VFS instance, honoring --root from argparse.

    The root value flows through the constructor, never via env mutation.
    """
    root = getattr(args, "root", None)
    return VFS(root=root, source_user_allowed=source_user_allowed)


def _sanitize_for_terminal(s: str) -> str:
    """Strip control + DEL chars before printing to a TTY."""
    return _REVIEW_STRIP.sub("", s)


# ---- agent surface ----

def _cmd_init(args) -> int:
    try:
        result = init_project(Path.cwd())
    except ValidationError as e:
        print(f"vfs init: {e}", file=sys.stderr)
        return EXIT_VALIDATION
    print(f"initialized .vfs/ (project_id={result['project_id']})")
    print("suggestion: echo '.vfs/' >> .gitignore", file=sys.stderr)
    return EXIT_OK


def _cmd_whoami(args) -> int:
    v = _vfs_for(args)
    try:
        output = {
            "writer_id": v.writer_id,
            "project_id": v.project_id,
            "root": str(v.root),
        }
        if args.json:
            print(json.dumps(output))
        else:
            for k, val in output.items():
                print(f"{k}: {val}")
        return EXIT_OK
    finally:
        v.close()


def _cmd_version(args) -> int:
    print(f"agent-vfs {__version__}")
    return EXIT_OK


def _cmd_read(args) -> int:
    v = _vfs_for(args)
    try:
        if args.zone == "temp":
            content = v.temp.read(args.key,
                                  offset=args.offset or 0,
                                  limit=args.limit)
            sys.stdout.write(content)
        else:
            body, fm = v.persistent.read(args.key)
            if args.json:
                print(json.dumps({"body": body, "frontmatter": fm}))
            else:
                sys.stdout.write(body)
        return EXIT_OK
    finally:
        v.close()


def _cmd_write(args) -> int:
    v = _vfs_for(args)
    try:
        if args.zone == "persistent":
            limit = int(os.environ.get("VFS_MAX_WRITES_PER_MINUTE", "300"))
            rl = WriteRateLimiter(
                str(v.root / ".vfs" / ".ratelimit.state"),
                limit=limit,
                window_s=60,
            )
            rl.check()
        content = sys.stdin.read()
        if args.zone == "temp":
            etag = v.temp.write(args.key, content)
        else:
            etag = v.persistent.write(
                args.key,
                content,
                source=args.source,
                if_match=args.if_match,
                allow_secret=args.allow_secret,
            )
        if args.json:
            print(json.dumps({"etag": etag}))
        else:
            print(etag)
        return EXIT_OK
    finally:
        v.close()


def _cmd_list(args) -> int:
    v = _vfs_for(args)
    try:
        zone = v.temp if args.zone == "temp" else v.persistent
        entries, cursor = zone.list(
            prefix=args.prefix or "",
            cursor=args.cursor,
            max_items=args.max or 100,
        )
        for e in entries:
            row = {"key": e.key, "size": e.size, "mtime": e.mtime, "etag": e.etag}
            print(json.dumps(row) if args.json else f"{e.key}\t{e.size}\t{e.etag}")
        if cursor and args.json:
            print(json.dumps({"_cursor": cursor}))
        return EXIT_OK
    finally:
        v.close()


def _cmd_delete(args) -> int:
    v = _vfs_for(args)
    try:
        if args.zone == "temp":
            v.temp.delete(args.key)
        else:
            v.persistent.delete(args.key, if_match=args.if_match)
        return EXIT_OK
    finally:
        v.close()


def _cmd_search(args) -> int:
    v = _vfs_for(args)
    try:
        zone = v.temp if args.zone == "temp" else v.persistent
        hits = zone.search(prefix=args.prefix or "",
                           query=args.query,
                           max_hits=args.max or 50)
        for h in hits:
            if args.json:
                print(json.dumps(h))
            else:
                print(f"{h['key']}:{h['line']}: {h['snippet']}")
        return EXIT_OK
    finally:
        v.close()


def _cmd_gc(args) -> int:
    from agent_vfs.gc import sweep_temp_zone
    v = _vfs_for(args)
    try:
        removed = sweep_temp_zone(str(v.root / ".vfs" / "temp"))
        if args.json:
            print(json.dumps({"removed": removed}))
        else:
            for name in removed:
                print(f"removed: {name}")
            print(f"swept {len(removed)} file(s)", file=sys.stderr)
        return EXIT_OK
    finally:
        v.close()


# ---- human surface (TTY-gated) ----

def _cmd_remember(args) -> int:
    if args.as_user:
        _require_tty()
    v = _vfs_for(args, source_user_allowed=args.as_user)
    try:
        content = sys.stdin.read()
        source = "user" if args.as_user else "agent"
        etag = v.persistent.write(args.key, content, source=source)
        print(etag)
        return EXIT_OK
    finally:
        v.close()


def _cmd_review(args) -> int:
    v = _vfs_for(args)
    try:
        log_path = v.root / ".vfs" / "diagnostic.log"
        if not log_path.exists():
            print("(no diagnostic.log yet)", file=sys.stderr)
            return EXIT_OK
        n = args.tail or 50
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        if not lines or lines == [""]:
            return EXIT_OK
        for line in lines[-n:]:
            if args.json:
                print(line)
            else:
                try:
                    rec = json.loads(line)
                    ts = _sanitize_for_terminal(str(rec.get("ts", "?")))
                    op = _sanitize_for_terminal(str(rec.get("op", "?")))
                    key = _sanitize_for_terminal(str(rec.get("key", "?")))
                    writer = _sanitize_for_terminal(str(rec.get("writer", "?")))
                    print(f"{ts}  {op:8}  {key:40}  by {writer}")
                except json.JSONDecodeError:
                    print(_sanitize_for_terminal(line))
        return EXIT_OK
    finally:
        v.close()


def _cmd_migrate(args) -> int:
    from agent_vfs.migrate import run_migration

    try:
        _require_tty()
    except PermissionGateError as e:
        print(f"vfs migrate: {e}", file=sys.stderr)
        return EXIT_PERMISSION

    try:
        v = _vfs_for(args)
    except VFSError as e:
        print(f"vfs migrate: {e}", file=sys.stderr)
        return _exit_for(e)
    try:
        try:
            result = run_migration(args, v)
        except ValidationError as e:
            print(f"vfs migrate: {e}", file=sys.stderr)
            return EXIT_VALIDATION
    finally:
        v.close()

    for key in result["migrated"]:
        print(f"migrated: {key}")
    for key, reason in result["skipped"]:
        print(f"skipped: {key} ({reason})", file=sys.stderr)
    return EXIT_OK if not result["skipped"] else EXIT_GENERIC


# ---- argparse wiring ----

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agent_vfs", description="agent-vfs CLI")
    p.add_argument("--json", action="store_true",
                   help="JSON output where applicable")
    p.add_argument("--root",
                   help="cross-project root (requires --as-user on subcommand)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(_func=_cmd_init)
    sub.add_parser("whoami").set_defaults(_func=_cmd_whoami)
    sub.add_parser("version").set_defaults(_func=_cmd_version)
    sub.add_parser("gc", help="sweep temp/ entries older than 7 days") \
       .set_defaults(_func=_cmd_gc)

    def _add_persistent_io(sub_parsers):
        rp = sub_parsers.add_parser("read")
        rp.set_defaults(_func=_cmd_read, zone="persistent")
        rp.add_argument("key")
        rp.add_argument("--offset", type=int)
        rp.add_argument("--limit", type=int)

        wp = sub_parsers.add_parser("write")
        wp.set_defaults(_func=_cmd_write, zone="persistent")
        wp.add_argument("key")
        wp.add_argument("--if-match", dest="if_match", default=None)
        wp.add_argument("--source", default="agent",
                        help="agent | tool:NAME | web:DOMAIN")
        wp.add_argument("--allow-secret", action="store_true",
                        dest="allow_secret")

        dp = sub_parsers.add_parser("delete")
        dp.set_defaults(_func=_cmd_delete, zone="persistent")
        dp.add_argument("key")
        dp.add_argument("--if-match", dest="if_match", default=None)

        lp = sub_parsers.add_parser("list")
        lp.set_defaults(_func=_cmd_list, zone="persistent")
        lp.add_argument("--prefix")
        lp.add_argument("--cursor")
        lp.add_argument("--max", type=int)

        sp = sub_parsers.add_parser("search")
        sp.set_defaults(_func=_cmd_search, zone="persistent")
        sp.add_argument("query")
        sp.add_argument("--prefix")
        sp.add_argument("--max", type=int)

    def _add_temp_io(sub_parsers):
        rp = sub_parsers.add_parser("read")
        rp.set_defaults(_func=_cmd_read, zone="temp")
        rp.add_argument("key")
        rp.add_argument("--offset", type=int)
        rp.add_argument("--limit", type=int)

        wp = sub_parsers.add_parser("write")
        wp.set_defaults(_func=_cmd_write, zone="temp")
        wp.add_argument("key")

        dp = sub_parsers.add_parser("delete")
        dp.set_defaults(_func=_cmd_delete, zone="temp")
        dp.add_argument("key")

        lp = sub_parsers.add_parser("list")
        lp.set_defaults(_func=_cmd_list, zone="temp")
        lp.add_argument("--prefix")
        lp.add_argument("--cursor")
        lp.add_argument("--max", type=int)

        sp = sub_parsers.add_parser("search")
        sp.set_defaults(_func=_cmd_search, zone="temp")
        sp.add_argument("query")
        sp.add_argument("--prefix")
        sp.add_argument("--max", type=int)

    _add_persistent_io(sub)

    temp = sub.add_parser("temp", help="ephemeral zone subcommands")
    temp_sub = temp.add_subparsers(dest="temp_cmd", required=True)
    _add_temp_io(temp_sub)

    rp = sub.add_parser("remember", help="write with source=user (TTY-gated)")
    rp.set_defaults(_func=_cmd_remember)
    rp.add_argument("--as-user", action="store_true", dest="as_user")
    rp.add_argument("key")

    rv = sub.add_parser("review", help="show diagnostic.log tail")
    rv.set_defaults(_func=_cmd_review)
    rv.add_argument("--tail", type=int)

    mp = sub.add_parser("migrate",
                        help="copy legacy memory dir into .vfs/persistent (TTY-gated)")
    mp.set_defaults(_func=_cmd_migrate)
    mp.add_argument("--from", dest="from_dir", required=True)
    mp.add_argument("--dry-run", action="store_true", dest="dry_run")
    mp.add_argument("--delete-source", action="store_true",
                    dest="delete_source")

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # Default `as_user` for commands that don't declare it
    if not hasattr(args, "as_user"):
        args.as_user = False
    # --root requires --as-user
    if getattr(args, "root", None):
        if not getattr(args, "as_user", False):
            print("vfs: --root requires --as-user (TTY-gated)", file=sys.stderr)
            return EXIT_PERMISSION
        try:
            _require_tty()
        except PermissionGateError as e:
            print(f"vfs: {e}", file=sys.stderr)
            return EXIT_PERMISSION
    try:
        return args._func(args)
    except VFSError as e:
        print(f"vfs: {e}", file=sys.stderr)
        return _exit_for(e)


if __name__ == "__main__":
    sys.exit(main())
