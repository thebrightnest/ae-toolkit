#!/usr/bin/env python3
"""aet harness-guard — detect the active harness and install a per-provider merge guard.

Subcommands:

  install   Detect the harness from workspace markers (or --harness override) and
            generate the matching merge guard. Idempotent: rewrites a prior AET
            guard in place and leaves a pre-existing non-AET harness config untouched.
  check     Report which merge guard is installed for the detected harness.

Standard-library only. The generated guard is harness-local config (e.g. under
.claude/) and is therefore gitignorable — it never becomes AET litter in the
tracked tree.
"""

from __future__ import annotations

import sys

from aet import harness_guard

if __name__ == "__main__":
    sys.exit(harness_guard.main())
