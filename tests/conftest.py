"""Pytest configuration.

This project keeps application code under the top-level `src/` directory.
To make `import src...` work in test runs without installing the package,
we add the repository root to `sys.path`.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


