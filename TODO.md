# Swarm Supervisor Fix — TODO

- [x] 1. Update `swarm/state.py` — Add `iteration_count`, remove `project_rules`
- [x] 2. Update `swarm/nodes.py` — Rewrite prompts to be strictly technical, remove ACIM/Enneagram confusion
- [x] 3. Update `swarm/graph.py` — Add max-iteration guard (3 cycles)
- [x] 4. Update `swarm/cli.py` — Initialize `iteration_count`, improve output formatting
- [x] 5. Verify imports and graph compilation — ALL PASS
- [ ] 6. Full CLI test (requires LLM backend): `python -m swarm.cli "Test task: Create a simple echo function"`
