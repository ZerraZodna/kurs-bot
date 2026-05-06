# Kurs Bot: 8-Milestone Implementation Plan

Self-contained prompts for each milestone. Copy/paste each into a new AI conversation to implement independently.

---

Vital missing points currently (Added by JS/AI)
8b. Compliance/production hardening items are missing: rate limiting, logging middleware, audit logging, GDPR delete/export endpoints, security headers, performance tests, and docs (e.g., src/middleware/logging.py, src/middleware/audit.py, tests/test_performance.py, docs/DEPLOYMENT.md, .github/SECURITY.md).


## **MILESTONE 1: Foundation & Data Layer**

You are implementing Milestone 1 of the Kurs Bot project: a learning-bot system with persistent memory for customers using SQL Server.

**Project Overview:**
- **Goal:** Build a chatbot/consultant with memory that delivers daily lessons and interval reminders via DM channels (Telegram, Slack, SMS, Teams) and email.
- **Tech Stack:** Python + FastAPI + SQLAlchemy ORM + SQL Server + Alembic migrations
- **Database:** SQL Server on Windows (localhost:1433 or cloud)
- **Repository:** `d:\dev\kurs-bot` (local Windows dev environment)

**Milestone 1 Tasks:** Set up the foundation and data layer for the bot.

**1.1 - Scaffold Project & Install Dependencies**
```bash
cd d:\dev\kurs-bot
python -m venv venv
venv\Scripts\activate
pip install fastapi uvicorn sqlalchemy pyodbc alembic python-telegram-bot slack-sdk sendgrid
pip install pytest pytest-cov httpx  # for testing
```

**1.2 - Create Folder Structure**
```
kurs-bot/
├── src/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── schemas.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── message_router.py
│   │   ├── memory_manager.py
│   │   ├── dialogue_engine.py
│   │   ├── lesson_engine.py
│   │   └── scheduler.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── database.py
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── telegram.py
│   │   ├── slack.py
│   │   ├── twilio.py
│   │   └── email.py
│   └── config.py
├── migrations/
│   └── versions/
├── tests/
│   ├── __init__.py
│   └── test_models.py
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── main.py
├── requirements.txt
└── README.md
```

**1.3 - Set Up SQLAlchemy Models & Database Connection**

In `src/models/database.py`:
- Define SQLAlchemy engine with connection pooling for SQL Server: `create_engine('mssql+pyodbc://sa:PASSWORD@localhost:1433/kurs_bot_db', pool_size=10, max_overflow=20)`
- Create `Base` class for ORM models
- Define ORM models: `User`, `Memory`, `Lesson`, `Schedule`, `MessageLog`, `Unsubscribe`
  - `User`: user_id (PK), external_id (channel-specific), channel, phone_number, email, first_name, last_name, opted_in, created_at, last_active_at
  - `Memory`: memory_id (PK), user_id (FK), category, key, value (JSON-friendly), confidence, created_at, updated_at, ttl_expires_at
  - `Lesson`: lesson_id (PK), title, content, difficulty_level, duration_minutes, created_at
  - `Schedule`: schedule_id (PK), user_id (FK), lesson_id (FK, nullable), schedule_type (one_time|daily|weekly|interval_reminder), cron_expression, next_send_time, last_sent_at, is_active, created_at
  - `MessageLog`: message_id (PK, BIGINT), user_id (FK), direction (inbound|outbound), channel, external_message_id, content, status (queued|sent|delivered|failed), error_message, created_at, processed_at
  - `Unsubscribe`: unsubscribe_id (PK), user_id (FK), channel, reason, unsubscribed_at, compliance_required

Use SQLAlchemy 2.0 syntax with `nullable=False` defaults, `DateTime2` for timestamps (UTC), and proper foreign key constraints.

**1.4 - Initialize Alembic Migrations**
```bash
cd d:\dev\kurs-bot
alembic init migrations
```
Edit `migrations/alembic.ini`:
- Set `sqlalchemy.url = mssql+pyodbc://sa:PASSWORD@localhost:1433/kurs_bot_db?driver=ODBC+Driver+18+for+SQL+Server`
- Edit `migrations/env.py` to import your models and set `target_metadata = Base.metadata`

**1.5 - Create Initial Migration**
```bash
alembic revision --autogenerate -m "init_create_all_tables"
alembic upgrade head
```

**1.6 - Set Up Configuration & Database Session Manager**

