# Onboarding Process (Current Workflow)

This document describes the actual onboarding sequence and the exact texts used in the current Kurs Bot implementation. The process is language-aware (English/Norwegian) and branches based on user responses.

---

## 1. Name Collection

**Bot:**
- English: `Welcome! I'm your spiritual coach for A Course in Miracles. What's your name?`
- Norwegian: `Velkommen! Jeg er din åndelige veileder for A Course in Miracles. Hva heter du?`

### 1a. User provides name
- Proceed to step 2.

### 1b. User does not provide name
- Bot will repeat or prompt again.

---

## 2. Consent for Data Storage (GDPR)

**Bot:**
- English: `Before we continue: Do you consent to me storing the conversation and relevant info to support you? (yes/no)`
- Norwegian: `Før vi fortsetter: Er det greit at jeg lagrer samtalen og relevant informasjon for å gi deg oppfølging? (ja/nei)`

### 2a. User consents (yes/ja)
- Consent is recorded. Proceed to step 3.

### 2b. User declines (no/nei)
- **Bot:** `Understood. I won't store your information. If you change your mind, just message me again.`
- User data is deleted. End onboarding.

---

## 3. Commitment to Lessons


**Bot:**
- English: `Beautiful, <name>!\nAre you interested in exploring these lessons together? I'm here to guide and support you on this journey.\nWould you like to begin? (yes/no)`
- Norwegian: `Herlig, <name>!\nEr du interessert i å utforske disse leksjonene sammen med meg? Jeg er her for å veilede og støtte deg på denne åndelige reisen.\nVil du begynne? (ja/nei)`

### 3a. User commits (yes/ja/etc)
- Proceed to step 4.

### 3b. User declines (no/nei/etc)
- **Bot:** `Understood. I won't ask about ACIM lessons. If you want to resume later, just message me.`
- End onboarding.

---

## 4. Lesson Status

**Bot:**
- English: `Wonderful, <name>! Are you new to ACIM, or have you already begun working with the lessons?`
- Norwegian: `Flott, <name>! Er du ny til ACIM, eller har du allerede begynt med leksjonene?`

#### User answers:
- If user says "new"/"ny"/"beginner":
	- **Bot:** Sends Lesson 1 welcome message and Lesson 1 content.
- If user says "continuing"/"fortsetter"/"already" or provides a lesson number:
	- **Bot:** Asks: `Great! Which lesson are you currently working on?` (Norwegian: `Flott! Hvilken leksjon jobber du med nå?`)
	- User provides lesson number, bot sends continuation welcome and that lesson's content.

---

## 5. Onboarding Complete

**Bot:**
- English: `Welcome to our spiritual community, <name>! 🙏\nI'm here to support you on your journey with A Course in Miracles.\n📅 **Daily reminders set up** - I'll send you lessons every day at 07:30 AM. You can change the time anytime.\nYou can also:\n💬 **Chat with me anytime** - Ask questions, share insights, or discuss the lessons\n📖 **Explore lessons** - Ask me about any of the 365 lessons whenever you're ready`
- Norwegian: `Velkommen til vårt åndelige fellesskap, <name>! 🙏\nJeg er her for å støtte deg på reisen din med A Course in Miracles.\n📅 **Daglige påminnelser satt opp** - Jeg vil sende deg leksjoner hver dag klokken 07:30. Du kan endre tiden når som helst.\nDu kan også:\n💬 **Chat med meg når som helst** - Still spørsmål, del innsikter eller diskuter leksjonene\n📖 **Utforsk leksjoner** - Spør meg om noen av de 365 leksjonene når du er klar`

---

## Example Lesson Welcome Messages

**Lesson 1 (English):**
```
Perfect, <name>! Let's begin together with Lesson 1. This is where transformation starts.

📅 **Daily support**: Each morning at 7:30 AM, I'll send you the next lesson.
💬 **Always available**: You can reach out anytime to discuss insights, ask questions, or reflect together.

Take your time with today's lesson. When you're ready to talk about it, I'm here. 🌿
```

**Lesson 1 (Norwegian):**
```
Perfekt, <name>! La oss begynne sammen med Leksjon 1. Dette er hvor transformasjonen starter.

📅 **Daglig støtte**: Hver morgen kl. 07:30 sender jeg deg neste leksjon.
💬 **Alltid tilgjengelig**: Du kan ta kontakt når som helst for å diskutere innsikter, stille spørsmål, eller reflektere sammen.

Ta deg tid med dagens leksjon. Når du er klar til å snakke om den, er jeg her. 🌿
```

**Continuation (English):**
```
Wonderful, <name>! You're on Lesson <n>. Let's continue this journey together.

📅 **Daily support**: Each morning at 7:30 AM, I'll send you the next lesson.
💬 **Always available**: You can reach out anytime to discuss, ask questions, or reflect.

Here's today's lesson:
```

**Continuation (Norwegian):**
```
Flott, <name>! Du er på Leksjon <n>. La oss fortsette reisen sammen.

📅 **Daglig støtte**: Hver morgen kl. 07:30 sender jeg deg neste leksjon.
💬 **Alltid tilgjengelig**: Du kan ta kontakt når som helst for å diskutere, stille spørsmål, eller reflektere.

Her er dagens leksjon:
```

---

This document reflects the current onboarding logic and user-facing texts. Update as the workflow evolves.
