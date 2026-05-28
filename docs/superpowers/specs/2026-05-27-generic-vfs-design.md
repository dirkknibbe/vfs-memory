# Generic VFS Design — Agent-Agnostic, Hardened, CLI-First

**Date:** 2026-05-27
**Author:** Dirk Knibbe
**Status:** Draft — pending implementation plan
**Predecessor:** [`2026-04-19-vfs-v0-design.md`](./2026-04-19-vfs-v0-design.md) (v0/v0.5, shipped)

## Problem

The current VFS (`/Users/dirkknibbe/claude-workflow/vfs/`) is a Python library bound to Claude Code conventions: it stores under `~/.claude/projects/<cwd-slug>/memory/`, derives project identity from CWD, and the `source` provenance field is caller-asserted. That's fine when the only consumer is Claude Code on a single user's machine. Three things break for any wider use:

1. **It is not consumable by non-Python agents.** Codex, Copilot CLI, Cursor, Continue, and most other agents either shell out to CLIs or speak MCP. A Python `import` is not a portable interface.
2. **The trust gradient is forgeable.** Any caller can write `source="user"` to upgrade the trust of arbitrary content. A prompt-injected agent will absolutely do this; the field is therefore useless as a security primitive in adversarial settings.
3. **Project identity is spoofable and Claude-specific.** CWD-derived slugs + a `~/.claude/projects` parent dir mean any agent that can `chdir` can name another project, and the layout cannot be lifted out of Claude Code without restructuring.

Beyond agent-agnosticism, an adversarial review of `localfs.py` and `frontmatter.py` surfaces several latent security issues that v0/v0.5 explicitly punted: symlink-following traversal, no size cap, permissive frontmatter framing, glob-based listing that recurses into symlinks, etc. These need to be closed before the surface is exposed more broadly.

## Goals

- **Agent-agnostic interface.** Any agent that can shell out can use the VFS. Skills are an optional layer for clients that support them (Claude Code, future Codex).
- **Per-project sandbox.** Each project owns its own `.vfs/` directory (like `.git`). Cross-project access is an explicit, human-gated operation.
- **Hardened against prompt injection, malicious local non-root processes, and supply-chain attacks.** Co-resident same-UID agents are in scope (this is the normal case for two Claude Code sessions on one project).
- **Stdlib-only, forever.** Zero runtime dependencies. Reproducible build. PyPI trusted publishing.
- **Honest about what it can defend.** Things we can't actually defend (a local-root attacker, secret-content exfiltration via the agent's own context) are documented limits, not features hidden behind theater.

## Non-goals

- **No MCP server in v1.** CLI is the universal interface; MCP can be added in v2 once the CLI shape is stable.
- **No Windows in v1.** Path semantics, perm model, and `fcntl` would need separate work that doesn't pay off until there's demand.
- **No backwards compatibility with the v0/v0.5 Python API.** The new package is a new shape under a new name (`agent-vfs`); migration is one-shot via `vfs migrate`.
- **No cryptographic attribution.** Per-writer keypairs and signed entries are overkill for a local memory layer.
- **No secret redaction.** Refusing to write obvious secrets is in scope; partial-text redaction on read is out (high false-positive rate, false-safety signal).
- **No global namespace, no auto-init.** `vfs init` is an explicit step. Walking up from CWD looking for `.vfs/` stops at `$HOME`.

## Architecture

Three independently versioned layers:

```
┌─────────────────────────────────────────────────────────────┐
│                  SKILLS (vfs:recall, vfs:remember)          │
│  optional, Claude-Code-shaped, shells out to the CLI        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       vfs CLI                               │
│  agent surface:  read|write|list|delete|search|init|whoami │
│  human surface:  remember --as-user, review, --root         │
│  (TTY-gated; no env overrides for security gates)           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│             vfs-core (Python library, stdlib-only)          │
│  VFS / PersistentZone / TempZone / LocalFSBackend           │
│  no project= kwarg, writer_id from $VFS_WRITER              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                  <project-root>/.vfs/
                  ├── config.toml
                  ├── persistent/
                  ├── temp/
                  └── diagnostic.log
```

