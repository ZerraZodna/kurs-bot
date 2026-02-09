#!/usr/bin/env python
"""
Repository-level command dispatcher wrapper.

This file allows running `python cli.py ...` from the project root and delegates
to `scripts/cmd.py` which contains the actual command implementations.
"""
import sys

if __name__ == "__main__":
    # Delegate to the scripts/cmd.py entrypoint
    # We import and call main() so argv handling remains consistent.
    from scripts import cli as _cmd
    _cmd.main()
