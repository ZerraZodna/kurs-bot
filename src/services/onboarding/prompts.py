from __future__ import annotations

from typing import Dict


def get_onboarding_prompts(language: str, name: str) -> Dict[str, str]:
    prompts = {
        "no": {
            "name": "Velkommen! Jeg er din åndelige veileder for A Course in Miracles. Hva heter du?",
            "consent": "Før vi fortsetter: Er det greit at jeg lagrer samtalen og relevant informasjon for å gi deg oppfølging? (ja/nei)",
            "commitment": (
                f"""Herlig, {name}! 
Er du interessert i å utforske disse leksjonene sammen med meg? Jeg er her for å veilede og støtte deg på denne åndelige reisen."""
            ),
            "lesson_status": f"Flott, {name}! Er du ny til ACIM, eller har du allerede begynt med leksjonene?",
        },
        "en": {
            "name": "Welcome! I'm your spiritual coach for A Course in Miracles. What's your name?",
            "consent": "Before we continue: Do you consent to me storing the conversation and relevant info to support you? (yes/no)",
            "commitment": (
                f"""Beautiful, {name}! 
Are you interested in exploring these lessons together? I'm here to guide and support you on this journey."""
            ),
            "lesson_status": f"Wonderful, {name}! Are you new to ACIM, or have you already begun working with the lessons?",
        },
    }

    return prompts.get(language, prompts["en"])


def get_lesson_1_welcome_message(language: str, name: str) -> str:
    messages = {
        "no": f"""Perfekt, {name}! La oss begynne sammen med Leksjon 1. Dette er hvor transformasjonen starter.

📅 **Daglig støtte**: Hver morgen kl. 07:30 sender jeg deg neste leksjon.
💬 **Alltid tilgjengelig**: Du kan ta kontakt når som helst for å diskutere innsikter, stille spørsmål, eller reflektere sammen.

Ta deg tid med dagens leksjon. Når du er klar til å snakke om den, er jeg her. 🌿""",
        "en": f"""Perfect, {name}! Let's begin together with Lesson 1. This is where transformation starts.

📅 **Daily support**: Each morning at 7:30 AM, I'll send you the next lesson.
💬 **Always available**: You can reach out anytime to discuss insights, ask questions, or reflect together.

Take your time with today's lesson. When you're ready to talk about it, I'm here. 🌿""",
    }
    return messages.get(language, messages["en"])


def get_continuation_welcome_message(language: str, name: str, lesson_id: int) -> str:
    messages = {
        "no": f"""Flott, {name}! Du er på Leksjon {lesson_id}. La oss fortsette reisen sammen.

📅 **Daglig støtte**: Hver morgen kl. 07:30 sender jeg deg neste leksjon.
💬 **Alltid tilgjengelig**: Du kan ta kontakt når som helst for å diskutere, stille spørsmål, eller reflektere.

Her er dagens leksjon:""",
        "en": f"""Wonderful, {name}! You're on Lesson {lesson_id}. Let's continue this journey together.

📅 **Daily support**: Each morning at 7:30 AM, I'll send you the next lesson.
💬 **Always available**: You can reach out anytime to discuss, ask questions, or reflect.

Here's today's lesson:""",
    }
    return messages.get(language, messages["en"])


def get_onboarding_complete_message_text(language: str, name: str) -> str:
    messages = {
        "no": f"""Velkommen til vårt åndelige fellesskap, {name}! 🙏

Jeg er her for å støtte deg på reisen din med A Course in Miracles.

📅 **Daglige påminnelser satt opp** - Jeg vil sende deg leksjoner hver dag klokken 07:30. Du kan endre tiden når som helst.

Du kan også:
💬 **Chat med meg når som helst** - Still spørsmål, del innsikter eller diskuter leksjonene
📖 **Utforsk leksjoner** - Spør meg om noen av de 365 leksjonene når du er klar""",
        "en": f"""Welcome to our spiritual community, {name}! 🙏

I'm here to support you on your journey with A Course in Miracles.

📅 **Daily reminders set up** - I'll send you lessons every day at 07:30 AM. You can change the time anytime.

You can also:
💬 **Chat with me anytime** - Ask questions, share insights, or discuss the lessons
📖 **Explore lessons** - Ask me about any of the 365 lessons whenever you're ready""",
    }
    return messages.get(language, messages["en"])
