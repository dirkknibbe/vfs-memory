# vfs-kickoff Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `vfs-kickoff` Claude Code skill at `~/.claude/skills/vfs-kickoff/SKILL.md`, per the design spec at `docs/superpowers/specs/2026-05-27-vfs-kickoff-skill-design.md`. Skill scaffolds a per-ticket workspace inside `.vfs/persistent/tickets/<name>/` on phrases like `lets kick off ENG-1234`, populates it from any auto-detected tracker MCP (Atlassian / Linear / Asana, including a one-level parent fetch), and provides a `lets resume <name>` verb for picking back up.

**Architecture:** Single Markdown file with YAML frontmatter + step-by-step prose + embedded Python snippets. Same shape as `~/.claude/skills/vfs-remember/SKILL.md`. Python snippets are inline in the SKILL.md prose — Claude writes each to a temp file (`/tmp/vfs_kickoff_<step>.py`) and executes via the Bash tool. Data flows between snippets through stdout `key=value` lines that Claude reads and threads into the next snippet's input strings.

**Tech Stack:** Markdown, Python 3.9+ (stdlib + `agent-vfs` library), git CLI for repo detection, MCP tool discovery via the `ToolSearch` tool.

---

## Important context

**Two artifact locations:**
- **The skill file** lives at `~/.claude/skills/vfs-kickoff/SKILL.md` (user-global, NOT inside the `vfs-memory` repo). Skill files are not versioned by git in this user's setup — no per-task commits of the skill file itself.
- **This plan** lives at `docs/superpowers/plans/2026-05-27-vfs-kickoff-implementation.md` inside the `vfs-memory` repo. The plan checkbox state IS committed (per task) so progress is durable across sessions.

**Optional vendoring (decide at end):** copy the finished SKILL.md into `vfs-memory/skills/vfs-kickoff/SKILL.md` as a backup/reference. Out of scope for early tasks; see Task 8.

**No Claude co-author trailer** on any commit this plan produces. User's global rule.

**Personal-tool framing:** the user is the only consumer. No pytest test suite. No CI. The 11 smoke tests in the spec are the test plan; they're run manually by the user (or by the agent dispatched to execute this plan).

**Spec drift discipline:** if any task here doesn't match the spec, STOP and ask the user. Do not silently deviate.

---

## File Structure

| Path | Role | Created in task |
|---|---|---|
| `~/.claude/skills/vfs-kickoff/SKILL.md` | The skill itself: YAML frontmatter + prose + embedded Python snippets | Task 1 (bootstrap), grown by Tasks 2-7 |
| `docs/superpowers/plans/2026-05-27-vfs-kickoff-implementation.md` | This plan; checkboxes ticked + committed per task | Task 0 (committed once at planning time) |
| `/tmp/vfs_kickoff_*.py` | Ephemeral execution helpers (one per Python snippet in SKILL.md). Claude writes + executes at skill-invocation time. NOT versioned. | Runtime |
| `<project>/.vfs/persistent/tickets/<workspace>/{ticket.md,plan.md,scratchpad.md,decisions/}` | The actual scaffold the skill produces in the project. NOT created by this plan; created at first skill invocation. | Runtime |

**Skill body structure** (the final SKILL.md will have these sections, in this order, added by the tasks below):

```
YAML frontmatter (name, description)              ← Task 1
# vfs-kickoff (H1 + one-line summary)             ← Task 1
## Step 0: Detect verb and extract ticket ID      ← Task 2
## Step 1: Resolve workspace name                  ← Task 3
## Step 2: Discover connected tracker MCPs         ← Task 4
## Step 3: Fetch primary ticket (kickoff only)     ← Task 4
## Step 4: Fetch parent ticket (kickoff only)      ← Task 5
## Step 5: Create the scaffold (kickoff only)      ← Task 6
## Step 6: Print transparency report (kickoff)     ← Task 6
## Step A: Locate workspace (resume only)          ← Task 7
## Step B: Read files + decisions list (resume)    ← Task 7
## Step C: Surface summary (resume)                ← Task 7
## Step D: Print one-liner (resume)                ← Task 7
## Smoke test checklist                            ← Task 8
```

---

## Task 0: Commit the plan to its own branch

**Files:**
- Create: `docs/superpowers/plans/2026-05-27-vfs-kickoff-implementation.md` (this file)

