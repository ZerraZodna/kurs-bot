"""
Manage RAG prompts for a user from the command line.

Usage examples:
  python scripts/rag_prompt.py list --user 1
  python scripts/rag_prompt.py select concise_coach_v1 --user 1
  python scripts/rag_prompt.py custom "My custom prompt text" --user 7
  python scripts/rag_prompt.py show --user 7
"""
import argparse
import os
import sys

# Ensure project root on path when invoked as a script
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.services.dialogue.command_handlers import handle_rag_prompt_command
from src.services.memory_manager import MemoryManager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sub", choices=["list", "select", "custom", "show"], help="Subcommand")
    parser.add_argument("rest", nargs=argparse.REMAINDER, help="Remaining arguments (key or custom text)")
    parser.add_argument("--user", type=int, required=False, help="User ID (default from CURRENT_USER_ID env or 1)")
    args = parser.parse_args()

    env_user = None
    try:
        env_user = int(os.getenv("CURRENT_USER_ID"))
    except Exception:
        env_user = None

    user_id = args.user or env_user or 1

    # Build a command string expected by the handler, e.g. 'rag_prompt list'
    rest_text = "".join([" " + p for p in args.rest]) if args.rest else ""
    cmd_text = f"rag_prompt {args.sub}{rest_text}"

    mm = MemoryManager()
    out = handle_rag_prompt_command(cmd_text, mm, user_id)
    if out:
        print(out)


if __name__ == "__main__":
    main()
