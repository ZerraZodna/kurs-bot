"""Seed default prompt templates into DB.

Run: python scripts/seed_prompt_templates.py
"""
import sys
import os

# Ensure repo root is on sys.path so `import src...` works when running this script directly
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.models.database import SessionLocal, PromptTemplate, init_db


def seed():
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(PromptTemplate).filter(PromptTemplate.key == 'concise_coach_v1').first()
        if existing:
            print('Default template already present')
            return
        tmpl = PromptTemplate(
            key='concise_coach_v1',
            title='Concise Coach (v1)',
            text='You are a concise helpful coach. Answer in 3-5 sentences, use bullets for steps, and be practical.',
            owner='system',
            visibility='public',
            version=1,
        )
        db.add(tmpl)
        db.commit()
        print('Seeded concise_coach_v1')
    finally:
        db.close()


if __name__ == '__main__':
    seed()