In `src/config.py`:
- Load environment variables: `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `SLACK_BOT_TOKEN`, `SENDGRID_API_KEY`, etc.
- Use `pydantic_settings.BaseSettings` for config management
- Secrets: store in `.env` file (add `.env` to `.gitignore`)

In `src/models/__init__.py`:
- Export session factory: `SessionLocal` for dependency injection in FastAPI
- Provide `get_db()` generator for FastAPI dependency

**1.7 - Write Unit Tests for Models**

In `tests/test_models.py`:
- Test User model CRUD operations (create, read, update, delete)
- Test Memory model with JSON values and TTL
- Test Schedule model with cron expression validation
- Use pytest fixtures for setup/teardown of test database (in-memory SQLite or separate test SQL Server instance)

**1.8 - Create README.md**

Document:
- Project name: Kurs Bot
- Purpose: Chatbot with persistent memory for wellness lessons via DM + email
- Tech stack: FastAPI, SQLAlchemy, SQL Server, Alembic
- Setup: how to install dependencies, initialize DB, run migrations
- Configuration: list environment variables needed

**Expected Deliverables:**
- Folder structure created
- SQLAlchemy ORM models defined and validated
- Alembic migrations initialized and first migration applied
- Configuration system in place
- Basic CRUD tests passing
- README.md with setup instructions

---

## **MILESTONE 2: Message Channel Integration (Phase 1: Telegram)**

You are implementing Milestone 2 of the Kurs Bot project: integrating Telegram as the first message channel.

**Project Context:**
- Previous milestone completed: data layer (SQLAlchemy models, DB, Alembic)
- This milestone: receive Telegram messages via webhook, normalize, and log

**2.1 - Create Telegram Integration Module**

In `src/integrations/telegram.py`:
- Create `TelegramHandler` class
- Method `parse_webhook(request: dict) -> dict`: normalize Telegram update JSON to internal format:
  ```python
  {
    "user_id": telegram_user_id (str),
    "channel": "telegram",
    "text": message_text,
    "external_message_id": message_id (str),
    "timestamp": datetime
  }
  ```
- Handle edge cases: empty message, bot commands, missing text fields
- Validate Telegram bot token from config

**2.2 - Create FastAPI Webhook Endpoint**

In `src/api/routes.py`:
- POST `/webhook/telegram`: 
  - Accept Telegram Bot API JSON payload
  - Call `TelegramHandler.parse_webhook()`
  - Dispatch to `MessageRouter.route_message()`
  - Return `{"ok": true}` (Telegram expects 200 OK immediately)
  - Log any errors without blocking response
- Add request validation: check Telegram bot token header if needed

**2.3 - Implement MessageRouter Service**

In `src/services/message_router.py`:
- Create `MessageRouter` class
- Method `route_message(normalized_msg: dict, session: Session) -> Task`:
  - Extract user_id, channel, text
  - Insert/update user in User table if new
  - Record message in MessageLog table with status="received"
  - Dispatch to `DialogueEngine.process_message(user_id, text)`
  - Return task/result for async handling

**2.4 - Create Pydantic Schemas**

In `src/api/schemas.py`:
- Define `TelegramUpdate` schema (for webhook payload)
- Define `MessageIn` schema (normalized message format)
- Define `MessageOut` schema (for API responses)

**2.5 - Add Outbound Message Sending**

In `src/integrations/telegram.py`:
- Add `send_message(user_id: int, text: str, channel: str) -> dict`:
  - Look up user's external_id from DB (Telegram user_id)
  - Call Telegram Bot API: `POST https://api.telegram.org/botTOKEN/sendMessage` with chat_id & text
  - Handle errors: rate limiting, invalid user, etc.
  - Return result dict with message_id or error

**2.6 - Implement Message Logging**

Modify `MessageRouter.route_message()`:
- Always log inbound messages to MessageLog table
- Log outbound messages when bot sends responses
- Include: user_id, channel, direction, external_message_id, content, status, timestamp

**2.7 - Set Up Telegram Webhook (Local Development)**

For local testing:
- Use ngrok or similar to expose FastAPI to internet: `ngrok http 8000`
- Run: `curl -X POST https://api.telegram.org/botTOKEN/setWebhook -d url=https://YOUR_NGROK_URL/webhook/telegram`

**2.8 - Write Integration Tests**

In `tests/test_telegram.py`:
- Mock Telegram API responses
- Test `parse_webhook()` with sample Telegram payloads
- Test message normalization and logging
- Test error handling (missing fields, invalid JSON)

**Expected Deliverables:**
- Telegram webhook endpoint working (`POST /webhook/telegram`)
- Messages normalized and logged to MessageLog table
- User auto-created on first message
- MessageRouter dispatches to DialogueEngine
- Telegram outbound message sending implemented
- Integration tests passing
- Local ngrok setup documented

---

## **MILESTONE 3: User Memory & Dialogue**

You are implementing Milestone 3 of the Kurs Bot project: storing user memory and handling conversations.

**Project Context:**
- Milestones 1–2 completed: data layer, Telegram messaging
- This milestone: capture user learning goals, preferences, and engagement history

**3.1 - Implement MemoryManager Service**

In `src/services/memory_manager.py`:
- Create `MemoryManager` class
- Method `get_memory(user_id: int, keys: List[str], session: Session) -> Dict`:
  - Query Memory table for matching key/user_id pairs
  - Return dict of {key: value} for non-expired entries
  - Skip TTL-expired entries
- Method `set_memory(user_id: int, key: str, value: str, ttl_seconds: Optional[int], session: Session) -> Memory`:
  - Insert or update Memory record
  - Calculate `ttl_expires_at` if TTL provided
  - Return created/updated Memory object
