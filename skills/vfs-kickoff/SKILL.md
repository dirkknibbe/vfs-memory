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

Parse the triggering user phrase. Save the snippet below to `/tmp/vfs_kickoff_parse.py` and run it. The inline asserts at the bottom MUST PASS — if they raise AssertionError, the skill is broken.

```python
# /tmp/vfs_kickoff_parse.py
import re
import sys

# Ticket-ID regex
PRIMARY_RE = re.compile(r"[A-Z][A-Z0-9]+-\d+")     # Jira / Linear: ENG-1234, PROJ-77
# ASANA_RE: bare 10+-digit numeric. Asana task IDs are typically 12-19
# digits; the 10-digit lower bound avoids matching incidental numbers in
# conversation (dates, amounts, etc.). Deliberate broad match — only used
# when PRIMARY_RE finds no Jira/Linear-style ID.
ASANA_RE = re.compile(r"\b\d{10,}\b")

VERB_PHRASE_RE = re.compile(
    r"\blet'?s?\b\s+(kick\s+off|pick\s+up|start|begin|resume)\b",
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
    re.compile(r"github\.com"),         # github.com (no GitHub Enterprise pattern — add as needed)
    re.compile(r"gitlab\."),            # gitlab.com OR any self-hosted gitlab.<tld>
    re.compile(r"bitbucket\.org"),      # bitbucket.org (no Bitbucket Server self-hosted pattern — add as needed)
    re.compile(r"gitea\."),             # any gitea.<tld>
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
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None  # no origin, not in a git repo, or git not on PATH
    host, path = parse_remote(url)
    if not host or not is_recognized_host(host):
        return None
    return path.rsplit("/", 1)[-1]

def next_task_counter(repo_name: str) -> int:
    """Scan vfs.persistent for tickets/<repo>-task-<N>, return max(N)+1, default 1.

    Note: agent-vfs PersistentZone.list returns (entries, next_cursor) — a tuple
    of List[Entry] and Optional[str] cursor for pagination. Default max_items=100
    is fine for personal-use scales; paginate if a single repo ever has 100+ workspaces.
    """
    import os
    os.sys.path.insert(0, os.getcwd())  # run as /tmp/*.py: put project root on import path
    os.environ.setdefault("VFS_WRITER", "claude")
    from agent_vfs import VFS
    v = VFS()
    prefix = f"tickets/{repo_name}-task-"
    entries, _cursor = v.persistent.list(prefix=prefix)
    pat = re.compile(rf"^{re.escape(prefix)}(\d+)(/|$)")
    nums = []
    for e in entries:
        m = pat.match(e.key)
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

## Step 5: Create the scaffold (kickoff only)

Skip if `intent == "resume"` — resume never writes.

Compose four writes to `vfs.persistent`. Use the snippet below — save to `/tmp/vfs_kickoff_scaffold.py` and run with the appropriate args.

```python
# /tmp/vfs_kickoff_scaffold.py
import json
from datetime import datetime, timezone
import os
os.sys.path.insert(0, os.getcwd())  # run as /tmp/*.py: put project root on import path
os.environ.setdefault("VFS_WRITER", "claude")
from agent_vfs import VFS


def _fmval(v):
    """Body-frontmatter scalar: None -> 'null', else a single-line string.

    The scaffold metadata block lives in the file BODY — agent-vfs's own
    frontmatter is a fixed provenance schema, not a metadata store, so
    workspace fields ride in the body and resume's parse_body_frontmatter
    reads them back. Collapse newlines so a multi-line value (e.g. a title
    pasted with a line break) can't break the line-based parser.
    """
    if v is None:
        return "null"
    return str(v).replace("\n", " ").replace("\r", " ")

# These come from earlier steps. Hardcode them at runtime via Claude's string-substitution.
WORKSPACE_NAME = "<workspace_name from Step 1>"
TICKET_ID      = "<ticket_id from Step 0, or empty>"
SELECTED_JSON  = """<json-dump of `selected` from Step 3, or "null">"""   # null when no MCP hit
PARENT_JSON    = """<json-dump of `parent_block` from Step 4, or "null">"""

now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
selected = json.loads(SELECTED_JSON) if SELECTED_JSON.strip() != "null" else None
parent = json.loads(PARENT_JSON) if PARENT_JSON.strip() != "null" else None

# Compose ticket.md. Build line-by-line (not textwrap.dedent + f-string) so a
# multi-line ticket description can't corrupt the leading metadata block.
if selected:
    fields = selected["fields"]
    pb = parent or {"id": None, "title": None, "status": None, "url": None}
    fm = "\n".join([
        "---",
        f"title: {_fmval(fields['title'])}",
        f"ticket_id: {_fmval(selected['ticket_id'])}",
        f"tracker: {_fmval(selected['tracker'])}",
        f"status: {_fmval(fields['status'])}",
        f"assignee: {_fmval(fields['assignee'])}",
        f"priority: {_fmval(fields['priority'])}",
        f"labels: {json.dumps(fields['labels'])}",
        f"source_url: {_fmval(fields['source_url'])}",
        "parent:",
        f"  id: {_fmval(pb['id'])}",
        f"  title: {_fmval(pb['title'])}",
        f"  status: {_fmval(pb['status'])}",
        f"  url: {_fmval(pb['url'])}",
        f"fetched_at: {now_iso}",
        "---",
        "",
        f"# {fields['title']}",
        "",
        fields["description"] or "",
        "",
    ])
