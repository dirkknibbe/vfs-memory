# vfs-kickoff skill — design

**Status:** approved 2026-05-27, ready for implementation plan.
**Audience:** the user (personal tool). Not OSS. Don't over-generalize.
**Related:** [`agent-vfs` README](../../../README.md), [`vfs-remember` skill](~/.claude/skills/vfs-remember/SKILL.md).

## Problem

When picking up a fresh piece of work, the first 15 minutes always go to the same setup ritual: figure out what the ticket says (open Jira/Linear/Asana, copy the title and description), make a place to keep notes/plan/decisions about *this* work, and remember to scope everything to it. None of that is the work. It's friction the agent could absorb.

## Goal

A single skill that fires on phrases like `lets kick off ENG-1234`, scaffolds a per-ticket workspace under `<project>/.vfs/persistent/tickets/<workspace-name>/`, populates it with whatever ticket details we can pull from a connected tracker MCP, and reports back transparently. Plus a `lets resume <workspace>` verb for picking back up later.

## Non-goals

Explicitly out of scope, so future scope-creep has a written line to point at:

- Fetching ticket comments, attachments, linked tickets. Defer until actually wanted. (Parent ticket context **is** in scope — see "Parent ticket fetch" below. Comments etc. are not.)
- Auto-scoping subsequent `vfs:remember` writes into the workspace. (User decided no — "doesn't bite if you forget" beats invisible session state.)
- Workspace listing, switching, archiving. `vfs list --prefix tickets/` and `vfs delete` cover those by hand.
- Hierarchy (subtasks, epics). One flat workspace per ticket.
- Integration with `docs/plans/YYYY-MM-DD-*.md`. That stays the long-form multi-step plan home; `tickets/<X>/plan.md` is short-form for in-workspace planning. They coexist; the skill does not touch `docs/plans/`.
- `lets refresh <X>` verb (force re-fetch from MCP on an existing workspace). Hold until the local-only `resume` actually bites.
- Override flags (`--prefer linear` on collision). Hold until the priority default actually bites.
- A CLI surface (`vfs kickoff ENG-1234`). Skill-only for now — the friction the skill removes is *triggering*, and a slash-command-style verb in chat is the natural surface for that.

## Architecture

Single-file skill at `~/.claude/skills/vfs-kickoff/SKILL.md`. Same shape as `vfs-remember`: a Markdown file with a `description:` frontmatter field (used by Claude Code to decide when to invoke) plus step-by-step instructions in the body.

The skill orchestrates Claude to run, in this order:

1. **Parse the user phrase** to decide verb (`kickoff` vs `resume`) and extract any ticket-ID-shaped token.
2. **Resolve the workspace name** using a 3-tier fallback chain (see below).
3. **For `kickoff`:** probe connected tracker MCPs in parallel, populate `ticket.md`, create the rest of the scaffold, report.
4. **For `resume`:** read the existing workspace files, surface a tight summary so the next conversation turn picks up with context, report.

All file I/O goes through the existing `agent-vfs` library (`from agent_vfs import VFS; v.persistent.write(...)`) — the skill does not invent new storage paths or bypass the VFS's locking / source-attribution.

## Trigger detection

**Skill description** (the text the Claude Code runtime uses to decide when to invoke the skill):

> Use when the user is starting work on a fresh piece — phrases like "lets kick off ENG-1234", "let's kick off PROJ-77", "lets start ABC-456", "let's start" (with no ticket — uses repo-based fallback), or when picking back up — "lets resume ENG-1234". Do NOT use for starting a process / dev server / command / unrelated activity (e.g. "let's start the server", "let's kick off the deploy"). Strong signal: the phrase is followed by a ticket-ID-shaped token (`[A-Z][A-Z0-9]+-\d+`) or by nothing at all (no-ticket fallback path).

**Verbs recognized:** `kick off`, `start`, `begin` (kickoff intent) and `resume`, `pick up` (resume intent). Both `lets` and `let's` accepted. Case-insensitive on the verb.

**Ticket-ID extraction regex** (applied to the rest of the phrase after the verb):