- Method `search_memory(user_id: int, query: str, session: Session) -> List[Memory]`:
  - Simple LIKE query on Memory.key or Memory.value
- Method `clear_expired(session: Session) -> int`:
  - Delete all Memory entries where `ttl_expires_at < now()`

**3.2 - Implement DialogueEngine Service**

In `src/services/dialogue_engine.py`:
- Create `DialogueEngine` class (dependency: MemoryManager, session)
- Method `process_message(user_id: int, text: str, session: Session) -> str`:
  - Parse user input for keywords (goal, time, preference, etc.)
  - Extract memory items from message (e.g., "my goal is Python")
  - Call `MemoryManager.set_memory()` to persist
  - Generate response text
  - Return bot response string
- Implement simple rule-based dialogue:
  - If message contains "goal": store learning_goal, ask "What's your goal?"
  - If message contains "time": store preferred_lesson_time, ask "When do you prefer lessons?"
  - If message is "yes"/"ok": positive engagement, store engagement_score
  - Default: "Thanks for sharing. Tell me more about your learning journey."

**3.3 - Implement Conversation State Management**

In `src/services/dialogue_engine.py`:
- Add method `get_conversation_state(user_id: int, session: Session) -> dict`:
  - Return current user memory + profile
  - Include: learning_goal, preferred_time, engagement_score, last_message_time
- Add method `set_conversation_state(user_id: int, state: dict, session: Session)`:
  - Update conversation context for multi-turn dialogue

**3.4 - Integrate MemoryManager into MessageRouter**

Update `MessageRouter.route_message()`:
- Call `DialogueEngine.process_message()` after logging message
- Get bot response
- Send response back via Telegram
- Log outbound response to MessageLog

**3.5 - Create Onboarding Flow**

In `src/services/dialogue_engine.py`:
- Add method `get_onboarding_prompt(user_id: int, session: Session) -> str`:
  - Check User.created_at: if < 10 minutes ago, user is new
  - If new, return sequence of prompts:
    1. "Welcome! What's your name?" → store first_name
    2. "Nice to meet you, {name}! What's your main learning goal?" → store learning_goal
    3. "What time do you prefer to start your day?" → store preferred_lesson_time
    4. "Perfect! I'll send you one lesson each day at {time} via Telegram."

**3.6 - Store Conversation History**

Extend MessageLog schema or create new `ConversationHistory` table:
- Track multi-turn dialogue flows
- Store: user_id, user_message, bot_response, turn_number, created_at

**3.7 - Write Unit Tests**

In `tests/test_dialogue.py`:
- Mock session and Memory queries
- Test memory CRUD operations
- Test dialogue routing (extract keywords, generate responses)
- Test onboarding flow
- Test conversation state retrieval

**3.8 - Manual Test with Telegram**

- Start bot: `fastapi dev main.py`
- Send message to Telegram bot: "Hi, my goal is Python"
- Verify: memory stored in DB, bot responds appropriately

**Expected Deliverables:**
- MemoryManager service with get/set/search/clear_expired
- DialogueEngine with rule-based dialogue parsing
- Onboarding flow for new users (name, goal, preferred time)
- Conversation state tracking
- Integration with MessageRouter (message → dialogue → response → send)
- Tests passing
- Manual Telegram test working end-to-end

---

## **MILESTONE 4: Lesson Delivery & Scheduling (Basic)**

You are implementing Milestone 4 of the Kurs Bot project: delivering daily lessons and scheduling reminders.

**Project Context:**
- Milestones 1–3 completed: data layer, Telegram, dialogue/memory
- This milestone: seed lessons, schedule delivery, APScheduler integration

**4.1 - Implement LessonEngine Service**

In `src/services/lesson_engine.py`:
- Create `LessonEngine` class
- Method `get_lesson(lesson_id: int, session: Session) -> Lesson`:
  - Query Lesson table by ID
  - Return Lesson object or None
- Method `list_lessons(skip: int, limit: int, session: Session) -> List[Lesson]`:
  - Return paginated lessons
- Method `get_lesson_for_user(user_id: int, session: Session) -> Lesson`:
  - Get next undelivered lesson for user (sorted by lesson_id)
  - Consider user difficulty level from Memory table
- Method `deliver_lesson(user_id: int, lesson_id: int, session: Session) -> str`:
  - Format lesson content for messaging (chunked if >4096 chars for Telegram)
  - Send via MessageRouter
  - Record delivery in MessageLog
  - Update Schedule.last_sent_at
  - Return formatted lesson text

**4.2 - Seed Lesson Database**

Create `scripts/seed_lessons.py`:
```python
from src.models.database import SessionLocal
from src.models.database import Lesson

lessons_data = [
    {"title": "Lesson 1: Getting Started", "content": "...", "difficulty_level": 1},
    {"title": "Lesson 2: Building Blocks", "content": "...", "difficulty_level": 1},
    # ... 10-20 sample lessons
]

with SessionLocal() as session:
    for data in lessons_data:
        lesson = Lesson(**data, created_at=datetime.now(timezone.utc))
        session.add(lesson)
    session.commit()
```