else:
    fm = "\n".join([
        "---",
        f"workspace: {WORKSPACE_NAME}",
        f"ticket_id: {TICKET_ID or 'null'}",
        "tracker: null",
        f"created_at: {now_iso}",
        "---",
        "",
        f"# {WORKSPACE_NAME}",
        "",
        "_No tracker ticket loaded. Use this file to capture what this work is about._",
        "",
    ])

# Empty stubs
stub = "\n".join([
    "---",
    f"workspace: {WORKSPACE_NAME}",
    f"created_at: {now_iso}",
    "---",
    "",
    "(empty)",
    "",
])

v = VFS()
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
import os
os.sys.path.insert(0, os.getcwd())  # run as /tmp/*.py: put project root on import path
os.environ.setdefault("VFS_WRITER", "claude")
from agent_vfs import VFS
from agent_vfs.types import NotFoundError

WORKSPACE_NAME = "<ticket_id from Step 0>"

v = VFS()
prefix = f"tickets/{WORKSPACE_NAME}"

# Existence probe: ticket.md is the canonical "workspace exists" marker.
try:
    ticket_body, ticket_fm = v.persistent.read(f"{prefix}/ticket.md")
except NotFoundError:
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
import os
os.sys.path.insert(0, os.getcwd())  # run as /tmp/*.py: put project root on import path
os.environ.setdefault("VFS_WRITER", "claude")
from agent_vfs import VFS
from agent_vfs.types import NotFoundError


def parse_body_frontmatter(body):
    """Parse the leading ---...--- metadata block the scaffold writes into the
    BODY. agent-vfs's own read() frontmatter is provenance-only (writer, ts,
    project_slug, ...), so workspace metadata (title, status, parent, ...)
    lives in the body — see the scaffold's _fmval note in Step 5.

    Returns (meta, rest): flat `key: value` plus a one-level-nested `parent:`
    block. Values of 'null'/'None'/'' normalize to None. `rest` is the file
    content after the block (used for the empty-stub checks below).
    """
    def _norm(x):
        return None if x in ("null", "None", "") else x
    if not body.startswith("---\n"):
        return {}, body
    end = body.find("\n---\n", 4)
    if end == -1:
        return {}, body
    block = body[4:end]
    rest = body[end + len("\n---\n"):]
    meta, parent = {}, None
    for line in block.split("\n"):
        if not line.strip():
            continue
        if line.startswith("  ") and parent is not None:
            k, _, val = line.strip().partition(":")
            parent[k.strip()] = _norm(val.strip())
            continue
        k, _, val = line.partition(":")
        k, val = k.strip(), val.strip()
        if k == "parent" and val == "":
            parent = {}
            meta["parent"] = parent
            continue
        parent = None
        meta[k] = _norm(val)
    return meta, rest


WORKSPACE_NAME = "<ticket_id from Step 0>"
v = VFS()
prefix = f"tickets/{WORKSPACE_NAME}"

ticket_raw, _prov = v.persistent.read(f"{prefix}/ticket.md")
meta, _ticket_rest = parse_body_frontmatter(ticket_raw)

# For plan/scratchpad, strip the leading metadata block before the
# emptiness check — otherwise the block itself reads as "content".
try:
    plan_raw, _ = v.persistent.read(f"{prefix}/plan.md")
    _pm, plan_body = parse_body_frontmatter(plan_raw)
    plan_body = plan_body.strip()
except NotFoundError:
    plan_body = ""

try:
    scratch_raw, _ = v.persistent.read(f"{prefix}/scratchpad.md")
    _sm, scratch_rest = parse_body_frontmatter(scratch_raw)
    scratch_tail = "\n".join(scratch_rest.splitlines()[-50:]).strip()
except NotFoundError:
    scratch_tail = ""

decisions_entries, _ = v.persistent.list(prefix=f"{prefix}/decisions/")
decisions = [
    e.key
    for e in decisions_entries
    if not e.key.endswith(".gitkeep")
]

parent = meta.get("parent") or {}
print(f"title={meta.get('title') or meta.get('workspace') or WORKSPACE_NAME}")
print(f"status={meta.get('status') or 'n/a'}")
print(f"parent_id={parent.get('id') or ''}")
print(f"parent_title={parent.get('title') or ''}")
print(f"parent_status={parent.get('status') or ''}")
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

### Last run: 2026-05-29

Validated end-to-end against a live `.vfs/` in the vfs-memory repo. Cases needing a real tracker MCP (1, 9) were exercised with a **simulated** `selected`/`parent` payload fed through the real Step 5 + Step B code, since no Atlassian/Linear/Asana MCP was connected; re-run them against a live MCP when one is available.

- [x] 1. Kickoff with MCP hit (simulated payload: colon-in-title, multi-line description)
- [x] 2. Kickoff with no MCP (stub workspace)
- [x] 3. Kickoff no-ID, repo recognized (`vfs-memory-task-1`)
- [x] 4. Kickoff no-ID, no remote (prompt fallback + `^[a-z0-9-]{1,64}$` validation)
- [x] 5. Kickoff into existing workspace (exists-probe → refuse)
- [x] 6. Resume existing workspace (title/status/parent surface)
- [x] 7. Resume missing workspace (hint message)
- [x] 8. Multi-tracker collision (priority atlassian > linear > asana)
- [x] 9. Kickoff with parent (simulated: parent block populated, surfaces on resume)
- [x] 10. Kickoff with no parent (parent fields null)
- [x] 11. Kickoff where parent fetch errors (workspace still created, parent fields null)