- Primary: `[A-Z][A-Z0-9]+-\d+` — covers Jira and Linear (e.g. `ENG-1234`, `PROJ-77`, `ABC123-9`).
- Asana fallback: bare numeric token of 10+ digits. (Asana task IDs are typically 12-19 digits; the 10-digit lower bound avoids matching incidental numbers in conversation like dates or amounts.)
- First match wins. If no token matches, treat as no-ticket.

## Workspace name resolution

```
if ticket_id:
    workspace_name = ticket_id          # preserve case from user input
else:
    if git remote URL matches github.com | gitlab.com | bitbucket.org | gitea.*:
        repo_name = parse from remote URL  # strip .git, take last path segment
        existing = vfs.persistent.list(prefix=f"tickets/{repo_name}-task-")
        n = max(parse_n(k) for k in existing) + 1 if existing else 1
        workspace_name = f"{repo_name}-task-{n}"
    else:
        prompt: "Not in a recognized repo. Enter a workspace name (lowercase letters, digits, hyphens, ≤64 chars):"
        validate: ^[a-z0-9-]{1,64}$
        workspace_name = user_input
```

**Remote URL parsing:** accept both SSH (`git@host:owner/repo.git`) and HTTPS (`https://host/owner/repo.git`); strip trailing `.git`; take the last path segment as `repo_name`. Use `origin` only — ignore `upstream` and others.

**Counter behavior:** scan `vfs.persistent` for keys matching `tickets/<repo_name>-task-<digits>` (the `<digits>` is a literal capture, not a glob), parse the digits, take max + 1. No counter file. If a workspace is later deleted, the counter naturally reuses-but-skips because `max + 1` advances even with gaps. (Concrete: workspaces `-task-1`, `-task-2`, `-task-3` exist; delete `-task-2`; next kickoff is `-task-4`, not `-task-2`. Counter is monotonic with respect to history, not reused.)

**Workspace key style:** preserve the case the user typed (`ENG-1234` stays `ENG-1234` in the key). On macOS APFS (case-preserving but case-insensitive by default), `tickets/ENG-1234/` and `tickets/eng-1234/` would resolve to the same on-disk path — but in practice each ticket has one canonical form (`ENG-1234`) that the user always types, so the case-insensitive collapse is invisible. Not a concern for personal-tool use.

## MCP probing (kickoff only)

**Strategy: probe-all-connected, in parallel.** Not stop-at-first.

