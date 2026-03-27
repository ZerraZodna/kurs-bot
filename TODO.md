# Swarm Architect Persistence Upgrade
Status: Approved & In Progress

**Step 1: Create TODO.md** ✅

**Step 2: Upgrade swarm/cli.py**
- Fixed thread_id="architect-persistent"
- SqliteSaver("swarm-checkpoints.sqlite") for durable storage

**Step 3: Test persistence**
```
python -m swarm.cli "test task 1"
python -m swarm.cli "test task 2"  # Architect recalls task 1 messages
```

**Step 4: Verify ruff/pre-commit clean**

**Step 5: Commit & push**
