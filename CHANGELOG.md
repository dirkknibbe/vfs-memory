# Changelog

All notable changes to this project will be documented in this file. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] — 2026-05-27

Initial release of `agent-vfs` on PyPI. Succeeds an unpublished in-tree v0.5/v0.6 package now deprecated; see `docs/superpowers/specs/2026-05-27-generic-vfs-design.md` for the v1 design rationale and the cheat-sheet of changes.

### Added
- CLI: `vfs init / read / write / list / delete / search / temp <subcmd> / whoami / version / remember / review / migrate / gc`.
- Per-project `.vfs/` directory layout with `config.toml` carrying schema version and project UUID.
- TTY-gated human surface for `--as-user`, `--root`, and `vfs migrate`; no env override.
- Symlink-resistant traversal via `O_DIRECTORY` root FD + `O_NOFOLLOW` per component.
- 10 MB enforced write size cap; `VFS_MAX_FILES` / `VFS_MAX_BYTES_PER_FILE` traversal bounds.
- Secret-shape refusal for AWS keys, GitHub PATs, JWTs. Bypass via `--allow-secret` (TTY-gated).
- Append-only `diagnostic.log` with `fcntl.flock` and rotation at `VFS_MAX_DIAGNOSTIC_LOG_BYTES`.
- Write rate limiter (300/min default) with `fstat`-verified state file.
- TempZone 7-day GC sweep (opportunistic on `VFS()` init + explicit `vfs gc`).
- Stdlib-only; zero runtime dependencies enforced in CI via AST-based static check.

### Changed from in-tree v0.5
- `VFS(writer_id=...)` removed; reads `$VFS_WRITER` (validated `[\w.-]+`) instead.
- `PersistentZone.read/list/search` no longer accept `project=` kwarg.
- `PersistentZone.read(offset=, limit=)` removed; raw partial reads via `read_raw()`.
- Storage moved from `~/.claude/projects/<slug>/memory/` to `<project>/.vfs/`.
- Project identity is `config.toml::project_id` (UUID), not CWD slug.
- File perms hardened to 0700 / 0600 by default; `strict_perms=True` re-checked each session.
- CAS-create uses `O_CREAT|O_EXCL` rather than mtime-based existence check.
- No `$VFS_PROJECT_ROOT` env var (was a cross-project bypass).
