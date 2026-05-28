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
