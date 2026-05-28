import os
import time
from pathlib import Path

from vfs.gc import opportunistic_sweep, sweep_temp_zone


def test_sweep_removes_old(tmp_path):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    old = temp_dir / "old.md"
    fresh = temp_dir / "fresh.md"
    old.write_text("x")
    fresh.write_text("y")
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
    removed = sweep_temp_zone(str(temp_dir), cutoff_seconds=0)
    assert "shortcut.md" not in removed
    assert real.exists()


def test_sweep_idempotent_via_stamp(tmp_path):
    """Opportunistic sweep at VFS() init should only fire once/day."""
    vfs_dir = tmp_path / ".vfs"
    (vfs_dir / "temp").mkdir(parents=True)
    fired_first = opportunistic_sweep(vfs_dir)
    fired_second = opportunistic_sweep(vfs_dir)
    assert fired_first is True
    assert fired_second is False
