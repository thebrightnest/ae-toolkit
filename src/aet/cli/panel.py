#!/usr/bin/env python3
"""CLI entry point for `aet panel`."""

import sys

from aet.panel.serve import main

if __name__ == "__main__":
    sys.exit(main())
