# Architecture & Design Reference

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   External Integrations                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐     │
│  │  Telegram    │   │    Slack     │   │     Email    │     │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘     │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                    ┌────────▼─────────┐
                    │   FastAPI App    │
                    │ (src/api/app.py) │
                    └────────┬─────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
    ┌──────────┐      ┌────────────┐   ┌──────────────┐
    │ Dialogue │      │  Telegram  │   │  Other       │
    │ Routes   │      │ Webhook    │   │  Integrations│
    └─────┬────┘      └──────┬─────┘   └──────┬───────┘
          │                  │                │
          └──────────────────┼────────────────┘
                             │
                    ┌────────▼──────────┐
                    │ DialogueEngine    │
                    │ (orchestration)   │
                    └────────┬──────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
  │MemoryMgr    │   │PromptBuilder │   │ Ollama LLM   │
  │(retrieve)   │   │(assemble ctx)│   │(generation)  │
  └──────┬──────┘   └──────┬───────┘   └──────┬───────┘
         │                 │                  │
         └─────────┬───────┘                  │
                   │                          │
        ┌──────────▼────────────┐             │
        │ PromptOptimizer       │◄────────────┘
        │ (token mgmt)          │
        └──────────┬────────────┘
                   │
        ┌──────────▼──────────────┐
        │ Final Optimized Prompt  │
        │ (to Ollama)             │
        └──────────┬──────────────┘
                   │
                   ▼
           [AI Response Generated]
                   │
                   ▼
        ┌──────────────────────┐
        │ MessageLog Storage   │
        │ (conversation thread)│
        └──────────┬───────────┘
                   │
                   ▼
        ┌────────────────────┐
        │ Database           │
        │ (SQLAlchemy)       │
        └────────────────────┘
```

## Data Flow: User Message to AI Response

```
User Input (Message)
        │
        ▼
┌─────────────────────────────┐
│ 1. Message Arrives          │
│    - Parse (Telegram, etc)  │
│    - Get/Create User        │
│    - Validate permission    │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 2. Retrieve User Context    │
│    - Query Memories         │
│    - Filter by category     │
│    - Check expiration       │
│    - Sort by relevance      │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 3. Build Context Blocks     │
│    - Profile context        │
│    - Goals & preferences    │
│    - Recent progress        │
│    - Conversation history   │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 4. Assemble Prompt          │
│    - PromptBuilder          │
│    - Structure sections     │
│    - Format for readability │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 5. Optimize Prompt          │
│    - Estimate tokens        │
│    - Trim if needed         │
│    - Allocate budget        │
│    - Remove duplicates      │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 6. Call Ollama LLM          │
│    - HTTP POST request      │
│    - Full prompt sent       │
│    - Stream/wait response   │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 7. Log Messages             │
│    - User message (inbound) │
│    - AI response (outbound) │
│    - Thread ID & roles      │
│    - Timestamps             │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 8. Update Memory            │
│    - Store insights         │
│    - Update progress        │
│    - Conflict resolution    │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 9. Send Response Back       │
│    - Channel-specific send  │
│    - Status tracking        │
│    - Error handling         │
└────────────┬────────────────┘
             │
             ▼
        User Receives Response
