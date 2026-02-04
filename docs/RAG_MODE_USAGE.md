# RAG Mode Usage Guide

RAG (Retrieval-Augmented Generation) mode bypasses the ACIM default behavior and uses semantic search to find only the most relevant memories for your query.

## Commands

### One-time RAG Query
Use the `rag:` or `rag ` prefix for a single message:

```
rag: Tell me about myself
rag what do you know about my background
```

**Effect:**
- Message is processed in RAG mode only
- ACIM lesson is skipped
- Only semantically relevant memories are included
- Returns to normal mode for the next message

### Toggle RAG Mode (Persistent)
Enable or disable RAG mode for all future messages:

```
rag_mode on       # Enable RAG for all messages
rag_mode off      # Disable RAG, back to normal
```

**Effect:**
- Once enabled, all messages use RAG until you turn it off
- Similar to the `next_day` debug command

## Workflow Comparison

### Normal Mode
```
User Message → [System Prompt + ACIM Lesson + Profile + Goals + Preferences + Conversation History] → LLM
```

### RAG Mode
```
User Message → [System Prompt + Semantic Search Results + Minimal Profile + Recent History] → LLM
```

## When to Use RAG Mode

Use RAG mode when:
- You want to ask personal questions without ACIM context
- You want focused responses based only on relevant memories
- ACIM lessons are getting in the way of your personal discussion
- You want a "semantic search first" approach

## Examples

**Scenario 1: Ask about yourself (skip ACIM)**
```
User: rag: What have I told you about my work life?

Bot: Uses only memories related to "work" via semantic search.
Does NOT include today's ACIM lesson.
```

**Scenario 2: Persistent RAG mode for personal planning**
```
User: rag_mode on
Bot: "RAG mode enabled. I will use semantic search for all future messages."

User: What are my goals for this quarter?
User: How is my progress?
User: Tell me about my learning style

(All three use RAG mode with only relevant memories)

User: rag_mode off
Bot: "RAG mode disabled. Back to standard workflow."
```

## Implementation Details

- RAG mode prefix detection happens before any other processing
- The actual message is extracted after removing the `rag:` or `rag ` prefix
- `rag_mode_enabled` memory persists in the database until toggled off
- Both modes still extract and store memories from your message
