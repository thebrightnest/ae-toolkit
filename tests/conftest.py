"""pytest configuration for orchestrator tests."""

import sys
from pathlib import Path

# Add aet-work/lib to the import path
sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))