**Package naming:** `agent-vfs` on PyPI (because `vfs` is too generic to claim and a different unrelated package already holds it), binary `vfs`, Python import `vfs`. Distributed via pipx for end-users; pip for library consumers. The PyPI-name-vs-import-name split is a standard pattern (e.g., `python-magic` ships `magic`); collisions are a non-issue in practice.

**Repository:** new repo `agent-vfs` on GitHub. MIT license. The existing in-tree `/Users/dirkknibbe/claude-workflow/vfs/` is deprecated to a 0.6 release with a `DeprecationWarning` and deleted one quarter later.

## On-disk layout

```
<project-root>/
└── .vfs/                             # 0700, owned by user
    ├── config.toml                   # 0600 — schema_version, project_id (uuid), created_at
    ├── persistent/                   # 0700 — durable, provenance-tagged
    │   ├── notes/
    │   ├── decisions/
    │   ├── gotchas/
    │   ├── conventions.md
    │   └── …                         # caller-defined namespacing
    ├── temp/                         # 0700 — flat, ephemeral, no frontmatter
    │   └── *.md                      # 7-day GC sweep
    └── diagnostic.log                # 0600 — append-only JSONL, locked appends
```

- **Project identity is `config.toml::project_id`** — a UUID written at `vfs init`. Not CWD-derived. This closes the chdir-spoofability finding.
- **No nested `.vfs/`.** `vfs init` refuses if a `.vfs/` exists upward in the tree; it prints the discovered root.
- **No automatic `.gitignore` edits.** `vfs init` *suggests* adding `.vfs/` to `.gitignore` but never writes outside `.vfs/`.

## Root resolution

`vfs <cmd>` resolves `.vfs/` by walking upward from `os.getcwd()` looking for `.vfs/`. Boundary stops: filesystem root, `$HOME`, or a hit. None found → error with `vfs init` remediation. Never auto-init.

**No `$VFS_PROJECT_ROOT` env var.** An earlier draft included one as a "skip the walk" shortcut. Removed: it doubles as a cross-project access bypass that a prompt-injected agent could set freely. The only override is `--root /abs/path` on the human surface, TTY-gated. If you need a non-CWD root from a library caller, pass `root=` to the `VFS(root=...)` constructor — explicit and visible at the call site.

The discovered root is opened with `os.open(root, O_DIRECTORY)` and the FD is held for the process. Every read/write traverses via `os.open(rel, O_NOFOLLOW, dir_fd=root_fd)` per component — defeats TOCTOU on symlinks.

## CLI command grammar

### Agent surface (callable by any agent without TTY)

```
vfs init                              # create .vfs/ in CWD; error if one already exists upward
vfs read <key> [--offset N] [--limit N]
vfs write <key> [--source agent|tool:NAME|web:DOMAIN]
                [--if-match ETAG] [--allow-secret] -    # stdin
vfs list [--prefix PFX] [--cursor C] [--max N]
vfs delete <key> [--if-match ETAG]
vfs search <query> [--prefix PFX] [--max N]
vfs temp {read|write|list|delete} ...                   # nested subcommand group
vfs gc                                                  # sweep temp/ entries older than 7 days
vfs whoami                                              # writer_id, project_id, root path
vfs version
```

`vfs temp` is a nested subparser, not a dotted name (`vfs temp.read` would break shell completion in bash/zsh).

### Human surface (TTY-gated)

```
vfs remember <key> [--as-user] -                       # write with source=user
vfs review                                              # pretty-print diagnostic.log
vfs --root /abs/other read|list|search                 # cross-project
vfs migrate --from <legacy-dir> [--dry-run] [--delete-source]
```

