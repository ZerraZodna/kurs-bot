#!/usr/bin/env python3
"""Importer: extract lessons from PDF and insert into DB.

DEPRECATED: This script has been refactored into src/lessons/ package.
Please use the new location or update imports to use src.lessons.

This wrapper exists for backwards compatibility and will be removed
in a future version.
"""
import sys

# Redirect to the new module location
from src.lessons import main

if __name__ == '__main__':
    raise SystemExit(main())

