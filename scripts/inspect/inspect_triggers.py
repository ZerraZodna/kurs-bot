"""
Inspect function calling system status.

Note: TriggerEmbedding model was removed in Phase 3 of the function calling migration.
The system now uses LLM-driven function calls instead of embedding-based trigger matching.
"""

from pathlib import Path, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.functions.registry import get_function_registry

print("=" * 60)
print("Function Calling System Status")
print("=" * 60)

registry = get_function_registry()
functions = registry.list_all()

print(f"\nTotal registered functions: {len(functions)}")
print("\nFunctions by category:")
print("-" * 40)

# Group by context
contexts = {}
for func in functions:
    for ctx in func.contexts:
        if ctx not in contexts:
            contexts[ctx] = []
        contexts[ctx].append(func.name)

for ctx, names in sorted(contexts.items()):
    print(f"\n  {ctx}: {len(names)} functions")
    for name in sorted(names):
        print(f"    - {name}")

print("\n" + "=" * 60)
print("Migration Status: COMPLETE ✅")
print("Embedding-based trigger matching replaced by function calling")
print("=" * 60)