Hard rules on the human surface:

- `--as-user` refuses unless both `sys.stdin.isatty()` AND `sys.stdout.isatty()` are true.
- `--root` refuses unless `--as-user` is also set; the value flows to `VFS(root=...)` directly — **never via env-var mutation** (would leak to subprocess children).
- `vfs migrate` is TTY-gated. Even without `--delete-source`, migration walks an attacker-readable directory and stamps content into `.vfs/persistent/`; no agent use case exists. Refuses unless stdin and stdout are both TTYs.
- **No env override** for any of the above gates.

### Output & exit codes

JSON-Lines on stdout for machine consumers (`list`, `search`, `read --json`); plain text otherwise. `--json` flag forces JSON. Exit codes:

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Generic error |
| 2 | Not found |
| 3 | Conflict (CAS mismatch) |
| 4 | Validation error (bad key, frontmatter, secret refusal, size cap) |
| 5 | Permission / TTY gate refusal |

## Environment variables

| Var | Purpose | Default |
|---|---|---|
| `VFS_WRITER` | Writer ID stamped into frontmatter (validated against `[\w.-]+`; rejected otherwise) | `agent` |
| `VFS_MAX_FILES` | Bound on list/search traversal | `10000` |
| `VFS_MAX_BYTES_PER_FILE` | Per-file size cap on traversal | `10000000` |
| `VFS_MAX_WRITES_PER_MINUTE` | Soft rate limit (CLI only) | `300` |
| `VFS_MAX_DIAGNOSTIC_LOG_BYTES` | Rotate diagnostic.log → `.1` at this size | `100000000` |

**No env override for source=user, `--as-user`, `--root`, or `vfs migrate`. No `$VFS_PROJECT_ROOT`** — root is always upward-walked from CWD, or passed explicitly via `--root` (TTY-gated) or `VFS(root=...)`.

## Library API (Python)

The library exposes the same shape as v0.5 but with three breaking changes:

```python
from vfs import VFS

v = VFS()                          # resolves upward from CWD; no constructor args for writer_id
body, fm = v.persistent.read("notes/foo.md")              # full file → (body, fm)
chunk = v.persistent.read_raw("notes/foo.md", offset=0, limit=4096)  # raw partial → str
etag = v.persistent.write("notes/foo.md", body, source="agent")
hits = v.persistent.search(prefix="notes/", query="foo")

# Cross-project: explicit second instance, library only
other = VFS(root="/abs/other/.vfs")
body, fm = other.persistent.read("decisions/x.md")
```

**Breaking changes from v0.5:**

1. `VFS(writer_id=...)` constructor arg is dropped. Writer ID is read from `$VFS_WRITER` at construction (and validated — see Controls 11).
2. `PersistentZone.read/list/search` no longer accept a `project=` kwarg. Cross-project access is via a fresh `VFS(root=...)` instance — explicit, no implicit kwarg.
3. `PersistentZone.read(offset=..., limit=...)` is **removed**. Partial reads ignore frontmatter framing, so returning `(body, fm)` after a partial read was a silent destructuring trap. Callers who need raw partial reads use `read_raw(key, offset, limit) -> str`, which returns the raw file content (frontmatter included) and is honest about it. `TempZone.read` retains `offset`/`limit` since temp has no frontmatter.

### Library API trust model (non-goal)

**The Python library API is a trusted surface, not a prompt-injection-hardened one.** A library caller can construct `VFS(source_user_allowed=True)`, pass `allow_secret=True`, or call write paths that the CLI gates. This is intentional: library users have legitimate test-harness, migration-tool, and embedded-system reasons. The CLI is the prompt-injection-resistant surface; everything an agent does should go through `vfs <cmd>`, not `import vfs`. Skills shell out to the CLI on purpose.

## Security model

Defends against:

