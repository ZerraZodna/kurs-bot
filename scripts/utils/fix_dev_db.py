"""Dev DB fixer (moved into scripts/utils).

This keeps the same behavior as scripts/fix_dev_db.py but lives under
`scripts/utils/` for clearer organization.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path('src/data/dev.db')
if not DB_PATH.exists():
    print('dev.db not found at', DB_PATH)
    raise SystemExit(1)

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

def has_table(name):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def column_exists(table, column):
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols

print('Tables in DB:')
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([r[0] for r in cur.fetchall()])

if not has_table('users'):
    print('users table missing — aborting')
    raise SystemExit(1)

to_add = []
if not column_exists('users', 'processing_restricted'):
    to_add.append(("processing_restricted", "BOOLEAN NOT NULL DEFAULT 0"))
if not column_exists('users', 'restriction_reason'):
    to_add.append(("restriction_reason", "TEXT"))
if not column_exists('users', 'is_deleted'):
    to_add.append(("is_deleted", "BOOLEAN NOT NULL DEFAULT 0"))
if not column_exists('users', 'deleted_at'):
    to_add.append(("deleted_at", "DATETIME"))

for name, typ in to_add:
    sql = f"ALTER TABLE users ADD COLUMN {name} {typ};"
    print('Adding column:', name)
    cur.execute(sql)

# Create GDPR-related tables if they don't exist
cur.execute('''
CREATE TABLE IF NOT EXISTS consent_logs (
    consent_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    scope VARCHAR(64) NOT NULL,
    granted BOOLEAN NOT NULL,
    consent_version VARCHAR(32),
    source VARCHAR(64),
    created_at DATETIME NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS gdpr_requests (
    request_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    request_type VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    reason TEXT,
    details TEXT,
    actor VARCHAR(64) NOT NULL,
    requested_at DATETIME NOT NULL,
    processed_at DATETIME
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS gdpr_audit_logs (
    audit_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    action VARCHAR(64) NOT NULL,
    details TEXT,
    actor VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL
)
''')

con.commit()
print('Done. Updated schema for dev.db')
cur.execute("PRAGMA table_info(users)")
print('users columns:', [r[1] for r in cur.fetchall()])
con.close()