Run once: `python scripts/seed_lessons.py`

**4.3 - Implement APScheduler Integration**

In `src/services/scheduler.py`:
- Create `SchedulerService` class
- Use APScheduler with `SQLAlchemyJobStore` backed by SQL Server
- Method `init_scheduler()`:
  - Initialize `BackgroundScheduler`
  - Configure job store: `SQLAlchemyJobStore(url=DATABASE_URL, tablename='apscheduler_jobs')`
  - Start scheduler on app startup
- Method `schedule_lesson(user_id: int, lesson_id: int, schedule_type: str, cron_expr: str, session: Session)`:
  - Insert into Schedule table
  - Add job to APScheduler:
    - If schedule_type="daily": `cron(hour=9, minute=0)`
    - If schedule_type="weekly": `cron(day_of_week=0, hour=9, minute=0)` (Monday)
    - If cron_expr provided: use as-is (e.g., `0 9 * * 1-5`)
  - Job function: `execute_scheduled_task(user_id, lesson_id)`
- Method `execute_scheduled_task(user_id: int, lesson_id: int)`:
  - Call `LessonEngine.deliver_lesson()`
  - Update Schedule.last_sent_at
  - Log execution to MessageLog
  - Catch and log errors

**4.4 - Add FastAPI Lifespan Events**

In `main.py`:
- Add startup event to initialize scheduler
- Add shutdown event to clean up scheduler
- Use FastAPI lifespan context manager:
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.init_scheduler()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
```

**4.5 - Create Schedule Management Endpoints**

In `src/api/routes.py`:
- POST `/api/schedule/create`: create new schedule (user_id, lesson_id, schedule_type, cron_expr)
- GET `/api/schedule/user/{user_id}`: list active schedules for user
- DELETE `/api/schedule/{schedule_id}`: deactivate schedule (set is_active=False)

**4.6 - Implement Lesson Delivery Logic**

In `LessonEngine.deliver_lesson()`:
- Format lesson for Telegram (respect 4096 char limit, split if needed)
- Add inline buttons: "Completed", "Skip", "Remind later"
- Send via `MessageRouter.send_message(user_id, lesson_text, channel="telegram")`

**4.7 - Write Tests**

In `tests/test_lessons.py`:
- Mock APScheduler and SQL Server
- Test lesson CRUD
- Test schedule creation and job registration
- Test cron expression parsing
- Test delivery formatting (splitting long content)

**4.8 - Manual Test**

- Seed 5 test lessons
- Create user and schedule for 9am today
- Verify APScheduler job created
- Manually trigger job: verify message sent to Telegram

**Expected Deliverables:**
- LessonEngine with get/list/deliver methods
- APScheduler integrated with SQL Server job store
- Lessons table seeded with 10–20 sample lessons
- Schedule creation endpoint working
- Daily/weekly/cron scheduling working
- Lesson delivery to Telegram working
- Tests passing
- Manual test showing message at scheduled time

---

## **MILESTONE 5: Multi-Channel Support (Slack, SMS via Twilio)**

You are implementing Milestone 5 of the Kurs Bot project: expanding to Slack and SMS channels.

**Project Context:**
- Milestones 1–4 completed: core lessons & scheduling
- This milestone: Slack webhook, SMS via Twilio, channel-agnostic message sending

**5.1 - Implement Slack Integration**

In `src/integrations/slack.py`:
- Create `SlackHandler` class
- Method `parse_webhook(request: dict) -> dict`: normalize Slack event JSON
  - Handle url_verification challenge
  - Extract message type (app_mention, message)
  - Normalize to internal format: {user_id, channel, text, external_message_id, timestamp}
- Method `send_message(user_id: str, text: str, session: Session) -> dict`:
  - Look up user's Slack user_id from User.external_id
  - Call Slack API: `chat.postMessage` with user_id (DM channel)
  - Handle errors (user not found, rate limits)
  - Return result
- OAuth setup: store Slack bot token in config

**5.2 - Create Slack Webhook Endpoint**

In `src/api/routes.py`:
- POST `/webhook/slack`:
  - Verify Slack request signature (middleware)
  - Call `SlackHandler.parse_webhook()`
  - Handle url_verification response
  - Dispatch to MessageRouter
  - Return 200 OK immediately

**5.3 - Implement Twilio SMS Integration**

In `src/integrations/twilio.py`:
- Create `TwilioHandler` class
- Method `parse_webhook(request: dict) -> dict`: normalize Twilio Webhook JSON
  - Extract From (sender phone), Body (message text), MessageSid
  - Normalize to internal format
- Method `send_sms(user_id: int, text: str, session: Session) -> dict`:
  - Look up user's phone_number from User table
  - Call Twilio API: `messages.create(to=phone_number, from_=BOT_PHONE, body=text)`
  - Chunk message if > 160 chars (SMS limit)
  - Return result

**5.4 - Create Twilio Webhook Endpoint**

In `src/api/routes.py`:
- POST `/webhook/sms`:
  - Verify Twilio request signature
  - Call `TwilioHandler.parse_webhook()`
  - Dispatch to MessageRouter
  - Return TwiML response (empty for SMS)

**5.5 - Refactor MessageRouter for Channel Abstraction**

Update `src/services/message_router.py`:
- Generalize `route_message()` to handle any channel
- Create channel dispatcher:
  ```python
  def send_message_via_channel(user_id: int, text: str, channel: str, session: Session):
      if channel == "telegram":
          return TelegramHandler.send_message(user_id, text)
      elif channel == "slack":
          return SlackHandler.send_message(user_id, text, session)
      elif channel == "sms":
          return TwilioHandler.send_sms(user_id, text, session)
      else:
          raise ValueError(f"Unknown channel: {channel}")
  ```

**5.6 - Update DialogueEngine for Multi-Channel**

Modify `DialogueEngine.process_message()`:
- Accept `channel` parameter
- Adjust response formatting per channel (emoji for Slack, plain text for SMS)
- Call `MessageRouter.send_message_via_channel()`

**5.7 - Update Onboarding for Channel Selection**

In `DialogueEngine.get_onboarding_prompt()`:
- Ask user for preferred channel: "Do you prefer Telegram, Slack, or SMS?"
- Store in Memory: "preferred_channel"
- For SMS/Slack: collect phone number or Slack user ID

**5.8 - Update LessonEngine for Channel-Aware Delivery**

In `LessonEngine.deliver_lesson()`:
- Get user's preferred_channel from Memory
- Format lesson per channel constraints:
  - Telegram: 4096 chars, markdown, inline buttons
  - Slack: thread-based, blocks
  - SMS: 160 chars per message, plain text
- Call `MessageRouter.send_message_via_channel()`

**5.9 - Write Integration Tests**

In `tests/test_slack.py`, `tests/test_twilio.py`:
- Mock Slack/Twilio APIs
- Test webhook parsing and normalization
- Test outbound message sending
- Test error handling (rate limits, user not found)

**5.10 - Update Configuration**

In `.env`:
- Add: `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`
- Add: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`

