scripts — operational helpers

Quick helpers for DB setup and seeding. Keep it simple.

From the repository root, activate your venv first:

```powershell
# PowerShell (Windows)
. .venv\Scripts\Activate.ps1

# Bash (Linux/macOS)
source .venv/bin/activate
```

Commands (for a CLEAN new host):

```powershell
# Run full setup on a CLEAN new host (creates prod.db and seeds defaults)
./scripts/setup_new_host.ps1 -Yes

# If you prefer to run only the production DB initializer directly (Python)
python scripts/utils/init_prod_db.py --yes

# Import ACIM lessons from PDF (Python)
python scripts/utils/import_acim_lessons.py --pdf src/data/"Sparkly ACIM lessons-extracted.pdf"

# Run Alembic migrations (reads DATABASE_URL from .env)
python scripts/utils/migrate_db.py --yes
```

Notes:
- `setup_new_host.ps1 -Yes` must be run on a CLEAN new host; it will abort if `src/data/prod.db` already exists.
- To target a non-default DB, set `DATABASE_URL` in `.env` or the environment and use `migrate_db.py` (or `init_prod_db.py` where appropriate).
- `init_prod_db.py` can import ACIM lessons with `--lessons /path/to.pdf`.
- See `docs/` for full operational details.

# New prompts
$env:PYTHONPATH='.'; python .\scripts\utils\seed_prompt_templates.py
# Reset triggers after changing from Local to Ollama for Embeddings
$env:PYTHONPATH='.'; python .\scripts\utils\reset_trigger_embeddings.py