```

## GDPR Implementation Status & Documentation

GDPR compliance is now fully implemented in the system. All major requirements for data subject rights, consent management, data retention, and audit logging are supported. The architecture and codebase have been updated to ensure personal data is handled according to GDPR principles.

**For detailed information, refer to the following documentation in the `docs/` directory:**

- [PRIVACY_NOTICE.md](docs/PRIVACY_NOTICE.md): Explains how personal data is collected, used, and protected.
- [RETENTION_SCHEDULE.md](docs/RETENTION_SCHEDULE.md): Details data retention periods and deletion policies.
- [DSR_ID_VERIFICATION.md](docs/DSR_ID_VERIFICATION.md): Describes the process for handling Data Subject Requests (DSR), including identity verification.
- [ROPA.md](docs/ROPA.md): Records of Processing Activities for GDPR compliance.
- [DPIA.md](docs/DPIA.md): Data Protection Impact Assessment.
- [IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md): Overview of GDPR implementation steps and controls.

**Other relevant documents:**
- [INCIDENT_RESPONSE_PLAN.md](docs/INCIDENT_RESPONSE_PLAN.md)
- [VENDOR_SUBPROCESSORS.md](docs/VENDOR_SUBPROCESSORS.md)

For technical details on data flows, storage, and processing, see the original section below:

## GDPR Data Inventory & Personal Data Flow

This section documents where personal data is stored, logged, and transmitted throughout the system, in accordance with GDPR requirements.

### Personal Data Inventory (by storage)

**Core Database Models:**
- **Users**: Stores user identifiers (internal user_id, external_id from channels), contact info (email, phone_number), profile data (first_name, last_name), consent/status flags, and metadata (channel, created_at, last_active_at).
- **Memory**: Stores user-derived content (key, value) which may contain personal data, along with metadata (category, confidence, source, timestamps, TTL, embedding).
- **MessageLog**: Stores all communication content (user and assistant messages), direction, channel, status, timestamps, thread id, and message role.
- **Schedule**: Stores user delivery preferences (schedule_type, cron_expression, next_send_time, last_sent_at).
- **Unsubscribe**: Stores user opt-out preferences (channel, reason, compliance_required, unsubscribed_at).
- **ConsentLog**: Records consent events (scope, granted flag, consent_version, source, created_at).
- **GdprRequest / GdprAuditLog**: Stores Data Subject Request (DSR) metadata, actor, reasons, details, and audit timestamps.

**Operational Logs:**
- MessageLog rows act as conversation logs and retain content and metadata for a defined retention period.

### Personal Data Flows (High Level)

1. **Inbound Message**
        - Source: Telegram, Slack, Email, Twilio, etc.
        - Data: external user id, message content, metadata
        - Stored in: Users (external_id/channel), MessageLog (content/status)

2. **Processing & Memory Extraction**
        - DialogueEngine and MemoryExtractor derive structured memories from message content
        - Stored in: Memory (key/value/category/metadata)

3. **Scheduling**
        - User preferences and timing for reminders
        - Stored in: Schedule (cron, next_send_time)

4. **Consent & GDPR Requests**
        - Consent events recorded in ConsentLog
        - DSR requests and audit logs recorded in GdprRequest and GdprAuditLog

5. **Outbound Response**
        - Data: assistant response content, delivery metadata
        - Stored in: MessageLog (content/status)

### Integrations That Receive/Send Personal Data
- **Telegram**: Inbound messages and outbound replies include user id and message content
- **Slack**: Same data types for workspace users
- **Email**: Address and message content
- **Twilio**: Phone number and message content

For further details, see the GDPR documentation in the `docs/` directory.


## Memory System State Machine

```
┌──────────────────────────────────────────────────┐
│                 Store New Memory                 │
│              (key, value, category)              │
└────────────────────┬─────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ Query Active Memories  │
        │ (user_id, key, cat)    │
        └───┬────────────────────┘
            │
            ├─── No matches ──────┐
            │                     │
            │              ┌──────▼────────┐
            │              │ Create New    │
            │              │ (is_active=T) │
            │              └──────┬────────┘
            │                     │
            ├─── Match identical value ───┐
            │                             │
            │                      ┌──────▼────────────┐
            │                      │ Update (merge)    │
            │                      │ - Increase conf   │
            │                      │ - Update timestamp│
            │                      └──────┬────────────┘
            │                             │
            │                      ┌──────▼───────────┐
            │                      │ Commit           │
            │                      │ Return memory_id │
            │                      └──────────────────┘
            │
            └─── Match different value ───────┐
                                              │
                                       ┌──────▼──────────────┐
                                       │ Create Conflict     │
                                       │ - Assign conflict_id│
                                       │ - Archive old       │
                                       │ - Create new active │
                                       └──────┬──────────────┘
                                              │
                                       ┌──────▼─────────────┐
                                       │ Commit             │
                                       │ Return memory_id   │
                                       └────────────────────┘