**Expected Deliverables:**
- Slack webhook integration working
- SMS/Twilio webhook integration working
- Channel-agnostic MessageRouter
- Multi-channel lesson delivery
- Updated onboarding to ask for channel preference
- Tests passing for Slack and SMS
- `.env` config updated with new channel tokens

---

## **MILESTONE 6: Email Support & SendGrid Integration**

You are implementing Milestone 6 of the Kurs Bot project: email channel support.

**Project Context:**
- Milestones 1–5 completed: all DM channels
- This milestone: SendGrid email integration, opt-out links, bounce handling

**6.1 - Implement Email Integration**

In `src/integrations/email.py`:
- Create `EmailHandler` class
- Method `send_email(user_id: int, subject: str, html_body: str, session: Session) -> dict`:
  - Query user email from User table
  - Call SendGrid API: `mail.send()`
  - Include unsubscribe link: `/api/opt-out?token={user_id}`
  - Handle errors (invalid email, rate limits)
  - Return result (message_id or error)
- Method `send_email_with_template(user_id: int, template_id: str, substitutions: dict, session: Session)`:
  - Send using SendGrid dynamic template
  - Include dynamic unsubscribe link

**6.2 - Create Email Webhook Endpoint (Bounce Handling)**

In `src/api/routes.py`:
- POST `/webhook/email/bounce`:
  - Verify SendGrid request signature
  - Parse bounce/complaint events
  - On bounce/complaint: set User.opted_in=False, log to Unsubscribe table
  - Return 200 OK

**6.3 - Update LessonEngine for Email**

In `LessonEngine.deliver_lesson()`:
- If channel="email":
  - Format lesson as HTML (with styling)
  - Add lesson_id and completion link
  - Call `EmailHandler.send_email()`
  - Example subject: "Lesson 5: {lesson_title}"
  - Include: lesson content, "Mark Complete" link, "Skip" link

**6.4 - Create Opt-Out Handler**

In `src/api/routes.py`:
- GET `/api/opt-out`:
  - Accept query params: user_id (or encrypted token), channel
  - Update User.opted_in=False (or specific channel unsubscribe)
  - Log to Unsubscribe table: reason (auto from email), timestamp
  - Return confirmation page: "You've been unsubscribed. You can re-subscribe anytime."

**6.5 - Add Email Templates**

Create `src/integrations/email_templates.py`:
- Daily lesson template (HTML):
  ```html
  <h1>{lesson_title}</h1>
  <p>{lesson_content}</p>
  <a href="https://bot.example.com/complete/{lesson_id}">Mark as Complete</a>
  <a href="https://bot.example.com/opt-out?user_id={user_id}">Unsubscribe</a>
  ```
- Reminder template (HTML):
  ```html
  <p>Hi {first_name}, don't forget your lesson today!</p>
  <a href="https://bot.example.com/complete/{lesson_id}">Start Lesson</a>
  ```

**6.6 - Update MessageRouter for Email**

