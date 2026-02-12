"""Pytest fixtures and config."""
import sys
from pathlib import Path

# ensure src is on path when running tests from repo root
root = Path(__file__).resolve().parent.parent
src = root / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))
