# Resume prompt — paste into a fresh Claude Code session

Copy the block below into a new Claude Code session opened in `/Users/dirkknibbe/vfs-memory/`. Do not paste anything above the `---` line — just the block.

---

I'm resuming work on `vfs-memory` (PyPI: `agent-vfs`, import: `agent_vfs`, binary: `vfs`) after clearing the previous session's context. The repo is at `/Users/dirkknibbe/vfs-memory/`, public on GitHub at https://github.com/dirkknibbe/vfs-memory, v0.6.0, 151 tests passing.

**Read `docs/plans/2026-05-27-handoff.md` first.** It's the full context dump: what's done, what's pending, the strategic decisions still open (C-1: reposition pitch, C-2: ship non-Claude agent integrations), the two manual hardening steps still pending, and the conventions I expect you to follow (no Claude co-author trailer on commits, no `tempfile.mkstemp` in localfs paths, no `os.umask` in concurrent writes, etc.).

Then check `git log --oneline | head -15` and `make verify` to confirm the tree is in the state the handoff describes.

After that, ask me what to work on. The most likely pieces of work, in priority order:

1. The two pending security hardening steps (one `gh api` retry + one manual UI toggle in Settings → Actions). Listed verbatim in the handoff under "Security posture".
2. Strategic decision on C-1 (reposition README to "portable AGENTS.md with provenance") and C-2 (ship reference integrations for Aider + Codex). I deferred both — need to tell you which to pursue.
3. Open one real PR (not a trivial diff — the Claude review workflow skips those) to validate the auto-review fires.
4. Hold off PyPI publish until C-2 is decided.

Do not start writing code without first reading the handoff and confirming the open decisions with me. If you have any questions about *intent* before starting work, ask them one at a time.