Modify `MessageRouter.route_message()`:
- Support inbound emails (from email replies)
- Parse email content as user message
- Store as inbound message in MessageLog

**6.7 - Update Configuration**

In `.env`:
- Add: `SENDGRID_API_KEY`
- Add: `EMAIL_FROM_ADDRESS` (e.g., bot@example.com)
- Add: `WEBHOOK_BASE_URL` (for opt-out links)

**6.8 - Write Tests**

In `tests/test_email.py`:
- Mock SendGrid API
- Test email sending with/without template
- Test bounce webhook handling
- Test opt-out link generation and handling
- Test HTML template rendering

**6.9 - Manual Test**

- Create user with email channel preference
- Schedule a lesson
- Verify SendGrid sends email with correct subject/body
- Click opt-out link, verify user marked opted_out

**Expected Deliverables:**
- EmailHandler with send_email() and template support
- Email webhook endpoint for bounce/complaint handling
- Opt-out endpoint working
- Email channel support in LessonEngine
- Email templates (lesson, reminder)
- Tests passing
- Manual test showing email delivery and opt-out

---

## **MILESTONE 7: Interval Reminders & Advanced Scheduling**

You are implementing Milestone 7 of the Kurs Bot project: interval-based reminders for lesson progress.

**Project Context:**
- Milestones 1–6 completed: all channels, email, basic scheduling
- This milestone: send reminders if user hasn't completed lesson after X hours

**7.1 - Extend Schedule Table Schema**

Alembic migration:
- Add columns to Schedule table:
  - `interval_type`: VARCHAR(50) - 'daily', 'weekly', 'custom_cron', 'interval_reminder'
  - `interval_hours`: INT nullable - e.g., 2 (remind after 2 hours)
  - `reminder_count`: INT default 0 - how many reminders to send per day
  - `last_reminder_sent_at`: DATETIME2 nullable - track reminder timing
  
Run migration: `alembic revision --autogenerate -m "add_interval_reminder_fields" && alembic upgrade head`

**7.2 - Update LessonEngine for Completion Tracking**

Add methods to `src/services/lesson_engine.py`:
- `mark_lesson_complete(user_id: int, lesson_id: int, session: Session)`:
  - Store completion status in Memory table: key="lesson_completion_{lesson_id}", value="true"
  - Update Schedule.last_sent_at to reset reminder timer
- `is_lesson_complete(user_id: int, lesson_id: int, session: Session) -> bool`:
  - Check Memory for completion flag
- `get_hours_since_delivery(user_id: int, lesson_id: int, session: Session) -> float`:
  - Query MessageLog for most recent outbound lesson
  - Calculate hours since delivery
  - Return hours or None if not sent

**7.3 - Implement Interval Reminder Logic**

In `src/services/scheduler.py`:
- Add method `check_interval_reminders(session: Session)`:
  - Query all active Schedules where `schedule_type="interval_reminder"`
  - For each schedule:
    - Get hours since delivery: `LessonEngine.get_hours_since_delivery(user_id, lesson_id)`
    - If hours >= `interval_hours` and `is_lesson_complete()=False`:
      - Increment reminder_count
      - If reminder_count <= 3 (max reminders):
        - Send reminder message via user's channel
        - Update last_reminder_sent_at
      - Else: mark schedule as completed or paused
- Schedule this check to run every 15–60 minutes via APScheduler

**7.4 - Create Reminder Message Templates**

In `src/services/lesson_engine.py`:
- Method `get_reminder_message(user_id: int, lesson_id: int, reminder_count: int, session: Session) -> str`:
  - 1st reminder (2h): "Still interested in your lesson? You can continue or skip."
  - 2nd reminder (4h): "Don't miss out! Complete your lesson now or reschedule."
  - 3rd reminder (24h): "Last chance for today's lesson. Start now or it will reset tomorrow."

**7.5 - Update Schedule Creation Endpoint**

In `src/api/routes.py`:
- Extend POST `/api/schedule/create` to accept:
  - `schedule_type`: "daily", "weekly", "interval_reminder"
  - `interval_hours`: 2 (if interval_reminder)
  - `reminder_count`: max reminders per day

**7.6 - Add Completion Endpoints**

In `src/api/routes.py`:
- GET `/api/lesson/{lesson_id}/complete`:
  - Mark lesson complete for authenticated user
  - Reset reminder timer
  - Return success message
- GET `/api/lesson/{lesson_id}/skip`:
  - Skip lesson without marking complete
  - Reset timer anyway
  - Return success message

**7.7 - Update LessonEngine Delivery to Track Start**

Modify `deliver_lesson()`:
- Log delivery timestamp to Memory: `lesson_start_time_{lesson_id}`
- Include "Start" and "Skip" buttons in message (channel-specific)

**7.8 - Write Tests**

In `tests/test_intervals.py`:
- Mock time passage
- Test interval reminder check logic
- Test completion tracking
- Test reminder message escalation (1st, 2nd, 3rd)
- Test max reminder limit
- Test button click handling (complete/skip)

