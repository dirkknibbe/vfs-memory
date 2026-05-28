# Security

## Reporting

Email dirk.knibbe@yahoo.com. We respond within 5 business days.

## Threat model

In scope:
- Prompt-injected agent attempts to exfiltrate, escalate trust, or escape the project's `.vfs/`.
- Malicious local non-root process on the same machine reads or tampers with VFS data.
- Supply chain: compromised build/publish.

Out of scope:
- Local root attacker.
- Audit-log integrity against the audited process. (The log is `diagnostic.log`, not `audit.log` — explicit non-claim.)
- Secret content exfiltration via the agent's own LLM context. We refuse obvious secret shapes on write, but do not perform read-side redaction.
- Secret-shape evasion (base64, whitespace insertion, Unicode confusables). The write-side refusal catches direct paste-ins only.
- Library API hardening against prompt injection — the CLI is the prompt-injection-resistant surface; the library is for trusted callers.
- Cryptographic attribution between writers.

## Controls (summary)

- All file access via `O_DIRECTORY` root FD + per-component `O_NOFOLLOW`. Defeats symlink escape and TOCTOU.
- `source=user` is TTY-gated. No env override exists.
- Cross-project access (`--root`) requires TTY (`--as-user`).
- `vfs migrate` is TTY-gated; source dir walked with `followlinks=False` and per-file symlink refusal.
- `O_CREAT|O_EXCL` for CAS-create.
- 10 MB enforced size cap on writes.
- 0700 / 0600 perms with `os.umask` and explicit chmod. Re-checked each session (`strict_perms=True` default).
- `VFS_WRITER` validated against `[\w.-]+` at construction; closes ANSI-escape injection into `vfs review` output.
- `vfs review` strips control chars from non-JSON output.
- Diagnostic log rotates at `VFS_MAX_DIAGNOSTIC_LOG_BYTES`; `O_APPEND` + `fcntl.flock` for same-UID safety.
- Rate-limiter state file `fstat`-verified (regular file, owner, mode, st_nlink); raises (no silent reset) on JSON parse failure.
- Stdlib-only forever. CI asserts zero `Requires-Dist` entries (excluding extras) in built wheels.
- AST-based static check rejects imports of `urllib`, `http`, `socket`, `ssl`, `requests`, `httpx`, `aiohttp`, `subprocess`, `ftplib`, `smtplib`, `telnetlib`.
- Substring scan rejects shell-call / dynamic-code-evaluation builtins.
- PyPI trusted publishing (OIDC), no long-lived tokens.

## Out of the box

After `vfs init`, your `.vfs/` is 0700 with files 0600. The CLI refuses to operate on a `.vfs/` with looser perms — fix them or `vfs init` fresh.

If `vfs review` shows a write you didn't expect from `writer: agent`, that's the diagnostic surface working as designed.

## GitHub-side hardening (for maintainers)

- Branch protection on `main` requiring PR review + status checks.
- Release-workflow approval via a GitHub Environment with a named reviewer.
- All third-party Actions pinned to commit SHAs, not floating tags.
- PyPI account has 2FA.
