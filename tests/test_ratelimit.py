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
    rl.check()


def test_corrupt_state_raises(tmp_path):
    state = tmp_path / "rl.state"
    state.write_text("not json", encoding="utf-8")
    state.chmod(0o600)
    rl = WriteRateLimiter(str(state), limit=5, window_s=60)
    with pytest.raises(VFSError, match="corrupted"):
        rl.check()
