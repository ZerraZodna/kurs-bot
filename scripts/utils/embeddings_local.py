"""Build a local hnswlib index from lessons in the database.

Usage:
  python scripts/utils/embeddings_local.py --out data/emb_index.bin

This script loads lessons from the database and builds an hnswlib index
using sentence-transformers/all-MiniLM-L6-v2.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sqlite3
import json
import numpy as np

def load_lessons_from_db():
    # Import DB model dynamically so the repo .env is respected
    import sys, os
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from src.models.database import SessionLocal, Lesson
    session = SessionLocal()
    try:
        lessons = session.query(Lesson).order_by(Lesson.lesson_id).all()
        texts = [f"Lesson {l.lesson_id}: {l.title}\n\n{(l.content or '')[:3000]}" for l in lessons]
        ids = [l.lesson_id for l in lessons]
        return ids, texts
    finally:
        session.close()


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True, help='Output index file prefix (directory will be created)')
    ns = p.parse_args(argv)
    outdir = Path(ns.out)
    outdir.parent.mkdir(parents=True, exist_ok=True)

    ids, texts = load_lessons_from_db()
    if not texts:
        print('No lessons found in DB')
        return 2

    # import local model and hnswlib
    try:
        from sentence_transformers import SentenceTransformer
        import hnswlib
    except Exception as e:
        print('Missing packages: pip install sentence-transformers hnswlib')
        raise

    model = SentenceTransformer('all-MiniLM-L6-v2')
    print(f"DEBUG: embeddings_local building embeddings for {len(texts)} texts using model 'all-MiniLM-L6-v2' (show_progress_bar=True)")
    emb = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
    dim = emb.shape[1]

    index = hnswlib.Index(space='cosine', dim=dim)
    index.init_index(max_elements=len(emb), ef_construction=200, M=16)
    index.add_items(emb, np.array(ids))
    index.set_ef(50)

    idx_path = str(outdir)
    index.save_index(idx_path)
    print(f'Saved index to {idx_path}')

    # Save metadata mapping
    meta_path = outdir + '.meta.json'
    with open(meta_path, 'w', encoding='utf8') as fh:
        json.dump({'dim': dim, 'count': len(ids)}, fh)
    print(f'Saved metadata to {meta_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
