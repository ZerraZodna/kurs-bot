from __future__ import annotations

from typing import Dict




def get_lesson_1_welcome_message(language: str, name: str) -> str:
	messages = {
		"no": f"""Perfekt, {name}! La oss begynne sammen med Leksjon 1. Dette er hvor transformasjonen starter.

📅 **Daglig støtte**: Hver morgen kl. 07:30 sender jeg deg neste leksjon.
💬 **Alltid tilgjengelig**: Du kan ta kontakt når som helst for å diskutere innsikter, stille spørsmål, eller reflektere sammen.

Ta deg tid med dagens leksjon. Når du er klar til å snakke om den, er jeg her. 🌿""",
		"en": f"""Perfect, {name}! Let's begin together with Lesson 1. This is where transformation starts.

📅 **Daily support**: Each morning at 7:30 AM, I'll send you the next lesson.
💬 **Always available**: You can reach out anytime to discuss insights, ask questions, or reflect together.

If you want to change the time, or need to take a pause, just let me know.

Take your time with today's lesson. If you have any questions, please ask me. 🌿""",
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


# General onboarding messages used by the onboarding flow
ONBOARD_MESSAGES = {
	"consent_declined": {
		"en": "Understood. I won't store your information. If you change your mind, just message me again. 🙏",
		"no": "Forstått. Jeg lagrer ikke informasjonen din. Hvis du ombestemmer deg, bare send meg en melding igjen. 🙏",
	},
	"commitment_declined": {
		"en": "Understood. I won't ask about ACIM lessons. If you want to resume later, just message me. You still have access if there is anything I can help you with. 🌿",
		"no": "Forstått. Jeg spør ikke om ACIM-leksjoner. Hvis du vil fortsette senere, bare send meg en melding. Du kan fortsatt spørre meg om alt mulig. Jeg er her hvis det er noe jeg kan hjelpe deg med. 🌿",
	},
	"lesson_load_error": {
		"en": "I couldn't load that lesson right now. Please try again. 🔁",
		"no": "Jeg kunne ikke laste inn den leksjonen akkurat nå. Vennligst prøv igjen. 🔁",
	},
	"lesson_1_load_error": {
		"en": "I couldn't load Lesson 1 right now. Please try again. 🔁",
		"no": "Jeg kunne ikke laste inn Leksjon 1 akkurat nå. Vennligst prøv igjen. 🔁",
	},
	"ask_lesson_number": {
		"en": "Great! Which lesson are you currently working on? 📚",
		"no": "Flott! Hvilken leksjon jobber du med nå? 📚",
	},
	"name_prompt": {
		"en": "Welcome! I'm your spiritual coach for A Course in Miracles. I see your name in Telegram is {full}. Is it OK if I call you {first}? 👋",
		"no": "Velkommen! Jeg er din åndelige veileder for A Course in Miracles. Jeg ser at navnet ditt i Telegram er {full}. Er det greit at jeg kaller deg {first}? 👋",
	},
	"consent_prompt": {
		"en": "Before we continue: Do you consent to me storing the conversation and relevant info to support you? At any time you may erase all your data with GDPR erase. 🗑️ (yes/no)",
		"no": "Før vi fortsetter: Er det greit at jeg lagrer samtalen og relevant informasjon for å gi deg oppfølging? Du kan når som helst slette alle dataene dine med kommandoen 'GDPR erase'. 🗑️ (ja/nei)",
	},
	"consent_granted": {
		"en": "Thank you for consenting to store your conversation data. This helps me provide better support. 🙏\nIf you have any concerns type: gdpr",
		"no": "Takk for at du samtykker til å lagre samtalen. Dette hjelper meg å gi deg bedre støtte. 🙏\nHvis du har bekymringer, skriv: gdpr",
	},
	"commitment_prompt": {
		"en": "Beautiful, {name}!\nAre you interested in exploring these lessons together? I'm here to guide and support you on this journey. Will you commit to doing the ACIM lessons each day? 🌿",
		"no": "Herlig, {name}!\nEr du interessert i å utforske disse leksjonene sammen med meg? Jeg er her for å veilede og støtte deg på denne reisen. Er du bestemt for å gjøre ACIM leksjonene hver dag så godt som? 🌿",
	},
	"ask_new_or_continuing": {
		"en": "Now, {name}, are you new to ACIM, or have you already begun working with the lessons? 🌱",
		"no": "Nå, {name}, er du ny til ACIM, eller har du allerede begynt med leksjonene? 🌱",
	},
}


def get_onboarding_message(key: str, language: str = "en") -> str:
	"""Return a template message for the onboarding flow.

	Templates may include placeholders such as `{name}` which the caller can format.
	"""
	lang_key = language
	if isinstance(language, str):
		lname = language.lower()
		if lname in ("norwegian", "nb", "nn"):
			lang_key = "no"
		elif lname in ("english", "en"):
			lang_key = "en"
		else:
			lang_key = language

	entry = ONBOARD_MESSAGES.get(key, None)
	if not entry:
		return ""
	return entry.get(lang_key, entry.get("en", ""))


def get_lesson_confirmation_prompt(language: str, lesson_id: int) -> str:
	"""Return a bilingual, gentle confirmation prompt asking if the user
	completed the reported lesson yesterday.
	"""
	template = get_onboarding_message("confirm_lesson", language)
	try:
		return template.format(lesson_id=lesson_id)
	except Exception:
		# Fallback to a simple English message if formatting fails
		return ONBOARD_MESSAGES["confirm_lesson"]["en"].format(lesson_id=lesson_id)


# Confirmation prompt template for when a user reports a current lesson
ONBOARD_MESSAGES["confirm_lesson"] = {
	"en": "Yesterday you told me you were on Lesson {lesson_id}. From a gentle, loving place: did you complete that lesson yesterday? Reply 'yes' to receive today's lesson, or 'no' if you'd like to continue where you left off.",
	"no": "I går sa du at du var på Leksjon {lesson_id}. Fra et mildt, kjærlig sted: fullførte du den leksjonen i går? Svar 'ja' for å motta dagens leksjon, eller 'nei' hvis du vil fortsette der du slapp.",
}
