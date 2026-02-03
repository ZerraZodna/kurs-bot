#!/usr/bin/env python
"""
Kurs Bot - Development & Database Management Tool

Quick commands for common tasks:
  db status              Show database status
  db reset               Reset dev.db (keeps lessons)
  db backup              Backup current database
  db info                Show detailed DB info
  db fresh-start         Complete fresh start (delete + re-import lessons)
  
  import-lessons         Import ACIM lessons from PDF
  
  debug memory           Debug memory extraction
  debug schedule         Debug schedule creation
  
  init-prod              Initialize production database

Examples:
  python cmd.py db status
  python cmd.py db reset
  python cmd.py debug memory
  python cmd.py import-lessons
"""

import sys
import subprocess
from pathlib import Path

def run_command(script: str, args: list = None):
    """Run a script in the scripts folder."""
    cmd = [sys.executable, f"scripts/{script}"]
    if args:
        cmd.extend(args)
    
    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    # Database commands
    if command == "db":
        if not args or args[0] == "help":
            print("Database Management Commands:\n")
            print("  db status              - Show table counts")
            print("  db info                - Show detailed info with samples")
            print("  db reset               - Clear users/messages (keep lessons)")
            print("  db backup              - Create timestamped backup")
            print("  db clean-all           - DELETE everything (dangerous!)")
            print("  db fresh-start         - Complete fresh start")
            print("  db restore             - Restore from latest backup")
            return
        
        subcommand = args[0]
        
        if subcommand == "status":
            run_command("db_manage.py", ["status"])
        elif subcommand == "info":
            run_command("db_manage.py", ["info"])
        elif subcommand == "reset":
            run_command("reset_dev_db.py", ["--force"])
        elif subcommand == "backup":
            run_command("reset_recipes.py", ["backup"])
        elif subcommand == "clean-all":
            run_command("db_manage.py", ["clean-all"])
        elif subcommand == "fresh-start":
            run_command("reset_recipes.py", ["fresh-start"])
        elif subcommand == "restore":
            run_command("reset_recipes.py", ["restore"])
        else:
            print(f"Unknown database command: {subcommand}")
            sys.exit(1)
    
    # Import lessons
    elif command == "import-lessons":
        run_command("import_acim_lessons.py", args)
    
    # Debug commands
    elif command == "debug":
        if not args:
            print("Debug Commands:\n")
            print("  debug memory           - Debug memory extraction")
            print("  debug schedule         - Debug schedule creation")
            return
        
        debug_cmd = args[0]
        if debug_cmd == "memory":
            run_command("debug/debug_extraction.py")
        elif debug_cmd == "schedule":
            run_command("debug/debug_schedule.py")
        else:
            print(f"Unknown debug command: {debug_cmd}")
            sys.exit(1)
    
    # Initialize production database
    elif command == "init-prod":
        run_command("init_prod_db.py", args)
    
    # Help
    elif command in ["help", "-h", "--help"]:
        print(__doc__)
    
    else:
        print(f"Unknown command: {command}\n")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
