# vfs-memory

[![PyPI](https://img.shields.io/pypi/v/agent-vfs)](https://pypi.org/project/agent-vfs/)
[![Python](https://img.shields.io/pypi/pyversions/agent-vfs)](https://pypi.org/project/agent-vfs/)
[![CI](https://github.com/dirkknibbe/vfs-memory/actions/workflows/ci.yml/badge.svg)](https://github.com/dirkknibbe/vfs-memory/actions/workflows/ci.yml)

Portable project memory across LLM agents. A per-project `.vfs/` directory — like `.git` — that any agent can read and write via a CLI. Stdlib-only Python, file-shaped, git-adjacent.

Switch from Claude Code to Codex mid-feature and the next agent picks up where the last one left off, because both shell out to the same `vfs read|write|list|search`. No agent lock-in, no SaaS, no proprietary memory format.

**Use this if:** you rotate across multiple agents on the same project and want shared, persistent, attributable memory.
**Don't use this if:** you only use one agent and its built-in memory works for you.

## Install

```bash
pipx install agent-vfs   # CLI
pip install agent-vfs    # library
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

Add `.vfs/` to your `.gitignore` (the CLI suggests this on `vfs init`).

## What's stored where

```
<project-root>/
└── .vfs/
    ├── config.toml          # schema_version, project UUID
    ├── persistent/          # frontmatter-tagged, survives sessions
    ├── temp/                # flat, ephemeral, 7-day GC sweep
    └── diagnostic.log       # append-only JSONL of writes/deletes (rotates at 100 MB)
```

## Trust model

Agents can only write with `source=agent`. Human-tagged writes require a TTY (`vfs remember --as-user`). Cross-project access requires `--root /path --as-user`. See [SECURITY.md](SECURITY.md) for the full threat model and controls.

## CLI

<details>
<summary>Agent surface</summary>

```
vfs init                              # create .vfs/ in CWD
vfs read <key> [--offset N] [--limit N]
vfs write <key> [--source agent|tool:NAME|web:DOMAIN]
                [--if-match ETAG] [--allow-secret]   # body on stdin
vfs list [--prefix PFX] [--cursor C] [--max N]
vfs delete <key> [--if-match ETAG]
vfs search <query> [--prefix PFX] [--max N]
vfs temp {read|write|list|delete|search} ...        # ephemeral zone
vfs gc                                              # sweep temp/ older than 7 days
vfs whoami                                          # writer_id, project_id, root
vfs version
```

</details>

<details>
<summary>Human surface (TTY-gated)</summary>

```
vfs remember <key> [--as-user]                     # write with source=user
vfs review                                          # show diagnostic.log tail
vfs --root /abs/other read|list|search             # cross-project (requires --as-user)
vfs migrate --from <legacy-dir> [--dry-run] [--delete-source]
```

</details>

## Environment

| Var | Purpose | Default |
|---|---|---|
| `VFS_WRITER` | writer ID stamped into frontmatter (validated `[\w.-]+`) | `agent` |
| `VFS_MAX_FILES` | bound on list/search traversal | `10000` |
| `VFS_MAX_BYTES_PER_FILE` | per-file size cap on traversal | `10000000` |
| `VFS_MAX_WRITES_PER_MINUTE` | soft rate limit | `300` |
| `VFS_MAX_DIAGNOSTIC_LOG_BYTES` | rotate `diagnostic.log` at this size | `100000000` |

No env override exists for `source=user`, `--as-user`, `--root`, or `vfs migrate` — security gates are not tunable.

## Why not X?

- **Not [`diskcache`](https://pypi.org/project/diskcache/)** — that's a KV cache, no frontmatter, no agent provenance.
- **Not [`mem0`](https://github.com/mem0ai/mem0) / [Letta](https://github.com/letta-ai/letta)** — those are SaaS-flavored vector stores. `agent-vfs` is plain files on disk, no embeddings, no server.
- **Not your agent's built-in memory** — those live inside one tool. `agent-vfs` is the same file tree for all of them.
- **Not raw files** — raw files have no symlink hardening, no provenance fields, no rate limit, no TTY gate, no cross-project isolation.

## How this project is maintained

PRs get an automated review from Claude via [`anthropics/claude-code-action`](https://github.com/anthropics/claude-code-action). The repo also runs a 4-Python × 2-OS test matrix and an AST-based static check on every push. See [SECURITY.md](SECURITY.md) for the supply-chain controls.

## License

MIT.
