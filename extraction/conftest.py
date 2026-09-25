"""Pytest configuration: put the `extraction/` root on sys.path so tests (and
the future `main.py`) can `import src...` regardless of the invocation
directory (plan.md §5 layout)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
