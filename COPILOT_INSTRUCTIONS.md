Repository instructions for GitHub Copilot / AI assistants

- Do NOT insert ad-hoc, high-level, or hard-coded command handlers into production code without explicit approval from the repository owner.
- All code changes made by AI assistants must be:
  - Small, focused, and documented in the pull request description.
  - Reviewed and approved by a human maintainer before merging.
  - Reversible: include tests or ensure tests are run locally before committing.
- If a requested behavioral change cannot be implemented safely within a single function or service, present options and ask for explicit permission.
- For language/UX overrides or new user-facing commands, confirm design and tests first.
- If you are an automated tool or bot modifying this repo, respect these rules and stop; notify the user and request explicit permission.
- Do not use try:  except: when code is supposed to run. Example not to do:
                try:
                    print(f"[EXTRACT DEBUG] stored memory for user {user_id}: {memory.get('key')}={memory.get('value')}")
                except Exception:
                    pass
                    
Maintainers: add a note in your PR template or CONTRIBUTING.md referencing this file to enforce the policy.