**7.9 - Manual Test**

- Schedule lesson for now via API
- Send lesson to user
- Wait 5 minutes, manually trigger reminder check
- Verify 1st reminder sent
- Click "Complete" button
- Verify reminder timer reset

**Expected Deliverables:**
- Schedule table schema updated with interval fields
- Completion tracking in Memory table
- Interval reminder checker running every 15–60 minutes
- Reminders escalating (1st, 2nd, 3rd) based on time
- Completion and skip endpoints working
- Tests passing
- Manual test showing reminder flow

---

## **MILESTONE 8: Compliance, Privacy & Production Hardening**

You are implementing Milestone 8 of the Kurs Bot project: security, compliance, and production readiness.

**Project Context:**
- Milestones 1–7 completed: all core features
- This milestone: rate limiting, encryption, GDPR compliance, audit logs, security

**8.1 - Implement Rate Limiting**

Install: `pip install slowapi`

In `main.py`:
- Add middleware: `slowapi` limiter
- Configure per-user limits: 10 messages/minute, 100 messages/day
- Configure per-endpoint limits: webhooks 30 req/sec, API 10 req/sec
- Return 429 Too Many Requests on violation

**8.2 - Add Request/Response Logging Middleware**

Create `src/middleware/logging.py`:
- Log all inbound requests: timestamp, IP, user_id (if available), endpoint, method, status
- Log all outbound messages: timestamp, user_id, channel, direction, message_id, status
- Store logs to MessageLog table + optional file logging
- Include request/response headers (except secrets)
- Implement log retention: delete logs > 90 days old via scheduled job

**8.3 - Encrypt SQL Server Connection**

In `src/config.py`:
- Enable SQL Server TLS: add `Connection Timeout=30;Encrypt=yes;TrustServerCertificate=no` to connection string
- Use ODBC Driver 18 for SQL Server (latest)
- Test connection: `python -c "from src.models.database import engine; engine.connect()"`

**8.4 - Implement Environment-Based Secrets Management**

In `src/config.py`:
- Use `pydantic_settings.BaseSettings` with `.env` file
- Never log API keys (redact in logs)
- Validate required secrets on startup
- Example:
  ```python
  class Settings(BaseSettings):
      DATABASE_URL: str
      TELEGRAM_BOT_TOKEN: SecretStr  # Pydantic SecretStr
      SENDGRID_API_KEY: SecretStr
      class Config:
          env_file = ".env"
  settings = Settings()
  ```

**8.5 - Add GDPR / Data Privacy Compliance**

In `src/api/routes.py`:
- Endpoint DELETE `/api/user/{user_id}/delete`:
  - Verify user owns request (authentication/token check)
  - Delete from Users, Memory, MessageLog tables
  - Keep Unsubscribe and audit logs for compliance
  - Log deletion event with timestamp and reason
  - Return: "Your data has been permanently deleted."
- Endpoint GET `/api/user/{user_id}/data`:
  - Export all user data as JSON (Data Portability)
  - Include: User profile, Memory, MessageLog, Schedules
  - Return downloadable JSON file

**8.6 - Implement Consent & Opt-In Tracking**

In `MessageRouter.route_message()`:
- Check User.opted_in before sending any message
- Log all consent actions (opt-in, opt-out) with timestamp
- Update Unsubscribe table with compliance_required flag for legal holds

**8.7 - Add Audit Logging**

Create `src/middleware/audit.py`:
- Log all data mutations (INSERT, UPDATE, DELETE) to audit table
- Include: user_id, table_name, operation, old_value, new_value, timestamp, actor_id
- Audit table: never delete, only read for compliance reviews

**8.8 - Input Validation & Sanitization**

In `src/api/routes.py`:
- Validate all user inputs: max length, allowed characters
- Sanitize message text: no SQL injection, no prompt injection
- Use Pydantic models for request validation (automatic)
- Example:
  ```python
  from pydantic import BaseModel, constr, validator
  class MessageSchema(BaseModel):
      text: constr(max_length=4096)
      @validator('text')
      def no_sql_injection(cls, v):
          if any(x in v.lower() for x in ['drop', 'delete', 'exec']):
              raise ValueError('Invalid message')
          return v
  ```

**8.9 - Add Security Headers**

