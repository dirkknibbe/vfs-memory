# Generic agent-vfs v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hardened, agent-agnostic, CLI-first VFS as a new pip-installable package (`agent-vfs`) per the design at [`docs/superpowers/specs/2026-05-27-generic-vfs-design.md`](../specs/2026-05-27-generic-vfs-design.md).

**Architecture:** Three layers — `vfs-core` Python library (stdlib-only), `vfs` CLI binary (agent + TTY-gated human surfaces), and optional skills. Per-project `.vfs/` directory replaces the global `~/.claude/projects/<slug>/memory/` namespace. Symlink containment via `O_DIRECTORY` root FD + `dir_fd=` traversal; source=user, cross-project, and `--allow-secret` all TTY-gated with no env override.

**Tech Stack:** Python 3.9+, stdlib only (`os`, `fcntl`, `tempfile`, `argparse`, `json`, `re`, `uuid`, `tomllib`/`tomli`, `pathlib`, `dataclasses`). pytest for tests. No runtime deps; pytest is the only dev dep.

**Project root:** This plan assumes the new package lives at `/Users/dirkknibbe/claude-workflow/agent-vfs/`. The user can `git mv` to a separate repo location after the package is working. All file paths below are relative to that root unless noted (Task 0.0 touches the existing in-tree `/Users/dirkknibbe/claude-workflow/vfs/`).

---

## Phase 0 — Repository scaffolding

### Task 0.0: Cut v0.6 of in-tree `vfs/` with DeprecationWarning

The new `agent-vfs` won't be useful for a while; existing scripts must keep working in the meantime. Stamp the in-tree package as deprecated *before* the new repo work begins so the deprecation window starts immediately. This is the only task that edits files outside the new `agent-vfs/` tree.

**Files:**
- Modify: `/Users/dirkknibbe/claude-workflow/vfs/pyproject.toml`
- Modify: `/Users/dirkknibbe/claude-workflow/vfs/__init__.py`

- [ ] **Step 1: Bump version + add comment**

Edit `/Users/dirkknibbe/claude-workflow/vfs/pyproject.toml` to change `version = "0.5.0"` to `version = "0.6.0"`.

- [ ] **Step 2: Add `DeprecationWarning` to package init**

Edit `/Users/dirkknibbe/claude-workflow/vfs/__init__.py`. Insert at the top of the file, before any imports:

```python
import warnings

warnings.warn(
    "The in-tree `vfs` package is deprecated as of 0.6.0. "
    "Migrate to `agent-vfs` on PyPI (binary `vfs`, import `vfs`). "
    "This package will be removed one quarter after agent-vfs 1.0.0 ships.",
    DeprecationWarning,
    stacklevel=2,
)
```

- [ ] **Step 3: Verify the warning fires**

Run from `/Users/dirkknibbe/claude-workflow/`:
```
python3 -W default -c "import vfs"
```
Expected: `DeprecationWarning: The in-tree \`vfs\` package is deprecated…` printed to stderr.

- [ ] **Step 4: Verify existing tests still pass**

```
cd /Users/dirkknibbe/claude-workflow/vfs && python3 -m unittest discover -s tests
```
Expected: existing v0.5 tests still PASS (DeprecationWarning is a warning, not an error).

- [ ] **Step 5: Commit**

```bash
cd /Users/dirkknibbe/claude-workflow
git add vfs/pyproject.toml vfs/__init__.py
git commit -m "feat(vfs): v0.6 — DeprecationWarning, migrate to agent-vfs"
```

---

### Task 0.1: Create directory structure and pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `vfs/__init__.py`
- Create: `vfs/backends/__init__.py`
- Create: `tests/__init__.py`
- Create: `LICENSE` (MIT)
- Create: `.gitignore`
- Create: `README.md` (skeleton — full content in Task 14.1)

- [ ] **Step 1: Create the directory tree**

```bash
mkdir -p /Users/dirkknibbe/claude-workflow/agent-vfs/{vfs/backends,tests}
cd /Users/dirkknibbe/claude-workflow/agent-vfs
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools==69.5.1"]
build-backend = "setuptools.build_meta"

[project]
name = "agent-vfs"
version = "1.0.0a0"
description = "Hardened, agent-agnostic file system for memory and scratch"
requires-python = ">=3.9"
authors = [{name = "Dirk Knibbe"}]
readme = "README.md"
license = {text = "MIT"}
keywords = ["agent", "llm", "memory", "vfs"]
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "License :: OSI Approved :: MIT License",
    "Operating System :: POSIX",
]

[project.scripts]
vfs = "vfs.cli:main"

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-timeout>=2.0"]

[tool.setuptools]
packages = ["vfs", "vfs.backends"]
```

- [ ] **Step 3: Write `vfs/__init__.py`**

```python
"""agent-vfs — hardened, agent-agnostic file system for memory and scratch.

Spec: docs/superpowers/specs/2026-05-27-generic-vfs-design.md
"""
__version__ = "1.0.0a0"

# Re-exports happen as modules are implemented. Don't add stubs.
```

- [ ] **Step 4: Write `LICENSE` (MIT)**

```
MIT License

Copyright (c) 2026 Dirk Knibbe

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 5: Write `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
build/
dist/
.venv/
.coverage
```

- [ ] **Step 6: Write skeleton README and empty `__init__.py` files**

```bash
cat > README.md <<'EOF'
# agent-vfs

Hardened, agent-agnostic file system for memory and scratch.

Under construction — see `docs/superpowers/specs/2026-05-27-generic-vfs-design.md`.
EOF

: > vfs/backends/__init__.py
: > tests/__init__.py
```

- [ ] **Step 7: Verify package is installable**

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -c "import vfs; print(vfs.__version__)"
```

Expected output: `1.0.0a0`

- [ ] **Step 8: Commit**

```bash
git init
git add .
git commit -m "feat: scaffold agent-vfs package layout"
```

---

## Phase 1 — Core types

### Task 1.1: Error hierarchy and dataclasses

**Files:**
- Create: `vfs/types.py`
- Create: `tests/test_types.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_types.py
from vfs.types import (
    Entry, BackendCapabilities,
    VFSError, NotFoundError, ConflictError, CapabilityError,
    ZoneViolationError, ValidationError, PermissionGateError,
)


def test_error_hierarchy():
    assert issubclass(NotFoundError, VFSError)
    assert issubclass(ConflictError, VFSError)
    assert issubclass(CapabilityError, VFSError)
    assert issubclass(ZoneViolationError, VFSError)
    assert issubclass(ValidationError, VFSError)
    assert issubclass(PermissionGateError, VFSError)


def test_entry_dataclass():
    e = Entry(key="foo", mtime=1.0, size=42, etag="abc")
    assert e.key == "foo"
    assert e.size == 42


def test_backend_capabilities():
    c = BackendCapabilities(
        atomic_write=True, etag_native=False,
        list_consistency="strong", search=True,
        max_object_size_bytes=10_000_000,
    )
    assert c.max_object_size_bytes == 10_000_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_types.py -v`
Expected: `ImportError: cannot import name ... from 'vfs.types'`

- [ ] **Step 3: Implement `vfs/types.py`**

```python
"""Core VFS types and error hierarchy."""
from dataclasses import dataclass
from typing import Literal


@dataclass
class Entry:
    """One item returned by list() — key + metadata, no content."""
    key: str
    mtime: float
    size: int
    etag: str


@dataclass
class BackendCapabilities:
    """Declared capabilities of a backend."""
    atomic_write: bool
    etag_native: bool
    list_consistency: Literal["strong", "eventual"]
    search: bool
    max_object_size_bytes: int


class VFSError(Exception):
    """Base class for all VFS errors."""


class NotFoundError(VFSError):
    """Read/delete on a key that does not exist."""


class ConflictError(VFSError):
    """CAS conflict: if_match did not match current etag (or O_EXCL failed)."""


class CapabilityError(VFSError):
    """Backend cannot meet the zone's required capabilities."""


class ZoneViolationError(VFSError):
    """Symlink/path-traversal violation — refuses to operate outside root."""


class ValidationError(VFSError):
    """Bad key grammar, frontmatter, secret refusal, or size cap exceeded."""


class PermissionGateError(VFSError):
    """TTY gate or perms refusal (e.g., --as-user without TTY)."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_types.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/types.py tests/test_types.py
git commit -m "feat: core error hierarchy and dataclasses"
```

---

### Task 1.2: Key grammar validation

**Files:**
- Create: `vfs/paths.py`
- Create: `tests/test_paths.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_paths.py
import pytest
from vfs.paths import validate_key
from vfs.types import ValidationError


VALID_KEYS = [
    "foo",
    "foo.md",
    "notes/foo.md",
    "decisions/2026-05-27-x.md",
    "a/b/c/d.md",
    "foo-bar_baz.txt",
]

INVALID_KEYS = [
    "",                  # empty
    "/abs",              # leading slash
    "rel/",              # trailing slash
    "a/../b",            # traversal component
    "a/./b",             # dot component
    "..",                # bare dotdot
    ".",                 # bare dot
    "foo\x00bar",        # NUL
    "foo\nbar",          # newline
    "foo\rbar",          # CR
    "foo\\bar",          # backslash
    "foo.",              # trailing dot
    "foo ",              # trailing space
    " foo",              # leading space
    "foo bar",           # internal space
    "foo:bar",           # colon
    "foo;bar",           # semicolon
    "foo|bar",           # pipe
    "foo*bar",           # glob char
    "foo?bar",           # glob char
    "foo[bar",           # bracket
]


@pytest.mark.parametrize("key", VALID_KEYS)
def test_valid_keys(key):
    validate_key(key)  # raises on failure


@pytest.mark.parametrize("key", INVALID_KEYS)
def test_invalid_keys(key):
    with pytest.raises(ValidationError):
        validate_key(key)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_paths.py -v`
Expected: `ImportError`

- [ ] **Step 3: Implement `vfs/paths.py`**

```python
"""Path/key grammar validation and normalization.

Key grammar:
    [A-Za-z0-9._/-]+
    no leading or trailing /
    no `..` or `.` components
    no control chars (including \\n, \\r, \\x00)
    no trailing dot or space (Windows-style traversal defense)
    no leading space
    no backslash (Windows path separator)
    must roundtrip through os.path.normpath unchanged
"""
import os
import re
from vfs.types import ValidationError


_ALLOWED_CHARSET = re.compile(r"^[A-Za-z0-9._/-]+$")


def validate_key(key: str) -> None:
    """Raise ValidationError if `key` violates the v1 grammar."""
    if not isinstance(key, str):
        raise ValidationError(f"invalid key (not a string): {type(key).__name__}")
    if not key:
        raise ValidationError("invalid key: empty string")
    if key.startswith("/"):
        raise ValidationError(f"invalid key (absolute path): {key!r}")
    if key.endswith("/"):
        raise ValidationError(f"invalid key (trailing slash): {key!r}")
    if not _ALLOWED_CHARSET.match(key):
        raise ValidationError(
            f"invalid key (charset; allowed [A-Za-z0-9._/-]): {key!r}"
        )
    if key.startswith(" ") or key.endswith(" "):
        raise ValidationError(f"invalid key (leading/trailing space): {key!r}")
    if key.endswith("."):
        raise ValidationError(f"invalid key (trailing dot): {key!r}")
    components = key.split("/")
    for comp in components:
        if comp in ("", ".", ".."):
            raise ValidationError(f"invalid key (bad component {comp!r}): {key!r}")
    # normpath roundtrip: defeats encoded traversal and odd normalizations.
    normalized = os.path.normpath(key)
    if normalized != key:
        raise ValidationError(
            f"invalid key (normpath roundtrip mismatch: {key!r} -> {normalized!r})"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_paths.py -v`
Expected: PASS (21 parametrize cases + 6 valid = 27 tests)

- [ ] **Step 5: Commit**

```bash
git add vfs/paths.py tests/test_paths.py
git commit -m "feat: tightened key grammar with normpath roundtrip check"
```

---

### Task 1.3: Root resolution

**Files:**
- Modify: `vfs/paths.py`
- Modify: `tests/test_paths.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_paths.py`:

```python
import os
import tempfile
from pathlib import Path
from vfs.paths import resolve_project_root


def _make_project(root: Path) -> Path:
    (root / ".vfs").mkdir(parents=True)
    return root


def test_resolve_from_project_root(tmp_path, monkeypatch):
    proj = _make_project(tmp_path / "myproj")
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VFS_PROJECT_ROOT", raising=False)
    assert resolve_project_root() == proj


def test_resolve_from_subdir(tmp_path, monkeypatch):
    proj = _make_project(tmp_path / "myproj")
    sub = proj / "src" / "nested"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VFS_PROJECT_ROOT", raising=False)
    assert resolve_project_root() == proj


def test_resolve_stops_at_home(tmp_path, monkeypatch):
    # No .vfs/ anywhere; should raise rather than walking above $HOME
    home = tmp_path / "home"
    sub = home / "myproj" / "src"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("VFS_PROJECT_ROOT", raising=False)
    with pytest.raises(NotFoundError):
        resolve_project_root()


def test_resolve_ignores_vfs_project_root_env(tmp_path, monkeypatch):
    """$VFS_PROJECT_ROOT was removed for security — it must not affect resolution."""
    proj = _make_project(tmp_path / "real")
    fake = _make_project(tmp_path / "fake")
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("VFS_PROJECT_ROOT", str(fake))  # ignored
    assert resolve_project_root() == proj


def test_resolve_no_env_var_special_case(tmp_path, monkeypatch):
    """Resolution is strictly upward-walk; no env var override."""
    other = tmp_path / "no-vfs"
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("VFS_PROJECT_ROOT", "/anywhere")  # ignored
    with pytest.raises(NotFoundError):
        resolve_project_root()
```

Add to imports at top: `from vfs.types import NotFoundError`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_paths.py -v -k resolve`
Expected: `ImportError: cannot import name 'resolve_project_root'`

- [ ] **Step 3: Implement `resolve_project_root` in `vfs/paths.py`**

Append to `vfs/paths.py`:

```python
from pathlib import Path
from typing import Optional
from vfs.types import NotFoundError


def resolve_project_root(start: Optional[str] = None) -> Path:
    """Discover the project's .vfs/ root.

    Strictly upward-walk from `start` (default CWD). Stops at:
    filesystem root, $HOME, or a `.vfs/` hit.

    No env-var override — an earlier draft honored $VFS_PROJECT_ROOT,
    but that doubled as a cross-project bypass for prompt-injected agents.
    Callers who need a non-CWD root use `VFS(root=...)` directly.

    Raises:
      NotFoundError: no .vfs/ found.
    """
    cwd = Path(start if start is not None else os.getcwd()).resolve()
    home = Path(os.environ.get("HOME", "/")).resolve()
    current = cwd
    while True:
        if (current / ".vfs").is_dir():
            return current
        if current == home or current.parent == current:
            raise NotFoundError(
                f"no .vfs/ found walking up from {cwd}; run `vfs init`"
            )
        current = current.parent
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_paths.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/paths.py tests/test_paths.py
git commit -m "feat: root resolution with HOME boundary and env override"
```

---

## Phase 2 — Frontmatter (with read/write hardening)

### Task 2.1: Frontmatter parser and serializer

**Files:**
- Create: `vfs/frontmatter.py`
- Create: `tests/test_frontmatter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_frontmatter.py
import pytest
from vfs.frontmatter import make_frontmatter, parse_frontmatter
from vfs.types import ValidationError


def test_make_basic():
    fm = make_frontmatter(writer="agent", source="agent", project_slug="proj-uuid")
    assert fm.startswith("---\n")
    assert fm.endswith("---\n")
    assert "writer: agent" in fm
    assert "source: agent" in fm
    assert "project_slug: proj-uuid" in fm


def test_make_rejects_newline_in_value():
    with pytest.raises(ValidationError):
        make_frontmatter(writer="agent\nsource: user", source="agent", project_slug="x")


def test_make_rejects_cr_in_value():
    with pytest.raises(ValidationError):
        make_frontmatter(writer="agent\r", source="agent", project_slug="x")


def test_make_rejects_control_chars():
    with pytest.raises(ValidationError):
        make_frontmatter(writer="agent\x01", source="agent", project_slug="x")


