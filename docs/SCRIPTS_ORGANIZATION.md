# Project Scripts Organization

## Quick Command Runner (Root)

**`cli.py`** - Single entry point for all development commands

```bash
python cli.py db status              # Show database status
python cli.py db reset               # Reset dev.db (keeps 365 lessons)
python cli.py db backup              # Create backup
python cli.py db fresh-start         # Complete fresh start
python cli.py import-lessons         # Import ACIM lessons
python cli.py debug memory           # Debug memory extraction
python cli.py debug schedule         # Debug schedule creation
python cli.py init-prod              # Initialize production database
```

## Database Scripts (`scripts/`)

- **`db_manage.py`** - Quick database utilities
- **`reset_dev_db.py`** - Reset dev.db while preserving lessons
- **`reset_recipes.py`** - Pre-configured recipes for common scenarios
- **`import_acim_lessons.py`** - Import 365 ACIM lessons from PDF

## Debug Scripts (`scripts/debug/`)

- **`debug_extraction.py`** - Test memory extraction
- **`debug_schedule.py`** - Debug schedule creation

## Data Scripts (`scripts/`)

- **`test_*.py`** - Test scripts for specific features
- **`init_prod_db.py`** - Initialize production database
- **`debug_memory_extraction.py`** - Memory extraction debugging

---

## Root Level (Essential Only)

| File | Purpose | Keep? |
|------|---------|-------|
| `main.py` | ✅ App entry point | **YES** |
| `cli.py` | ✅ Command runner | **YES** |
| `conftest.py` | ✅ Pytest config | **YES** |
| `debug_extraction.py` | Moved to scripts/debug/ | **DELETE** |
| `debug_schedule.py` | Moved to scripts/debug/ | **DELETE** |
| `init_prod_db.py` | Moved to scripts/ | **DELETE** |
| `run_tests.ps1` | Can use pytest directly | **KEEP** (useful) |
| `start_kursbot.ps1` | Convenience starter | **KEEP** (useful) |

---

## Commands to Clean Up Root

```powershell
# Remove old root-level scripts (now in scripts/ folder)
Remove-Item debug_extraction.py
Remove-Item debug_schedule.py
Remove-Item init_prod_db.py

# Old redundant database scripts (replaced by new ones)
Remove-Item scripts/clear_dev_db.py       # Replaced by reset_dev_db.py
Remove-Item scripts/delete_dev_db.py      # Replaced by reset_dev_db.py
```

---

## Usage Examples

### Before (Messy)
```bash
python debug_extraction.py
python scripts/clear_dev_db.py
python scripts/delete_dev_db.py
python init_prod_db.py
python scripts/reset_dev_db.py --force
python scripts/reset_recipes.py fresh-start
python scripts/import_acim_lessons.py
```

### After (Clean)
```bash
python cli.py debug memory
python cli.py db reset
python cli.py db fresh-start
python cli.py import-lessons
python cli.py db status
python cli.py init-prod
```

---

## Directory Structure

### Root (Clean)
```
kurs-bot/
├── main.py              ← App entry point
├── cli.py               ← Command runner
├── conftest.py          ← Pytest config
├── run_tests.ps1        ← Test runner
├── start_kursbot.ps1    ← App starter
├── requirements.txt
├── .env
├── .gitignore
├── README.md
├── src/                 ← Source code
├── tests/               ← Tests
├── scripts/             ← All scripts here
├── migrations/          ← DB migrations
└── docker/              ← Docker config
```

### Scripts Organization
```
scripts/
├── cmd.py                       ← Entry point (copied to root as cli.py)
├── db_manage.py                 ← DB utilities
├── reset_dev_db.py              ← Reset preserving lessons
├── reset_recipes.py             ← DB recipes
├── import_acim_lessons.py       ← Import ACIM lessons
├── init_prod_db.py              ← Init production DB
├── test_*.py                    ← Feature tests
├── debug/
│   ├── debug_extraction.py      ← Memory extraction test
│   └── debug_schedule.py        ← Schedule creation test
└── debug_memory_extraction.py   ← Alternative memory test (can delete)
```

---

## Benefits

✅ **Single command interface** - `python cli.py <command>`
✅ **Clear organization** - Related scripts grouped in folders
✅ **Reduced root clutter** - Only essential files at root level
✅ **Easy discoverability** - All commands in one place
✅ **No redundancy** - Old scripts removed
✅ **Backward compatible** - Full functionality preserved

---

## Migration Steps

1. ✅ Created `cli.py` as master command runner
2. ✅ Moved debug scripts to `scripts/debug/`
3. ✅ Moved `init_prod_db.py` to `scripts/`
4. ⏳ Delete redundant root scripts:
   - `debug_extraction.py`
   - `debug_schedule.py`
   - `init_prod_db.py` (old one)
5. ⏳ Delete old DB scripts:
   - `scripts/clear_dev_db.py`
   - `scripts/delete_dev_db.py`
