New project structure
kurs-bot/                          # Root of your project (evolve from existing repo)
├── pyproject.toml                 # Main dependencies + workspace config
├── README.md
├── alembic/                       # Keep your existing migrations
├── .env
│
├── packages/                      # Reusable independent packages
│   ├── core-llm/                  # New: llama-cpp-server wrapper + structured output
│   │   ├── pyproject.toml
│   │   ├── src/core_llm/
│   │   │   ├── __init__.py
│   │   │   ├── client.py          # OpenAI-compatible client for llama-cpp-server
│   │   │   ├── config.py
│   │   │   └── structured.py      # Pydantic + JSON schema / tool calling helpers
│   │   └── tests/
│   │
│   ├── spiritual-knowledge/       # Extract & improve from your lessons/
│   │   ├── pyproject.toml
│   │   ├── src/spiritual_knowledge/
│   │   │   ├── __init__.py
│   │   │   ├── acim_loader.py     # Load Text, Workbook, Manual into vector store
│   │   │   ├── enneagram_db.py    # Structured Enneagram types, wings, growth paths
│   │   │   ├── retriever.py       # RAG tools (ACIM grounding + Enneagram)
│   │   │   └── embeddings.py
│   │   └── data/                  # ACIM text files (or load from DB)
│   │
│   ├── user-memory/               # Replacement for your memories/ module
│   │   ├── pyproject.toml
│   │   ├── src/user_memory/
│   │   │   ├── __init__.py
│   │   │   ├── mem0_client.py     # Mem0 initialization + config (Chroma backend)
│   │   │   ├── profile.py         # Bridge to SQL user data (Enneagram type etc.)
│   │   │   ├── tools.py           # search_memory, add_memory, update_memory tools for LangGraph
│   │   │   └── summarizer.py      # Optional: post-conversation memory update logic
│   │   └── tests/
│   │
│   └── agent-orchestration/       # New: LangGraph graphs & nodes
│       ├── pyproject.toml
│       ├── src/agent_orchestration/
│       │   ├── __init__.py
│       │   ├── state.py           # Typed State (user_id, messages, memories, etc.)
│       │   ├── graph.py           # Main LangGraph definition
│       │   ├── nodes.py           # Nodes: retrieve_profile, retrieve_acim, reason, update_memory, etc.
│       │   └── tools.py           # Combined tools (knowledge + memory)
│       └── tests/
│
├── src/                           # Application-specific code (not reusable packages)
│   ├── telegram/                  # Keep & improve your existing Telegram integration
│   │   ├── bot.py
│   │   ├── handlers.py
│   │   ├── keyboards.py           # Enneagram quiz, daily prompts, etc.
│   │   └── webhook.py
│   │
│   ├── api/                       # FastAPI app (your existing one)
│   │   ├── main.py
│   │   ├── deps.py                # Dependency injection (user, memory, llm)
│   │   └── routes/
│   │       └── chat.py            # Endpoint that runs the LangGraph agent
│   │
│   ├── models/                    # SQLAlchemy models (keep & extend)
│   │   ├── user.py                # user_id, enneagram_type, wing, preferences, etc.
│   │   ├── lesson_progress.py
│   │   └── memory_log.py          # Optional audit of Mem0 updates
│   │
│   └── utils/                     # Shared: prompts, safety, logging
│
├── scripts/                       # Daily lesson cron, onboarding, etc.
└── tests/
