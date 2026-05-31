"""Regression guard for the public top-level import surface.

Library consumers should be able to write::

    from agent_vfs import VFS

without knowing about the internal module layout. This test exists because
``VFS`` was missing from ``__init__.py`` in an earlier 0.6.x snapshot, which
broke every external consumer until caught.
"""


def test_vfs_importable_from_top_level() -> None:
    from agent_vfs import VFS

    assert VFS.__name__ == "VFS"


def test_version_string_matches_pyproject() -> None:
    """Catch divergence between ``__version__`` and the wheel's metadata.

    Read pyproject.toml directly to avoid pulling in tomllib/tomli (the
    repo is stdlib-only on 3.9+, see ``agent_vfs/config.py`` rationale).
    """
    import re
    from pathlib import Path

    import agent_vfs

    pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert match is not None, "pyproject.toml version line not found"
    assert agent_vfs.__version__ == match.group(1), (
        f"agent_vfs.__version__={agent_vfs.__version__!r} but "
        f"pyproject version={match.group(1)!r}"
    )


def test_all_exports_listed() -> None:
    import agent_vfs

    assert "VFS" in agent_vfs.__all__
    assert "__version__" in agent_vfs.__all__