```

## Memory Categories Relationship

```
┌─────────────────────────────────────────────┐
│              User Profile                   │
│    (demographics, preferences, setup)       │
├─────────────────────────────────────────────┤
│  Keys: full_name, timezone, language        │
│        accessibility_needs, email           │
└──────────────────┬──────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
    ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Goals    │  │Preferences│ │ Progress │
│(learning)│  │(communication)│(achievement)
├──────────┤  ├──────────┤  ├──────────┤
│learning_ │  │preferred_│  │lesson_   │
│goal      │  │tone      │  │completed │
│learning_ │  │contact_  │  │practice_ │
│style     │  │frequency │  │streak    │
│milestone │  │difficulty│  │mastery_  │
└──────────┘  └──────────┘  │level     │
       │           │        └──────────┘
       │           │              │
       └───────────┼──────────────┘
                   │
                   ▼
         ┌──────────────────┐
         │  Insights        │
         │  (AI-derived)    │
         ├──────────────────┤
         │learning_pattern  │
         │engagement_level  │
         │knowledge_gap     │
         │strength_area     │
         └──────────────────┘
                   │
                   ▼
         ┌──────────────────┐
         │  Conversation    │
         │  (active state)  │
         ├──────────────────┤
         │last_topic        │
         │open_questions    │
         │conversation_state│
         └──────────────────┘
```

## Prompt Assembly Process

```
System Prompt (Role Definition)
        │
        ▼
┌────────────────────────────────────┐
│ 1. Profile Context (150 tokens)    │
│    ├─ Name                         │
│    ├─ Email                        │
│    ├─ Channel                      │
│    └─ Days as user                 │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ 2. Goals Context (200 tokens)      │
│    ├─ Learning goals               │
│    ├─ Milestones                   │
│    └─ Completion rate              │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ 3. Preferences Context (100 tokens)│
│    ├─ Learning style               │
│    ├─ Tone preference              │
│    ├─ Difficulty level             │
│    └─ Contact frequency            │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ 4. Progress Context (150 tokens)   │
│    ├─ Completed lessons            │
│    ├─ Recent insights              │
│    └─ Current strengths/gaps       │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ 5. History Context (400 tokens)    │
│    ├─ Last N conversation turns    │
│    ├─ Thread grouping              │
│    ├─ Message roles (user/asst)    │
│    └─ Chronological order          │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ 6. Current Input                   │
│    ├─ User: [current message]      │
│    └─ Assistant: [ready for response]
└────────────┬───────────────────────┘
             │
             ▼
     [Final Optimized Prompt]
```

## Token Budget Allocation Strategy

```
┌─────────────────────────────────────┐
│ Total Token Budget (e.g., 2000)     │
└────────────┬────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
┌──────────┐    ┌──────────────────┐
│Fixed     │    │Flexible          │
│(reserved)│    │(context sections)│
├──────────┤    ├──────────────────┤
│System:   │    │Profile:    150   │
│ 200      │    │Goals:      200   │
│User input│    │Preferences:100   │
│ 100      │    │Progress:   150   │
│Buffer:   │    │History:    400   │
│ 100      │    │(Total: 1000)     │
└──────────┘    └──────────────────┘
│Fixed=400│     │If over budget:   │
│         │     │1. Trim history   │
│Remaining│     │2. Trim progress  │
│= 1600   │     │3. Trim goals     │
│         │     │4. Trim profile   │
└─────────┘     └──────────────────┘
```

## Database Schema Relationships

```
┌──────────────┐
│    Users     │
├──────────────┤
│ user_id (PK) │◄──┐
│ external_id  │   │
│ channel      │   │
│ first_name   │   │
│ last_name    │   │
│ email        │   │
│ created_at   │   │
└──────┬───────┘   │
       │           │ 1:N
       │           │
       └─────► ┌──────────────────┐
               │    Memories      │
               ├──────────────────┤
               │ memory_id (PK)   │
               │ user_id (FK) ────┘
               │ category         │
               │ key              │
               │ value            │
               │ value_hash       │
               │ confidence       │
               │ is_active        │
               │ created_at       │
               │ updated_at       │
               │ ttl_expires_at   │
               │ archived_at      │
               └──────────────────┘

       │
       │ 1:N
       │
       └─────► ┌──────────────────┐
               │  MessageLogs     │
               ├──────────────────┤
               │ message_id (PK)  │
               │ user_id (FK) ────┘
               │ direction        │
               │ channel          │
               │ content          │
               │ message_role     │
               │ conversation_id  │
               │ status           │
               │ created_at       │
               │ processed_at     │
               └──────────────────┘
