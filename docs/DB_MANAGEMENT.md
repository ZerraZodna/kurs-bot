# Database Management Quick Reference

## Overview

Three complementary scripts for managing the dev.db database:

1. **`reset_dev_db.py`** - Full reset while preserving lessons
2. **`db_manage.py`** - Status checks and utilities
3. **`reset_recipes.py`** - Quick recipes for common scenarios

## Quick Commands

### Check Database Status
```bash
python scripts/db_manage.py status
```
Shows: Users, Memories, Lessons, Schedules, Messages, Unsubscribes

### Clean Dev DB (Keep Lessons)
```bash
python scripts/reset_dev_db.py --force
```
- Clears all users, memories, messages, schedules
- **Preserves all 365 ACIM lessons**
- Fastest way to start fresh for testing

### Create Backup
```bash
python scripts/reset_recipes.py backup
```
Creates `dev.db.backup.YYYYMMDD_HHMMSS`

### Complete Fresh Start
```bash
python scripts/reset_recipes.py fresh-start
```
- Deletes dev.db completely
- Re-imports all 365 lessons
- Slowest but cleanest option

### Get Detailed Info
```bash
python scripts/db_manage.py info
```
Shows sample data and counts

## Common Scenarios

### Scenario 1: Start Over for Testing
```bash
# Fastest: Keep lessons, clear users
python scripts/reset_dev_db.py --force

# Or use recipe
python scripts/reset_recipes.py clean-users
```

### Scenario 2: Preserve Current State
```bash
# Backup before making changes
python scripts/reset_recipes.py backup

# Check status
python scripts/db_manage.py status
```

### Scenario 3: Complete Wipe + Fresh Lessons
```bash
python scripts/reset_recipes.py fresh-start
```

### Scenario 4: Restore Old State
```bash
# See available backups
python scripts/reset_recipes.py restore

# Choose backup to restore
```

## Database Tables

| Table | Purpose | Reset Behavior |
|-------|---------|---|
| `users` | User accounts | 🗑️ Cleared |
| `memory` | User memories/facts | 🗑️ Cleared |
| `message_log` | Chat history | 🗑️ Cleared |
| `schedules` | Lesson schedules | 🗑️ Cleared |
| `unsubscribe` | Unsubscribe tracking | 🗑️ Cleared |
| `lessons` | ACIM lessons | 🔒 **Preserved** |

## Script Details

### reset_dev_db.py
**Purpose**: Reset database while keeping lessons

**Options**:
- `--force` - Skip confirmation
- `--backup` - Create backup before resetting
- `--lessons-only` - Just show lesson count

**Example**:
```bash
python scripts/reset_dev_db.py --backup --force
```

### db_manage.py
**Purpose**: Quick database utilities

**Commands**:
- `status` - Show table counts
- `info` - Show detailed info with samples
- `backup` - Create backup
- `reset` - Reset (calls reset_dev_db.py)
- `clean-all` - DELETE everything (dangerous!)

**Example**:
```bash
python scripts/db_manage.py status
python scripts/db_manage.py backup
```

### reset_recipes.py
**Purpose**: Pre-configured recipes for common operations

**Recipes**:
- `fresh-start` - Complete wipe + re-import lessons
- `clean-users` - Clear users, keep lessons
- `backup` - Create timestamped backup
- `restore` - Restore from latest backup
- `list` - Show all recipes

**Example**:
```bash
python scripts/reset_recipes.py clean-users
```

## Performance

| Operation | Time |
|-----------|------|
| Check status | < 1 second |
| Reset (keep lessons) | ~2 seconds |
| Create backup | ~5 seconds |
| Import lessons | ~30 seconds |
| Complete fresh start | ~35 seconds |

## Backup Files

Backups are stored in `src/data/` with timestamps:
- `dev.db.backup.20260202_150000`
- `dev.db.bak.20260202_150500`

Restore manually if needed:
```bash
copy src/data/dev.db.backup.20260202_150000 src/data/dev.db
```

## Tips

✅ **DO**:
- Backup before major changes
- Use `--force` for scripting
- Check status before and after reset
- Run fresh-start for clean testing

❌ **DON'T**:
- Use `clean-all` unless you're sure
- Delete backups without archiving
- Run reset scripts while app is running
- Manually edit dev.db (use scripts instead)

## Troubleshooting

### "Database is locked" error
- Stop the running app: `Ctrl+C` on uvicorn terminal
- Wait 2 seconds
- Run the script again

### "No lessons found after reset"
- Check import script ran: `python scripts/db_manage.py status`
- If 0 lessons: Run `python scripts/import_acim_lessons.py --clear`

### Restore from backup failed
- Try: `python scripts/reset_recipes.py restore`
- Or manually: `copy src/data/dev.db.backup.* src/data/dev.db`

## Development Workflow

### Daily Testing
```bash
# Before each test session
python scripts/reset_dev_db.py --force
python main.py
```

### After Major Changes
```bash
# Backup first
python scripts/reset_recipes.py backup

# Test with clean state
python scripts/reset_recipes.py clean-users
python main.py
```

### Release Candidate
```bash
# Complete fresh start
python scripts/reset_recipes.py fresh-start

# Run full test suite
pytest tests/
```
