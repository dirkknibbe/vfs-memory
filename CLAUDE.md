# vfs-memory — Claude Development Context

## What this project is

Hardened, agent-agnostic file system for memory and scratch. Per-project `.vfs/` directory (like `.git`). Consumed via a CLI (`vfs`) usable from any agent that can shell out — Claude Code, Codex, Copilot, Cursor.

GitHub repo: `vfs-memory`. PyPI package: `agent-vfs`. Python import: `agent_vfs`. Binary: `vfs`.

## Stack

- Python 3.9+, stdlib-only at runtime
- Tests: `pytest` (dev dep only)
- Type check: not currently enforced (lib is small; ground truth is the test suite)
- Build: `python -m build` (dev dep)
- Static checks: `python scripts/static_checks.py` (no banned imports, no shell/dynamic-code, no runtime deps)

## Layout

```
agent_vfs/               # the Python package (import name)
  __init__.py
  core.py                # VFS, init_project
  types.py               # error hierarchy + dataclasses
  paths.py               # key grammar, root resolution
  frontmatter.py         # provenance frontmatter (write strict, read sanitizing)
  zones.py               # TempZone, PersistentZone
  config.py              # .vfs/config.toml hand-rolled reader
  diagnostic.py          # append-only JSONL log
  secrets.py             # secret-shape refusal
  ratelimit.py           # write-rate limiter (CLI surface)
  gc.py                  # temp-zone 7-day sweep
  migrate.py             # legacy auto-memory dir migration
  cli.py                 # argparse entry point
  backends/
    localfs.py           # the only backend in v1
tests/                   # pytest suite
scripts/static_checks.py
.github/workflows/       # PR review workflows
```

## Spec + plan

- **Design spec**: `docs/superpowers/specs/2026-05-27-generic-vfs-design.md`
- **Implementation plan**: `docs/superpowers/plans/2026-05-27-generic-vfs-implementation.md`
- Both have been through a 4-agent review pass; the second commit on each applies the review findings.

## Rules specific to this project

- **Stdlib-only at runtime, forever.** `pyproject.toml` MUST have zero entries in `[project.dependencies]`. `scripts/static_checks.py` enforces this.
- **No banned imports**: `urllib`, `http`, `socket`, `ssl`, `requests`, `httpx`, `aiohttp`, `subprocess`, `ftplib`, `smtplib`, `telnetlib`. The AST-based static check catches direct and aliased imports.
- **No shell-call or dynamic-code builtins** in `vfs/`. The static check enforces this by substring scan.
- **`__del__` is banned for FD-holding classes.** Use explicit `close()` with try/finally in callers.
- **All file ops in `LocalFSBackend` traverse via `dir_fd` + `O_NOFOLLOW`.** No absolute-path `os.open` paths inside the backend after init. No `tempfile.mkstemp` (it can't accept `dir_fd`). CAS-create uses `os.link` (atomic) to refuse if dest exists.
- **Security gates have no env override.** `--as-user`, `--root`, and `vfs migrate` are TTY-gated only. Do not add an env-var bypass even for CI.

## Commits

- No `Co-Authored-By` trailer. No `Generated with Claude Code` line. Commits stand as the author's work.