1. **Prompt-injected agent.** Adversarial content (tool output, web fetches, file contents) coerces a well-meaning agent into exfiltrating, deleting, or writing malicious data.
2. **Malicious local non-root process.** Another process under the same or a different UID tries to read or tamper with VFS data.
3. **Supply-chain.** Hardening the package's own surface against compromise of build/publish.

Co-resident same-UID agents (e.g., two Claude Code sessions on the same project) are treated as the **normal case**, not a threat — locking and CAS must behave correctly under concurrent same-UID writers.

Explicit non-goals (documented limits, not silent assumptions):

- Local root attacker — out of scope.
- Audit-log integrity against the audited process — out of scope (which is why we call it `diagnostic.log`).
- Secret content exfiltration via the agent's own context — out of scope (we refuse obvious shapes on write, no read-side redaction).
- **Secret-shape evasion** — out of scope. The refusal regex catches direct paste-ins (`AKIA…`, `ghp_…`, JWTs). Any non-trivial encoding (base64, whitespace insertion, Unicode confusables, partial-string splits) bypasses it. Treat the refusal as friction, not containment.
- **Library API hardening against prompt injection** — out of scope. The CLI is the prompt-injection-resistant surface; the library is for trusted callers (skills shell out to the CLI, agents don't `import vfs`).

### Controls — prompt-injected agent

1. **Source=user gating.** Agent CLI cannot set `source=user`. Only `vfs remember --as-user` does, and it refuses unless `sys.stdin.isatty()` and `sys.stdout.isatty()` are both true. No env override.

2. **No cross-project access from agent CLI.** The `project=` kwarg is removed from the library default API. `--root /abs/path` is on the human surface only and requires `--as-user`.

3. **Symlink containment via `dir_fd` traversal.** Project root opened with `O_DIRECTORY` at init; all subsequent ops use `os.open(rel, O_NOFOLLOW, dir_fd=root_fd)`. On write, `os.lstat(dest)` first; refuse if symlink.

4. **No symlink-following traversal.** Replace `glob.glob(..., recursive=True)` at [localfs.py:121](../../vfs/backends/localfs.py:121) and [:170](../../vfs/backends/localfs.py:170) with `os.walk(self.root, followlinks=False)`. Per-entry realpath assertion: `realpath(p).startswith(self.root + os.sep)` (exact-slash defeats `<root>-evil/` adjacency).

5. **Bounded list/search.** Default ceilings via env vars (above). Exceedance → `VFSError` (exit 4). No silent truncation.

6. **Write size cap.** `max_object_size_bytes=10_000_000` enforced at `LocalFSBackend.write()` entry. (Current `BackendCapabilities.max_object_size_bytes=100MB` was aspirational and unenforced — dropped to 10MB and enforced.)

7. **Frontmatter framing (write).** All field values rejected if they contain `[\x00-\x1f]` (includes `\n` and `\r`). Preserved non-VFS-owned fields are routed through the **same** validator (`_check_field_key` + `_check_field_value`) as VFS-owned fields before being re-emitted on merge-on-write. Validation failure drops the bad field and logs to `diagnostic.log`.

8. **Frontmatter framing (read).** `parse_frontmatter` validates field keys against `[\w.-]+` and values against the same control-char filter. Bad fields silently dropped from the returned dict. Defeats injection via pre-planted file content.

9. **Secret-shape refusal on write.** Writes rejected if body matches: AWS keys (`AKIA[0-9A-Z]{16}`), GitHub PATs (`gh[ps]_[A-Za-z0-9]{36,}`), JWTs (`eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`). Bypass: `vfs write --allow-secret`, TTY-gated. See non-goal on evasion above.

10. **Diagnostic log.** `.vfs/diagnostic.log` is append-only JSONL with `{ts, op, key, writer, source, etag, caller_pid}`. `O_APPEND` plus `fcntl.flock(LOCK_EX)` for concurrent same-UID safety. **Named `diagnostic` not `audit` because it is co-writable by the audited process — explicit non-claim of forensic integrity.** Rotates to `.1` at `VFS_MAX_DIAGNOSTIC_LOG_BYTES` (default 100 MB) to bound disk usage; rotation is not integrity-preserving (consistent with the non-claim).

11. **Key grammar + writer ID — tightened.** Key grammar: allowed `[A-Za-z0-9._/-]+`; reject backslashes, control chars, leading `/`, trailing `/`, trailing dot or space, any `.`-only component, any `..`. Post-construction `os.path.normpath` re-validation against the root. **`$VFS_WRITER` is validated at construction** against `[\w.-]+` and refused if it contains control chars — closes ANSI-escape-injection into `vfs review` output via attacker-set writer IDs.

12. **Rate limit (CLI only).** `VFS_MAX_WRITES_PER_MINUTE=300` enforced in CLI. State file `.vfs/.ratelimit.state` opened with `O_NOFOLLOW`, then `fstat`-checked to be a regular file owned by current UID, mode 0600, `st_nlink==1`. JSON parse failure raises (no silent reset, which would defeat the limiter).

13. **`vfs review` output sanitization.** Non-JSON output of diagnostic-log fields strips `[\x00-\x1f\x7f]` before printing. JSON mode is unaffected (`json.dumps` escapes them).

### Controls — local non-root process

14. **Tight perms, re-checked each session.** `.vfs/` dir 0700, files 0600. `os.umask(0o077)` before any create. `VFS()` construction defaults to `strict_perms=True` — every session refuses to operate on a `.vfs/` whose dir mode has `0o077` bits set, not just at init. Closes the post-init chmod-by-peer attack. Documented escape hatch: `VFS(strict_perms=False)` for library callers who have a reason; the CLI never sets it.

15. **Same-UID peer locking.** `diagnostic.log` appends use `fcntl.flock(LOCK_EX)`. CAS handles concurrent data writes.

16. **No /tmp races.** Atomic writes use `os.open(O_CREAT|O_EXCL|O_NOFOLLOW, dir_fd=parent_fd)` for the temp file, then `os.rename(src_dir_fd, dst_dir_fd)` for the atomic move. Both stay inside the symlink-contained traversal — no `tempfile.mkstemp` path that bypasses `dir_fd`.

17. **CAS-create via `O_EXCL`.** `if_match=""` uses `O_CREAT|O_EXCL` rather than mtime/size existence check. Update path (`if_match=<etag>`) retains mtime+size comparison.

18. **No subprocess, eval, or exec in core.** CI lint enforces; import-time-only check.

### Controls — supply chain

19. **Stdlib-only forever.** CI step asserts no `Requires-Dist` in built wheel METADATA. **Includes the TOML reader**: `tomllib` is Python 3.11+, so the project either bumps the floor to 3.11 OR ships a tiny hand-rolled reader for the 3-field `config.toml` schema. We choose the latter — a 30-line ad-hoc parser keeps the 3.9/3.10 matrix and the stdlib-only claim consistent.

20. **Reproducible build.** Pinned `setuptools` in `[build-system].requires`. Python `>=3.9`. No optional extras with deps.

21. **No network calls — verified by AST.** CI runs an AST walk of `Import`/`ImportFrom` nodes in the `vfs/` package against an explicit blocklist (`urllib`, `http`, `socket`, `ssl`, `requests`, `httpx`, `aiohttp`, `ftplib`, `smtplib`, `telnetlib`). Replaces the earlier keyword-grep, which was bypassable via `__import__("\x73ocket")` or string concatenation.

22. **PyPI trusted publishing + GitHub-side hardening.** OIDC from GitHub Actions. PyPI 2FA. No long-lived tokens. The GitHub repo enforces: branch protection on `main` requiring PR review + status checks, the release-workflow approval requires a named reviewer via a GitHub Environment, and all third-party Actions are pinned to commit SHAs (not floating tags). (No Sigstore — pip doesn't verify it without separate tooling.)

## Migration from current VFS

The new generic VFS does **not** absorb Claude Code's auto-memory dir. Two independent stores:

- Claude Code's auto-memory continues to live at `~/.claude/projects/<slug>/memory/`, untouched.
- The new VFS stores at `<project-root>/.vfs/`.

This avoids reintroducing the global namespace + CWD-slug spoofability we just removed.

### `vfs migrate` command

```
vfs migrate --from <legacy-dir> [--delete-source] [--dry-run]
```

- **TTY-gated.** `vfs migrate` refuses unless both stdin and stdout are TTYs. No agent use case — migration walks an attacker-readable directory and stamps content into `.vfs/persistent/`, so it lives on the human surface.
- Requires `.vfs/` to exist at the destination. If not, errors with `vfs init` remediation.
- `<legacy-dir>` is typically `~/.claude/projects/-Users-foo-bar/memory`. Refuses unless it contains at least one `.md` file (sanity check against pointing at the wrong directory).
- **Symlink-contained source walk.** Source directory opened with `O_DIRECTORY|O_NOFOLLOW`. Walked via `os.walk(followlinks=False)`. Each candidate file is `lstat`-checked: symlinks refused (no following into `~/.ssh`, `/etc`, or sibling projects). Realpath of each file must remain a descendant of the resolved legacy-dir.
- Copies each file into `<discovered .vfs root>/persistent/<same-relative-key>`.
- Re-stamps frontmatter: preserves any non-VFS-owned fields (validated through the same `_check_field_*` validators), refreshes `ts`, sets `writer="vfs-migrate"`, sets `source="agent"` (never `source="user"` — the old layout's claim is unverifiable).
- Each migrated file logged to `diagnostic.log` with the legacy path.
- `--delete-source` removes the legacy file after a verified copy.
- `--dry-run` prints the plan without writing.
- Files exceeding the new 10MB cap are skipped, listed, and exit non-zero.

### After migration — shutting off the legacy writer

The "two independent stores" design has an awkward seam: after `vfs migrate`, Claude Code's auto-memory continues to write to `~/.claude/projects/<slug>/memory/`, but the user is now reading from `<project>/.vfs/persistent/`. New writes from Claude's auto-memory won't be visible.

Three options, in order of effort:

1. **Stop auto-memory writes.** Edit `~/.claude/CLAUDE.md` to remove the auto-memory section. Existing Claude Code sessions stop writing there. (Recommended after a successful migration.)
2. **Periodic re-migration.** Keep auto-memory active; re-run `vfs migrate --from ~/.claude/projects/<slug>/memory` periodically. Cheap because migrate is idempotent (CAS), but accumulates duplicate diagnostic-log entries.
3. **Manual sync.** Don't migrate; instead, point `vfs-recall` / `vfs-remember` skills at the legacy dir directly. Only viable for Claude-Code-only setups; defeats the agent-agnostic purpose.

The README walks through option 1 as the canonical path.

### Deprecation of the in-tree `vfs/` package

Three steps, in order:

1. **Cut v0.6 of the existing `/Users/dirkknibbe/claude-workflow/vfs/` package first** — bumps version to 0.6, adds `DeprecationWarning` on import pointing at `agent-vfs`, otherwise no behavior change. This is the first work item in the plan (Task 0.0) so the deprecation window starts before v1 ships.
2. **Release 1.0 of `agent-vfs`** under the new repo and PyPI name. The in-tree `vfs/` remains importable at 0.6 so existing scripts don't break.
3. **One quarter later**, delete the in-tree directory. Anyone still importing the old name should have migrated by then; the `DeprecationWarning` has been live the whole time.

**No backward-compat shim in the new package.** `VFS(writer_id=...)` raises `TypeError` with a clear migration message.

### Claude Code integration after migration

- `vfs-recall` / `vfs-remember` skills get updated to shell out to the new `vfs` CLI.
- Skill descriptions stay the same (same trigger prompts).
- The current `~/.claude/projects/<slug>/memory/` dir is no longer touched by the skills.
- The pre-session hook at `tools/pre-session-check.sh` (currently check 6 reads the legacy dir) calls `vfs whoami` and reports the discovered `.vfs/` root.

## Testing & verification

Each Section 2 control gets at least one adversarial test that **passes only if the attack fails**. The matrix (abbreviated):

| Control | Test |
|---|---|
| Source=user gating | `vfs write --source user` exits 4; `vfs remember --as-user < /dev/null` exits 5. |
| Default source unaffected by `$VFS_WRITER` | With `VFS_WRITER=user`, `vfs write foo.md` produces frontmatter with `source: agent`. |
| No cross-project from agent CLI | `vfs --root /tmp/other read foo` (no `--as-user`) exits 5. |
| No `--root` env-leak | After invoking with `--root --as-user`, `os.environ` is unchanged in the parent. |
| Symlink at dest | Pre-plant symlink at dest path; `vfs write` exits non-zero; sentinel unchanged. |
| Symlink in path component | Pre-plant symlink in intermediate dir; `vfs write` refuses. |
| TOCTOU swap | Threaded test (N=10_000, barrier-synced, mid-write delay hook) swaps a component mid-op; assert at least one violation observed (proves race fired); sentinel outside root unchanged. |
| Symlink loop in search | `ln -s . loop`; `vfs search` completes bounded. |
| Sibling adjacency | `<root>-evil/` not surfaced by list/search. |
| List bound | Plant 20k files; `vfs list` exits 4 (not silent truncation). |
| Write size cap, boundary | Exactly 10 MB → success; 10 MB + 1 byte → exit 4; zero-byte → success. |
| Frontmatter write hardening | `--source "agent\nsource: user"` rejected. |
| Frontmatter read hardening (e2e) | Pre-plant `.vfs/persistent/` file with injected `source: user` + control-char value; `vfs read` returns sanitized fm. |
| Merge-on-write field validation | Pre-plant file with control-char preserved fields; merge-on-write drops them, logs to diagnostic.log. |
| Secret refusal | `AKIA...` body → exit 4; `--allow-secret` without TTY → exit 5. |
| Diagnostic log concurrency | 50 concurrent writes → 50 valid JSONL lines, no interleave. |
| Diagnostic log rotation | `VFS_MAX_DIAGNOSTIC_LOG_BYTES=1024`; verify rotation to `.1` and a fresh `.log`. |
| `vfs review` ANSI safety | `$VFS_WRITER` rejected at construction if it contains control chars; printed entries strip `\x00-\x1f\x7f` in non-JSON output. |
| Key grammar | Table including `["", "/abs", "a/../b", "a/./b", "foo\x00", "foo\nbar", "foo\\bar", "foo.", "foo ", "..", ".", "café.md"]` and a 4096-char key → all exit 4 (or 0 if valid; café is invalid by charset). |
| Rate limit | 350 writes in 60s → 51st blocks. Pre-plant `.ratelimit.state` with garbage JSON → raises (no silent reset). |
| File perms | Post-`init`, dir 0700, files 0600; chmod `.vfs/` to 0755 between sessions → next `VFS()` refuses. |
| Same-UID peer locking | Concurrent appends → well-formed JSONL. |
| O_EXCL CAS-create | Concurrent `--if-match ""` (N=20) → exactly one succeeds (0), rest fail (3). |
| Concurrent read/write | Reader loop while writer does 100 writes → every read returns either v_old or v_new, never empty/partial. |
| Migration symlink containment | Pre-plant symlink in legacy-dir pointing at `/etc/passwd`; `vfs migrate` refuses to follow. |
| Migration corner cases | Existing dest file, non-UTF-8 legacy content, broken legacy frontmatter — all handled per spec. |
| Migration TTY gate | `vfs migrate` without TTY → exit 5. |
| CLI exit-code matrix | At least one e2e test reaching each of 0, 1, 2, 3, 4, 5. |
| No banned imports | AST walk over `vfs/` rejects `Import`/`ImportFrom` of `subprocess`, `urllib`, `http`, `socket`, `ssl`, `requests`, `httpx`, `aiohttp`, `ftplib`, `smtplib`, `telnetlib`. Substring scan for code-evaluation builtins returns zero non-test hits. |
| Stdlib-only | Built wheel METADATA has zero `Requires-Dist` lines. |

### CI matrix

- **OS:** macOS-latest, ubuntu-latest. Windows out of v1.
- **Python:** 3.9, 3.10, 3.11, 3.12.
- **Coverage gate:** 90% line.
- **Static checks** (perms, no-deps, no-network, no-subprocess) run on every PR.

### Release gates

A release tag triggers:

1. Full CI matrix on the tagged commit.
2. `pip wheel . && twine check`.
3. Stdlib-only assertion against the built wheel.
4. **Manual maintainer diff review** between this tag and the previous tag. No auto-publish.
5. PyPI trusted publishing (OIDC).
6. GitHub Release with auto-generated changelog.

(1)-(3) failing blocks the release. No `--force-publish` flag.

## Open questions

None at design time. Implementation surfaces will be sequenced in the plan doc.

## Behavior changes from v0.5 (cheat sheet)

| Aspect | v0.5 | v1 (generic) |
|---|---|---|
| Storage location | `~/.claude/projects/<slug>/memory/` | `<project-root>/.vfs/` |
| Project identity | CWD slug | UUID in `config.toml` |
| Package name on PyPI | unpublished | `agent-vfs` |
| Python import | `vfs` | `vfs` (same) |
| Binary | none | `vfs` |
| Cross-project read | `read(project=...)` kwarg | `VFS(root=...)` second instance only |
| Cross-project CLI | n/a | `vfs --root --as-user` (TTY-gated, root passed via constructor, not env) |
| Env-pinned root | n/a | **No `$VFS_PROJECT_ROOT`.** Walk-from-CWD or `VFS(root=...)` only. |
| Writer ID | `VFS(writer_id=...)` arg | `$VFS_WRITER` env, validated `[\w.-]+` at construction |
| `source="user"` | unrestricted | TTY-gated subcommand only |
| Library `PersistentZone.read` | accepts `offset`/`limit` | full-file `(body, fm)` only; partial via `read_raw()` |
| Symlinks | followed | refused via O_NOFOLLOW + lstat + dir_fd traversal |
| Glob recursion | `glob(**, recursive=True)` | `os.walk(followlinks=False)` |
| Write size cap | unenforced 100MB | enforced 10MB |
| Frontmatter values | newline-only check on write | control-char check on write + read; merge preserved fields validated |
| CAS-create | mtime/size race | `O_CREAT\|O_EXCL` |
| Diagnostic log | none | `.vfs/diagnostic.log` (locked appends, 100MB rotation) |
| Rate limit | none | 300 writes/min, `.ratelimit.state` validated at fstat |
| File perms | default umask | 0700 dir, 0600 files; re-checked each session (strict_perms default-on) |
| Temp zone GC | claimed but not implemented | `vfs gc` subcommand + opportunistic sweep at `VFS()` init (rate-limited via stamp file) |
| Migration | n/a | `vfs migrate` TTY-gated, source dir symlink-contained |
| Static no-network check | n/a | AST-based, not keyword grep |
| Audit naming | n/a | explicitly `diagnostic.log`, not `audit.log` |
| TOML parsing | n/a | hand-rolled (no `tomli` dep) — keeps stdlib-only on Py 3.9/3.10 |
| Windows support | n/a | out of v1 |
