"""Seed default prompt templates into the database.

Exposes a `seed()` function for programmatic use and prints concise
progress messages when run as a script.
"""
from typing import Optional

from src.models.database import SessionLocal, PromptTemplate, init_db


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(PromptTemplate).filter(PromptTemplate.key == 'concise_coach_v1').first()
        if existing:
            print('✅ Default template already present')
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
        print('✅ Seeded concise_coach_v1')
    finally:
        db.close()


def main(argv: Optional[list] = None) -> int:
    try:
        seed()
        return 0
    except Exception as exc:
        print('❌ Failed to seed prompt templates:', exc)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