"In parallel" here means a single Claude message containing multiple MCP tool calls (Claude Code's native parallel-tool-call mechanism), not separate concurrent processes. Results land together; the skill picks the priority winner from the set of returned hits.

At skill invocation, the skill instructs Claude to use `ToolSearch` to find available tools matching `atlassian`, `linear`, `asana`. For each connected tracker, fire the appropriate "get ticket / get issue / get task" call with the parsed ticket ID.

Concrete tool-name patterns (Claude resolves the exact name at invocation via `ToolSearch`):
- Atlassian: `mcp__*atlassian*__getJiraIssue` (or similar)
- Linear: `mcp__*linear*__get_issue` (or similar)
- Asana: `mcp__*asana*__get_task` (or similar)

Do **not** hardcode the exact tool names in the skill — different Atlassian/Linear/Asana MCP implementations expose differently named tools. The skill description tells Claude to discover them.

**Priority order on multi-hit (collision):** `atlassian > linear > asana`. Chosen because in the user's actual workflow, Jira (Atlassian) is the work-tracker that matters most; if a personal-project ID happens to collide, Jira's the more important one to surface.

**Transparency report.** Every kickoff prints, in this format:

```
kicked off tickets/<workspace_name>/
trackers queried: <comma-list of connected> [(<comma-list of not-connected> not connected)]
hit in: <comma-list>  |  (none)  |  (no ticket ID — repo fallback)
selected: <tracker>  |  (none — stub workspace)  |  (n/a)
parent: <parent_id> (<status>)  |  (no parent)  |  (parent fetch failed: <reason>)  |  (n/a)
```

The parenthetical "not connected" suffix is **omitted** when all known trackers are connected. The `parent:` line is **omitted entirely** when no primary tracker hit occurred (no parent to fetch). The other lines are always present in the order shown; the `|` markers just enumerate the value variants per line. Examples below show the actual rendering.

Examples:

```
kicked off tickets/ENG-1234/
trackers queried: atlassian (linear, asana not connected)
hit in: atlassian
selected: atlassian
parent: EPIC-7 (In Progress)
```

```
kicked off tickets/ENG-1234/
trackers queried: atlassian, linear (asana not connected)
hit in: atlassian, linear
selected: atlassian (priority: atlassian > linear > asana)
parent: (no parent)
```

```
kicked off tickets/ENG-1234/
trackers queried: atlassian
hit in: atlassian
selected: atlassian
parent: (parent fetch failed: 404 not found)
```

```
kicked off tickets/ENG-1234/
trackers queried: atlassian, linear, asana
hit in: (none)
selected: (none — created stub workspace)
```

```
kicked off tickets/vfs-memory-task-3/
trackers queried: (no ticket ID — repo fallback)
selected: (n/a)
```

## Parent ticket fetch

When the main ticket fetch succeeds and the returned ticket has a parent (Jira: parent epic / parent story for subtasks; Linear: `parent` field; Asana: parent task), fire **one additional** MCP call to the *same* tracker that won the primary fetch to retrieve the parent's `id`, `title`, `status`, and `url`.

**One level only. No recursion** — we do not fetch the grandparent or any sub-issues. Bounded, predictable cost (0 or 1 additional MCP call per kickoff).

**Failure handling:** if the parent fetch errors (network, auth, not-found), leave the parent fields null in `ticket.md` frontmatter and append a single-line note to the transparency report. The kickoff still completes — parent context is best-effort, not a hard requirement.

**Cross-tracker parents** (e.g. a Linear ticket whose parent lives in Asana) are not supported. We only query the winning tracker. In practice parent relations are intra-tracker.

## Scaffold layout

Under `<project>/.vfs/persistent/tickets/<workspace_name>/`:

```
ticket.md       # title + description (populated from MCP, or stub)
plan.md         # empty stub
scratchpad.md   # empty stub  (named scratchpad — not "notes" — to avoid mirroring the project-wide notes/ convention)
decisions/      # empty dir, holds future tickets/<X>/decisions/<slug>.md entries
```

All four created on kickoff via `v.persistent.write(...)` with `source="agent"`. (The decisions dir is created lazily by writing a `.gitkeep` placeholder — the VFS treats `tickets/<X>/decisions/.gitkeep` as a normal key.)

### `ticket.md` content — MCP-hit case

```markdown
---
title: <title from MCP>
ticket_id: <id>
tracker: <atlassian|linear|asana>
status: <status>
assignee: <assignee or null>
priority: <priority or null>
labels: [<list>]
source_url: <permalink back to ticket>
parent:
  id: <parent_id or null>
  title: <parent_title or null>
  status: <parent_status or null>
  url: <parent_url or null>
fetched_at: <ISO-8601>
---

# <title>

<description, markdown body from MCP>
```

The `parent:` block is always present in the frontmatter for shape consistency. All four nested fields are `null` when the ticket has no parent. When parent fetch fails, all four are also `null` (and the transparency report notes the failure).

### `ticket.md` content — no-MCP / stub case

```markdown
---
workspace: <workspace_name>
ticket_id: <id-if-user-provided-or-null>
tracker: null
created_at: <ISO-8601>
---

# <workspace_name>

_No tracker ticket loaded. Use this file to capture what this work is about._
```

### `plan.md` and `scratchpad.md` — both identical empty stub

```markdown
---
workspace: <workspace_name>
created_at: <ISO-8601>
---

(empty)
```

**Frontmatter compatibility:** the agent-vfs `PersistentZone` write path attaches its own frontmatter fields (writer_id, ts, source, etag, etc.) and the merge logic preserves user-defined non-VFS fields with type validation. Tested by `tests/test_zones.py::test_persistent_merge_preserves_non_vfs_fields` and `..._drops_bad_preserved_fields`. The skill's user fields above (title, status, assignee, etc.) are simple types (str / list[str] / null) — they survive the merge.

## Resume verb

Triggered by `lets resume <X>` / `let's resume <X>` / `lets pick up <X>`. `<X>` is the workspace name (ticket ID or `<repo>-task-<n>` or a user-named workspace).

**Strict local read** — no MCP re-fetch. (User decided: faster, offline, predictable; no surprise MCP calls. A future `lets refresh <X>` could be added if drift bites.)

```
1. If tickets/<X>/ticket.md does not exist:
     error: "no workspace at tickets/<X>/ — did you mean 'lets kick off <X>'?"
     abort.
2. Read tickets/<X>/ticket.md  → extract frontmatter (title, status, ...).
3. Read tickets/<X>/plan.md    → body content.
4. Read tickets/<X>/scratchpad.md → tail (last 50 lines, configurable).
5. List tickets/<X>/decisions/* keys.
6. Surface a tight summary as a system-style note in the conversation:
     - Ticket title + status (or workspace name if stub)
     - Parent reference (id + title + status), if `parent:` block in ticket.md frontmatter has non-null fields
     - Plan body (if non-empty)
     - Last 50 lines of scratchpad (if non-empty)
     - List of decisions keys
7. Print one-liner: "resumed tickets/<X>/ — <D> decisions, last scratched <iso>"
```

The surfaced summary is the value-add: without it, `lets resume` is just `vfs read tickets/<X>/ticket.md`.

## Edge cases — full table

| Case | Behavior |
|---|---|
| `lets kick off ENG-1234`, MCP fetch succeeds (single hit) | Workspace = `ENG-1234`, ticket.md populated, report shows hit |
| `lets kick off ENG-1234`, MCP fetch fails / not connected | Workspace = `ENG-1234`, ticket.md = stub, report shows `hit in: (none)`. No warning prefix — the transparency report itself is the signal. |
| `lets kick off ENG-1234`, multi-tracker collision | Workspace = `ENG-1234`, ticket.md from priority winner, report shows all hits + which selected |
| `lets kick off ENG-1234`, MCP returns "not found" (vs error) | Same as fetch fails: workspace + stub, report transparent |
| Main fetch succeeds, ticket has no parent | `parent:` block fields all `null`; transparency report shows `parent: (no parent)` |
| Main fetch succeeds, parent fetch errors | `parent:` block fields all `null`; transparency report shows `parent: (parent fetch failed: <reason>)`. Workspace creation still succeeds — parent is best-effort. |
| Cross-tracker parent (Linear ticket with Asana parent) | Not supported. Only the winning tracker is queried for parent. In practice this combination doesn't occur. |
| `lets kick off`, no ID, repo recognized | Workspace = `<repo>-task-<N>`, no MCP probe (no ID to probe with), ticket.md = stub with `ticket_id: null` |
| `lets kick off`, no ID, no recognized remote | Prompt user for workspace name; validate `^[a-z0-9-]{1,64}$`; re-prompt once on invalid; abort cleanly on empty (no scaffold created) |
| `lets kick off ENG-1234`, workspace already exists | Refuse, print: `tickets/ENG-1234/ already exists. Use 'lets resume ENG-1234' to pick it back up.` Don't clobber any file. |
| `lets resume ENG-1234`, workspace missing | Error: `no workspace at tickets/ENG-1234/ — did you mean 'lets kick off ENG-1234'?` |
| `.vfs/` doesn't exist in current project | Error: `no .vfs/ in current project. Run 'vfs init' first.` No auto-init (surprising silent state). |
| Phrase trigger-shaped but obviously wrong (`let's start the dev server`) | Skill description's negative examples + Claude's judgment. Not a regex problem — let the runtime decide. |
| Multiple git remotes | Use `origin`. Ignore others. |
| SSH vs HTTPS remote URL | Parse both shapes; strip `.git`; take last path segment. |
| Counter scan: existing keys `-task-1`, `-task-2`, `-task-5` (gap) | Next = 6 (max + 1, monotonic — gaps don't refill) |
| Counter scan: zero matches | Next = 1 |
| User-named workspace collides with existing | Re-prompt during the "totally local" prompt loop, same as invalid-name case |
| User cancels the "totally local" prompt (empty input) | Abort cleanly, print: `cancelled — no workspace created` |

## Testing strategy

The skill itself is a single Markdown file. The behavior under test is the prompt → Claude → tool-calls chain, which has real-world dependencies (live MCP servers, real git remotes, the local `.vfs/`) that don't lend themselves to unit tests.

**Strategy: manual smoke tests, run by the user when the skill is first installed and after non-trivial changes.** Documented as a checklist in the skill body so future-you can run them cold.

Smoke checklist (each case = one chat-turn invocation):

1. **Kickoff with MCP hit** — in a repo with a connected tracker MCP, `lets kick off <known-real-id>`. Verify: workspace created, ticket.md populated, report shows hit + selected.
2. **Kickoff with no MCP** — disconnect all tracker MCPs (or use a project with none), `lets kick off FAKE-9999`. Verify: workspace created with stub, report shows `hit in: (none)`.
3. **Kickoff no-ID, repo recognized** — `lets kick off`. Verify: workspace = `<this-repo>-task-1` (or N+1).
4. **Kickoff no-ID, no remote** — in a plain directory (or `git init`-only), `lets kick off`. Verify: skill prompts; enter valid name; workspace created.
5. **Kickoff into existing workspace** — repeat case 1 with the same ID. Verify: refuses with "use resume" message.
6. **Resume an existing workspace** — `lets resume <id>`. Verify: summary surfaced (title, status, scratchpad tail, decisions list).
7. **Resume missing workspace** — `lets resume NEVER-OPENED-1`. Verify: error with "did you mean kick off" hint.
8. **Multi-tracker collision** (if both Atlassian and Linear MCPs connected with overlapping IDs) — verify report shows both hits + priority selection.
9. **Kickoff for a ticket with a known parent** — verify `parent:` block in ticket.md has all four fields populated and transparency report shows `parent: <id> (<status>)`.
10. **Kickoff for a ticket with no parent** — verify `parent:` block fields are all `null` and report shows `parent: (no parent)`.
11. **Kickoff where parent fetch errors** (simulate by killing MCP between main + parent calls, if feasible) — verify main workspace still created, parent fields null, report shows the failure reason.

No automated test suite. The 8 cases above are short and the cost of regression is low (it's a personal tool; the user will notice).

## Implementation surface

**File to create:** `~/.claude/skills/vfs-kickoff/SKILL.md`

**Frontmatter** (in YAML at the top of `SKILL.md`):
```yaml
---
name: vfs-kickoff
description: Use when the user is starting work on a fresh piece — phrases like "lets kick off ENG-1234", "let's start ABC-456", "lets kick off" (no ticket — uses repo-based fallback), or picking back up — "lets resume ENG-1234". Do NOT use for starting a process / dev server / command. Scaffolds a per-ticket workspace under .vfs/persistent/tickets/, populates from a connected tracker MCP (Atlassian / Linear / Asana, auto-detected) when an ID is given, reports transparently.
---
```

**Body** (the Markdown instructions Claude follows): step-by-step matching the flow above. Heavy on examples. Light on prose. Same density as `vfs-remember`.

**External dependencies the skill assumes:**
- `agent-vfs` is installed and importable (`from agent_vfs import VFS`). The skill writes a small Python snippet to a temp file and executes it (same pattern as `vfs-remember` Step 3).
- `git` is on PATH.
- At least one of {Atlassian, Linear, Asana} MCPs is connected for the MCP path to do anything useful; absence is handled (stub workspace).

**Versioning:** the skill itself is not versioned independently. If the agent-vfs API changes (e.g., `PersistentZone.write` signature), the skill needs updating in lockstep. Acceptable — it's all the user's code.

## Future work (deferred, captured here so we don't re-discover)

- `lets refresh <X>` — force re-fetch from MCP on an existing workspace. Add only when local-only resume actually bites (e.g. user keeps seeing stale status on resume).
- Override flags (`lets kick off ENG-1234 from linear`) — add only when priority default loses to a tracker the user actually wants more often.
- Workspace listing / switching commands — `vfs list --prefix tickets/` covers this today; add a dedicated verb if the volume grows.
- Auto-archive of old workspaces — manual `vfs delete` covers this today; add if the user accumulates 50+ inactive workspaces and finds them noisy.
- Pulling comments / linked tickets / attachments on the MCP fetch — add when the user wants this on a specific real ticket and the friction is visible. (Parent epics / parent tickets shipped in v1.)
- Slash-command verb (`/kickoff ENG-1234`) as an alternative to the natural-language trigger — add if the trigger detection produces too many false negatives in practice.
