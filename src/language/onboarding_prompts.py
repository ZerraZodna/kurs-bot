from __future__ import annotations

from typing import Dict


def get_lesson_1_welcome_message(language: str, name: str) -> str:
	messages = {
		"no": f"""Perfekt, {name}! La oss begynne sammen med Leksjon 1. Dette er hvor transformasjonen starter.

📅 <strong>Daglig støtte</strong>: Hver morgen kl. 07:30 sender jeg deg neste leksjon.
💬 <strong>Alltid tilgjengelig</strong>: Du kan ta kontakt når som helst for å diskutere innsikter, stille spørsmål, eller reflektere sammen.

Ta deg tid med dagens leksjon. Når du er klar til å snakke om den, er jeg her. 🌿""",
		"en": f"""Perfect, {name}! Let's begin together with Lesson 1. This is where transformation starts.

📅 <strong>Daily support</strong>: Each morning at 7:30 AM, I'll send you the next lesson.
💬 <strong>Always available</strong>: You can reach out anytime to discuss insights, ask questions, or reflect together.

If you want to change the time, or need to take a pause, just let me know.

Take your time with today's lesson. If you have any questions, please ask me. 🌿""",
	}
	return messages.get(language, messages["en"])


def get_continuation_welcome_message(language: str, name: str, lesson_id: int) -> str:
	messages = {
		"no": f"""Flott, {name}! Du er på Leksjon {lesson_id}. La oss fortsette reisen sammen.

📅 <strong>Daglig støtte</strong>: Hver morgen kl. 07:30 sender jeg deg neste leksjon.
💬 <strong>Alltid tilgjengelig</strong>: Du kan ta kontakt når som helst for å diskutere, stille spørsmål, eller reflektere.

Her er dagens leksjon:""",
		"en": f"""Wonderful, {name}! You're on Lesson {lesson_id}. Let's continue this journey together.

📅 <strong>Daily support</strong>: Each morning at 7:30 AM, I'll send you the next lesson.
💬 <strong>Always available</strong>: You can reach out anytime to discuss, ask questions, or reflect.

Here's today's lesson:""",
	}
	return messages.get(language, messages["en"])


def get_onboarding_complete_message_text(language: str, name: str) -> str:
	messages = {
		"no": f"""Velkommen til vårt åndelige fellesskap, {name}! 🙏

Jeg er her for å støtte deg på reisen din med A Course in Miracles.

📅 <strong>Daglige påminnelser satt opp</strong> - Jeg vil sende deg leksjoner hver dag klokken 07:30. Du kan endre tiden når som helst.

Du kan også:
💬 <strong>Chat med meg når som helst</strong> - Still spørsmål, del innsikter eller diskuter leksjonene
📖 <strong>Utforsk leksjoner</strong> - Spør meg om noen av de 365 leksjonene når du er klar""",
		"en": f"""Welcome to our spiritual community, {name}! 🙏

I'm here to support you on your journey with A Course in Miracles.

📅 <strong>Daily reminders set up</strong> - I'll send you lessons every day at 07:30 AM. You can change the time anytime.

You can also:
💬 <strong>Chat with me anytime</strong> - Ask questions, share insights, or discuss the lessons
📖 <strong>Explore lessons</strong> - Ask me about any of the 365 lessons whenever you're ready""",
	}
	return messages.get(language, messages["en"])


# Onboarding messages - simplified to name + consent only
ONBOARD_MESSAGES = {
	"consent_declined": {
		"en": "Understood. I won't store your information. If you change your mind, just message me again. 🙏",
		"no": "Forstått. Jeg lagrer ikke informasjonen din. Hvis du ombestemmer deg, bare send meg en melding igjen. 🙏",
	},
	"consent_prompt": {
		"en": "Hi {name}! 👋\n\nI'm your spiritual companion for A Course in Miracles. Each day, I'll send you one lesson and we can chat about it anytime.\n\nTo help me support you better: Do you consent to me storing our conversation? You can erase your data anytime with 'GDPR erase'. 🗑️ (yes/no)",
		"no": "Hei {name}! 👋\n\nJeg er din åndelige følgesvenn for Et kurs i mirakler. Hver dag sender jeg deg én leksjon, og vi kan snakke om den når som helst.\n\nFor å hjelpe meg å støtte deg bedre: Samtykker du til at jeg lagrer samtalen vår? Du kan slette dataene dine når som helst med 'GDPR erase'. 🗑️ (ja/nei)",
	},
	"consent_granted": {
		"en": "Thank you! You're all set. 🙏\n\nWelcome to our spiritual community! You can ask me about ACIM lessons anytime, or we can chat about anything on your mind.",
		"no": "Takk! Du er klar. 🙏\n\nVelkommen til vårt åndelige fellesskap! Du kan spørre meg om ACIM-leksjoner når som helst, eller vi kan snakke om alt som opptar deg.",
	},
	"lesson_load_error": {
		"en": "I couldn't load that lesson right now. Please try again. 🔁",
		"no": "Jeg kunne ikke laste inn den leksjonen akkurat nå. Vennligst prøv igjen. 🔁",
	},
	"lesson_1_load_error": {
		"en": "I couldn't load Lesson 1 right now. Please try again. 🔁",
		"no": "Jeg kunne ikke laste inn Leksjon 1 akkurat nå. Vennligst prøv igjen. 🔁",
	},
	"lesson_0_fallback": {
		"en": "Introduction\n\nWelcome to A Course in Miracles. This introduction gives you the context for the journey ahead and how to work with the lessons gently, one day at a time.",
		"no": "Introduksjon\n\nVelkommen til Et kurs i mirakler. Denne introduksjonen gir deg rammen for reisen videre og hvordan du kan jobbe med leksjonene rolig, én dag av gangen.",
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


def format_onboarding_message_with_name(template: str, name: str) -> str:
	"""Format an onboarding message template with the user's name.
	
	Args:
		template: The message template containing optional {name} placeholder
		name: The user's name (from get_name which returns "friend" as fallback)
	
	Returns:
		The template with {name} replaced by actual name, or cleaned up if name is "friend"
	"""
	if name and name != "friend" and "{name}" in template:
		return template.replace("{name}", name)
	elif "{name}" in template:
		# Remove the placeholder if name is not available
		return template.replace("{name}! ", "").replace("{name} ", "")
	return template


def get_lesson_confirmation_prompt(language: str, lesson_id: int) -> str:
	"""Return a bilingual, gentle confirmation prompt with a repeat option."""
	template = get_onboarding_message("confirm_lesson", language)
	try:
		return template.format(lesson_id=lesson_id)
	except Exception:
		# Fallback to a simple English message if formatting fails
		return ONBOARD_MESSAGES["confirm_lesson"]["en"].format(lesson_id=lesson_id)


# Confirmation prompt template for when a user reports a current lesson
ONBOARD_MESSAGES["confirm_lesson"] = {
    "en": "From a gentle, loving place: You mentioned Lesson {lesson_id} last time. Would you like to move to the next lesson, or continue where you left off? Reply 'yes' to move forward, or 'no' to stay with this lesson.",
    "no": "Fra et mildt, kjærlig sted: Du nevnte Leksjon {lesson_id} sist. Vil du gå videre til neste leksjon, eller fortsette der du slapp? Svar 'ja' for å gå videre, eller 'nei' for å bli på denne leksjonen.",
}

