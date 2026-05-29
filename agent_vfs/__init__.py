"""agent-vfs — hardened, agent-agnostic file system for memory and scratch.

Spec: docs/superpowers/specs/2026-05-27-generic-vfs-design.md (in the
parent claude-workflow repo, not vendored here).

Public surface: ``from agent_vfs import VFS``. Construction reads
``$VFS_WRITER`` (validated ``[\\w.-]+``) — it does NOT accept a
``writer_id=`` kwarg. See ``VFS`` docstring for details.
"""
from .core import VFS

__version__ = "0.6.0"

__all__ = ["VFS", "__version__"]
