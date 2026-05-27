# vfs-memory

Hardened, agent-agnostic file system for memory and scratch. Per-project `.vfs/` directory (like `.git`). Usable from any agent that can shell out — Claude Code, Codex, Copilot, Cursor.

Under construction. See the design spec and implementation plan in the parent `claude-workflow` repo:

- `docs/superpowers/specs/2026-05-27-generic-vfs-design.md`
- `docs/superpowers/plans/2026-05-27-generic-vfs-implementation.md`

## Install (once published)

```bash
pipx install agent-vfs   # CLI
pip install agent-vfs    # library
```

## Quickstart

```bash
cd ~/projects/my-thing
vfs init                                 # creates .vfs/ in this directory
echo "a useful fact" | vfs write notes/foo.md
vfs read notes/foo.md
vfs list --prefix notes/
vfs search foo
```

## License

MIT.
