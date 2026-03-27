# Python 3.10+ Upgrade & Fix Plan (Approved & In Progress)

## Current Status
- Python environment upgraded
- pyproject.toml updated to >=3.10
- ruff/mypy targeted to py310

## Steps Completed
- [x] Update pyproject.toml configs
- [x] Add ruff>=0.6.0 to requirements-dev.txt

## Steps In Progress - BLACKBOXAI Python Fix
### 1. Fix ruff UP038 errors (union syntax)
- [x] scripts/debug/test_ollama_auth.py
- [x] src/functions/handlers/memory.py
- [x] src/functions/registry.py
- [x] src/services/dialogue/ollama_client.py
- [x] tests/unit/scheduler/test_timezone_migration.py

### 2. Update pre-commit config
- [x] .pre-commit-config.yaml → python3.12 (system env match)

### 3. Run pre-commit
- [x] pre-commit run --all-files **✓ PASSED**

### 4. Commit fixes
```
git add .
git commit -m "Fix Python 3.10+ ruff UP038 + pre-commit python3.10"
```

## Remaining Steps
### 5. Recreate virtualenv [PENDING]
```
rm -rf .venv
python3.12 -m venv .venv  # or python3.11
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```

### 6. Test
```
pre-commit install
pre-commit run --all-files
pytest
```

### 7. Migrate DB
```
scripts/utils/migrate_db.py
scripts/utils/seed_prompt_templates.py
```