In `main.py`:
- Add middleware to set HTTP security headers:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security: max-age=31536000`

**8.10 - Performance Testing & Load Testing**

Create `tests/test_performance.py`:
- Load test with 1000 concurrent users (using `locust` or `ab`)
- Measure: message delivery latency, throughput, error rates
- Target: < 100ms p95 latency, > 1000 msg/sec throughput
- Run: `locust -f tests/locustfile.py --headless -u 1000 -r 50 -t 5m`

**8.11 - Dependency Audit**

Run:
```bash
pip-audit  # check for known vulnerabilities in dependencies
bandit -r src/  # security linter
```

**8.12 - Update README & Security Policy**

Document:
- Privacy policy: what data is collected, how it's used, opt-out process
- Security: encryption, rate limiting, audit logs
- GDPR: data deletion, data export, consent
- `.github/SECURITY.md`: vulnerability reporting process

**8.13 - Create Deployment Checklist**

Document in `docs/DEPLOYMENT.md`:
- Pre-production: database backups, secrets rotation, rate limits tested
- Monitoring: error tracking (Sentry), logs (ELK stack)
- Incident response: alert channels, on-call playbook

**Expected Deliverables:**
- Rate limiting middleware working
- Request/response logging to MessageLog + files
- SQL Server TLS encryption enabled
- Environment secrets management in place
- GDPR delete/export endpoints working
- Audit logging table populated
- Input validation & sanitization on all endpoints
- Security headers added
- Load test results: < 100ms p95, > 1000 msg/sec
- Dependency audit passing (no critical vulns)
- README with privacy policy
- Security documentation
- Production deployment checklist

---

## **Memory System: Conflict-Resolution, Provenance & AI Store Decision**

Add this section into the plan so any AI coder knows how to implement a robust personal-memory store that supports deduplication, conflict resolution, provenance and archival.

Overview:
- Purpose: store meaningful user facts/preferences/goals while avoiding noise; support corrections and audit; enable TTL-based ephemeral memory and archival of conflicting or outdated values.
- DB: extend existing `Memory` table (or use new columns) to store provenance, value hash, conflict group id, is_active, archived_at.

Recommended schema additions (SQL Server style):
```sql
ALTER TABLE Memory
ADD value_hash VARBINARY(32) NULL,
    source NVARCHAR(100) NULL,
    is_active BIT NOT NULL DEFAULT 1,
    conflict_group_id UNIQUEIDENTIFIER NULL,
    archived_at DATETIME2 NULL;

CREATE INDEX IX_Memory_UserKey ON Memory(user_id, [key], is_active);
CREATE INDEX IX_Memory_ValueHash ON Memory(value_hash);
```

Conflict-resolution & archival rules (app-level):
1. Compute `value_hash = HASHBYTES('SHA2_256', value)` on insert.
2. In a single transaction, find existing active memory rows for same `(user_id,key)`.
   - If existing.value_hash == value_hash: merge (update confidence/updated_at).
   - If different (conflict): create or reuse a `conflict_group_id`, mark losing rows `is_active=0, archived_at=NOW()`, set `conflict_group_id` on all related rows, insert the new record as active (or archive new if policy prefers existing), and write audit log.
3. Prefer explicit user corrections (user message with "actually"/"no, my X is Y") over inferred updates; use confidence and timestamp as tie-breakers.

AI decision step (store/skip classifier):
- Implement a small classifier (start rule-based, upgrade to LLM prompt) that returns JSON:
  {
    "store": true|false,
    "key": "user:learning_goal",
    "value": "Complete ACIM 365 lessons",
    "confidence": 0.92,
    "ttl_hours": null,
    "source": "dialogue_engine"
  }
- Heuristics:
  - Always store: explicit identity/contact, long-term goals, explicit commitments, medical/legal flags only if explicit consent.
  - Store with TTL: ephemeral state, short-term reminders, session notes.
  - Skip: casual chit-chat, inferred emotional states without explicit consent, system prompts.

Example few-shot AI prompt template (brief):
"You are a personal coach memory classifier. Input: user_message, conversation_context, user_consent_flags, candidate_key/value (if provided). Decide whether to store. Output strict JSON with keys: store(bool), key(str|null), value(str|null), confidence(float 0-1), ttl_hours(int|null), source(str). Follow these rules: store explicit facts and long-term goals; only store sensitive health/legal info with explicit consent; prefer user corrections. Examples: [three short examples here]."

Retention & purge:
- Keep `archived` rows for audit for configurable period (e.g., 365 days), then either move to `MemoryArchive` table or delete per policy.
- Implement a scheduled purge job that runs daily and deletes/moves old archived rows.

Indexes & performance:
- Index `(user_id, key, is_active)` and `value_hash`.
- For large scale, partition Memory by `created_at` or archive older users' histories.

Privacy & consent:
- Always check `User.opted_in` before storing any memory that contains PII or sensitive material.
- Log consent timestamp and source.

Developer instructions (what to add to repo plan):
- Add this section to the main plan (done).
- Create an Alembic migration to add `value_hash, source, is_active, conflict_group_id, archived_at` (M2 or separate small migration).
- Implement `MemoryManager.store_memory()` transactional flow with conflict resolution and audit logging (Milestone 3/7 work item).
- Add `memory_classifier` module and a `memory_decision` interface that accepts message+context and returns the JSON decision (start rule-based; add LLM prompt file for later).
- Add scheduled purge job script in `src/services/maintenance.py`.

Expected artifacts:
- Alembic migration SQL file for Memory schema changes.
- `src/services/memory_manager.py` extended with `store_memory()` that performs transactional conflict-resolution.
- `src/services/memory_classifier.py` with rule-based decisions and the LLM prompt template file `docs/memory_classifier_prompt.md`.
- Scheduled purge job script in `src/services/maintenance.py`.

---

End of plan.