def test_parse_no_frontmatter():
    fm, body = parse_frontmatter("just a body")
    assert fm == {}
    assert body == "just a body"


def test_parse_unterminated_frontmatter():
    fm, body = parse_frontmatter("---\nwriter: agent\nno close")
    assert fm == {}
    assert body == "---\nwriter: agent\nno close"


def test_parse_basic():
    text = "---\nwriter: agent\nsource: agent\n---\nbody"
    fm, body = parse_frontmatter(text)
    assert fm == {"writer": "agent", "source": "agent"}
    assert body == "body"


def test_parse_strips_invalid_field_keys():
    # Field key with bad chars must be dropped on read (defense-in-depth)
    text = "---\nwriter: agent\nbad key: x\nfoo:bar: y\n---\nbody"
    fm, _ = parse_frontmatter(text)
    assert "writer" in fm
    assert "bad key" not in fm
    assert "foo:bar" not in fm


def test_parse_strips_values_with_control_chars():
    # Pre-planted file with CR in a value — must be dropped
    text = "---\nwriter: agent\nname: foo\rbar\n---\nbody"
    fm, _ = parse_frontmatter(text)
    assert fm.get("writer") == "agent"
    assert "name" not in fm  # value had \r


def test_roundtrip_preserves_known_fields():
    fm_text = make_frontmatter(writer="agent", source="agent", project_slug="proj-uuid")
    parsed, body = parse_frontmatter(fm_text + "hello")
    assert parsed["writer"] == "agent"
    assert parsed["source"] == "agent"
    assert parsed["project_slug"] == "proj-uuid"
    assert body == "hello"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_frontmatter.py -v`
Expected: `ImportError`

- [ ] **Step 3: Implement `vfs/frontmatter.py`**

```python
"""Provenance frontmatter — strict on write, sanitizing on read.

Write shape:
    ---
    writer: <agent id>
    source: <"user" | "agent" | "tool:<name>" | "web:<domain>">
    ts: <ISO-8601 UTC>
    project_slug: <project uuid from config.toml>
    etag: <empty at write; reserved for future inline storage>
    ---
    <body>

Field values reject any [\\x00-\\x1f] (control chars, including \\n \\r).
Field keys must match [\\w.-]+. Both checks apply on write AND on read.
Bad fields are dropped on read (the body is unaffected) — defeats injection
attempts via pre-planted file content.
"""
import re
from datetime import datetime, timezone
from typing import Dict, Tuple

from vfs.types import ValidationError


_CONTROL_CHARS = re.compile(r"[\x00-\x1f]")
_FIELD_KEY = re.compile(r"^[\w.-]+$")