Already on branch `docs/spec-vfs-kickoff-skill` from the spec PR (#5). Plan rides the same PR so spec + plan land together.

- [x] **Step 1: Verify branch**

```bash
cd /Users/dirkknibbe/vfs-memory
git status                                  # expect: on docs/spec-vfs-kickoff-skill, clean
git log --oneline | head -3                 # expect: spec commits at top
```

- [x] **Step 2: Commit the plan**

```bash
cd /Users/dirkknibbe/vfs-memory
git add docs/superpowers/plans/2026-05-27-vfs-kickoff-implementation.md
git -c gpg.program=gpg commit -m "docs(plan): vfs-kickoff skill implementation plan

Companion to docs/superpowers/specs/2026-05-27-vfs-kickoff-skill-design.md.
8 tasks: bootstrap → phrase parsing → name resolution → MCP fetch →
parent fetch → scaffold writes + report → resume verb → smoke tests."
git push 2>&1 | tail -3
```

Expected: push succeeds, PR #5 updated.

---

## Task 1: Bootstrap the skill file with frontmatter and skeleton

**Files:**
- Create: `~/.claude/skills/vfs-kickoff/SKILL.md`

**Success criterion:** the skill is discoverable. Restarting Claude Code (or starting a fresh session) shows `vfs-kickoff` in the available-skills list. Smoke test #0 (implicit, not in the spec's 11): typing a trigger phrase causes Claude to identify the skill as applicable.

- [x] **Step 1: Create the directory**

```bash
mkdir -p ~/.claude/skills/vfs-kickoff
ls -ld ~/.claude/skills/vfs-kickoff      # expect: directory exists
```

- [x] **Step 2: Write the bootstrap SKILL.md (frontmatter + section skeleton)**

Create `~/.claude/skills/vfs-kickoff/SKILL.md` with this exact content. Tasks 2-8 will replace the placeholder section bodies with real instructions/code.

````markdown
---
name: vfs-kickoff
description: Use when the user is starting work on a fresh piece — phrases like "lets kick off ENG-1234", "let's kick off PROJ-77", "lets start ABC-456", "lets start" (with no ticket — uses repo-based fallback), or when picking back up — "lets resume ENG-1234". Do NOT use for starting a process / dev server / command / unrelated activity (e.g. "let's start the server", "let's kick off the deploy"). Strong signal that this skill applies: the phrase is followed by a ticket-ID-shaped token (e.g. `[A-Z][A-Z0-9]+-\d+`) or by nothing at all (no-ticket fallback path). Scaffolds a per-ticket workspace under `.vfs/persistent/tickets/<workspace_name>/`, auto-detects connected tracker MCPs (Atlassian / Linear / Asana) and populates the workspace from the ticket. Resume verb does a strict local read of an existing workspace, no MCP re-fetch.
---

# vfs-kickoff

Scaffold a per-ticket VFS workspace, or resume an existing one. See `docs/superpowers/specs/2026-05-27-vfs-kickoff-skill-design.md` in the vfs-memory repo for the full design contract.

## Preconditions (check before doing anything)

1. `.vfs/` directory exists in the current project root. If it doesn't, refuse with:
   > `no .vfs/ in current project. Run 'vfs init' first.`

   No auto-init — surprising silent state. Abort the skill.

2. The `agent_vfs` Python library is importable (`python3 -c "import agent_vfs"`). If not, refuse with:
   > `agent-vfs not installed. Run 'pip install agent-vfs' or 'pipx install agent-vfs' first.`

## Step 0: Detect verb and extract ticket ID

(Task 2 fills this in.)

## Step 1: Resolve workspace name

(Task 3 fills this in.)

## Step 2: Discover connected tracker MCPs

(Task 4 fills this in.)

## Step 3: Fetch primary ticket (kickoff only)

(Task 4 fills this in.)

## Step 4: Fetch parent ticket (kickoff only)

(Task 5 fills this in.)

## Step 5: Create the scaffold (kickoff only)

(Task 6 fills this in.)

## Step 6: Print transparency report (kickoff)

(Task 6 fills this in.)

## Resume branch

(Task 7 fills in Steps A-D.)

## Smoke test checklist

(Task 8 fills this in with the 11 cases from the spec.)
````

- [x] **Step 3: Verify the skill is discoverable**

Open a NEW Claude Code session (current sessions don't reload skills). Confirm `vfs-kickoff` appears in the system-reminder skill list at session start.

Alternative quick check: `cat ~/.claude/skills/vfs-kickoff/SKILL.md | head -5` should show the frontmatter.

- [x] **Step 4: Tick the box in this plan + commit**

```bash
cd /Users/dirkknibbe/vfs-memory
# After ticking the Task 1 checkbox above:
git add docs/superpowers/plans/2026-05-27-vfs-kickoff-implementation.md
git -c gpg.program=gpg commit -m "docs(plan): tick Task 1 — skill bootstrap"
git push
```

---

## Task 2: Phrase parsing — verb detection + ticket-ID extraction

**Files:**
- Modify: `~/.claude/skills/vfs-kickoff/SKILL.md` — replace the `## Step 0` placeholder

**Success criterion:** the snippet below, with its inline `assert` block at the bottom, runs without AssertionError. This is the unit test for phrase parsing.

- [ ] **Step 1: Write the failing assertions first** (TDD shape, even for a skill snippet)

Replace the `## Step 0: Detect verb and extract ticket ID` section in `~/.claude/skills/vfs-kickoff/SKILL.md` with this *placeholder* version first:

````markdown
## Step 0: Detect verb and extract ticket ID

Parse the triggering user phrase. Save the snippet below to `/tmp/vfs_kickoff_parse.py` and run it. The inline asserts at the bottom MUST PASS — if they raise AssertionError, the skill is broken.

```python
# /tmp/vfs_kickoff_parse.py
import re
import sys

# Verbs that mean "start fresh"
KICKOFF_VERBS = {"kick off", "start", "begin"}
# Verbs that mean "pick back up"
RESUME_VERBS = {"resume", "pick up"}

# Ticket-ID regex
PRIMARY_RE = re.compile(r"[A-Z][A-Z0-9]+-\d+")     # Jira / Linear: ENG-1234, PROJ-77
ASANA_RE = re.compile(r"\b\d{10,}\b")              # Asana: bare 10+-digit numeric

VERB_PHRASE_RE = re.compile(
    r"\blets?\b\s+(kick\s+off|pick\s+up|start|begin|resume)\b",
    re.IGNORECASE,
)

def parse_phrase(phrase: str):
    """
    Returns (verb_intent, ticket_id) where:
      verb_intent in {"kickoff", "resume", None}
      ticket_id is a string or None
    """
    m = VERB_PHRASE_RE.search(phrase)
    if not m:
        return (None, None)
    raw_verb = re.sub(r"\s+", " ", m.group(1).lower())
    if raw_verb in {"kick off", "start", "begin"}:
        intent = "kickoff"
    elif raw_verb in {"resume", "pick up"}:
        intent = "resume"
    else:
        intent = None
    # Find ticket ID in everything after the verb
    tail = phrase[m.end():]
    pm = PRIMARY_RE.search(tail) or ASANA_RE.search(tail)
    ticket_id = pm.group(0) if pm else None
    return (intent, ticket_id)

# Inline tests — these run every invocation. Failing = broken skill.
assert parse_phrase("lets kick off ENG-1234") == ("kickoff", "ENG-1234")
assert parse_phrase("let's kick off PROJ-77") == ("kickoff", "PROJ-77")
assert parse_phrase("lets start ABC-456") == ("kickoff", "ABC-456")
assert parse_phrase("let's start") == ("kickoff", None)
assert parse_phrase("lets begin") == ("kickoff", None)
assert parse_phrase("lets resume ENG-1234") == ("resume", "ENG-1234")
assert parse_phrase("let's pick up ENG-1234") == ("resume", "ENG-1234")
assert parse_phrase("lets kick off 1234567890123") == ("kickoff", "1234567890123")
assert parse_phrase("hello world") == (None, None)
assert parse_phrase("lets kick off the deploy") == ("kickoff", None)  # no token; OK
assert parse_phrase("LETS KICK OFF eng-1234") == ("kickoff", None)  # lowercase ID doesn't match PRIMARY_RE — that's fine, treat as no-ID

# When invoked for real, the phrase comes from Claude. Print result for the next step to consume.
phrase = sys.argv[1] if len(sys.argv) > 1 else ""
intent, ticket_id = parse_phrase(phrase)
print(f"intent={intent}")
print(f"ticket_id={ticket_id or ''}")
```

**Output format:** two lines, `intent=<kickoff|resume>` and `ticket_id=<id|empty>`. Empty `intent` (i.e., `intent=None`) means the phrase didn't actually match — return to the user with `phrase did not match a kickoff/resume trigger`.

If `intent=kickoff`, proceed to Step 1 (workspace name resolution).
If `intent=resume`, jump to the Resume branch.
````

- [ ] **Step 2: Run the asserts to verify they pass**

```bash
python3 -c "
import re
VERB_PHRASE_RE = re.compile(r'\\blets?\\b\\s+(kick\\s+off|pick\\s+up|start|begin|resume)\\b', re.IGNORECASE)
PRIMARY_RE = re.compile(r'[A-Z][A-Z0-9]+-\\d+')
ASANA_RE = re.compile(r'\\b\\d{10,}\\b')

def parse_phrase(phrase):
    m = VERB_PHRASE_RE.search(phrase)
    if not m: return (None, None)
    raw = re.sub(r'\\s+', ' ', m.group(1).lower())
    intent = 'kickoff' if raw in {'kick off','start','begin'} else 'resume' if raw in {'resume','pick up'} else None
    tail = phrase[m.end():]
    pm = PRIMARY_RE.search(tail) or ASANA_RE.search(tail)
    return (intent, pm.group(0) if pm else None)

assert parse_phrase('lets kick off ENG-1234') == ('kickoff','ENG-1234')
assert parse_phrase(\"let's resume ENG-1234\") == ('resume','ENG-1234')
assert parse_phrase('hello world') == (None,None)
print('OK')
"
```

Expected: `OK`. If AssertionError: the regex or logic is wrong in Step 1's snippet; fix and re-run.

- [ ] **Step 3: Commit**

```bash
cd /Users/dirkknibbe/vfs-memory
git add docs/superpowers/plans/2026-05-27-vfs-kickoff-implementation.md
git -c gpg.program=gpg commit -m "docs(plan): tick Task 2 — phrase parsing in vfs-kickoff"
git push
```

---

## Task 3: Workspace-name resolution chain

**Files:**
- Modify: `~/.claude/skills/vfs-kickoff/SKILL.md` — replace the `## Step 1` placeholder

**Success criterion:** for each of the three branches (ticket-ID given, repo-detected, totally local), the snippet outputs a sensible workspace name. Inline asserts cover the repo-detection logic. The counter-scan path is harder to unit-test inline (needs a real VFS) — covered by smoke tests 3 and (implicitly) any test that re-runs Task 6.

- [ ] **Step 1: Replace `## Step 1: Resolve workspace name` in SKILL.md**

````markdown
## Step 1: Resolve workspace name

Given the parsed `(intent, ticket_id)` from Step 0, decide the workspace name. Three branches:

```
if ticket_id:                            → workspace_name = ticket_id (preserve case)
elif intent == "kickoff" and recognized git remote:
                                         → workspace_name = "<repo>-task-<N>" (counter)
else:
                                         → prompt the user for a name
```

Save the snippet below to `/tmp/vfs_kickoff_name.py` and run it with the ticket_id from Step 0 as `$1` (empty string if none).

```python
# /tmp/vfs_kickoff_name.py
import os
import re
import subprocess
import sys

# Allow-listed git hosts (any URL matching one of these → "recognized repo")
HOST_PATTERNS = [
    re.compile(r"github\.com"),
    re.compile(r"gitlab\."),           # gitlab.com OR any self-hosted gitlab.<tld>
    re.compile(r"bitbucket\.org"),
    re.compile(r"gitea\."),            # any gitea.<tld>
]

# SSH (git@host:owner/repo.git) and HTTPS (https://host/owner/repo.git)
SSH_REMOTE_RE = re.compile(r"^(?:git@|ssh://git@)([^/:]+)[:/](.+?)(?:\.git)?$")
HTTPS_REMOTE_RE = re.compile(r"^https?://([^/]+)/(.+?)(?:\.git)?/?$")

def parse_remote(url: str):
    """Returns (host, owner/repo_path) or (None, None) if unparseable."""
    for pat in (SSH_REMOTE_RE, HTTPS_REMOTE_RE):
        m = pat.match(url.strip())
        if m:
            return (m.group(1), m.group(2))
    return (None, None)

def is_recognized_host(host: str) -> bool:
    return any(p.search(host) for p in HOST_PATTERNS)

def repo_name_from_origin():
    """Returns repo_name (last path segment, no .git) or None if no recognized origin."""
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return None  # no origin or not in a git repo
    host, path = parse_remote(url)
    if not host or not is_recognized_host(host):
        return None
    return path.rsplit("/", 1)[-1]

def next_task_counter(repo_name: str) -> int:
    """Scan vfs.persistent for tickets/<repo>-task-<N>, return max(N)+1, default 1."""
    from agent_vfs import VFS
    v = VFS(writer_id="claude")
    prefix = f"tickets/{repo_name}-task-"
    entries = v.persistent.list(prefix=prefix)
    pat = re.compile(rf"^{re.escape(prefix)}(\d+)(/|$)")
    nums = []
    for e in entries:
        m = pat.match(e.key if hasattr(e, "key") else e)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1

# Inline tests for the URL parser + host recognizer (pure functions, no I/O)
assert parse_remote("git@github.com:dirkknibbe/vfs-memory.git") == ("github.com", "dirkknibbe/vfs-memory")
assert parse_remote("https://github.com/dirkknibbe/vfs-memory.git") == ("github.com", "dirkknibbe/vfs-memory")
assert parse_remote("https://gitlab.com/foo/bar") == ("gitlab.com", "foo/bar")
assert parse_remote("git@bitbucket.org:foo/bar.git") == ("bitbucket.org", "foo/bar")
assert parse_remote("git@gitea.example.com:foo/bar.git") == ("gitea.example.com", "foo/bar")
assert parse_remote("nonsense") == (None, None)
assert is_recognized_host("github.com")
assert is_recognized_host("gitlab.example.com")
assert is_recognized_host("gitea.example.com")
assert not is_recognized_host("random.example.com")

ticket_id = sys.argv[1] if len(sys.argv) > 1 else ""

if ticket_id:
    workspace_name = ticket_id
    print(f"workspace_name={workspace_name}")
    print(f"name_source=ticket")
    sys.exit(0)

repo = repo_name_from_origin()
if repo:
    n = next_task_counter(repo)
    workspace_name = f"{repo}-task-{n}"
    print(f"workspace_name={workspace_name}")
    print(f"name_source=repo")
    sys.exit(0)

# Fall-through: prompt user via Claude.
print(f"workspace_name=")
print(f"name_source=prompt_required")
```

**If `name_source=prompt_required`**, ask the user (via direct chat, not a Python prompt):

> Not in a recognized repo. Enter a workspace name (lowercase letters, digits, hyphens, ≤64 chars):

Validate `^[a-z0-9-]{1,64}$`. Re-prompt once on invalid. Abort cleanly with `cancelled — no workspace created` if the user gives empty input.

**Workspace-already-exists check** (applies to all branches): after computing `workspace_name`, check whether `tickets/<workspace_name>/ticket.md` already exists in vfs.persistent. If yes, refuse:
> `tickets/<workspace_name>/ already exists. Use 'lets resume <workspace_name>' to pick it back up.`

Abort the skill.
````

- [ ] **Step 2: Verify the URL parsing + host recognition unit tests pass**

```bash
python3 -c "
import re
SSH_REMOTE_RE = re.compile(r'^(?:git@|ssh://git@)([^/:]+)[:/](.+?)(?:\\.git)?$')
HTTPS_REMOTE_RE = re.compile(r'^https?://([^/]+)/(.+?)(?:\\.git)?/?$')
def parse_remote(url):
    for pat in (SSH_REMOTE_RE, HTTPS_REMOTE_RE):
        m = pat.match(url.strip())
        if m: return (m.group(1), m.group(2))
    return (None, None)
assert parse_remote('git@github.com:dirkknibbe/vfs-memory.git') == ('github.com','dirkknibbe/vfs-memory')
assert parse_remote('https://github.com/dirkknibbe/vfs-memory.git') == ('github.com','dirkknibbe/vfs-memory')
assert parse_remote('git@bitbucket.org:foo/bar.git') == ('bitbucket.org','foo/bar')
assert parse_remote('git@gitea.example.com:foo/bar.git') == ('gitea.example.com','foo/bar')
print('OK')
"
```

Expected: `OK`. If failure: regex is broken; fix the snippet in the SKILL.md.

- [ ] **Step 3: Verify the live repo case end-to-end**

```bash
cd /Users/dirkknibbe/vfs-memory
git remote get-url origin       # expect: github URL
```

This is what `repo_name_from_origin()` calls. Confirms git is wired correctly.

- [ ] **Step 4: Commit**

```bash
cd /Users/dirkknibbe/vfs-memory
git add docs/superpowers/plans/2026-05-27-vfs-kickoff-implementation.md
git -c gpg.program=gpg commit -m "docs(plan): tick Task 3 — workspace-name resolution"
git push
```

---

## Task 4: MCP discovery + primary ticket fetch

**Files:**
- Modify: `~/.claude/skills/vfs-kickoff/SKILL.md` — replace the `## Step 2` and `## Step 3` placeholders

**Success criterion:** when invoked with a real ticket ID against a connected tracker MCP, the skill resolves the right tool name via `ToolSearch` and returns a populated ticket payload. Falsifiable by smoke test #1 (kickoff with MCP hit) and #2 (kickoff with no MCP — should report `hit in: (none)`).

This is the largest task. It is mostly *prose* instructing Claude how to do tool discovery + parallel tool calls — there is no Python helper that can replace `ToolSearch` because the available MCP tool names are runtime-discovered.

- [ ] **Step 1: Replace `## Step 2: Discover connected tracker MCPs`**

````markdown
## Step 2: Discover connected tracker MCPs

This step is prose-driven, not Python. You (Claude) use `ToolSearch` to find the actual MCP tool names for each tracker.

Run these three `ToolSearch` calls **in parallel** (single message, three tool calls):

1. `ToolSearch(query="atlassian jira issue", max_results=5)`
2. `ToolSearch(query="linear issue", max_results=5)`
3. `ToolSearch(query="asana task", max_results=5)`

For each tracker, look in the returned tools for the most plausible "get a single ticket / issue / task by ID" tool. Common names:

| Tracker | Likely tool-name shape |
|---|---|
| Atlassian | `mcp__*atlassian*__getJiraIssue`, `mcp__*atlassian*__get_issue`, `mcp__*atlassian*__jira_get_issue` |
| Linear | `mcp__*linear*__get_issue`, `mcp__*linear*__getIssue` |
| Asana | `mcp__*asana*__get_task`, `mcp__*asana*__getTask` |

For each tracker, build a record:

```
{tracker: "atlassian", connected: bool, get_tool_name: str | None, get_parent_tool_name: str | None}
```

The `get_parent_tool_name` is the same tool if it returns parent info in the response, or a separate tool (e.g., `mcp__*atlassian*__getJiraIssue` typically includes a `fields.parent` field — so the same tool covers parent fetch with a different ID).

If a tracker's ToolSearch returns no plausible tool, mark it `connected=False` and move on. Do NOT error.

Build the list:

```
trackers = [
  {tracker: "atlassian", ...},
  {tracker: "linear",    ...},
  {tracker: "asana",     ...},
]
queried = [t.tracker for t in trackers if t.connected]
not_connected = [t.tracker for t in trackers if not t.connected]
```

Save `queried` and `not_connected` for the Step 6 transparency report.

## Step 3: Fetch primary ticket (kickoff only)

If `ticket_id` is empty (no-ID kickoff), skip this step entirely and go to Step 5. The transparency report will show `hit in: (no ticket ID — repo fallback)`.

If `ticket_id` is non-empty and at least one tracker is `connected`:

Fire one MCP call per connected tracker, **in parallel** (single message containing N tool calls, where N = number of connected trackers). Each call is the tracker's `get_tool_name` from Step 2, with the ticket ID as the argument.

Collect the results into:

```
hits = [{tracker, payload} for trackers that returned a ticket]
errors = [{tracker, reason} for trackers that errored (network, auth, etc.)]
not_found = [tracker for trackers that returned "not found"]
```

**Priority order on multi-hit:** `atlassian > linear > asana`. If `hits` is non-empty, the winner is the highest-priority hit.

If `hits` is empty (all not_found or all errored):
- `selected = None`
- `ticket.md` will be a stub (Step 5 handles this).
- Transparency report shows `hit in: (none)`.

If `hits` is non-empty:
- `selected = hits[priority_order_winner]`
- Extract fields from the selected payload into a normalized dict:

```python
# /tmp/vfs_kickoff_extract.py  (or inline — fields vary per tracker)
def normalize(tracker: str, payload: dict) -> dict:
    """Normalize per-tracker payload to a common shape."""
    if tracker == "atlassian":
        f = payload.get("fields", payload)
        return {
            "title": f.get("summary", ""),
            "status": (f.get("status") or {}).get("name"),
            "assignee": ((f.get("assignee") or {}).get("displayName")),
            "priority": ((f.get("priority") or {}).get("name")),
            "labels": f.get("labels", []),
            "source_url": payload.get("self") or payload.get("url"),
            "description": f.get("description", ""),
            "parent_id": ((f.get("parent") or {}).get("key")),
        }
    if tracker == "linear":
        return {
            "title": payload.get("title", ""),
            "status": (payload.get("state") or {}).get("name"),
            "assignee": (payload.get("assignee") or {}).get("name"),
            "priority": payload.get("priority"),
            "labels": [l.get("name") for l in (payload.get("labels") or {}).get("nodes", []) or []],
            "source_url": payload.get("url"),
            "description": payload.get("description", ""),
            "parent_id": (payload.get("parent") or {}).get("id"),
        }
    if tracker == "asana":
        return {
            "title": payload.get("name", ""),
            "status": (payload.get("custom_fields") or [{}])[0].get("display_value"),  # Asana statuses live in custom fields; this is approximate
            "assignee": (payload.get("assignee") or {}).get("name"),
            "priority": None,  # Asana has no native priority; could be a custom field
            "labels": [t.get("name") for t in (payload.get("tags") or [])],
            "source_url": payload.get("permalink_url"),
            "description": payload.get("notes", ""),
            "parent_id": (payload.get("parent") or {}).get("gid"),
        }
    raise ValueError(f"unknown tracker: {tracker}")
```

Save `selected` (with normalized fields) for Steps 4 and 5.

**Performance note:** with three connected trackers, this step does 3 parallel calls (~1s round trip each). In practice the user has 1-2 trackers connected, so it's faster. The visibility of all three results (via the transparency report in Step 6) is worth the cost.
````

- [ ] **Step 2: Verify by inspecting the SKILL.md**

```bash
grep -c "## Step 2: Discover connected tracker MCPs" ~/.claude/skills/vfs-kickoff/SKILL.md   # expect: 1
grep -c "## Step 3: Fetch primary ticket" ~/.claude/skills/vfs-kickoff/SKILL.md              # expect: 1
grep -c "(Task 4 fills this in)" ~/.claude/skills/vfs-kickoff/SKILL.md                       # expect: 0 (both placeholders gone)
```

- [ ] **Step 3: Live integration test deferred to Task 8 smoke tests**

There is no isolated unit test for tool discovery — the Bash environment doesn't have access to `ToolSearch`. The full path is exercised by smoke tests #1, #2, #4 in Task 8. Defer.

- [ ] **Step 4: Commit**

```bash
cd /Users/dirkknibbe/vfs-memory
git add docs/superpowers/plans/2026-05-27-vfs-kickoff-implementation.md
git -c gpg.program=gpg commit -m "docs(plan): tick Task 4 — MCP discovery + primary fetch"
git push
```

---

## Task 5: Parent ticket fetch

**Files:**
- Modify: `~/.claude/skills/vfs-kickoff/SKILL.md` — replace the `## Step 4` placeholder

**Success criterion:** when the primary fetch in Step 3 returned a `parent_id`, fire one additional MCP call to the same tracker, normalize the response, and populate `parent_*` fields. When `parent_id` is null, skip; when the fetch errors, leave parent fields null and capture the error reason for the transparency report. Falsifiable by smoke tests #9, #10, #11 in Task 8.

- [ ] **Step 1: Replace `## Step 4: Fetch parent ticket (kickoff only)`**

````markdown
## Step 4: Fetch parent ticket (kickoff only)

Skip this step entirely if any of:
- `intent != "kickoff"` (resume path)
- `selected is None` (no primary hit, can't fetch a parent we don't know about)
- `selected.parent_id is None` (ticket has no parent)

Otherwise: fire ONE MCP call to the SAME tracker that won the primary fetch (using `selected.tracker` and the `get_tool_name` from Step 2), passing `selected.parent_id` as the argument.

Collect the result:

```
parent_result = {
  fetched: bool,         # True if the call returned a valid payload
  reason: str | None,    # error reason if not fetched (e.g. "404 not found")
  fields: dict | None,   # normalized via the Step 3 normalize() function, if fetched
}
```

If `parent_result.fetched`, extract for ticket.md frontmatter:

```python
parent_block = {
    "id":     selected.parent_id,
    "title":  parent_result.fields["title"],
    "status": parent_result.fields["status"],
    "url":    parent_result.fields["source_url"],
}
```

If not fetched (error or returned-not-found), `parent_block` fields are all `null`. Capture `parent_result.reason` for the transparency report (Step 6).

**No recursion.** Do not fetch the parent's parent. Bounded cost: 0 or 1 additional MCP call per kickoff.

**No cross-tracker fetch.** If a tracker exposes a `parent.tracker` field that differs from the winning tracker (extremely rare, e.g. Asana → Jira parent relation), do not chase it. Treat as no-parent.
````

- [ ] **Step 2: Verify by inspecting the SKILL.md**

```bash
grep -c "## Step 4: Fetch parent ticket" ~/.claude/skills/vfs-kickoff/SKILL.md       # expect: 1
grep -c "(Task 5 fills this in)" ~/.claude/skills/vfs-kickoff/SKILL.md               # expect: 0
```

- [ ] **Step 3: Commit**

```bash
cd /Users/dirkknibbe/vfs-memory
git add docs/superpowers/plans/2026-05-27-vfs-kickoff-implementation.md
git -c gpg.program=gpg commit -m "docs(plan): tick Task 5 — parent ticket fetch"
git push
```

---

## Task 6: Scaffold writes + transparency report

**Files:**
- Modify: `~/.claude/skills/vfs-kickoff/SKILL.md` — replace the `## Step 5` and `## Step 6` placeholders

**Success criterion:** after running, the four scaffold keys exist in `vfs.persistent` with valid frontmatter. The transparency report prints in the exact format the spec specifies (5 examples in the spec, "Transparency report" section). Falsifiable by smoke tests #1, #5 in Task 8.

- [ ] **Step 1: Replace `## Step 5: Create the scaffold (kickoff only)`**

````markdown
## Step 5: Create the scaffold (kickoff only)

Skip if `intent == "resume"` — resume never writes.

Compose four writes to `vfs.persistent`. Use the snippet below — save to `/tmp/vfs_kickoff_scaffold.py` and run with the appropriate args.

```python
# /tmp/vfs_kickoff_scaffold.py
import json
import sys
import textwrap
from datetime import datetime, timezone
from agent_vfs import VFS

# These come from earlier steps. Hardcode them at runtime via Claude's string-substitution.
WORKSPACE_NAME = "<workspace_name from Step 1>"
TICKET_ID      = "<ticket_id from Step 0, or empty>"
SELECTED_JSON  = """<json-dump of `selected` from Step 3, or "null">"""   # null when no MCP hit
PARENT_JSON    = """<json-dump of `parent_block` from Step 4, or "null">"""

now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
selected = json.loads(SELECTED_JSON) if SELECTED_JSON.strip() != "null" else None
parent = json.loads(PARENT_JSON) if PARENT_JSON.strip() != "null" else None

# Compose ticket.md
if selected:
    fields = selected["fields"]
    parent_block = parent or {"id": None, "title": None, "status": None, "url": None}
    fm = textwrap.dedent(f"""\
        ---
        title: {fields['title']!r}
        ticket_id: {selected['ticket_id']}
        tracker: {selected['tracker']}
        status: {fields['status']!r}
        assignee: {fields['assignee']!r}
        priority: {fields['priority']!r}
        labels: {json.dumps(fields['labels'])}
        source_url: {fields['source_url']!r}
        parent:
          id: {parent_block['id']!r}
          title: {parent_block['title']!r}
          status: {parent_block['status']!r}
          url: {parent_block['url']!r}
        fetched_at: {now_iso}
        ---

        # {fields['title']}

        {fields['description']}
        """)
else:
    fm = textwrap.dedent(f"""\
        ---
        workspace: {WORKSPACE_NAME}
        ticket_id: {TICKET_ID or 'null'}
        tracker: null
        created_at: {now_iso}
        ---

        # {WORKSPACE_NAME}

        _No tracker ticket loaded. Use this file to capture what this work is about._
        """)

# Empty stubs
stub = textwrap.dedent(f"""\
    ---
    workspace: {WORKSPACE_NAME}
    created_at: {now_iso}
    ---

    (empty)
    """)

v = VFS(writer_id="claude")
prefix = f"tickets/{WORKSPACE_NAME}"

etag1 = v.persistent.write(f"{prefix}/ticket.md",     fm,   source="agent")
etag2 = v.persistent.write(f"{prefix}/plan.md",       stub, source="agent")
etag3 = v.persistent.write(f"{prefix}/scratchpad.md", stub, source="agent")
etag4 = v.persistent.write(f"{prefix}/decisions/.gitkeep", "", source="agent")

print(f"ticket_etag={etag1}")
print(f"plan_etag={etag2}")
print(f"scratchpad_etag={etag3}")
print(f"decisions_etag={etag4}")
```

If any of the writes fail with `KeyAlreadyExistsError` (because the workspace-exists check in Step 1 has a race), surface the error and abort — do NOT clobber.

## Step 6: Print transparency report (kickoff)

Print to stdout using EXACTLY this format. The user reads this every kickoff.

```
kicked off tickets/<WORKSPACE_NAME>/
trackers queried: <comma-list of queried> [( <comma-list of not_connected> not connected)]
hit in: <comma-list of hits.tracker> | (none) | (no ticket ID — repo fallback)
selected: <selected.tracker> | (none — stub workspace) | (n/a)
parent: <parent.id> (<parent.status>) | (no parent) | (parent fetch failed: <reason>)
```

**Omit** the `not connected` parenthetical when all known trackers are connected.

**Omit the entire `parent:` line** when `selected is None` (no primary hit → nothing to fetch parent from) or when `ticket_id` was empty.

Examples (verbatim from spec):

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
````

- [ ] **Step 2: Verify by inspecting the SKILL.md**

```bash
grep -c "## Step 5: Create the scaffold" ~/.claude/skills/vfs-kickoff/SKILL.md     # expect: 1
grep -c "## Step 6: Print transparency report" ~/.claude/skills/vfs-kickoff/SKILL.md  # expect: 1
grep -c "(Task 6 fills this in)" ~/.claude/skills/vfs-kickoff/SKILL.md             # expect: 0
```

- [ ] **Step 3: Verify scaffold compose is shell-safe**

The textwrap + f-string approach handles strings cleanly, but ticket descriptions can contain triple-quotes or backticks. The smoke tests (Task 8 #1) will catch this in real use. If a real ticket description breaks the snippet, switch from `textwrap.dedent` to a list-of-lines + `"\n".join` shape.

- [ ] **Step 4: Commit**

```bash
cd /Users/dirkknibbe/vfs-memory
git add docs/superpowers/plans/2026-05-27-vfs-kickoff-implementation.md
git -c gpg.program=gpg commit -m "docs(plan): tick Task 6 — scaffold writes + transparency report"
git push
```

---

## Task 7: Resume verb

**Files:**
- Modify: `~/.claude/skills/vfs-kickoff/SKILL.md` — replace the `## Resume branch` placeholder

**Success criterion:** `lets resume <X>` reads an existing workspace, surfaces a tight summary (title/status, parent if present, plan body, scratchpad tail, decisions list), and prints a one-liner. Errors clearly if the workspace doesn't exist. Falsifiable by smoke tests #6, #7 in Task 8.

- [ ] **Step 1: Replace `## Resume branch`**

````markdown
## Resume branch

Triggered when `intent == "resume"` from Step 0. `ticket_id` (or whatever Step 0 extracted) becomes the workspace name to look up.

If no `ticket_id` was extracted from the resume phrase, refuse:
> `'lets resume' requires a workspace name. Try 'lets resume ENG-1234' or 'lets resume vfs-memory-task-3'.`

Abort.

### Step A: Locate workspace

```python
# /tmp/vfs_kickoff_resume.py
import json
import sys
from agent_vfs import VFS

WORKSPACE_NAME = "<ticket_id from Step 0>"

v = VFS(writer_id="claude")
prefix = f"tickets/{WORKSPACE_NAME}"

# Existence probe: ticket.md is the canonical "workspace exists" marker.
try:
    ticket_body, ticket_fm = v.persistent.read(f"{prefix}/ticket.md")
except FileNotFoundError:
    print(f"missing=true")
    print(f"hint=no workspace at tickets/{WORKSPACE_NAME}/ — did you mean 'lets kick off {WORKSPACE_NAME}'?")
    sys.exit(0)

print(f"missing=false")
print(f"ticket_fm={json.dumps(ticket_fm)}")
```

If `missing=true`: print the hint message to the user and abort. Do not proceed to Steps B-D.

### Step B: Read files + decisions list

```python
# /tmp/vfs_kickoff_resume_read.py (continuation; assumes Step A succeeded)
import json
from agent_vfs import VFS

WORKSPACE_NAME = "<ticket_id from Step 0>"
v = VFS(writer_id="claude")
prefix = f"tickets/{WORKSPACE_NAME}"

ticket_body, ticket_fm = v.persistent.read(f"{prefix}/ticket.md")

try:
    plan_body, _ = v.persistent.read(f"{prefix}/plan.md")
    plan_body = plan_body.strip()
except FileNotFoundError:
    plan_body = ""

try:
    scratch_body, _ = v.persistent.read(f"{prefix}/scratchpad.md")
    scratch_tail = "\n".join(scratch_body.splitlines()[-50:]).strip()
except FileNotFoundError:
    scratch_tail = ""

decisions = [
    e.key if hasattr(e, "key") else e
    for e in v.persistent.list(prefix=f"{prefix}/decisions/")
    if not (e.key if hasattr(e, "key") else e).endswith(".gitkeep")
]

print(f"title={ticket_fm.get('title') or ticket_fm.get('workspace') or WORKSPACE_NAME}")
print(f"status={ticket_fm.get('status') or 'n/a'}")
print(f"parent_id={(ticket_fm.get('parent') or {}).get('id') or ''}")
print(f"parent_title={(ticket_fm.get('parent') or {}).get('title') or ''}")
print(f"parent_status={(ticket_fm.get('parent') or {}).get('status') or ''}")
print(f"plan_nonempty={'yes' if plan_body and plan_body != '(empty)' else 'no'}")
print(f"scratch_nonempty={'yes' if scratch_tail and scratch_tail != '(empty)' else 'no'}")
print(f"decisions_count={len(decisions)}")
print(f"decisions_keys={json.dumps(decisions)}")
print(f"plan_body={json.dumps(plan_body)}")
print(f"scratch_tail={json.dumps(scratch_tail)}")
```

### Step C: Surface summary

Compose and print a Markdown summary block that Claude can read for context in the next turn:

```
**Resumed workspace `tickets/<WORKSPACE_NAME>/`**

- **Title:** <title> (<status>)
- **Parent:** <parent_id> — <parent_title> (<parent_status>)        ← only if parent_id non-empty
- **Plan:**
  <plan_body, indented as a blockquote>                              ← only if plan_nonempty=yes
- **Scratchpad (last 50 lines):**
  <scratch_tail, indented as a blockquote>                           ← only if scratch_nonempty=yes
- **Decisions:** <decisions_count> entries
  - <key 1>
  - <key 2>
  ...
```

Omit each section that has no content. The decisions list lives in `decisions_keys` from Step B — show all of them; for a personal-use tool, even 20+ decisions are fine to list.

### Step D: Print one-liner

```
resumed tickets/<WORKSPACE_NAME>/ — <decisions_count> decisions, last scratched <iso-timestamp>
```

For the `last scratched <iso-timestamp>` field, use the frontmatter `ts` field of `tickets/<WORKSPACE_NAME>/scratchpad.md` (it's the etag's last-write time managed by VFS). If scratchpad has never been written to since scaffold, use `created_at` from the same frontmatter.

If etag/ts access is awkward, fall back to: `last scratched (unknown)`.
````

- [ ] **Step 2: Verify by inspecting the SKILL.md**

```bash
grep -c "### Step A: Locate workspace" ~/.claude/skills/vfs-kickoff/SKILL.md         # expect: 1
grep -c "### Step D: Print one-liner" ~/.claude/skills/vfs-kickoff/SKILL.md          # expect: 1
grep -c "(Task 7 fills" ~/.claude/skills/vfs-kickoff/SKILL.md                        # expect: 0
```

- [ ] **Step 3: Commit**

```bash
cd /Users/dirkknibbe/vfs-memory
git add docs/superpowers/plans/2026-05-27-vfs-kickoff-implementation.md
git -c gpg.program=gpg commit -m "docs(plan): tick Task 7 — resume verb"
git push
```

---

## Task 8: Smoke test checklist + finalize

**Files:**
- Modify: `~/.claude/skills/vfs-kickoff/SKILL.md` — replace the `## Smoke test checklist` placeholder, append the spec's 11 cases
- (Optionally) Create: `vfs-memory/skills/vfs-kickoff/SKILL.md` — vendor a copy of the finished skill into the repo, for backup + reviewable diff

**Success criterion:** all 11 smoke tests pass in the user's actual environment. If any fail, capture the failure and either patch the skill (loop back to the relevant earlier task) OR add a TODO to the plan with the discrepancy.

- [ ] **Step 1: Replace `## Smoke test checklist`**

````markdown
## Smoke test checklist

Run each case manually after non-trivial skill changes. The skill is a Markdown file; there is no automated test harness.

1. **Kickoff with MCP hit** — in a repo with a connected tracker MCP, type `lets kick off <known-real-id>`. Verify: workspace created (`vfs list --prefix tickets/<id>/`), ticket.md populated (title, description, source_url all non-null), report shows `hit in: <tracker>` + `selected: <tracker>`.

2. **Kickoff with no MCP** — disconnect all tracker MCPs (or use a project with none connected), type `lets kick off FAKE-9999`. Verify: workspace created with stub ticket.md (`workspace: FAKE-9999`, `ticket_id: FAKE-9999`, body says "No tracker ticket loaded"); report shows `hit in: (none)` + `selected: (none — created stub workspace)`.

3. **Kickoff no-ID, repo recognized** — in vfs-memory (or any github repo), type `lets kick off`. Verify: workspace = `vfs-memory-task-<N>` where N is max+1 of existing tickets/vfs-memory-task-*; report shows `trackers queried: (no ticket ID — repo fallback)`.

4. **Kickoff no-ID, no remote** — in a plain directory (no git, or `git init` with no remote), type `lets kick off`. Verify: skill prompts "Not in a recognized repo..."; entering a valid name (e.g. "test-1") creates the workspace; entering empty input aborts cleanly with "cancelled — no workspace created".

5. **Kickoff into existing workspace** — repeat smoke #1 with the same ticket ID. Verify: refuses with `tickets/<id>/ already exists. Use 'lets resume <id>' to pick it back up.` and does not clobber any file (check etags unchanged via `vfs read tickets/<id>/ticket.md`).

6. **Resume existing workspace** — type `lets resume <id>` where `<id>` is a previously-kicked-off workspace. Verify: summary block surfaces with title, status, plan (if non-empty), scratchpad tail (if non-empty), decisions list; one-liner prints `resumed tickets/<id>/ — N decisions, last scratched <iso>`.

7. **Resume missing workspace** — type `lets resume NEVER-OPENED-1`. Verify: error with hint `no workspace at tickets/NEVER-OPENED-1/ — did you mean 'lets kick off NEVER-OPENED-1'?`.

8. **Multi-tracker collision** — (if both Atlassian and Linear MCPs connected with overlapping IDs) type `lets kick off <colliding-id>`. Verify: report shows `hit in: atlassian, linear` + `selected: atlassian (priority: atlassian > linear > asana)`; ticket.md frontmatter has `tracker: atlassian`.

9. **Kickoff for a ticket with a known parent** — type `lets kick off <id-with-parent>`. Verify: ticket.md frontmatter `parent:` block has all four fields populated; report shows `parent: <parent-id> (<parent-status>)`.

10. **Kickoff for a ticket with no parent** — type `lets kick off <id-no-parent>`. Verify: `parent:` block fields are all `null`; report shows `parent: (no parent)`.

11. **Kickoff where parent fetch errors** — (simulate by using a ticket ID whose parent has been deleted in the tracker, or by killing MCP between calls if feasible). Verify: main workspace still created, `parent:` block fields all `null`, report shows `parent: (parent fetch failed: <reason>)`.

### Recording results

After running the suite, append a results block to this file (in SKILL.md) under a `### Last run` heading:

```
### Last run: <YYYY-MM-DD>
- [x] 1. Kickoff with MCP hit
- [x] 2. Kickoff with no MCP
- [ ] 3. ...
```

Update on each substantial change.
````

- [ ] **Step 2: Run all 11 smoke tests**

For each case 1-11 above: trigger the skill, observe the output, verify against the expected behavior. Capture any failures.

Approximate time: 30-60 minutes for the full suite (some cases require setting up specific MCP states).

If any case fails: do NOT mark this task complete. Loop back to the relevant prior task, patch the skill, re-run the failing case.

- [ ] **Step 3: Decide on vendoring**

Ask the user: should we copy the finished SKILL.md into `vfs-memory/skills/vfs-kickoff/SKILL.md` for backup + git history?

- **If yes:** create the directory, copy the file, commit:
  ```bash
  mkdir -p /Users/dirkknibbe/vfs-memory/skills/vfs-kickoff
  cp ~/.claude/skills/vfs-kickoff/SKILL.md /Users/dirkknibbe/vfs-memory/skills/vfs-kickoff/SKILL.md
  cd /Users/dirkknibbe/vfs-memory
  git add skills/vfs-kickoff/SKILL.md
  git -c gpg.program=gpg commit -m "feat(skill): vendor vfs-kickoff skill into repo"
  git push
  ```

- **If no:** the skill lives only in `~/.claude/skills/vfs-kickoff/` and is not versioned. Make a one-line note in the plan that this was the decision.

- [ ] **Step 4: Final commit — plan complete**

```bash
cd /Users/dirkknibbe/vfs-memory
git add docs/superpowers/plans/2026-05-27-vfs-kickoff-implementation.md
git -c gpg.program=gpg commit -m "docs(plan): tick Task 8 — vfs-kickoff implementation complete

All 11 smoke tests passed (see plan for details). Vendored: <yes|no per Step 3>."
git push
```

- [ ] **Step 5: Merge the PR**

PR #5 now contains: spec, plan, (optionally) vendored skill. After CI passes and Claude review fires, merge to main.

---

## Open questions for the user (resolve before / during Task 8)

1. **Vendoring decision (Task 8 Step 3):** copy finished SKILL.md into vfs-memory repo for version history, or leave it user-global only?

2. **Smoke test MCP availability:** which tracker MCPs are connected today? This determines which smoke tests (1, 8, 9, 10, 11) can actually be exercised vs. deferred to "when an Atlassian/Linear/Asana MCP is set up later".

3. **Tool name discovery confidence:** Task 4's prose says Claude figures out the MCP tool names from `ToolSearch` results. If the actual tool names in the user's MCPs look very different from the table in Task 4 ("Likely tool-name shape"), update the table with the real names as a follow-up patch.
