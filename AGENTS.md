# Bobby — Codex Agent Instructions

## Session Start

Before writing any code, read:
1. `docs/AI_CONTEXT.md` — stack, model routing, team structure
2. `PHASES.md` — current build plan and task status
3. `docs/HANDOFF.md` — what the last agent left off
4. `docs/CURRENT_TASK.md` — active task in flight
5. `docs/ENGINEERING_LOG.md` — recent decisions and commit log

## Project Conventions

- All tools return `ToolResult(success, message, data)` — never change this interface
- External content passed to Bobby's brain is wrapped in `<data>` XML tags (prompt injection defense)
- Threading: pipeline uses `_processing_lock` to serialize commands — be careful with async/threading
- Config lives in `config.yaml` + `.env` — never hardcode keys or paths
- Never `git add .` or `git add -A` — stage specific files only

## Learning Explanations (Non-Negotiable)

After every planning session or implementation slice, include a **Design Rationale** section:
- What decision was made and what alternatives were rejected
- Why this approach was chosen (the tradeoff)
- How the pieces fit together conceptually

Kenny is actively learning agentic system design, RAG/retrieval, and evaluation. If you skip this, the work has no learning value.

## Documentation Hygiene

After every code change, update before committing:
- `docs/ENGINEERING_LOG.md` — what changed and why (include commit hash after commit)
- `docs/HANDOFF.md` — if architecture or component ownership changed
- `docs/CURRENT_TASK.md` — reflect active work
- `PHASES.md` — mark completed tasks in real time

## Model Routing

- Escalate complex architecture or concurrency bugs to Claude Opus 4.7
- Hand off large, well-spec'd parallel features back to Codex
- Simple well-spec'd implementation → Codex handles it

## Commit Flow

1. Update docs
2. Stage specific files (never `git add .`)
3. Commit with clear imperative message (≤72 chars subject)
4. `git push`
5. Log hash in `docs/ENGINEERING_LOG.md`