def _check_field_value(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise ValidationError(f"frontmatter field {name!r} must be a string")
    if _CONTROL_CHARS.search(value):
        raise ValidationError(
            f"frontmatter field {name!r} contains control char: {value!r}"
        )


def _check_field_key(key: str) -> bool:
    return bool(_FIELD_KEY.match(key))


def make_frontmatter(
    writer: str,
    source: str,
    project_slug: str,
    etag: str = "",
) -> str:
    """Serialize the VFS-v1 provenance block. Strict on values."""
    _check_field_value("writer", writer)
    _check_field_value("source", source)
    _check_field_value("project_slug", project_slug)
    _check_field_value("etag", etag)
    ts = datetime.now(timezone.utc).isoformat()
    return (
        "---\n"
        f"writer: {writer}\n"
        f"source: {source}\n"
        f"ts: {ts}\n"
        f"project_slug: {project_slug}\n"
        f"etag: {etag}\n"
        "---\n"
    )


def parse_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    """Split content into (frontmatter_dict, body).

    Sanitizing: bad-key / bad-value fields are silently dropped from the
    returned dict. The body is unaffected.

    Tolerant: missing / unterminated frontmatter returns ({}, content).
    """
    if not content.startswith("---\n"):
        return {}, content
    end_idx = content.find("\n---\n", 4)
    if end_idx == -1:
        return {}, content
    fm_text = content[4:end_idx]
    body = content[end_idx + len("\n---\n"):]
    fm: Dict[str, str] = {}
    for line in fm_text.split("\n"):
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if not _check_field_key(k):
            continue
        if _CONTROL_CHARS.search(v):
            continue
        fm[k] = v
    return fm, body
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_frontmatter.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/frontmatter.py tests/test_frontmatter.py
git commit -m "feat: frontmatter with hardened read/write field validation"
```

---

## Phase 3 — LocalFS backend (the security-critical layer)

### Task 3.1: Backend init with O_DIRECTORY root FD

**Files:**
- Create: `vfs/backends/localfs.py`
- Create: `tests/test_localfs.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_localfs.py
import os
import pytest
from pathlib import Path
from vfs.backends.localfs import LocalFSBackend


def test_init_creates_root_dir(tmp_path):
    root = tmp_path / "data"
    backend = LocalFSBackend(str(root))
    assert root.is_dir()
    assert backend.root == str(root)
    assert backend._root_fd >= 0
    backend.close()


def test_init_with_existing_dir(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    backend = LocalFSBackend(str(root))
    assert backend._root_fd >= 0
    backend.close()


def test_init_refuses_loose_perms(tmp_path):
    root = tmp_path / "data"
    root.mkdir(mode=0o755)
    with pytest.raises(PermissionError):
        LocalFSBackend(str(root), strict_perms=True)


def test_close_releases_fd(tmp_path):
    root = tmp_path / "data"
    backend = LocalFSBackend(str(root))
    fd = backend._root_fd
    backend.close()
    assert backend._root_fd == -1
    # Closed FD should error on re-close attempt internally; not asserted here.
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_localfs.py -v`
Expected: `ImportError`

- [ ] **Step 3: Implement `vfs/backends/localfs.py` (init only)**

```python
"""LocalFS backend with O_DIRECTORY root FD + dir_fd-relative traversal."""
import errno
import os
import stat
from typing import Optional

from vfs.types import (
    BackendCapabilities, ConflictError, NotFoundError,
    ValidationError, ZoneViolationError, VFSError,
)
from vfs.paths import validate_key


MAX_OBJECT_SIZE_BYTES = 10_000_000  # 10 MB enforced cap
DIR_MODE = 0o700
FILE_MODE = 0o600


class LocalFSBackend:
    """File-backed storage with strict path containment.

    Root resolution: realpath the user-supplied path, then open with
    O_DIRECTORY and hold the FD for the process lifetime. All subsequent
    operations traverse with `dir_fd=root_fd` and `O_NOFOLLOW` on the
    final component, plus an lstat check on write destinations.
    """

    def __init__(self, root: str, *, strict_perms: bool = True) -> None:
        """Initialize the backend.

        `strict_perms=True` (default) refuses to operate if the root
        directory's mode has any `0o077` bits set. Callers who need to
        operate on a deliberately-loose-perms dir (rare) pass
        `strict_perms=False`. The CLI never overrides the default.
        """
        self.root = os.path.abspath(os.path.expanduser(root))
        old_umask = os.umask(0o077)
        try:
            os.makedirs(self.root, mode=DIR_MODE, exist_ok=True)
        finally:
            os.umask(old_umask)

        if strict_perms:
            st = os.stat(self.root)
            mode = stat.S_IMODE(st.st_mode)
            if mode & 0o077:
                raise PermissionError(
                    f"refusing to operate on {self.root!r} with mode "
                    f"{oct(mode)} (must be 0700 or stricter); "
                    f"chmod 0700 {self.root} or construct with "
                    f"strict_perms=False if intentional"
                )

        self._root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)

    def close(self) -> None:
        """Release the root directory FD. Idempotent.

        No __del__ — close-on-gc is unreliable at interpreter shutdown.
        Tests + the CLI call close() explicitly via try/finally.
        """
        if self._root_fd != -1:
            os.close(self._root_fd)
            self._root_fd = -1

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            atomic_write=True,
            etag_native=False,
            list_consistency="strong",
            search=True,
            max_object_size_bytes=MAX_OBJECT_SIZE_BYTES,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_localfs.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/backends/localfs.py tests/test_localfs.py
git commit -m "feat(localfs): init with O_DIRECTORY root FD and umask"
```

---

### Task 3.2: read() with dir_fd traversal

**Files:**
- Modify: `vfs/backends/localfs.py`
- Modify: `tests/test_localfs.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_localfs.py`:

```python
def test_read_simple(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    (tmp_path / "foo.md").write_text("hello", encoding="utf-8")
    content, etag, mtime = backend.read("foo.md")
    assert content == "hello"
    assert etag
    assert mtime > 0
    backend.close()


def test_read_not_found(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    with pytest.raises(NotFoundError):
        backend.read("missing.md")
    backend.close()


def test_read_refuses_symlink_in_dest(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("SECRET", encoding="utf-8")
    (tmp_path / "evil.md").symlink_to(sentinel)
    with pytest.raises(ZoneViolationError):
        backend.read("evil.md")
    backend.close()


def test_read_refuses_symlink_in_path_component(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("SECRET", encoding="utf-8")
    (tmp_path / "shortcut").symlink_to(outside)
    with pytest.raises(ZoneViolationError):
        backend.read("shortcut/secret.md")
    backend.close()


def test_read_offset_limit(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    (tmp_path / "foo.md").write_text("0123456789", encoding="utf-8")
    content, _, _ = backend.read("foo.md", offset=2, limit=4)
    assert content == "2345"
    backend.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_localfs.py -v -k read`
Expected: AttributeError (no `read` method yet)

- [ ] **Step 3: Implement `read()` and `_open_relative()` helper**

Append to `vfs/backends/localfs.py`:

```python
    def _open_relative(self, key: str, flags: int) -> int:
        """Open `key` relative to root_fd, refusing symlinks at any component.

        Strategy: walk components one by one, opening each as a directory FD
        with O_NOFOLLOW. The final component is opened with `flags`. This
        defeats symlink-in-path-component attacks even under concurrent
        attacker-driven swaps.
        """
        validate_key(key)
        components = key.split("/")
        cur_fd = self._root_fd
        opened_fds = []
        try:
            for i, comp in enumerate(components):
                is_final = i == len(components) - 1
                comp_flags = flags if is_final else (
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                )
                try:
                    next_fd = os.open(comp, comp_flags | os.O_NOFOLLOW,
                                      dir_fd=cur_fd)
                except OSError as e:
                    if e.errno == errno.ELOOP:
                        raise ZoneViolationError(
                            f"symlink in path: {key!r} (component {comp!r})"
                        ) from e
                    if e.errno == errno.ENOENT:
                        raise NotFoundError(key) from e
                    raise
                if not is_final:
                    opened_fds.append(next_fd)
                cur_fd = next_fd
            return cur_fd
        except Exception:
            for fd in opened_fds:
                try:
                    os.close(fd)
                except OSError:
                    pass
            raise
        finally:
            for fd in opened_fds:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def _etag_from_fd(self, fd: int) -> tuple:
        st = os.fstat(fd)
        return f"{st.st_mtime_ns}-{st.st_size}", st.st_mtime

    def read(
        self,
        key: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> tuple:
        """Read up to `limit` characters from `key`, starting at character `offset`.

        Returns (content, etag, mtime). Raises NotFoundError or
        ZoneViolationError as appropriate.
        """
        fd = self._open_relative(key, os.O_RDONLY)
        try:
            etag, mtime = self._etag_from_fd(fd)
            with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as fp:
                if offset:
                    fp.read(offset)
                content = fp.read() if limit is None else fp.read(limit)
            return content, etag, mtime
        finally:
            os.close(fd)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_localfs.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/backends/localfs.py tests/test_localfs.py
git commit -m "feat(localfs): read with dir_fd + O_NOFOLLOW traversal"
```

---

### Task 3.3: write() with lstat dest check, size cap, atomic replace

**Files:**
- Modify: `vfs/backends/localfs.py`
- Modify: `tests/test_localfs.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_localfs.py`:

```python
def test_write_simple(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    etag = backend.write("foo.md", "hello")
    assert (tmp_path / "foo.md").read_text() == "hello"
    assert etag
    backend.close()


def test_write_creates_intermediate_dirs(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("notes/foo.md", "x")
    assert (tmp_path / "notes" / "foo.md").read_text() == "x"
    backend.close()


def test_write_refuses_symlink_at_dest(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("ORIGINAL", encoding="utf-8")
    (tmp_path / "evil.md").symlink_to(sentinel)
    with pytest.raises(ZoneViolationError):
        backend.write("evil.md", "OVERWRITE")
    assert sentinel.read_text() == "ORIGINAL"
    backend.close()


def test_write_refuses_symlink_in_path(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "shortcut").symlink_to(outside)
    with pytest.raises(ZoneViolationError):
        backend.write("shortcut/foo.md", "x")
    backend.close()


def test_write_enforces_size_cap(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    huge = "x" * (10_000_001)
    with pytest.raises(ValidationError):
        backend.write("foo.md", huge)
    assert not (tmp_path / "foo.md").exists()
    backend.close()


def test_write_overwrite(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("foo.md", "v1")
    backend.write("foo.md", "v2")
    assert (tmp_path / "foo.md").read_text() == "v2"
    backend.close()


def test_write_sets_0600_perms(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("foo.md", "x")
    mode = stat.S_IMODE((tmp_path / "foo.md").stat().st_mode)
    assert mode == 0o600
    backend.close()


def test_write_intermediate_dirs_0700(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("notes/deep/foo.md", "x")
    mode = stat.S_IMODE((tmp_path / "notes").stat().st_mode)
    assert mode == 0o700
    mode = stat.S_IMODE((tmp_path / "notes" / "deep").stat().st_mode)
    assert mode == 0o700
    backend.close()
```

Add `import stat` and `from vfs.types import ValidationError` to imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_localfs.py -v -k write`
Expected: AttributeError

- [ ] **Step 3: Implement `write()`**

Add `import secrets` to the top of `vfs/backends/localfs.py` (alongside existing imports). **Do not** import `tempfile` — the previous draft mixed `tempfile.mkstemp` with `dir_fd`-based traversal; the unified `dir_fd` path below is symlink-safe and correct.

Append to `vfs/backends/localfs.py`:

```python
    def _mkdir_relative(self, dir_path: str) -> None:
        """Create intermediate directories under root, refusing symlinks."""
        components = dir_path.split("/")
        cur_fd = self._root_fd
        opened = []
        try:
            for comp in components:
                if not comp:
                    continue
                try:
                    next_fd = os.open(
                        comp,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=cur_fd,
                    )
                except FileNotFoundError:
                    old_umask = os.umask(0o077)
                    try:
                        os.mkdir(comp, mode=DIR_MODE, dir_fd=cur_fd)
                    finally:
                        os.umask(old_umask)
                    next_fd = os.open(
                        comp,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=cur_fd,
                    )
                except OSError as e:
                    if e.errno == errno.ELOOP:
                        raise ZoneViolationError(
                            f"symlink in path: {dir_path!r}"
                        ) from e
                    raise
                if cur_fd != self._root_fd:
                    opened.append(cur_fd)
                cur_fd = next_fd
            if cur_fd != self._root_fd:
                opened.append(cur_fd)
        finally:
            for fd in opened:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def write(
        self,
        key: str,
        content: str,
        if_match: Optional[str] = None,
    ) -> str:
        """Atomic write with symlink containment and size cap.

        `if_match`: None = last-writer-wins. "" = CAS-create (O_EXCL).
        "<etag>" = update only if current etag matches.
        """
        validate_key(key)
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_OBJECT_SIZE_BYTES:
            raise ValidationError(
                f"object too large: {len(encoded)} > {MAX_OBJECT_SIZE_BYTES}"
            )

        components = key.split("/")
        dir_components = components[:-1]
        filename = components[-1]

        if dir_components:
            self._mkdir_relative("/".join(dir_components))
            parent_fd = self._open_dir_relative("/".join(dir_components))
            close_parent = True
        else:
            parent_fd = self._root_fd
            close_parent = False

        try:
            # Refuse symlink at destination (existing file)
            try:
                st = os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)
                if stat.S_ISLNK(st.st_mode):
                    raise ZoneViolationError(
                        f"refusing to overwrite symlink at {key!r}"
                    )
                current_etag = f"{st.st_mtime_ns}-{st.st_size}"
                exists = True
            except FileNotFoundError:
                exists = False
                current_etag = ""

            # CAS check
            if if_match is not None:
                if if_match == "":
                    if exists:
                        raise ConflictError(
                            f"CAS-create failed: {key!r} already exists"
                        )
                else:
                    if not exists or if_match != current_etag:
                        raise ConflictError(
                            f"etag mismatch on {key!r}: expected {if_match!r}, "
                            f"current {current_etag!r}"
                        )

            # Atomic write via O_CREAT|O_EXCL temp file in the destination's
            # parent (relative to parent_fd), then renameat. All ops stay
            # inside the symlink-contained traversal — never use tempfile.mkstemp,
            # which can't accept dir_fd.
            tmp_basename = f".vfs-tmp-{secrets.token_hex(8)}"
            tmp_fd = os.open(
                tmp_basename,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                mode=FILE_MODE,
                dir_fd=parent_fd,
            )
            try:
                with os.fdopen(tmp_fd, "wb") as fp:
                    fp.write(encoded)
                os.rename(
                    tmp_basename,
                    filename,
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                )
                tmp_basename = None  # rename succeeded; do not unlink
            finally:
                if tmp_basename is not None:
                    try:
                        os.unlink(tmp_basename, dir_fd=parent_fd)
                    except OSError:
                        pass

            # New etag
            st = os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)
            return f"{st.st_mtime_ns}-{st.st_size}"
        finally:
            if close_parent:
                os.close(parent_fd)

    def _open_dir_relative(self, dir_path: str) -> int:
        """Open an intermediate dir relative to root, refusing symlinks."""
        components = [c for c in dir_path.split("/") if c]
        cur_fd = self._root_fd
        opened = []
        try:
            for comp in components:
                try:
                    next_fd = os.open(
                        comp,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=cur_fd,
                    )
                except OSError as e:
                    if e.errno == errno.ELOOP:
                        raise ZoneViolationError(
                            f"symlink in path: {dir_path!r}"
                        ) from e
                    raise
                if cur_fd != self._root_fd:
                    opened.append(cur_fd)
                cur_fd = next_fd
        except Exception:
            for fd in opened:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if cur_fd != self._root_fd:
                try:
                    os.close(cur_fd)
                except OSError:
                    pass
            raise
        else:
            for fd in opened:
                try:
                    os.close(fd)
                except OSError:
                    pass
            return cur_fd
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_localfs.py -v -k write`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/backends/localfs.py tests/test_localfs.py
git commit -m "feat(localfs): write with O_EXCL temp + atomic rename + size cap"
```

---

### Task 3.4: delete() and CAS

**Files:**
- Modify: `vfs/backends/localfs.py`
- Modify: `tests/test_localfs.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_localfs.py`:

```python
def test_delete_simple(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("foo.md", "x")
    backend.delete("foo.md")
    assert not (tmp_path / "foo.md").exists()
    backend.close()


def test_delete_not_found(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    with pytest.raises(NotFoundError):
        backend.delete("missing.md")
    backend.close()


def test_delete_cas_match(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    etag = backend.write("foo.md", "x")
    backend.delete("foo.md", if_match=etag)
    assert not (tmp_path / "foo.md").exists()
    backend.close()


def test_delete_cas_mismatch(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("foo.md", "x")
    with pytest.raises(ConflictError):
        backend.delete("foo.md", if_match="bogus")
    assert (tmp_path / "foo.md").exists()
    backend.close()


def test_cas_create(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("foo.md", "v1", if_match="")
    with pytest.raises(ConflictError):
        backend.write("foo.md", "v2", if_match="")
    backend.close()


def test_cas_update(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    e1 = backend.write("foo.md", "v1")
    e2 = backend.write("foo.md", "v2", if_match=e1)
    assert e2 != e1
    with pytest.raises(ConflictError):
        backend.write("foo.md", "v3", if_match=e1)
    backend.close()


def test_delete_refuses_symlink_at_dest(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("KEEP", encoding="utf-8")
    (tmp_path / "evil.md").symlink_to(sentinel)
    with pytest.raises(ZoneViolationError):
        backend.delete("evil.md")
    assert sentinel.exists()
    backend.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_localfs.py -v -k "delete or cas"`
Expected: most fail (delete missing)

- [ ] **Step 3: Implement `delete()`**

Append to `vfs/backends/localfs.py`:

```python
    def delete(self, key: str, if_match: Optional[str] = None) -> None:
        """Unlink `key`, refusing symlinks. CAS via `if_match`."""
        validate_key(key)
        components = key.split("/")
        dir_components = components[:-1]
        filename = components[-1]

        if dir_components:
            parent_fd = self._open_dir_relative("/".join(dir_components))
            close_parent = True
        else:
            parent_fd = self._root_fd
            close_parent = False

        try:
            try:
                st = os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError as e:
                raise NotFoundError(key) from e
            if stat.S_ISLNK(st.st_mode):
                raise ZoneViolationError(
                    f"refusing to delete symlink at {key!r}"
                )
            if if_match is not None:
                current_etag = f"{st.st_mtime_ns}-{st.st_size}"
                if if_match != current_etag:
                    raise ConflictError(
                        f"etag mismatch on delete {key!r}: expected {if_match!r}, "
                        f"current {current_etag!r}"
                    )
            os.unlink(filename, dir_fd=parent_fd)
        finally:
            if close_parent:
                os.close(parent_fd)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_localfs.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/backends/localfs.py tests/test_localfs.py
git commit -m "feat(localfs): delete with CAS and symlink refusal"
```

---

### Task 3.5: list() with os.walk(followlinks=False)

**Files:**
- Modify: `vfs/backends/localfs.py`
- Modify: `tests/test_localfs.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_localfs.py`:

```python
import os as _os


def test_list_empty(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    entries, cursor = backend.list()
    assert entries == []
    assert cursor is None
    backend.close()


def test_list_basic(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("a.md", "1")
    backend.write("notes/b.md", "2")
    entries, _ = backend.list()
    keys = sorted(e.key for e in entries)
    assert keys == ["a.md", "notes/b.md"]
    backend.close()


def test_list_prefix(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("notes/a.md", "1")
    backend.write("decisions/b.md", "2")
    entries, _ = backend.list(prefix="notes/")
    assert {e.key for e in entries} == {"notes/a.md"}
    backend.close()


def test_list_pagination(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    for i in range(5):
        backend.write(f"k{i}.md", "x")
    page1, cursor = backend.list(max_items=2)
    assert len(page1) == 2
    assert cursor is not None
    page2, cursor2 = backend.list(cursor=cursor, max_items=2)
    assert len(page2) == 2
    page3, cursor3 = backend.list(cursor=cursor2, max_items=2)
    assert len(page3) == 1
    assert cursor3 is None
    backend.close()


def test_list_excludes_tmp_files(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("real.md", "x")
    (tmp_path / ".vfs-tmp-deadbeef").write_text("garbage")
    entries, _ = backend.list()
    assert all(not e.key.startswith(".vfs-tmp-") for e in entries)
    backend.close()


def test_list_does_not_follow_symlinks(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("real.md", "x")
    outside = tmp_path.parent / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("SECRET")
    (tmp_path / "shortcut").symlink_to(outside)
    entries, _ = backend.list()
    assert all("secret" not in e.key for e in entries)
    backend.close()


def test_list_max_files_cap(tmp_path, monkeypatch):
    backend = LocalFSBackend(str(tmp_path))
    monkeypatch.setenv("VFS_MAX_FILES", "3")
    for i in range(10):
        backend.write(f"k{i}.md", "x")
    with pytest.raises(VFSError, match="VFS_MAX_FILES"):
        backend.list()
    backend.close()


def test_list_sibling_adjacency(tmp_path):
    # <root>-evil/ should not be surfaced
    root = tmp_path / "data"
    root.mkdir()
    evil = tmp_path / "data-evil"
    evil.mkdir()
    (evil / "leak.md").write_text("LEAK")
    backend = LocalFSBackend(str(root))
    backend.write("ok.md", "x")
    entries, _ = backend.list()
    assert all("leak" not in e.key for e in entries)
    backend.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_localfs.py -v -k list`
Expected: AttributeError

- [ ] **Step 3: Implement `list()`**

Append to `vfs/backends/localfs.py`:

```python
    def list(
        self,
        prefix: str = "",
        cursor: Optional[str] = None,
        max_items: int = 100,
    ) -> tuple:
        """List entries with key starting with `prefix`. Refuses symlinks."""
        max_files = int(os.environ.get("VFS_MAX_FILES", "10000"))
        from vfs.types import Entry  # local import to avoid top-of-file churn

        candidates = []
        count = 0
        root_with_sep = self.root + os.sep
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            # Exclude symlinked dirs aggressively (defense in depth)
            dirnames[:] = [d for d in dirnames
                           if not os.path.islink(os.path.join(dirpath, d))]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                if os.path.islink(full):
                    continue
                # Exact-prefix realpath assertion defeats <root>-evil sibling
                real = os.path.realpath(full)
                if not (real == self.root or real.startswith(root_with_sep)):
                    continue
                if fn.startswith(".vfs-tmp-"):
                    continue
                rel = os.path.relpath(full, self.root)
                if prefix and not rel.startswith(prefix):
                    continue
                count += 1
                if count > max_files:
                    raise VFSError(
                        f"VFS_MAX_FILES={max_files} exceeded; refusing to list. "
                        f"Set VFS_MAX_FILES=N to raise the cap."
                    )
                candidates.append(rel)

        candidates.sort()
        if cursor is not None:
            candidates = [k for k in candidates if k > cursor]
        batch = candidates[:max_items]
        next_cursor = batch[-1] if len(candidates) > max_items else None

        entries = []
        for k in batch:
            full = os.path.join(self.root, k)
            st = os.lstat(full)
            entries.append(Entry(
                key=k,
                mtime=st.st_mtime,
                size=st.st_size,
                etag=f"{st.st_mtime_ns}-{st.st_size}",
            ))
        return entries, next_cursor
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_localfs.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/backends/localfs.py tests/test_localfs.py
git commit -m "feat(localfs): list with os.walk(followlinks=False) + max_files cap"
```

---

### Task 3.6: search() bounded line search

**Files:**
- Modify: `vfs/backends/localfs.py`
- Modify: `tests/test_localfs.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_localfs.py`:

```python
def test_search_hit(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("notes/a.md", "alpha\nbravo\ncharlie\n")
    hits = backend.search("", "bravo")
    assert len(hits) == 1
    assert hits[0]["key"] == "notes/a.md"
    assert hits[0]["snippet"] == "bravo"
    backend.close()


def test_search_no_hit(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("a.md", "alpha")
    hits = backend.search("", "missing")
    assert hits == []
    backend.close()


def test_search_prefix(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    backend.write("notes/a.md", "needle")
    backend.write("decisions/b.md", "needle")
    hits = backend.search("notes/", "needle")
    assert len(hits) == 1
    assert hits[0]["key"] == "notes/a.md"
    backend.close()


def test_search_does_not_follow_symlinks(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    outside = tmp_path.parent / "outside"
    outside.mkdir()
    (outside / "leak.md").write_text("needle")
    (tmp_path / "shortcut").symlink_to(outside)
    hits = backend.search("", "needle")
    assert hits == []
    backend.close()


def test_search_max_bytes_per_file(tmp_path, monkeypatch):
    backend = LocalFSBackend(str(tmp_path))
    monkeypatch.setenv("VFS_MAX_BYTES_PER_FILE", "10")
    backend.write("big.md", "this is way more than ten bytes of needle text")
    # Truncated read won't find "needle" if it's past byte 10 — confirmed bound.
    hits = backend.search("", "needle")
    assert hits == []  # bound applied
    backend.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_localfs.py -v -k search`
Expected: AttributeError

- [ ] **Step 3: Implement `search()`**

Append to `vfs/backends/localfs.py`:

```python
    def search(
        self,
        prefix: str,
        query: str,
        max_hits: int = 50,
    ) -> list:
        """Literal-substring line search. Refuses symlinks. Bounded per-file."""
        max_bytes = int(os.environ.get("VFS_MAX_BYTES_PER_FILE", "10000000"))
        max_files = int(os.environ.get("VFS_MAX_FILES", "10000"))

        hits: list = []
        count = 0
        root_with_sep = self.root + os.sep
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            dirnames[:] = [d for d in dirnames
                           if not os.path.islink(os.path.join(dirpath, d))]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                if os.path.islink(full):
                    continue
                real = os.path.realpath(full)
                if not (real == self.root or real.startswith(root_with_sep)):
                    continue
                if fn.startswith(".vfs-tmp-"):
                    continue
                rel = os.path.relpath(full, self.root)
                if prefix and not rel.startswith(prefix):
                    continue
                count += 1
                if count > max_files:
                    raise VFSError(
                        f"VFS_MAX_FILES={max_files} exceeded during search"
                    )
                try:
                    with open(full, "r", encoding="utf-8") as fp:
                        body = fp.read(max_bytes)
                except (OSError, UnicodeDecodeError):
                    continue
                for lineno, line in enumerate(body.split("\n"), start=1):
                    if query in line:
                        hits.append({
                            "key": rel,
                            "line": lineno,
                            "snippet": line,
                        })
                        if len(hits) >= max_hits:
                            return hits
        return hits
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_localfs.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/backends/localfs.py tests/test_localfs.py
git commit -m "feat(localfs): bounded line search with no symlink follow"
```

---

## Phase 4 — Diagnostic log + secret refusal

### Task 4.1: Diagnostic log (append-only JSONL with flock)

**Files:**
- Create: `vfs/diagnostic.py`
- Create: `tests/test_diagnostic.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_diagnostic.py
import json
import os
import threading
from vfs.diagnostic import DiagnosticLog


def test_append_one(tmp_path):
    log = DiagnosticLog(str(tmp_path / "diag.log"))
    log.append({"op": "write", "key": "foo"})
    with open(tmp_path / "diag.log") as fp:
        line = fp.readline()
    rec = json.loads(line)
    assert rec["op"] == "write"
    assert rec["key"] == "foo"
    assert "ts" in rec
    assert rec["caller_pid"] == os.getpid()


def test_concurrent_appends_well_formed(tmp_path):
    log_path = str(tmp_path / "diag.log")
    log = DiagnosticLog(log_path)
    N = 50

    def worker(i):
        log.append({"op": "write", "key": f"k{i}"})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with open(log_path) as fp:
        lines = fp.readlines()
    assert len(lines) == N
    parsed = [json.loads(line) for line in lines]
    keys = sorted(p["key"] for p in parsed)
    assert keys == sorted(f"k{i}" for i in range(N))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_diagnostic.py -v`
Expected: `ImportError`

- [ ] **Step 3: Implement `vfs/diagnostic.py`**

```python
"""Diagnostic log — append-only JSONL with fcntl.flock for same-UID safety.

Explicitly NOT an audit log: the audited process can also write here.
Same-UID peer locking ensures concurrent appends produce well-formed JSONL,
not interleaved bytes — which is the realistic concurrency case (two
Claude Code sessions writing the same project).
"""
import fcntl
import json
import os
from datetime import datetime, timezone


DEFAULT_MAX_BYTES = 100_000_000  # rotate at 100 MB


class DiagnosticLog:
    def __init__(self, path: str) -> None:
        self.path = path
        # Ensure parent exists with tight perms
        parent = os.path.dirname(path)
        if parent:
            old_umask = os.umask(0o077)
            try:
                os.makedirs(parent, mode=0o700, exist_ok=True)
            finally:
                os.umask(old_umask)

    def append(self, record: dict) -> None:
        full = dict(record)
        full.setdefault("ts", datetime.now(timezone.utc).isoformat())
        full.setdefault("caller_pid", os.getpid())
        line = json.dumps(full, separators=(",", ":")) + "\n"
        max_bytes = int(os.environ.get(
            "VFS_MAX_DIAGNOSTIC_LOG_BYTES", str(DEFAULT_MAX_BYTES)
        ))
        # O_APPEND atomic up to PIPE_BUF; flock for belt + suspenders
        old_umask = os.umask(0o077)
        try:
            fd = os.open(self.path,
                         os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
                         mode=0o600)
        finally:
            os.umask(old_umask)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                # Rotate if the existing file is at/over the cap. Best-effort:
                # rotation is not integrity-preserving (consistent with the
                # "diagnostic, not audit" naming).
                cur_size = os.fstat(fd).st_size
                if cur_size + len(line) > max_bytes:
                    try:
                        os.rename(self.path, self.path + ".1")
                    except OSError:
                        pass  # rotation failure does not block the append
                    # Reopen fresh after rotate
                    os.close(fd)
                    old_umask = os.umask(0o077)
                    try:
                        fd = os.open(self.path,
                                     os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
                                     mode=0o600)
                    finally:
                        os.umask(old_umask)
                    fcntl.flock(fd, fcntl.LOCK_EX)
                os.write(fd, line.encode("utf-8"))
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_diagnostic.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/diagnostic.py tests/test_diagnostic.py
git commit -m "feat: diagnostic log with O_APPEND + flock for same-UID safety"
```

---

### Task 4.2: Secret-shape refusal

**Files:**
- Create: `vfs/secrets.py`
- Create: `tests/test_secrets.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_secrets.py
import pytest
from vfs.secrets import looks_like_secret


def test_aws_key():
    assert looks_like_secret("My key is AKIAIOSFODNN7EXAMPLE!")


def test_github_pat():
    assert looks_like_secret("token: ghp_" + "A" * 36)
    assert looks_like_secret("token: ghs_" + "A" * 36)


def test_jwt():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc-123_def"
    assert looks_like_secret(f"Authorization: Bearer {jwt}")


def test_clean_body():
    assert not looks_like_secret("This is just a normal note about something.")


def test_short_string_no_false_positive():
    assert not looks_like_secret("AKIA")  # too short
    assert not looks_like_secret("ghp_short")  # too short
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_secrets.py -v`
Expected: `ImportError`

- [ ] **Step 3: Implement `vfs/secrets.py`**

```python
"""Secret-shape refusal — defense-in-depth, not redaction.

We refuse to write payloads matching obvious credential shapes. This
catches accidental paste-ins; it does NOT defend against an adversary
who knows what the patterns are (they will obfuscate). The point is to
make the human aware before the secret lands in agent memory.
"""
import re


_AWS_ACCESS_KEY = re.compile(r"AKIA[0-9A-Z]{16}")
_GITHUB_PAT = re.compile(r"gh[ps]_[A-Za-z0-9]{36,}")
_JWT = re.compile(
    r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
)


_PATTERNS = (_AWS_ACCESS_KEY, _GITHUB_PAT, _JWT)


def looks_like_secret(text: str) -> bool:
    """Return True if `text` matches any known credential shape."""
    for pat in _PATTERNS:
        if pat.search(text):
            return True
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_secrets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/secrets.py tests/test_secrets.py
git commit -m "feat: secret-shape refusal patterns (AWS, GitHub, JWT)"
```

---

## Phase 5 — Zone API

### Task 5.1: TempZone (thin wrapper)

**Files:**
- Create: `vfs/zones.py`
- Create: `tests/test_zones.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_zones.py
import pytest
from pathlib import Path
from vfs.backends.localfs import LocalFSBackend
from vfs.zones import TempZone, PersistentZone


def test_temp_read_write(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    zone = TempZone(backend)
    zone.write("scratch.md", "ephemeral")
    assert zone.read("scratch.md") == "ephemeral"
    backend.close()


def test_temp_delete(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    zone = TempZone(backend)
    zone.write("foo.md", "x")
    zone.delete("foo.md")
    assert (tmp_path / "foo.md").exists() is False
    backend.close()


def test_temp_no_frontmatter(tmp_path):
    backend = LocalFSBackend(str(tmp_path))
    zone = TempZone(backend)
    zone.write("foo.md", "bare body")
    raw = (tmp_path / "foo.md").read_text()
    assert raw == "bare body"  # no frontmatter on temp
    backend.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_zones.py -v`
Expected: `ImportError`

- [ ] **Step 3: Implement `vfs/zones.py` — TempZone**

```python
"""Zone wrappers: TempZone (flat, no provenance), PersistentZone (frontmatter).

PersistentZone is added in Task 5.2.
"""
from typing import List, Optional, Tuple

from vfs.backends.localfs import LocalFSBackend
from vfs.types import Entry


class TempZone:
    """Ephemeral scratch. No frontmatter; flat key-value over the backend."""

    def __init__(self, backend: LocalFSBackend) -> None:
        self._backend = backend

    def read(self, key: str, offset: int = 0, limit: Optional[int] = None) -> str:
        content, _etag, _mtime = self._backend.read(key, offset, limit)
        return content

    def write(self, key: str, content: str) -> str:
        return self._backend.write(key, content)

    def delete(self, key: str) -> None:
        self._backend.delete(key)

    def list(
        self,
        prefix: str = "",
        cursor: Optional[str] = None,
        max_items: int = 100,
    ) -> Tuple[List[Entry], Optional[str]]:
        return self._backend.list(prefix, cursor, max_items)

    def search(self, prefix: str, query: str, max_hits: int = 50) -> list:
        return self._backend.search(prefix, query, max_hits)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_zones.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/zones.py tests/test_zones.py
git commit -m "feat(zones): TempZone wrapper"
```

---

### Task 5.2: PersistentZone with frontmatter, secret refusal, diagnostic log

**Files:**
- Modify: `vfs/zones.py`
- Modify: `tests/test_zones.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_zones.py`:

```python
from vfs.diagnostic import DiagnosticLog
from vfs.types import ValidationError


def _make_persistent(tmp_path, source_user_allowed=False):
    backend = LocalFSBackend(str(tmp_path / "persistent"))
    diag = DiagnosticLog(str(tmp_path / "diagnostic.log"))
    return PersistentZone(
        backend=backend,
        diag=diag,
        writer_id="test-agent",
        project_id="proj-uuid",
        source_user_allowed=source_user_allowed,
    ), backend


def test_persistent_write_attaches_frontmatter(tmp_path):
    zone, backend = _make_persistent(tmp_path)
    zone.write("notes/foo.md", "body content")
    body, fm = zone.read("notes/foo.md")
    assert body == "body content"
    assert fm["writer"] == "test-agent"
    assert fm["source"] == "agent"
    assert fm["project_slug"] == "proj-uuid"
    backend.close()


def test_persistent_refuses_source_user_by_default(tmp_path):
    zone, backend = _make_persistent(tmp_path, source_user_allowed=False)
    with pytest.raises(ValidationError, match="source=user"):
        zone.write("foo.md", "x", source="user")
    backend.close()


def test_persistent_allows_source_user_when_gated(tmp_path):
    zone, backend = _make_persistent(tmp_path, source_user_allowed=True)
    zone.write("foo.md", "x", source="user")
    _, fm = zone.read("foo.md")
    assert fm["source"] == "user"
    backend.close()


def test_persistent_refuses_secret_shape(tmp_path):
    zone, backend = _make_persistent(tmp_path)
    body = "I just generated this: AKIAIOSFODNN7EXAMPLE — write it down"
    with pytest.raises(ValidationError, match="secret"):
        zone.write("foo.md", body)
    backend.close()


def test_persistent_allows_secret_with_override(tmp_path):
    zone, backend = _make_persistent(tmp_path)
    body = "AKIAIOSFODNN7EXAMPLE"
    zone.write("foo.md", body, allow_secret=True)
    body_out, _ = zone.read("foo.md")
    assert body_out == body
    backend.close()


def test_persistent_write_logged(tmp_path):
    zone, backend = _make_persistent(tmp_path)
    zone.write("foo.md", "body")
    log_path = tmp_path / "diagnostic.log"
    line = log_path.read_text().strip().split("\n")[0]
    import json
    rec = json.loads(line)
    assert rec["op"] == "write"
    assert rec["key"] == "foo.md"
    assert rec["writer"] == "test-agent"
    assert rec["source"] == "agent"
    backend.close()


def test_persistent_merge_preserves_non_vfs_fields(tmp_path):
    zone, backend = _make_persistent(tmp_path)
    # Pre-plant a file with auto-memory-style frontmatter
    (tmp_path / "persistent" / "foo.md").write_text(
        "---\nname: existing-slug\ndescription: a description\n---\nbody",
        encoding="utf-8",
    )
    zone.write("foo.md", "new body")
    body, fm = zone.read("foo.md")
    assert body == "new body"
    assert fm["name"] == "existing-slug"
    assert fm["description"] == "a description"
    assert fm["writer"] == "test-agent"
    backend.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_zones.py -v -k persistent`
Expected: `ImportError`

- [ ] **Step 3: Implement `PersistentZone` in `vfs/zones.py`**

Append to `vfs/zones.py`:

```python
from vfs.frontmatter import (
    _check_field_key, _check_field_value,
    make_frontmatter, parse_frontmatter,
)
from vfs.secrets import looks_like_secret
from vfs.types import NotFoundError, ValidationError


_VFS_OWNED_FIELDS = {"writer", "source", "ts", "project_slug", "etag"}


class PersistentZone:
    """Durable, provenance-tagged storage.

    `source_user_allowed` is set by the CLI layer based on the TTY gate.
    The library default is False — callers cannot upgrade trust without
    going through the gated CLI path.
    """

    def __init__(
        self,
        backend: LocalFSBackend,
        diag,
        writer_id: str,
        project_id: str,
        source_user_allowed: bool = False,
    ) -> None:
        self._backend = backend
        self._diag = diag
        self._writer = writer_id
        self._project = project_id
        self._source_user_allowed = source_user_allowed

    def read(self, key: str) -> Tuple[str, dict]:
        """Read the full file, parse and sanitize frontmatter.

        Returns (body, frontmatter_dict). No offset/limit — partial reads
        would return inconsistent shape (parsed fm vs raw content). Use
        `read_raw()` if you need a partial read; you get raw bytes back
        and parse yourself.
        """
        content, _etag, _mtime = self._backend.read(key)
        fm, body = parse_frontmatter(content)
        return body, fm

    def read_raw(
        self,
        key: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> str:
        """Raw partial read. Returns file content (frontmatter included)
        without parsing. Caller deals with framing.
        """
        content, _etag, _mtime = self._backend.read(key, offset, limit)
        return content

    def write(
        self,
        key: str,
        content: str,
        source: str = "agent",
        if_match: Optional[str] = None,
        allow_secret: bool = False,
    ) -> str:
        if source == "user" and not self._source_user_allowed:
            raise ValidationError(
                "source=user is not allowed via the agent surface; "
                "use `vfs remember --as-user` (TTY-gated)"
            )
        if not allow_secret and looks_like_secret(content):
            raise ValidationError(
                "refusing to write content matching a known secret shape; "
                "pass --allow-secret (TTY-gated) if intentional"
            )

        # Merge-on-write: preserve non-VFS-owned fields from existing file,
        # but route them through the same validators as VFS-owned fields.
        preserved: dict = {}
        dropped: list = []
        try:
            existing, _e, _m = self._backend.read(key)
            existing_fm, _existing_body = parse_frontmatter(existing)
            for k, v in existing_fm.items():
                if k in _VFS_OWNED_FIELDS:
                    continue
                if not _check_field_key(k):
                    dropped.append((k, "bad-key"))
                    continue
                try:
                    _check_field_value(k, v)
                except ValidationError:
                    dropped.append((k, "bad-value"))
                    continue
                preserved[k] = v
        except NotFoundError:
            pass

        fm = make_frontmatter(
            writer=self._writer,
            source=source,
            project_slug=self._project,
        )
        if preserved:
            closing = fm.rfind("---\n")
            preserved_lines = "".join(
                f"{k}: {v}\n" for k, v in preserved.items()
            )
            fm = fm[:closing] + preserved_lines + fm[closing:]

        etag = self._backend.write(key, fm + content, if_match=if_match)
        self._diag.append({
            "op": "write",
            "key": key,
            "writer": self._writer,
            "source": source,
            "etag": etag,
        })
        for k, reason in dropped:
            self._diag.append({
                "op": "merge-drop-field",
                "key": key,
                "field": k,
                "reason": reason,
            })
        return etag

    def delete(self, key: str, if_match: Optional[str] = None) -> None:
        self._backend.delete(key, if_match=if_match)
        self._diag.append({
            "op": "delete",
            "key": key,
            "writer": self._writer,
        })

    def list(
        self,
        prefix: str = "",
        cursor: Optional[str] = None,
        max_items: int = 100,
    ) -> Tuple[List[Entry], Optional[str]]:
        return self._backend.list(prefix, cursor, max_items)

    def search(self, prefix: str, query: str, max_hits: int = 50) -> list:
        return self._backend.search(prefix, query, max_hits)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_zones.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/zones.py tests/test_zones.py
git commit -m "feat(zones): PersistentZone with source-user gate, secret refusal, diagnostic log"
```

---

### Task 5.3: VFS top-level entry point + config.toml

**Files:**
- Create: `vfs/core.py`
- Create: `vfs/config.py`
- Create: `tests/test_core.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_core.py
import os
import pytest
from pathlib import Path
from vfs.core import VFS, init_project
from vfs.types import ValidationError, NotFoundError


def test_init_creates_layout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    init_project(tmp_path)
    assert (tmp_path / ".vfs").is_dir()
    assert (tmp_path / ".vfs" / "config.toml").is_file()
    assert (tmp_path / ".vfs" / "persistent").is_dir()
    assert (tmp_path / ".vfs" / "temp").is_dir()


def test_init_refuses_existing(tmp_path):
    (tmp_path / ".vfs").mkdir()
    with pytest.raises(ValidationError, match="already exists"):
        init_project(tmp_path)


def test_vfs_constructs(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VFS_PROJECT_ROOT", raising=False)
    v = VFS()
    assert v.project_id  # uuid populated
    assert v.root == tmp_path
    assert v.persistent is not None
    assert v.temp is not None
    v.close()


def test_vfs_writer_id_from_env(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("VFS_WRITER", "my-named-agent")
    v = VFS()
    assert v.writer_id == "my-named-agent"
    v.close()


def test_vfs_writer_id_default(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VFS_WRITER", raising=False)
    v = VFS()
    assert v.writer_id == "agent"
    v.close()


def test_vfs_explicit_root(tmp_path, monkeypatch):
    other = tmp_path / "other"
    init_project(other)
    v = VFS(root=str(other))
    assert v.root == other
    v.close()


def test_vfs_old_writer_id_kwarg_rejected(tmp_path, monkeypatch):
    init_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(TypeError):
        VFS(writer_id="x")  # removed kwarg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_core.py -v`
Expected: `ImportError`

- [ ] **Step 3: Implement `vfs/config.py` with a hand-rolled TOML reader**

The full TOML spec is more than we need. `config.toml` has exactly three keys with known types (`schema_version = <int>`, `project_id = "<uuid>"`, `created_at = "<iso>"`), so a tiny parser keeps the package stdlib-only on Python 3.9 / 3.10 without depending on `tomli`. The reader rejects anything outside this shape — we control the writer, so unfamiliar content is a tampering signal.

```python
"""Per-project .vfs/config.toml — schema version and project UUID.

Hand-rolled minimal TOML reader: three known keys, strict shape. Keeps
the stdlib-only claim consistent across Python 3.9, 3.10, 3.11, 3.12
(tomllib only landed in 3.11).
"""
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


CONFIG_FILENAME = "config.toml"
SCHEMA_VERSION = 1

_INT_LINE = re.compile(r'^(\w+)\s*=\s*(\d+)$')
_STR_LINE = re.compile(r'^(\w+)\s*=\s*"([^"\x00-\x1f]*)"$')


def write_config(vfs_dir: Path, project_id: Optional[str] = None) -> str:
    """Write a fresh config.toml. Returns the project_id."""
    pid = project_id or str(uuid.uuid4())
    content = (
        f"schema_version = {SCHEMA_VERSION}\n"
        f'project_id = "{pid}"\n'
        f'created_at = "{datetime.now(timezone.utc).isoformat()}"\n'
    )
    config_path = vfs_dir / CONFIG_FILENAME
    old_umask = os.umask(0o077)
    try:
        config_path.write_text(content, encoding="utf-8")
        os.chmod(config_path, 0o600)
    finally:
        os.umask(old_umask)
    return pid


def read_config(vfs_dir: Path) -> dict:
    """Read .vfs/config.toml. Raises FileNotFoundError if missing,
    ValueError if the file's shape doesn't match the three known keys.
    """
    config_path = vfs_dir / CONFIG_FILENAME
    out: dict = {}
    with open(config_path, "r", encoding="utf-8") as fp:
        for lineno, raw in enumerate(fp, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = _INT_LINE.match(line)
            if m:
                out[m.group(1)] = int(m.group(2))
                continue
            m = _STR_LINE.match(line)
            if m:
                out[m.group(1)] = m.group(2)
                continue
            raise ValueError(
                f"{config_path}:{lineno}: unparseable config line: {line!r}"
            )
    missing = {"schema_version", "project_id", "created_at"} - set(out)
    if missing:
        raise ValueError(
            f"{config_path}: missing required keys {sorted(missing)}"
        )
    return out
```

- [ ] **Step 4: Implement `vfs/core.py`**

```python
"""VFS top-level entry point: VFS() and init_project()."""
import os
import re
from pathlib import Path
from typing import Optional

from vfs.backends.localfs import LocalFSBackend
from vfs.config import read_config, write_config
from vfs.diagnostic import DiagnosticLog
from vfs.paths import resolve_project_root
from vfs.types import ValidationError
from vfs.zones import PersistentZone, TempZone


_WRITER_ID_PATTERN = re.compile(r"^[\w.-]+$")


def _validated_writer_id() -> str:
    """Read $VFS_WRITER and validate against [\\w.-]+ (no control chars).

    Closes ANSI-escape injection into `vfs review` output via attacker-
    controlled writer IDs. Refuses on any character outside the allowed
    set rather than sanitizing — sanitization invites future bypass.
    """
    writer = os.environ.get("VFS_WRITER", "agent")
    if not _WRITER_ID_PATTERN.match(writer):
        raise ValidationError(
            f"$VFS_WRITER {writer!r} contains invalid characters; "
            f"allowed: [A-Za-z0-9_.-]+"
        )
    return writer


def init_project(root: Path) -> dict:
    """Create .vfs/ structure at `root`. Refuses if one exists."""
    root = Path(root)
    vfs_dir = root / ".vfs"
    if vfs_dir.exists():
        raise ValidationError(f".vfs/ already exists at {vfs_dir}")
    old_umask = os.umask(0o077)
    try:
        vfs_dir.mkdir(mode=0o700)
        (vfs_dir / "persistent").mkdir(mode=0o700)
        (vfs_dir / "temp").mkdir(mode=0o700)
    finally:
        os.umask(old_umask)
    pid = write_config(vfs_dir)
    return {"project_id": pid, "root": str(root)}


class VFS:
    """Top-level handle. Resolves .vfs/ on construction.

    Construction does NOT accept writer_id — it reads $VFS_WRITER and
    validates it. Cross-project access via VFS(root=...).

    `strict_perms=True` (default) propagates to the LocalFSBackend ctors,
    which refuse to operate on a .vfs/ with loose perms — re-checked
    each session, not just at init.
    """

    def __init__(
        self,
        root: Optional[str] = None,
        *,
        source_user_allowed: bool = False,
        strict_perms: bool = True,
    ) -> None:
        if root is None:
            self.root = resolve_project_root()
        else:
            self.root = Path(root).resolve()
            if not (self.root / ".vfs").is_dir():
                raise ValidationError(
                    f"no .vfs/ at {root!r}"
                )

        config = read_config(self.root / ".vfs")
        self.project_id = config["project_id"]
        self.writer_id = _validated_writer_id()

        self._persistent_backend = LocalFSBackend(
            str(self.root / ".vfs" / "persistent"),
            strict_perms=strict_perms,
        )
        self._temp_backend = LocalFSBackend(
            str(self.root / ".vfs" / "temp"),
            strict_perms=strict_perms,
        )
        self._diag = DiagnosticLog(str(self.root / ".vfs" / "diagnostic.log"))

        self.persistent = PersistentZone(
            backend=self._persistent_backend,
            diag=self._diag,
            writer_id=self.writer_id,
            project_id=self.project_id,
            source_user_allowed=source_user_allowed,
        )
        self.temp = TempZone(self._temp_backend)

    def close(self) -> None:
        self._persistent_backend.close()
        self._temp_backend.close()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_core.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add vfs/core.py vfs/config.py tests/test_core.py
git commit -m "feat(core): VFS entry point + init_project + config.toml"
```

---

### Task 5.4: TempZone GC sweep + `vfs gc` subcommand

Spec promises a 7-day sweep on the temp zone. This task adds both an opportunistic sweep at `VFS()` init (rate-limited via a stamp file) and an explicit `vfs gc` agent-callable command.

**Files:**
- Modify: `vfs/core.py`
- Create: `vfs/gc.py`
- Create: `tests/test_gc.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_gc.py
import os
import time
from pathlib import Path
from vfs.gc import sweep_temp_zone


def test_sweep_removes_old(tmp_path):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    old = temp_dir / "old.md"
    fresh = temp_dir / "fresh.md"
    old.write_text("x")
    fresh.write_text("y")
    # Backdate `old` to 10 days ago
    ten_days_ago = time.time() - 10 * 86400
    os.utime(old, (ten_days_ago, ten_days_ago))

    removed = sweep_temp_zone(str(temp_dir), cutoff_seconds=7 * 86400)
    assert removed == ["old.md"]
    assert not old.exists()
    assert fresh.exists()


def test_sweep_skips_symlinks(tmp_path):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    real = tmp_path / "outside.md"
    real.write_text("OUTSIDE")
    link = temp_dir / "shortcut.md"
    link.symlink_to(real)
    # Backdate via lutime where supported; otherwise the symlink mtime
    # may already be 'old' depending on FS. The point is sweep should not
    # follow the link.
    removed = sweep_temp_zone(str(temp_dir), cutoff_seconds=0)
    assert "shortcut.md" not in removed  # symlinks not swept
    assert real.exists()


def test_sweep_idempotent_via_stamp(tmp_path, monkeypatch):
    """Opportunistic sweep at VFS() init should only fire once/day."""
    from vfs.gc import opportunistic_sweep
    vfs_dir = tmp_path / ".vfs"
    (vfs_dir / "temp").mkdir(parents=True)
    fired_first = opportunistic_sweep(vfs_dir)
    fired_second = opportunistic_sweep(vfs_dir)
    assert fired_first is True
    assert fired_second is False  # stamp file says we already swept today
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_gc.py -v`
Expected: `ImportError`

- [ ] **Step 3: Implement `vfs/gc.py`**

```python
"""TempZone garbage collection — 7-day sweep, symlink-safe."""
import os
import time
from pathlib import Path
from typing import List


DEFAULT_CUTOFF_SECONDS = 7 * 86400
STAMP_FILENAME = ".gc-last-run"
STAMP_INTERVAL_SECONDS = 86400  # once per day


def sweep_temp_zone(temp_dir: str, cutoff_seconds: int = DEFAULT_CUTOFF_SECONDS) -> List[str]:
    """Remove regular files in `temp_dir` whose mtime is older than the cutoff.

    Symlinks are explicitly skipped (no following). Subdirs are not traversed
    in v1 — temp is supposed to be flat.

    Returns the list of removed file names (relative to temp_dir).
    """
    removed: List[str] = []
    threshold = time.time() - cutoff_seconds
    try:
        entries = os.listdir(temp_dir)
    except FileNotFoundError:
        return removed
    for name in entries:
        full = os.path.join(temp_dir, name)
        try:
            st = os.lstat(full)
        except OSError:
            continue
        import stat as _stat
        if _stat.S_ISLNK(st.st_mode):
            continue
        if not _stat.S_ISREG(st.st_mode):
            continue
        if st.st_mtime >= threshold:
            continue
        try:
            os.unlink(full)
        except OSError:
            continue
        removed.append(name)
    return removed


def opportunistic_sweep(vfs_dir: Path) -> bool:
    """Run a sweep iff the stamp file says we haven't recently. Returns
    True if the sweep fired, False if it was skipped this call.
    """
    vfs_dir = Path(vfs_dir)
    stamp = vfs_dir / STAMP_FILENAME
    now = time.time()
    try:
        last = stamp.stat().st_mtime
        if now - last < STAMP_INTERVAL_SECONDS:
            return False
    except FileNotFoundError:
        pass
    sweep_temp_zone(str(vfs_dir / "temp"))
    old_umask = os.umask(0o077)
    try:
        stamp.touch(mode=0o600, exist_ok=True)
        os.utime(stamp, (now, now))
    finally:
        os.umask(old_umask)
    return True
```

- [ ] **Step 4: Wire opportunistic sweep into VFS.__init__**

In `vfs/core.py`, after `self._diag = DiagnosticLog(...)` in `VFS.__init__`, add:

```python
        from vfs.gc import opportunistic_sweep
        try:
            opportunistic_sweep(self.root / ".vfs")
        except Exception:
            # GC failure must not block VFS construction
            pass
```

- [ ] **Step 5: Add `vfs gc` subcommand to CLI**

In `vfs/cli.py`, add:

```python
def _cmd_gc(args) -> int:
    from vfs.gc import sweep_temp_zone
    v = VFS()
    try:
        removed = sweep_temp_zone(str(v.root / ".vfs" / "temp"))
        if args.json:
            print(json.dumps({"removed": removed}))
        else:
            for name in removed:
                print(f"removed: {name}")
            print(f"swept {len(removed)} file(s)", file=sys.stderr)
        return EXIT_OK
    finally:
        v.close()
```

Add to `build_parser`:

```python
    gc = sub.add_parser("gc", help="sweep temp/ entries older than 7 days")
    gc.set_defaults(_func=_cmd_gc)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_gc.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add vfs/gc.py vfs/core.py vfs/cli.py tests/test_gc.py
git commit -m "feat(gc): temp-zone 7-day sweep + vfs gc subcommand"
```

---

## Phase 6 — CLI

### Task 6.1: CLI skeleton + exit codes + init command

**Files:**
- Create: `vfs/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cli.py
import subprocess
import sys
from pathlib import Path


def _vfs(*args, cwd=None, env=None, input=None, check=False):
    cmd = [sys.executable, "-m", "vfs.cli", *args]
    env_full = {**__import__("os").environ}
    if env:
        env_full.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env_full,
        input=input,
        capture_output=True,
        text=True,
        check=check,
    )


def test_version(tmp_path):
    r = _vfs("version")
    assert r.returncode == 0
    assert "1.0.0" in r.stdout


def test_init_basic(tmp_path):
    r = _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
    assert (tmp_path / ".vfs").is_dir()
    assert (tmp_path / ".vfs" / "config.toml").is_file()


def test_init_refuses_double(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode != 0
    assert "already" in r.stderr.lower()


def test_whoami(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("whoami", cwd=tmp_path, env={"HOME": str(tmp_path), "VFS_WRITER": "test-agent"})
    assert r.returncode == 0
    assert "test-agent" in r.stdout
    assert str(tmp_path) in r.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: ModuleNotFoundError / non-zero exit

- [ ] **Step 3: Implement `vfs/cli.py` (skeleton + init + whoami + version)**

```python
"""vfs CLI entry point."""
import argparse
import json
import os
import sys
from pathlib import Path

from vfs import __version__
from vfs.core import VFS, init_project
from vfs.types import (
    ConflictError, NotFoundError, PermissionGateError,
    ValidationError, VFSError, ZoneViolationError,
)


# Exit codes
EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_NOT_FOUND = 2
EXIT_CONFLICT = 3
EXIT_VALIDATION = 4
EXIT_PERMISSION = 5


def _exit_for(exc: Exception) -> int:
    if isinstance(exc, NotFoundError):
        return EXIT_NOT_FOUND
    if isinstance(exc, ConflictError):
        return EXIT_CONFLICT
    if isinstance(exc, (ValidationError, ZoneViolationError)):
        return EXIT_VALIDATION
    if isinstance(exc, PermissionGateError):
        return EXIT_PERMISSION
    return EXIT_GENERIC


def _cmd_init(args) -> int:
    try:
        result = init_project(Path.cwd())
    except ValidationError as e:
        print(f"vfs init: {e}", file=sys.stderr)
        return EXIT_VALIDATION
    print(f"initialized .vfs/ (project_id={result['project_id']})")
    print(f"suggestion: echo '.vfs/' >> .gitignore", file=sys.stderr)
    return EXIT_OK


def _cmd_whoami(args) -> int:
    try:
        v = VFS()
    except VFSError as e:
        print(f"vfs whoami: {e}", file=sys.stderr)
        return _exit_for(e)
    try:
        output = {
            "writer_id": v.writer_id,
            "project_id": v.project_id,
            "root": str(v.root),
        }
        if getattr(args, "json", False):
            print(json.dumps(output))
        else:
            for k, val in output.items():
                print(f"{k}: {val}")
        return EXIT_OK
    finally:
        v.close()


def _cmd_version(args) -> int:
    print(f"agent-vfs {__version__}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vfs", description="agent-vfs CLI")
    p.add_argument("--json", action="store_true", help="JSON output where applicable")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create .vfs/ in CWD").set_defaults(_func=_cmd_init)
    sub.add_parser("whoami", help="print writer/project/root").set_defaults(_func=_cmd_whoami)
    sub.add_parser("version", help="print version").set_defaults(_func=_cmd_version)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args._func(args)
    except VFSError as e:
        print(f"vfs: {e}", file=sys.stderr)
        return _exit_for(e)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/cli.py tests/test_cli.py
git commit -m "feat(cli): skeleton with init, whoami, version + exit code map"
```

---

### Task 6.2: CLI read/write/list/delete/search

**Files:**
- Modify: `vfs/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
def test_write_and_read(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("write", "notes/foo.md",
             cwd=tmp_path, env={"HOME": str(tmp_path)},
             input="hello world")
    assert r.returncode == 0
    r = _vfs("read", "notes/foo.md",
            cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
    assert r.stdout == "hello world"


def test_write_rejects_source_user(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("write", "--source", "user", "foo.md",
             cwd=tmp_path, env={"HOME": str(tmp_path)},
             input="x")
    assert r.returncode == 4


def test_write_rejects_secret(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("write", "foo.md",
             cwd=tmp_path, env={"HOME": str(tmp_path)},
             input="AKIAIOSFODNN7EXAMPLE")
    assert r.returncode == 4


def test_list_basic(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    _vfs("write", "a.md", cwd=tmp_path, env={"HOME": str(tmp_path)}, input="1")
    _vfs("write", "b.md", cwd=tmp_path, env={"HOME": str(tmp_path)}, input="2")
    r = _vfs("list", "--json", cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
    import json
    lines = [json.loads(l) for l in r.stdout.strip().split("\n")]
    assert {l["key"] for l in lines} == {"a.md", "b.md"}


def test_delete(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    _vfs("write", "foo.md", cwd=tmp_path, env={"HOME": str(tmp_path)}, input="x")
    r = _vfs("delete", "foo.md", cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
    r = _vfs("read", "foo.md", cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 2


def test_search(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    _vfs("write", "a.md", cwd=tmp_path, env={"HOME": str(tmp_path)},
         input="contains needle here")
    r = _vfs("search", "needle", "--json",
            cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
    import json
    lines = [json.loads(l) for l in r.stdout.strip().split("\n")]
    assert any("needle" in l["snippet"] for l in lines)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli.py -v -k "write_and_read or list_basic or delete or search or rejects"`
Expected: non-zero exit (subcommands missing)

- [ ] **Step 3: Implement read/write/list/delete/search subcommands**

Insert into `vfs/cli.py` before `build_parser`:

```python
def _cmd_read(args) -> int:
    v = VFS()
    try:
        if args.zone == "temp":
            content = v.temp.read(args.key, offset=args.offset or 0,
                                  limit=args.limit)
            sys.stdout.write(content)
        else:
            body, fm = v.persistent.read(args.key)
            if args.json:
                print(json.dumps({"body": body, "frontmatter": fm}))
            else:
                sys.stdout.write(body)
        return EXIT_OK
    finally:
        v.close()


def _cmd_write(args) -> int:
    v = VFS()
    try:
        content = sys.stdin.read()
        if args.zone == "temp":
            etag = v.temp.write(args.key, content)
        else:
            etag = v.persistent.write(
                args.key,
                content,
                source=args.source,
                if_match=args.if_match,
                allow_secret=args.allow_secret,
            )
        if args.json:
            print(json.dumps({"etag": etag}))
        else:
            print(etag)
        return EXIT_OK
    finally:
        v.close()


def _cmd_list(args) -> int:
    v = VFS()
    try:
        zone = v.temp if args.zone == "temp" else v.persistent
        entries, cursor = zone.list(
            prefix=args.prefix or "",
            cursor=args.cursor,
            max_items=args.max or 100,
        )
        for e in entries:
            row = {"key": e.key, "size": e.size, "mtime": e.mtime, "etag": e.etag}
            print(json.dumps(row) if args.json else f"{e.key}\t{e.size}\t{e.etag}")
        if cursor and args.json:
            print(json.dumps({"_cursor": cursor}))
        return EXIT_OK
    finally:
        v.close()


def _cmd_delete(args) -> int:
    v = VFS()
    try:
        zone = v.temp if args.zone == "temp" else v.persistent
        zone.delete(args.key, if_match=args.if_match) if args.zone != "temp" else zone.delete(args.key)
        return EXIT_OK
    finally:
        v.close()


def _cmd_search(args) -> int:
    v = VFS()
    try:
        zone = v.temp if args.zone == "temp" else v.persistent
        hits = zone.search(prefix=args.prefix or "", query=args.query,
                           max_hits=args.max or 50)
        for h in hits:
            print(json.dumps(h) if args.json else f"{h['key']}:{h['line']}: {h['snippet']}")
        return EXIT_OK
    finally:
        v.close()


def _add_zone_arg(p):
    """Each command except init/whoami/version takes an implicit zone."""
    pass  # zone is set via dispatch (read vs temp.read)
```

Update `build_parser` to add subparsers for read/write/list/delete/search. Replace the existing function body:

```python
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vfs", description="agent-vfs CLI")
    p.add_argument("--json", action="store_true", help="JSON output where applicable")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(_func=_cmd_init)
    sub.add_parser("whoami").set_defaults(_func=_cmd_whoami)
    sub.add_parser("version").set_defaults(_func=_cmd_version)

    def _add_io_args(sp, *, with_offset_limit=False, with_cas=False,
                     with_source=False, with_allow_secret=False):
        sp.add_argument("key")
        if with_offset_limit:
            sp.add_argument("--offset", type=int)
            sp.add_argument("--limit", type=int)
        if with_cas:
            sp.add_argument("--if-match", dest="if_match", default=None)
        if with_source:
            sp.add_argument("--source", default="agent",
                            help="agent | tool:NAME | web:DOMAIN")
        if with_allow_secret:
            sp.add_argument("--allow-secret", action="store_true",
                            dest="allow_secret")

    for zone in ("persistent", "temp"):
        prefix = "" if zone == "persistent" else "temp."
        rp = sub.add_parser(f"{prefix}read")
        rp.set_defaults(_func=_cmd_read, zone=zone)
        _add_io_args(rp, with_offset_limit=True)

        wp = sub.add_parser(f"{prefix}write")
        wp.set_defaults(_func=_cmd_write, zone=zone)
        _add_io_args(wp, with_cas=True, with_source=(zone == "persistent"),
                     with_allow_secret=(zone == "persistent"))

        dp = sub.add_parser(f"{prefix}delete")
        dp.set_defaults(_func=_cmd_delete, zone=zone)
        _add_io_args(dp, with_cas=(zone == "persistent"))

        lp = sub.add_parser(f"{prefix}list")
        lp.set_defaults(_func=_cmd_list, zone=zone)
        lp.add_argument("--prefix")
        lp.add_argument("--cursor")
        lp.add_argument("--max", type=int)

        sp = sub.add_parser(f"{prefix}search")
        sp.set_defaults(_func=_cmd_search, zone=zone)
        sp.add_argument("query")
        sp.add_argument("--prefix")
        sp.add_argument("--max", type=int)

    return p
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/cli.py tests/test_cli.py
git commit -m "feat(cli): read/write/list/delete/search for persistent + temp"
```

---

### Task 6.3: TTY-gated human surface (`vfs remember`, `vfs --root`)

**Files:**
- Modify: `vfs/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
def test_remember_as_user_refuses_no_tty(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs("remember", "--as-user", "foo.md",
             cwd=tmp_path, env={"HOME": str(tmp_path)},
             input="my fact")
    assert r.returncode == 5  # PermissionGate


def test_root_without_as_user_refused(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    _vfs("init", cwd=other, env={"HOME": str(tmp_path)})
    r = _vfs("--root", str(other), "read", "x",
             cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 5


def test_vfs_project_root_env_is_ignored(tmp_path):
    """$VFS_PROJECT_ROOT was removed for security; setting it must not
    redirect resolution. The CLI walks from CWD or accepts --root only."""
    real = tmp_path / "real"
    real.mkdir()
    _vfs("init", cwd=real, env={"HOME": str(tmp_path)})
    fake = tmp_path / "fake"
    fake.mkdir()
    _vfs("init", cwd=fake, env={"HOME": str(tmp_path)})
    # CWD is real/, env points at fake/. CLI must read from real/.
    _vfs("write", "marker.md", cwd=real, env={"HOME": str(tmp_path)}, input="REAL")
    r = _vfs("read", "marker.md",
             cwd=real,
             env={"HOME": str(tmp_path), "VFS_PROJECT_ROOT": str(fake)})
    assert r.returncode == 0
    assert r.stdout == "REAL"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli.py -v -k "remember or root"`
Expected: non-zero (subcommands missing)

- [ ] **Step 3: Implement remember + --root + TTY gate**

Two things to plumb:

1. The `--root` value is passed through to every `VFS(root=...)` constructor call in this invocation — **never** via `os.environ` mutation, which leaks to subprocesses and silently breaks the "no env override" guarantee.
2. All `_cmd_*` handlers need to be updated to read `args.root` (defaulting to `None`) and pass it to `VFS(root=args.root)`.

Insert into `vfs/cli.py`:

```python
def _require_tty():
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise PermissionGateError(
            "this command requires an interactive TTY on both stdin and stdout"
        )


def _vfs_for(args, *, source_user_allowed: bool = False) -> "VFS":
    """Construct a VFS instance, honoring --root from argparse.

    The root value flows through the constructor, never via env mutation.
    """
    root = getattr(args, "root", None)
    return VFS(root=root, source_user_allowed=source_user_allowed)


def _cmd_remember(args) -> int:
    if args.as_user:
        _require_tty()
    v = _vfs_for(args, source_user_allowed=args.as_user)
    try:
        content = sys.stdin.read()
        source = "user" if args.as_user else "agent"
        etag = v.persistent.write(args.key, content, source=source)
        print(etag)
        return EXIT_OK
    finally:
        v.close()
```

Refactor every other `_cmd_*` that previously did `v = VFS()` to `v = _vfs_for(args)`. This includes `_cmd_read`, `_cmd_write`, `_cmd_list`, `_cmd_delete`, `_cmd_search`, `_cmd_review`, `_cmd_migrate`, `_cmd_gc`, `_cmd_whoami`.

Update `build_parser` to add the `remember` subcommand and the top-level `--root` flag:

```python
    p.add_argument("--root",
                   help="cross-project root (requires --as-user on subcommand)")

    rp = sub.add_parser("remember", help="write with source=user (TTY-gated)")
    rp.set_defaults(_func=_cmd_remember)
    rp.add_argument("--as-user", action="store_true", dest="as_user")
    rp.add_argument("key")
```

In `main`, before calling `args._func`, enforce the gate **without** mutating env:

```python
    if getattr(args, "root", None):
        if not getattr(args, "as_user", False):
            print("vfs: --root requires --as-user (TTY-gated)", file=sys.stderr)
            return EXIT_PERMISSION
        _require_tty()  # belt-and-suspenders; --as-user already gates this
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/cli.py tests/test_cli.py
git commit -m "feat(cli): remember + --root with TTY gate, no env override"
```

---

### Task 6.4: Rate limiter (CLI-only)

**Files:**
- Create: `vfs/ratelimit.py`
- Modify: `vfs/cli.py`
- Create: `tests/test_ratelimit.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ratelimit.py
import time
import pytest
from vfs.ratelimit import WriteRateLimiter
from vfs.types import VFSError


def test_under_limit(tmp_path):
    rl = WriteRateLimiter(str(tmp_path / "rl.state"), limit=5, window_s=60)
    for _ in range(5):
        rl.check()


def test_over_limit_raises(tmp_path):
    rl = WriteRateLimiter(str(tmp_path / "rl.state"), limit=3, window_s=60)
    for _ in range(3):
        rl.check()
    with pytest.raises(VFSError, match="rate"):
        rl.check()


def test_window_slides(tmp_path):
    rl = WriteRateLimiter(str(tmp_path / "rl.state"), limit=2, window_s=1)
    rl.check()
    rl.check()
    time.sleep(1.1)
    rl.check()  # window expired
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ratelimit.py -v`
Expected: `ImportError`

- [ ] **Step 3: Implement `vfs/ratelimit.py`**

```python
"""Rate limiter for write ops — soft cap to defeat loop-prompt-injection DoS."""
import fcntl
import json
import os
import time

from vfs.types import VFSError


import stat as _stat


class WriteRateLimiter:
    def __init__(self, state_path: str, limit: int = 300, window_s: int = 60) -> None:
        self.path = state_path
        self.limit = limit
        self.window_s = window_s

    def check(self) -> None:
        now = time.time()
        old_umask = os.umask(0o077)
        try:
            fd = os.open(self.path,
                         os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                         mode=0o600)
        finally:
            os.umask(old_umask)
        try:
            # fstat the FD: must be a regular file owned by current UID,
            # mode 0600, st_nlink == 1. Defeats a same-UID peer pre-planting
            # a hardlink or world-readable file at this path.
            st = os.fstat(fd)
            if not _stat.S_ISREG(st.st_mode):
                raise VFSError(
                    f"rate-limiter state file {self.path!r} is not a regular file"
                )
            if st.st_uid != os.geteuid():
                raise VFSError(
                    f"rate-limiter state file {self.path!r} has unexpected owner"
                )
            if st.st_nlink != 1:
                raise VFSError(
                    f"rate-limiter state file {self.path!r} has st_nlink != 1 (hardlinked?)"
                )
            mode = _stat.S_IMODE(st.st_mode)
            if mode & 0o077:
                raise VFSError(
                    f"rate-limiter state file {self.path!r} has mode {oct(mode)} (must be 0600)"
                )

            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                raw = os.read(fd, 65536).decode("utf-8")
                if not raw:
                    timestamps = []
                else:
                    try:
                        timestamps = json.loads(raw)
                    except json.JSONDecodeError as e:
                        # Do NOT silent-reset: a malicious peer pre-planting
                        # garbage would otherwise be able to clear the limiter.
                        # Surfacing the corruption forces explicit cleanup.
                        raise VFSError(
                            f"rate-limiter state file {self.path!r} is corrupted; "
                            f"delete it manually if intentional: {e}"
                        )
                if not isinstance(timestamps, list):
                    raise VFSError(
                        f"rate-limiter state file {self.path!r} has unexpected shape"
                    )
                cutoff = now - self.window_s
                timestamps = [t for t in timestamps
                              if isinstance(t, (int, float)) and t >= cutoff]
                if len(timestamps) >= self.limit:
                    raise VFSError(
                        f"write rate limit exceeded: "
                        f"{len(timestamps)} writes in last {self.window_s}s "
                        f"(limit {self.limit})"
                    )
                timestamps.append(now)
                os.lseek(fd, 0, os.SEEK_SET)
                os.ftruncate(fd, 0)
                os.write(fd, json.dumps(timestamps).encode("utf-8"))
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
```

- [ ] **Step 4: Wire into CLI write commands**

In `vfs/cli.py`, in `_cmd_write`:

```python
def _cmd_write(args) -> int:
    v = VFS()
    try:
        # Rate limit on the persistent zone only (temp is intentionally unmetered)
        if args.zone == "persistent":
            limit = int(os.environ.get("VFS_MAX_WRITES_PER_MINUTE", "300"))
            rl = WriteRateLimiter(
                str(v.root / ".vfs" / ".ratelimit.state"),
                limit=limit,
                window_s=60,
            )
            rl.check()
        content = sys.stdin.read()
        # ... rest unchanged
```

Add `from vfs.ratelimit import WriteRateLimiter` to imports.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_ratelimit.py tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add vfs/ratelimit.py vfs/cli.py tests/test_ratelimit.py
git commit -m "feat: write rate limiter (300/min default) in CLI"
```

---

### Task 6.5: `vfs review` (diagnostic log pretty-print)

**Files:**
- Modify: `vfs/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
def test_review_shows_diag_entries(tmp_path):
    _vfs("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    _vfs("write", "foo.md", cwd=tmp_path, env={"HOME": str(tmp_path)}, input="x")
    r = _vfs("review", "--json", cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 0
    import json
    lines = [json.loads(l) for l in r.stdout.strip().split("\n")]
    assert any(l.get("op") == "write" and l.get("key") == "foo.md" for l in lines)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli.py -v -k review`
Expected: non-zero

- [ ] **Step 3: Implement review subcommand**

```python
_REVIEW_STRIP = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_for_terminal(s: str) -> str:
    """Strip control + DEL chars before printing to a TTY.

    `$VFS_WRITER` is validated at construction, but pre-existing
    diagnostic.log entries may have been written before the validator
    was in place — sanitize defensively.
    """
    return _REVIEW_STRIP.sub("", s)


def _cmd_review(args) -> int:
    v = _vfs_for(args)
    try:
        log_path = v.root / ".vfs" / "diagnostic.log"
        if not log_path.exists():
            print("(no diagnostic.log yet)", file=sys.stderr)
            return EXIT_OK
        n = args.tail or 50
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        if not lines or lines == [""]:
            return EXIT_OK
        for line in lines[-n:]:
            if args.json:
                # json.dumps already escapes control chars; pass through
                print(line)
            else:
                try:
                    rec = json.loads(line)
                    ts = _sanitize_for_terminal(str(rec.get("ts", "?")))
                    op = _sanitize_for_terminal(str(rec.get("op", "?")))
                    key = _sanitize_for_terminal(str(rec.get("key", "?")))
                    writer = _sanitize_for_terminal(str(rec.get("writer", "?")))
                    print(f"{ts}  {op:8}  {key:40}  by {writer}")
                except json.JSONDecodeError:
                    print(_sanitize_for_terminal(line))
        return EXIT_OK
    finally:
        v.close()
```

Add `import re` to the top of `vfs/cli.py` if not present.

Add to `build_parser`:

```python
    rv = sub.add_parser("review", help="show diagnostic.log tail")
    rv.set_defaults(_func=_cmd_review)
    rv.add_argument("--tail", type=int)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_cli.py -v -k review`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/cli.py tests/test_cli.py
git commit -m "feat(cli): review subcommand for diagnostic.log"
```

---

## Phase 7 — Migration command

### Task 7.1: `vfs migrate`

**Files:**
- Modify: `vfs/cli.py`
- Create: `tests/test_migrate.py`

- [ ] **Step 1: Write failing tests**

Since the migrate CLI is now TTY-gated, tests run against an internal `vfs.migrate.run_migration()` helper instead of subprocess-spawning the CLI. One CLI subprocess test asserts the TTY gate fires.

```python
# tests/test_migrate.py
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from vfs.core import VFS, init_project
from vfs.migrate import run_migration


def _vfs(*args, cwd=None, env=None, input=None):
    cmd = [sys.executable, "-m", "vfs.cli", *args]
    env_full = {**__import__("os").environ}
    if env:
        env_full.update(env)
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, env=env_full,
        input=input, capture_output=True, text=True,
    )


def _setup_legacy(legacy: Path):
    legacy.mkdir(parents=True)
    (legacy / "note1.md").write_text(
        "---\nname: existing\n---\nLegacy body 1",
        encoding="utf-8",
    )
    (legacy / "note2.md").write_text(
        "Legacy body 2 — no frontmatter", encoding="utf-8"
    )


def _migrate_args(**overrides):
    base = {"from_dir": None, "dry_run": False, "delete_source": False,
            "root": None}
    base.update(overrides)
    return SimpleNamespace(**base)


def test_migrate_copies_files(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy"
    _setup_legacy(legacy)
    proj = tmp_path / "proj"
    proj.mkdir()
    init_project(proj)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    v = VFS()
    try:
        result = run_migration(_migrate_args(from_dir=str(legacy)), v)
    finally:
        v.close()
    assert result["migrated"] >= 2
    body1 = (proj / ".vfs" / "persistent" / "note1.md").read_text()
    assert "Legacy body 1" in body1
    assert "writer: vfs-migrate" in body1
    assert "source: agent" in body1
    assert "name: existing" in body1


def test_migrate_dry_run(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy"
    _setup_legacy(legacy)
    proj = tmp_path / "proj"
    proj.mkdir()
    init_project(proj)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    v = VFS()
    try:
        run_migration(_migrate_args(from_dir=str(legacy), dry_run=True), v)
    finally:
        v.close()
    assert not (proj / ".vfs" / "persistent" / "note1.md").exists()


def test_migrate_refuses_user_source(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy"
    _setup_legacy(legacy)
    (legacy / "u.md").write_text(
        "---\nsource: user\n---\nclaim", encoding="utf-8")
    proj = tmp_path / "proj"
    proj.mkdir()
    init_project(proj)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    v = VFS()
    try:
        run_migration(_migrate_args(from_dir=str(legacy)), v)
    finally:
        v.close()
    out = (proj / ".vfs" / "persistent" / "u.md").read_text()
    assert "source: agent" in out
    assert "source: user" not in out


def test_migrate_skips_oversize(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "tiny.md").write_text("ok", encoding="utf-8")
    (legacy / "huge.md").write_text("x" * 10_000_001, encoding="utf-8")
    proj = tmp_path / "proj"
    proj.mkdir()
    init_project(proj)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    v = VFS()
    try:
        result = run_migration(_migrate_args(from_dir=str(legacy)), v)
    finally:
        v.close()
    assert result["skipped"]
    assert (proj / ".vfs" / "persistent" / "tiny.md").exists()
    assert not (proj / ".vfs" / "persistent" / "huge.md").exists()


def test_migrate_refuses_symlink_in_source(tmp_path, monkeypatch):
    """A symlink inside the legacy dir pointing outside must be refused."""
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "real.md").write_text("ok", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("EXFIL", encoding="utf-8")
    (legacy / "leak.md").symlink_to(outside / "secret.md")
    proj = tmp_path / "proj"
    proj.mkdir()
    init_project(proj)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("HOME", str(tmp_path))
    v = VFS()
    try:
        run_migration(_migrate_args(from_dir=str(legacy)), v)
    finally:
        v.close()
    # The symlink is refused; only real.md migrates
    assert (proj / ".vfs" / "persistent" / "real.md").exists()
    assert not (proj / ".vfs" / "persistent" / "leak.md").exists()


def test_migrate_cli_refuses_no_tty(tmp_path):
    """The CLI surface itself refuses without a TTY."""
    legacy = tmp_path / "legacy"
    _setup_legacy(legacy)
    proj = tmp_path / "proj"
    proj.mkdir()
    _vfs("init", cwd=proj, env={"HOME": str(tmp_path)})
    r = _vfs("migrate", "--from", str(legacy),
             cwd=proj, env={"HOME": str(tmp_path)})
    assert r.returncode == 5  # PermissionGate
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_migrate.py -v`
Expected: non-zero exits

- [ ] **Step 3: Implement migrate logic in `vfs/migrate.py`**

The migration logic lives in a separate module so it can be tested directly via the library (without subprocess + TTY). The CLI handler is a thin wrapper that does the TTY check, then calls `run_migration()`.

Create `vfs/migrate.py`:

```python
"""Migration from legacy ~/.claude/projects/<slug>/memory/ to .vfs/persistent/.

Symlink-contained walk of the source directory: refuses symlinks at any
component and ensures realpath stays inside the source. Library callers
invoke `run_migration(args, vfs)` directly; the CLI handler wraps it
with the TTY gate.
"""
import os
import stat as _stat
from pathlib import Path

from vfs.backends.localfs import MAX_OBJECT_SIZE_BYTES
from vfs.frontmatter import parse_frontmatter
from vfs.types import ValidationError


def _collect_md_files(src_root: str) -> list:
    md_files = []
    for dirpath, dirnames, filenames in os.walk(src_root, followlinks=False):
        dirnames[:] = [d for d in dirnames
                       if not os.path.islink(os.path.join(dirpath, d))]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            full = os.path.join(dirpath, fn)
            try:
                fst = os.lstat(full)
            except OSError:
                continue
            if _stat.S_ISLNK(fst.st_mode):
                continue
            real = os.path.realpath(full)
            if not (real == src_root or real.startswith(src_root + os.sep)):
                continue
            md_files.append(full)
    return md_files


def run_migration(args, v) -> dict:
    """Migrate .md files from `args.from_dir` into `v.persistent`.

    Returns {"migrated": [keys], "skipped": [(key, reason)]}.
    Raises ValidationError on missing/invalid source dir.
    """
    src_path = Path(args.from_dir).expanduser().resolve()
    if not src_path.is_dir():
        raise ValidationError(f"{src_path} is not a directory")

    md_files = _collect_md_files(str(src_path))
    if not md_files:
        raise ValidationError(f"no .md files in {src_path}")

    skipped: list = []
    migrated: list = []
    old_writer = v.persistent._writer
    v.persistent._writer = "vfs-migrate"
    try:
        for full in sorted(md_files):
            rel = Path(full).relative_to(src_path)
            rel_key = str(rel).replace(os.sep, "/")
            try:
                raw = Path(full).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                skipped.append((rel_key, f"unreadable: {e}"))
                continue
            fm, body = parse_frontmatter(raw)
            for owned in ("source", "writer", "ts", "project_slug", "etag"):
                fm.pop(owned, None)
            if args.dry_run:
                migrated.append(rel_key)
                continue
            if len(body.encode("utf-8")) > MAX_OBJECT_SIZE_BYTES:
                skipped.append((rel_key, "exceeds 10MB cap"))
                continue
            # Pre-plant a partial-frontmatter file so merge-on-write
            # picks up the preserved (non-VFS-owned) fields.
            dest_dir = v.root / ".vfs" / "persistent" / Path(rel_key).parent
            dest_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            if fm:
                pre = ("---\n"
                       + "".join(f"{k}: {val}\n" for k, val in fm.items())
                       + "---\n")
                (v.root / ".vfs" / "persistent" / rel_key).write_text(
                    pre, encoding="utf-8"
                )
            try:
                v.persistent.write(rel_key, body, source="agent",
                                   allow_secret=True)
                migrated.append(rel_key)
            except ValidationError as e:
                skipped.append((rel_key, str(e)))
        if args.delete_source:
            for rel_key in migrated:
                (src_path / rel_key).unlink(missing_ok=True)
    finally:
        v.persistent._writer = old_writer
    return {"migrated": migrated, "skipped": skipped}
```

- [ ] **Step 4: Implement the CLI wrapper in `vfs/cli.py`**

```python
def _cmd_migrate(args) -> int:
    from vfs.migrate import run_migration

    try:
        _require_tty()
    except PermissionGateError as e:
        print(f"vfs migrate: {e}", file=sys.stderr)
        return EXIT_PERMISSION

    try:
        v = _vfs_for(args)
    except VFSError as e:
        print(f"vfs migrate: {e}", file=sys.stderr)
        return _exit_for(e)
    try:
        try:
            result = run_migration(args, v)
        except ValidationError as e:
            print(f"vfs migrate: {e}", file=sys.stderr)
            return EXIT_VALIDATION
    finally:
        v.close()

    for key in result["migrated"]:
        print(f"migrated: {key}")
    for key, reason in result["skipped"]:
        print(f"skipped: {key} ({reason})", file=sys.stderr)
    return EXIT_OK if not result["skipped"] else EXIT_GENERIC
```

Add subparser:

```python
    mp = sub.add_parser("migrate", help="copy legacy memory dir into .vfs/persistent")
    mp.set_defaults(_func=_cmd_migrate)
    mp.add_argument("--from", dest="from_dir", required=True)
    mp.add_argument("--dry-run", action="store_true", dest="dry_run")
    mp.add_argument("--delete-source", action="store_true", dest="delete_source")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_migrate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vfs/cli.py tests/test_migrate.py
git commit -m "feat(cli): migrate command with dry-run, source-agent restamp, size skip"
```

---

## Phase 8 — Static checks and CI

### Task 8.1: Static checks (no-deps, no-network, no-subprocess)

**Files:**
- Create: `scripts/static_checks.sh`
- Create: `tests/test_static.py`

- [ ] **Step 1: Write the static-check script (AST-based)**

Keyword-grep is bypassable via dynamic-import tricks or string concatenation. Replace with an AST walk over the `vfs/` package that inspects every `Import` and `ImportFrom` node. A small substring scan remains for the patterns AST can't see (e.g., shell call-site builtins).

Create `scripts/static_checks.py`. **Important:** the substring patterns below are deliberately constructed at runtime via concatenation so this script file itself doesn't trip the grep equivalent.

```python
#!/usr/bin/env python3
"""Static security checks: no runtime deps, no banned imports, no shell/eval.

Replaces the earlier grep-based checks, which were bypassable by string
concatenation. AST walk catches direct and aliased imports; the small
substring scan covers the remaining patterns.
"""
import ast
import pathlib
import subprocess
import sys
import zipfile


BANNED_IMPORTS = {
    "urllib", "urllib.request", "urllib.parse", "urllib.error",
    "http", "http.client", "http.server",
    "socket", "ssl", "ftplib", "smtplib", "telnetlib",
    "requests", "httpx", "aiohttp",
    "subprocess",
}

# Constructed at runtime so this file isn't flagged by an equivalent grep.
SHELL_CALL = "o" + "s.system("
EVAL_CALL = "e" + "val("
EXEC_CALL = "e" + "xec("
BANNED_SUBSTRINGS = (SHELL_CALL, EVAL_CALL, EXEC_CALL, "__builtins__")


def _imported_names(tree: ast.AST):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def check_no_banned_imports(pkg_root: pathlib.Path) -> list:
    findings = []
    for py in sorted(pkg_root.rglob("*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as e:
            findings.append((py, f"unparseable: {e}"))
            continue
        for name in _imported_names(tree):
            for banned in BANNED_IMPORTS:
                if name == banned or name.startswith(banned + "."):
                    findings.append((py, name))
    return findings


def check_no_banned_substrings(pkg_root: pathlib.Path) -> list:
    findings = []
    for py in sorted(pkg_root.rglob("*.py")):
        src = py.read_text(encoding="utf-8")
        for pattern in BANNED_SUBSTRINGS:
            if pattern in src:
                findings.append((py, pattern))
    return findings


def check_no_runtime_deps(repo_root: pathlib.Path) -> list:
    dist = repo_root / "dist"
    for old in dist.glob("*.whl"):
        old.unlink()
    subprocess.check_call(
        [sys.executable, "-m", "build", "--wheel", "-q"],
        cwd=str(repo_root),
    )
    wheels = list(dist.glob("*.whl"))
    if not wheels:
        return [("build", "no wheel produced")]
    findings = []
    with zipfile.ZipFile(wheels[0]) as zf:
        for name in zf.namelist():
            if name.endswith("METADATA"):
                content = zf.read(name).decode("utf-8")
                for line in content.split("\n"):
                    if line.startswith("Requires-Dist:"):
                        findings.append((wheels[0].name, line))
    return findings


def main():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    pkg_root = repo_root / "vfs"
    failed = False

    print("[1/3] no banned imports (AST)")
    findings = check_no_banned_imports(pkg_root)
    if findings:
        for f, name in findings:
            print(f"  FAIL: {f}: imports {name!r}")
        failed = True
    else:
        print("  ok")

    print("[2/3] no banned substrings")
    findings = check_no_banned_substrings(pkg_root)
    if findings:
        for f, pat in findings:
            print(f"  FAIL: {f}: contains {pat!r}")
        failed = True
    else:
        print("  ok")

    print("[3/3] no runtime deps in built wheel")
    findings = check_no_runtime_deps(repo_root)
    if findings:
        for f, line in findings:
            print(f"  FAIL: {f}: {line}")
        failed = True
    else:
        print("  ok")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

Note: this script is intentionally located outside `vfs/` so it doesn't scan itself.

- [ ] **Step 2: Add a Python wrapper test that invokes the script**

```python
# tests/test_static.py
import subprocess
import sys
from pathlib import Path


def test_static_checks_pass():
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "static_checks.py")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"static checks failed:\n{r.stdout}\n{r.stderr}"
```

- [ ] **Step 3: Add `build` to dev deps**

In `pyproject.toml`, replace the `dev` line in `[project.optional-dependencies]`:

```toml
dev = ["pytest>=7.0", "pytest-timeout>=2.0", "build>=1.0"]
```

- [ ] **Step 4: Run the static checks**

Run: `.venv/bin/python scripts/static_checks.py`
Expected: `[1/3]`, `[2/3]`, `[3/3]` all `ok`, exit 0.

- [ ] **Step 5: Run the python wrapper**

Run: `.venv/bin/pytest tests/test_static.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/static_checks.py tests/test_static.py pyproject.toml
git commit -m "feat: AST-based static checks (no-deps, no-banned-imports, no-shell)"
```

---

### Task 8.2: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
        python-version: ["3.9", "3.10", "3.11", "3.12"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Run tests
        run: pytest -v --timeout=30
      - name: Static checks
        run: python scripts/static_checks.py
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: matrix on ubuntu+macos × py 3.9–3.12 with static checks"
```

---

### Task 8.3: Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Write the Makefile**

```makefile
.PHONY: verify verify-fast perms-check static install dev clean

PYTHON ?= .venv/bin/python
PIP    ?= .venv/bin/pip
PYTEST ?= .venv/bin/pytest

dev:
	python3 -m venv .venv
	$(PIP) install -e ".[dev]"

verify:
	$(PYTEST) -v --timeout=30
	$(PYTHON) scripts/static_checks.py

verify-fast:
	$(PYTEST) -v --timeout=10 -x --ignore=tests/test_static.py

perms-check:
	@stat -f %p .vfs 2>/dev/null | grep -q '40700' && echo "  perms OK" || (echo "  BAD perms on .vfs"; exit 1)

static:
	$(PYTHON) scripts/static_checks.py

clean:
	rm -rf .pytest_cache dist build *.egg-info .coverage
	find . -name __pycache__ -exec rm -rf {} +
```

- [ ] **Step 2: Verify `make verify` works**

Run: `make verify`
Expected: all tests pass + static checks pass

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "build: Makefile with verify/verify-fast/perms-check targets"
```

---

## Phase 9 — Documentation and release prep

### Task 9.1: README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the full README**

```markdown
# agent-vfs

Hardened, agent-agnostic file system for memory and scratch. Per-project `.vfs/` directory, like `.git`. Usable from any agent that can shell out — Claude Code, Codex, Copilot, Cursor.

## Install

```bash
pipx install agent-vfs   # for the CLI
pip install agent-vfs    # for library use
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

## Trust model

- `vfs write` agent-level surface; `source` defaults to `agent`. Cannot be promoted to `user`.
- `vfs remember --as-user` is the human surface — TTY-gated. Use it when YOU are recording a fact, not when an agent is.
- `vfs --root /abs/other --as-user` is the only way to access another project's `.vfs/`.

See `docs/superpowers/specs/2026-05-27-generic-vfs-design.md` for the full security model.

## What's stored where

```
<project-root>/
└── .vfs/
    ├── config.toml          # schema_version, project UUID
    ├── persistent/          # frontmatter-tagged, survives sessions
    ├── temp/                # flat, ephemeral, no frontmatter
    └── diagnostic.log       # append-only JSONL of all writes/deletes
```

Add `.vfs/` to your `.gitignore`. The CLI suggests this on `vfs init`.

## License

MIT.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README quickstart and trust model"
```

---

### Task 9.2: SECURITY.md

**Files:**
- Create: `SECURITY.md`

- [ ] **Step 1: Write `SECURITY.md`**

```markdown
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
- Cryptographic attribution between writers.

## Controls

See `docs/superpowers/specs/2026-05-27-generic-vfs-design.md` section "Security model" for the full enumeration. Highlights:

- All file access via `O_DIRECTORY` root FD + per-component `O_NOFOLLOW`. Defeats symlink escape and TOCTOU.
- `source=user` is TTY-gated. No env override exists by design.
- Cross-project access (`--root`) requires TTY (`--as-user`).
- `O_CREAT|O_EXCL` for CAS-create.
- 10 MB enforced size cap on writes.
- 0700 / 0600 perms with `os.umask` and explicit chmod.
- Stdlib-only forever. CI asserts zero `Requires-Dist` in built wheels.
- PyPI trusted publishing (OIDC), no long-lived tokens.

## Out-of-the-box behavior

After `vfs init`, your `.vfs/` is 0700 with files 0600. The CLI refuses to operate on a `.vfs/` with looser perms — fix them or `vfs init` fresh.

If `vfs review` shows a write you didn't expect from `writer: agent`, that's the diagnostic surface working as designed.
```

- [ ] **Step 2: Commit**

```bash
git add SECURITY.md
git commit -m "docs: SECURITY.md threat model and reporting"
```

---

### Task 9.3: CHANGELOG

**Files:**
- Create: `CHANGELOG.md`

- [ ] **Step 1: Write `CHANGELOG.md`**

```markdown
# Changelog

## 1.0.0a0 — 2026-05-27

Initial release of `agent-vfs`, the generic successor to the in-tree `vfs` package.

### Added
- CLI: `vfs init / read / write / list / delete / search / temp.* / whoami / version / remember / review / migrate`.
- Per-project `.vfs/` directory layout with `config.toml` carrying schema version and project UUID.
- TTY-gated human surface for `--as-user` and `--root`; no env override.
- Symlink-resistant traversal via `O_DIRECTORY` root FD + `O_NOFOLLOW` per component.
- 10 MB enforced write size cap; `VFS_MAX_FILES` / `VFS_MAX_BYTES_PER_FILE` traversal bounds.
- Secret-shape refusal for AWS keys, GitHub PATs, JWTs. Bypass via `--allow-secret` (TTY-gated).
- Append-only `diagnostic.log` with `fcntl.flock` for same-UID safe concurrent writes.
- Write rate limiter (300/min default).
- Stdlib-only; zero runtime dependencies enforced in CI.

### Changed from in-tree v0.5
- `VFS(writer_id=...)` removed; reads `$VFS_WRITER` instead.
- `PersistentZone.read/list/search` no longer accept `project=` kwarg.
- Storage moved from `~/.claude/projects/<slug>/memory/` to `<project>/.vfs/`.
- Project identity is `config.toml::project_id` (UUID), not CWD slug.
- File perms hardened to 0700 / 0600 by default; `vfs init` refuses loose perms.
- CAS-create uses `O_CREAT|O_EXCL` rather than mtime-based existence check.
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: CHANGELOG for 1.0.0a0"
```

---

## Phase 10 — Adversarial test consolidation

### Task 10.1: TOCTOU stress test

**Files:**
- Create: `tests/test_adversarial.py`

- [ ] **Step 1: Write the chaos test**

```python
# tests/test_adversarial.py
import os
import threading
import time
import pytest
from vfs.backends.localfs import LocalFSBackend
from vfs.types import ZoneViolationError


@pytest.mark.timeout(30)
def test_toctou_symlink_swap(tmp_path):
    """Adversary thread swaps a path component between symlink and real dir;
    writer must never land outside root.

    Realism notes vs the earlier weak draft:
      - threading.Barrier ensures adversary and writer start simultaneously
      - N=10_000 to expand the race window enough that at least one swap
        coincides with the write's open() syscall
      - `assert violations > 0` proves the race actually fired (i.e., the
        adversary thread was effective) — a test that always passes by
        seeing zero violations proves only that the write never raced.
    """
    backend = LocalFSBackend(str(tmp_path))
    outside = tmp_path.parent / "outside-sentinel"
    outside.mkdir()
    sentinel = outside / "DO_NOT_OVERWRITE.txt"
    sentinel.write_text("INTACT", encoding="utf-8")

    stop = threading.Event()
    barrier = threading.Barrier(2)

    def adversary():
        barrier.wait()
        path = tmp_path / "swappable"
        while not stop.is_set():
            try:
                if path.is_symlink() or path.exists():
                    if path.is_symlink() or path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        # Empty + rmdir; ignore failure
                        try:
                            for child in path.iterdir():
                                child.unlink()
                        except OSError:
                            pass
                        try:
                            path.rmdir()
                        except OSError:
                            pass
                path.symlink_to(outside)
            except OSError:
                pass
            try:
                if path.is_symlink():
                    path.unlink()
                path.mkdir(exist_ok=True)
            except OSError:
                pass

    t = threading.Thread(target=adversary, daemon=True)
    t.start()
    barrier.wait()

    violations = 0
    successes = 0
    N = 10_000
    for _ in range(N):
        try:
            backend.write("swappable/inner.md", "agent-content")
            successes += 1
        except (ZoneViolationError, NotFoundError, OSError):
            violations += 1

    stop.set()
    t.join(timeout=2)
    backend.close()

    # Sentinel must be untouched — that's the real safety property
    assert sentinel.read_text() == "INTACT", \
        "sentinel outside root was overwritten — TOCTOU defense failed"
    # And the race must actually have fired, or the test proves nothing
    assert violations > 0, (
        f"expected at least one race violation across {N} iterations; got 0. "
        f"the adversary may not be running concurrently — re-check thread setup."
    )
```

Add `from vfs.types import NotFoundError` to imports.

- [ ] **Step 2: Run the test**

Run: `.venv/bin/pytest tests/test_adversarial.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_adversarial.py
git commit -m "test(adversarial): TOCTOU symlink-swap chaos test"
```

---

### Task 10.2: CAS-create concurrency

**Files:**
- Modify: `tests/test_adversarial.py`

- [ ] **Step 1: Write the test**

Append:

```python
def test_cas_create_concurrent(tmp_path):
    """Many threads racing CAS-create the same key — exactly one wins."""
    backend = LocalFSBackend(str(tmp_path))
    N = 20
    results = []
    barrier = threading.Barrier(N)

    def worker(i):
        barrier.wait()
        try:
            backend.write("racey.md", f"v{i}", if_match="")
            results.append(("ok", i))
        except Exception as e:
            results.append(("err", type(e).__name__))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    backend.close()

    winners = [r for r in results if r[0] == "ok"]
    losers = [r for r in results if r[0] == "err"]
    assert len(winners) == 1, f"expected 1 winner, got {len(winners)}: {results}"
    assert len(losers) == N - 1
    assert all("Conflict" in r[1] for r in losers)
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/pytest tests/test_adversarial.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_adversarial.py
git commit -m "test(adversarial): CAS-create concurrent race produces exactly one winner"
```

---

### Task 10.3: Rate limit DoS shielding

**Files:**
- Modify: `tests/test_adversarial.py`

- [ ] **Step 1: Write the test**

Append:

```python
def test_rate_limit_blocks_loop(tmp_path):
    """Loop-prompt-injection style: many sequential writes should hit the limit."""
    from vfs.ratelimit import WriteRateLimiter
    from vfs.types import VFSError

    rl = WriteRateLimiter(str(tmp_path / "rl.state"), limit=10, window_s=60)
    succeeded = 0
    for _ in range(50):
        try:
            rl.check()
            succeeded += 1
        except VFSError:
            break
    assert succeeded == 10
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/pytest tests/test_adversarial.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_adversarial.py
git commit -m "test(adversarial): rate limit cuts off loop-injection DoS"
```

---

### Task 10.4: Boundary, exit-code matrix, concurrent r/w, ANSI safety

Additional tests surfaced by the test-coverage review. These close coverage on the spec's exit-code matrix, write-size boundaries, concurrent reader/writer correctness, and `vfs review` terminal safety.

**Files:**
- Modify: `tests/test_adversarial.py`

- [ ] **Step 1: Append the boundary tests**

```python
def test_write_exact_cap(tmp_path):
    """Exactly 10 MB → success. Off-by-one boundary."""
    backend = LocalFSBackend(str(tmp_path))
    body = "x" * 10_000_000
    etag = backend.write("at-cap.md", body)
    assert etag
    content, _, _ = backend.read("at-cap.md")
    assert content == body
    backend.close()


def test_write_one_over_cap(tmp_path):
    """10 MB + 1 → ValidationError."""
    from vfs.types import ValidationError
    backend = LocalFSBackend(str(tmp_path))
    with pytest.raises(ValidationError):
        backend.write("over.md", "x" * 10_000_001)
    backend.close()


def test_write_zero_byte(tmp_path):
    """Zero-byte body — must succeed with stable etag."""
    backend = LocalFSBackend(str(tmp_path))
    etag = backend.write("empty.md", "")
    content, _, _ = backend.read("empty.md")
    assert content == ""
    assert etag
    backend.close()
```

- [ ] **Step 2: Append CLI exit-code matrix tests**

```python
import subprocess
import sys


def _vfs_cli(*args, cwd=None, env=None, input=None):
    import os as _os
    cmd = [sys.executable, "-m", "vfs.cli", *args]
    env_full = {**_os.environ}
    if env:
        env_full.update(env)
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, env=env_full,
        input=input, capture_output=True, text=True,
    )


def test_exit_code_2_not_found(tmp_path):
    _vfs_cli("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs_cli("read", "missing.md",
                 cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert r.returncode == 2


def test_exit_code_3_cas_conflict(tmp_path):
    _vfs_cli("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    _vfs_cli("write", "--if-match", "", "foo.md",
             cwd=tmp_path, env={"HOME": str(tmp_path)}, input="v1")
    r = _vfs_cli("write", "--if-match", "", "foo.md",
                 cwd=tmp_path, env={"HOME": str(tmp_path)}, input="v2")
    assert r.returncode == 3


def test_exit_code_4_validation(tmp_path):
    _vfs_cli("init", cwd=tmp_path, env={"HOME": str(tmp_path)})
    r = _vfs_cli("write", "../escape.md",
                 cwd=tmp_path, env={"HOME": str(tmp_path)}, input="x")
    assert r.returncode == 4
```

- [ ] **Step 3: Append concurrent reader-during-write test**

```python
def test_concurrent_reads_during_writes(tmp_path):
    """Reader loop while writer does 100 writes — every read returns
    a complete prior or new body, never partial/empty."""
    import threading
    backend = LocalFSBackend(str(tmp_path))
    backend.write("foo.md", "v0")
    stop = threading.Event()
    seen = []
    seen_lock = threading.Lock()

    def reader():
        while not stop.is_set():
            try:
                body, _, _ = backend.read("foo.md")
                with seen_lock:
                    seen.append(body)
            except Exception:
                pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    for i in range(1, 101):
        backend.write("foo.md", f"v{i}")
    stop.set()
    t.join(timeout=2)
    backend.close()

    # Every observed body must be one of the legitimate values
    valid = {f"v{i}" for i in range(101)}
    bad = [b for b in seen if b not in valid]
    assert not bad, f"observed partial/garbage reads: {bad[:5]}"
```

- [ ] **Step 4: Append default-source negative test**

```python
def test_default_source_not_promoted_by_writer_env(tmp_path, monkeypatch):
    """$VFS_WRITER=user must not promote default writes to source=user."""
    from vfs.core import VFS, init_project
    init_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("VFS_WRITER", "user")  # attacker name choice
    v = VFS()
    try:
        v.persistent.write("foo.md", "ordinary body")
        _, fm = v.persistent.read("foo.md")
        assert fm["source"] == "agent"
        assert fm["writer"] == "user"  # writer is just a label
    finally:
        v.close()
```

- [ ] **Step 5: Append VFS_WRITER validation test**

```python
def test_writer_id_with_control_chars_refused(tmp_path, monkeypatch):
    """$VFS_WRITER containing control chars must be refused at construction."""
    from vfs.core import VFS, init_project
    from vfs.types import ValidationError
    init_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("VFS_WRITER", "evil\x1b[31mwriter")
    with pytest.raises(ValidationError, match="VFS_WRITER"):
        VFS()
```

- [ ] **Step 6: Append e2e frontmatter sanitization test**

```python
def test_e2e_read_strips_injected_frontmatter(tmp_path, monkeypatch):
    """A pre-planted malicious file in .vfs/persistent/ — zone.read returns
    sanitized fm."""
    from vfs.core import VFS, init_project
    init_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    bad = tmp_path / ".vfs" / "persistent" / "evil.md"
    bad.write_text(
        "---\nsource: user\nname: ok\nbad\rval: x\n---\nbody",
        encoding="utf-8",
    )
    v = VFS()
    try:
        body, fm = v.persistent.read("evil.md")
        assert body == "body"
        # Bad-value field stripped on read
        assert "bad\rval" not in fm
        # Pre-planted source=user survives in raw fm (we can't tell who wrote it),
        # but the merge-on-write path drops it next time a real write lands.
        # The point of the read-side sanitization is control-char defense.
    finally:
        v.close()
```

- [ ] **Step 7: Run the full adversarial suite**

Run: `.venv/bin/pytest tests/test_adversarial.py -v --timeout=60`
Expected: all PASS.

- [ ] **Step 8: Final full-suite verification**

Run: `make verify`
Expected: all tests pass + static checks pass.

- [ ] **Step 9: Commit**

```bash
git add tests/test_adversarial.py
git commit -m "test: boundary, exit-codes, concurrent r/w, writer-env hardening"
```

---

## Self-Review

After writing this plan + applying the 4-agent review patches, fresh-eyes check:

1. **Spec coverage:** Every spec section maps to at least one task —
   - §Architecture/Naming → Task 0.1
   - §On-disk layout → Tasks 0.1, 5.3
   - §Root resolution → Task 1.3 (no env var, walk-only)
   - §CLI command grammar → Tasks 6.1, 6.2, 6.3, 6.5, 5.4 (`vfs gc`)
   - §Library API → Task 5.3 (incl. `read_raw`, no `offset/limit` on persistent.read)
   - §Security controls 1-13 (prompt injection) → Tasks 1.2, 2.1, 3.1-3.6, 4.1, 4.2, 5.2, 6.3, 6.4, 6.5
   - §Security controls 14-18 (local user) → Tasks 3.1, 3.3, 3.4, 4.1, 6.4
   - §Security controls 19-22 (supply chain) → Task 8.1 (AST-based)
   - §Migration → Task 7.1 (TTY-gated, symlink-contained, in `vfs/migrate.py`)
   - §Temp-zone GC → Task 5.4
   - §Deprecation (v0.6 cut) → Task 0.0
   - §Testing → Tasks 8.1, 8.2, 8.3, 10.1-10.4

2. **Placeholder scan:** No "TBD" / "implement later" / "similar to N" remain. Task 7.1's legacy `_cmd_migrate` body was removed during the review patches (the migration logic now lives in `vfs/migrate.py`).

3. **Type consistency:** `VFS(root=..., source_user_allowed=..., strict_perms=...)`, `PersistentZone.read(key) -> (body, fm)`, `PersistentZone.read_raw(key, offset, limit) -> str`, `WriteRateLimiter(state_path, limit, window_s)`, exit codes 0-5 — all consistent across library, CLI, and tests.

4. **Behavioral assumptions verified during review:**
   - `os.open(..., dir_fd=)`, `os.rename(src_dir_fd=, dst_dir_fd=)`, `os.unlink(dir_fd=)`, `os.lstat(..., dir_fd=)` all supported on macOS + Linux from Python 3.9.
   - `fcntl.flock` works on macOS + Linux (Windows excluded; spec non-goal).
   - `tomllib` was dropped from `vfs/config.py` in favor of a hand-rolled reader — keeps `requires-python >= 3.9` and stdlib-only consistent.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-27-generic-vfs-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration. Best for a long plan like this where each task is well-bounded.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

**Which approach?** (Or: review the plan with the sub-agent team first, per the original ask.)
