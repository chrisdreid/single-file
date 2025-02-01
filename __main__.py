#!/usr/bin/env python
"""
Entry point for SingleFile.
This module delegates execution to the main() function in single_file.singlefile.
"""

from single_file.singlefile import main
import sys

if __name__ == "__main__":
    sys.exit(main())
