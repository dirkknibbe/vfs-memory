# vfs-memory

Hardened, agent-agnostic file system for memory and scratch. Per-project `.vfs/` directory, like `.git`. Usable from any agent that can shell out — Claude Code, Codex, Copilot, Cursor.

## Install

```bash
pipx install agent-vfs   # for the CLI
pip install agent-vfs    # for library use
```

## Quickstart

```bash
cd ~/projects/my-thing
vfs init                                # creates .vfs/ in this directory
echo "a useful fact" | vfs write notes/foo.md
vfs read notes/foo.md
vfs list --prefix notes/
vfs search foo
```

## Trust model

- `vfs write` is the agent surface; `source` defaults to `agent` and cannot be set to `user`.
- `vfs remember --as-user` is the human surface — TTY-gated. Use it when YOU are recording a fact.
- `vfs --root /abs/other --as-user` is the only way to access another project's `.vfs/`.
- `vfs migrate` is TTY-gated and walks legacy `~/.claude/projects/<slug>/memory/` content into `.vfs/persistent/`.

See `SECURITY.md` and the design spec for the full security model.

## What's stored where

```
<project-root>/
└── .vfs/
    ├── config.toml          # schema_version, project UUID
    ├── persistent/          # frontmatter-tagged, survives sessions
    ├── temp/                # flat, ephemeral, 7-day GC sweep
    └── diagnostic.log       # append-only JSONL of writes/deletes (rotates at 100 MB)
```

Add `.vfs/` to your `.gitignore`. The CLI suggests this on `vfs init`.

## CLI reference

### Agent surface

```
vfs init                              # create .vfs/ in CWD
vfs read <key> [--offset N] [--limit N]
vfs write <key> [--source agent|tool:NAME|web:DOMAIN]
                [--if-match ETAG] [--allow-secret]   # body on stdin
vfs list [--prefix PFX] [--cursor C] [--max N]
vfs delete <key> [--if-match ETAG]
vfs search <query> [--prefix PFX] [--max N]
vfs temp {read|write|list|delete|search} ...        # ephemeral zone
vfs gc                                              # sweep temp/ entries older than 7 days
vfs whoami                                          # writer_id, project_id, root path
vfs version
```

### Human surface (TTY-gated)

```
vfs remember <key> [--as-user]                     # write with source=user
vfs review                                          # show diagnostic.log tail
vfs --root /abs/other read|list|search             # cross-project (requires --as-user)
vfs migrate --from <legacy-dir> [--dry-run] [--delete-source]
```

## Environment

| Var | Purpose | Default |
|---|---|---|
| `VFS_WRITER` | writer ID stamped into frontmatter | `agent` |
| `VFS_MAX_FILES` | bound on list/search traversal | `10000` |
| `VFS_MAX_BYTES_PER_FILE` | per-file size cap on traversal | `10000000` |
| `VFS_MAX_WRITES_PER_MINUTE` | soft rate limit | `300` |
| `VFS_MAX_DIAGNOSTIC_LOG_BYTES` | rotate `diagnostic.log` → `.1` at this size | `100000000` |

No env override exists for `source=user`, `--as-user`, `--root`, or `vfs migrate` — security gates are not tunable.

## License

MIT.
