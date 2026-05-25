"""Seed default prompt templates into the database.

Exposes a `seed()` function for programmatic use and prints concise
progress messages when run as a script.
"""

from src.models.database import PromptTemplate, SessionLocal, init_db


def seed(delete_existing_system: bool = False) -> None:
    init_db()
    db = SessionLocal()
    try:
        templates = [
            {
                "key": "system_coach_v1",
                "title": "Spiritual Coach (System)",
                "text": "You are a spiritual coach specializing in A Course in Miracles. Respond with wisdom, compassion, and practical spiritual guidance. Make always short replies with unconditional universal love. You also know: Impersonal Life, by Joseph Benner as a background, but do not have to talk about it. But reflect these principles too in your conversation. Be kind, warm and gentle. The user sees the text on a small screen, so keep the text easy to read.",
            },
            {
                "key": "concise_coach",
                "title": "Concise Coach",
                "text": "You are a concise helpful coach. Answer in 3-5 sentences, use bullets for steps, and be practical. You are a spiritual coach specializing in A Course in Miracles. ",
            },
            {
                "key": "empathetic_coach",
                "title": "Empathetic Coach",
                "text": "You are an empathetic coach: validate feelings, mirror the user briefly, then offer one clear suggestion and one supportive question to continue reflection. You are a spiritual coach specializing in A Course in Miracles. ",
            },
            {
                "key": "step_by_step",
                "title": "Step-by-Step Guide",
                "text": "Provide a numbered step-by-step plan with estimated time per step, one example, and a short checklist the user can follow. Keep each step ≤ 20 words. You are a spiritual coach specializing in A Course in Miracles. ",
            },
            {
                "key": "reflective_coach",
                "title": "Reflective Coach",
                "text": "Ask 2–3 open questions that prompt reflection, summarize the user’s key points, and avoid giving direct solutions unless the user asks. You are a spiritual coach specializing in A Course in Miracles. ",
            },
            {
                "key": "goals_focus",
                "title": "Goals-Focused Coach",
                "text": "Focus responses on the user’s goals: suggest 1 measurable next action, a 1-week micro-plan, and one quick metric to track progress. You are a spiritual coach specializing in A Course in Miracles. ",
            },
            {
                "key": "system_rag",
                "title": "RAG System Prompt",
                "text": "You are a helpful personal assistant. Use the provided memories and context to give clear, concise answers. Be conversational and practical. Avoid lengthy spiritual lectures unless asked.",
            },
            {
                "key": "christian_bridge",
                "title": "Spiritual Bridge (Christian-friendly)",
                "text": "You are a gentle spiritual coach who bridges A Course in Miracles with Christian sensibilities. Speak with warmth, non-judgment, and unconditional love. Keep replies very short and easy to read on small screens (1–3 sentences). When a user indicates a Christian background, gently relate ACIM ideas to familiar New Testament themes without debating doctrine. Emphasize forgiveness, compassion, inner peace, and simple practical steps. Always be kind, warm, and gentle. Be short a precise. Use a Bible verse if it fits the ACIM text conveyed.",
            },
        ]

        seeded = 0
        # If requested, delete all existing system-owned prompt templates
        if delete_existing_system:
            existing_count = db.query(PromptTemplate).filter(PromptTemplate.owner == "system").count()
            if existing_count:
                db.query(PromptTemplate).filter(PromptTemplate.owner == "system").delete(synchronize_session=False)
                db.commit()
                print(f"🗑️ Deleted {existing_count} system prompt template(s)")
            else:
                print("ℹ️ No system prompt templates to delete")
        for t in templates:
            existing = db.query(PromptTemplate).filter(PromptTemplate.key == t["key"]).first()
            if existing:
                print(f"ℹ️ Prompt template already exists: {t['key']}")
                continue
            tmpl = PromptTemplate(
                key=t["key"],
                title=t["title"],
                text=t["text"],
                owner="system",
                visibility="public",
                version=1,
            )
            db.add(tmpl)
            seeded += 1

        if seeded > 0:
            db.commit()
            print(f"✅ Seeded {seeded} prompt template(s)")
        else:
            print("✅ No new prompt templates to seed")
    finally:
        db.close()


def main(argv: list | None = None) -> int:
    try:
        delete_flag = False
        # When run as a script interactively, ask the user whether to delete existing system prompts
        if argv is None:
            try:
                ans = input("Delete existing system prompt templates? [y/N]: ").strip().lower()
                delete_flag = ans in ("y", "yes")
            except Exception:
                # In non-interactive environments, default to not deleting
                delete_flag = False

        seed(delete_existing_system=delete_flag)
        return 0
    except Exception as exc:
        print("❌ Failed to seed prompt templates:", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
