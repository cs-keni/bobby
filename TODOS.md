# Bobby — TODOS

Deferred work captured during plan-eng-review. Pick these up when the time is right.

---

## [ ] Plugin/Skills Interface

**What:** Design a plugin interface so skills can be added without modifying Bobby's core code. Each skill is a Python file with a `register_tools() -> list[Tool]` function.

**Why:** If Bobby gets open-sourced, contributors will want to add Spotify, home automation, custom scripts, etc. Without a plugin interface, every PR touches core files and risks breaking things. With it, a new skill is a single file drop.

**When to pick up:** Phase 0 — before the tool dispatcher is built.

**How to start:**
```python
# tools/base.py
class Tool:
    name: str
    description: str
    handler: Callable
    parameters: dict  # JSON Schema

# Each skill file:
def register_tools() -> list[Tool]:
    return [Tool(name="open_spotify", ...)]

# core/brain.py discovers plugins:
tools = load_tools_from_directory("tools/skills/")
```

**Depends on:** Phase 0 project structure.

---