```

## Key-Value Query Performance

```
Query Type          │ Complexity │ Performance
────────────────────┼────────────┼────────────
Get memory by key   │ O(log n)   │ ~5ms
Get all by category │ O(n)       │ ~10ms
Insert new memory   │ O(1)       │ ~10ms
Check conflict      │ O(k)       │ ~5ms
                    │ k=conflicts│
Filter by TTL       │ O(n)       │ ~15ms
```

Indexes to add for performance:
```sql
CREATE INDEX idx_memory_user_key ON memories(user_id, key);
CREATE INDEX idx_memory_user_category ON memories(user_id, category);
CREATE INDEX idx_memory_active ON memories(user_id, is_active);
CREATE INDEX idx_messagelog_user_role ON message_logs(user_id, message_role);
CREATE INDEX idx_messagelog_thread ON message_logs(conversation_thread_id);
```

## Multi-User Safety Patterns

```
Request Processing
    │
    ▼
┌─────────────────────────┐
│ Extract user_id from    │
│ - JWT token             │
│ - Session               │
│ - Request parameter     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Validate User Exists    │
│ SELECT * FROM users     │
│ WHERE user_id = ?       │
└────────┬────────────────┘
         │
         ├─ NOT found ───► 404 Error
         │
         ├─ Not active ──► 403 Forbidden
         │
         └─ Found ─────────┐
                           │
                           ▼
                 ┌──────────────────┐
                 │ All DB queries   │
                 │ filtered by      │
                 │ user_id          │
                 └────┬─────────────┘
                      │
                      ▼
                 ┌──────────────────┐
                 │ Session Commit   │
                 │ on success only  │
                 └────┬─────────────┘
                      │
                      ▼
                  Return Response
```

## Error Handling Flow

```
Request
   │
   ▼
Try Block
   │
   ├─ Validation Error ──────────────┐
   │                                 │
   ├─ Database Error ────────────────┤
   │                                 │
   ├─ Ollama Timeout ────────────────├──► Log Error
   │                                 │
   ├─ User Not Found ────────────────┤
   │                                 │
   └─ Other Exceptions ──────────────┘
         │                │
         │                └──► Rollback
         │                     Transaction
         │                     Return 500
         │
         ▼
    Rollback
    Session
         │
         ▼
Return Error Response
with appropriate HTTP status
```

## Performance Optimization Hierarchy

```
Level 1: Query Optimization
├─ Index frequently queried columns
├─ Batch operations together
├─ Limit result sets
└─ Use connection pooling

Level 2: Context Optimization
├─ Prioritize memories by relevance
├─ Compress conversation history
├─ Allocate token budget
└─ Deduplicate memories

Level 3: Cache Layer (Future)
├─ Cache user profile
├─ Cache recent conversation
├─ Cache frequent memories
└─ TTL-based invalidation

Level 4: Async Processing (Future)
├─ Queue long operations
├─ Background memory updates
├─ Async Ollama calls
└─ Non-blocking message logging
```

