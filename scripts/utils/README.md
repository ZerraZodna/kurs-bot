Scripts utilities

Place for small operational helpers related to database initialization and maintenance.

Files:

- `init_prod_db.py` - create a clean `prod.db` and seed defaults (use `--yes` to skip prompt)
- `migrate_db.py` - run Alembic migrations against `dev` or `prod` (use `--yes` to auto-stamp on failure)
- `fix_dev_db.py` - idempotent repair script for `src/data/dev.db` to add missing GDPR columns/tables

Usage examples:

```bash
python scripts/utils/init_prod_db.py --yes
python scripts/utils/migrate_db.py --db dev
python scripts/utils/fix_dev_db.py
```
