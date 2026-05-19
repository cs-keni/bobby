# Bobby — AI Development Context

This file is read by Claude Code at the start of every session.

---

## Project Summary

Bobby is a Jarvis-style personal AI assistant running on Windows (via WSL). It handles voice commands, OS control, memory, and remote phone access.

**Stack:** Python backend, React PWA (phone), FastAPI server, Claude API (runtime brain), ElevenLabs TTS, Whisper STT, SQLite + ChromaDB memory, Cloudflare Tunnel.

---

## AI Development Team

Three models collaborate on this project:

| Model | Role | Strengths |
|---|---|---|
| Claude Sonnet 4.6 | Default workhorse (Claude Code) | Fast iteration, implementation, debugging, refactoring |
| Claude Opus 4.7 | Deep reasoning escalation | Architecture, concurrency bugs, security review, hard tradeoffs |
| GPT-5.5 (Codex) | Parallel agent | Large implementation tasks, code generation at scale, independent feature branches |

---

## Model Routing Guide

### Use Sonnet 4.6 (default — current model) for:
- Feature implementation when the spec is clear
- Refactoring and cleanup
- Writing/fixing tests
- Explaining code
- Routine debugging
- PHASES.md updates
- Handoff doc updates

### Escalate to Opus 4.7 when:
- Designing a new phase or major subsystem from scratch
- Debugging concurrency or race conditions in the pipeline (threading, locks, events)
- Security review of any server/auth/tunnel surface
- A task has multiple non-obvious architectural tradeoffs
- Something subtle keeps breaking and Sonnet hasn't found the root cause
- Reviewing Codex's output for correctness before merging

**How to escalate:** User runs `/model claude-opus-4-7` in Claude Code, or starts a fresh session. Claude should provide a ready-to-paste prompt summarizing the task and relevant context.

### Hand off to GPT-5.5 (Codex) when:
- Task is large, parallelizable, and well-spec'd (Codex can work independently)
- Implementing a full phase that doesn't require architectural judgment
- User wants a second opinion or independent implementation to compare
- Task is purely generative with a clear spec (e.g., "build the React phone app UI")

**How to hand off:** Claude should provide a self-contained Codex prompt with: goal, constraints, relevant file paths, interfaces to preserve, and expected output shape.

---

## Claude Code Behavior

- **Proactively flag model mismatches.** If a task would be better handled by Opus 4.7 or GPT-5.5, say so before starting and provide a ready-to-paste prompt.
- **Don't silently downgrade.** If you're Sonnet tackling something Opus would handle better, be transparent about the tradeoff — let the user decide.
- **Handoff docs are mandatory.** After every meaningful implementation slice, update `docs/HANDOFF.md`, `docs/CURRENT_TASK.md`, and `docs/ENGINEERING_LOG.md` so Codex can pick up cleanly.

---

## Key Files to Read Each Session

- `PHASES.md` — current build plan and task status
- `docs/HANDOFF.md` — what the last agent left off (if exists)
- `docs/CURRENT_TASK.md` — active task in flight (if exists)
- `docs/ENGINEERING_LOG.md` — commit history and decisions (if exists)
