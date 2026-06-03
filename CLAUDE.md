# Bobby — Claude Code Instructions

## Session Start Checklist

At the start of every session, read these files before writing any code:
1. `docs/AI_CONTEXT.md` — model routing, team structure, project summary
2. `PHASES.md` — current build plan and task status
3. `docs/HANDOFF.md` — last agent's notes (if exists)
4. `docs/CURRENT_TASK.md` — active task (if exists)
5. `docs/ENGINEERING_LOG.md` — recent decisions and commit log (if exists)

## Model Routing (summary — full guide in `docs/AI_CONTEXT.md`)

Before starting any task, assess whether it's the right fit for Sonnet 4.6:

- **Escalate to Opus 4.7** for: architecture design, concurrency bugs, security review, hard tradeoffs, anything Sonnet keeps failing at
- **Hand off to GPT-5.5 (Codex)** for: large well-spec'd implementations, parallel feature work, independent second opinions

If a task belongs elsewhere, **say so before starting** and provide a ready-to-paste prompt for the target model. Don't silently attempt tasks where a better tool exists.

## Project Conventions

- All tools return `ToolResult(success, message, data)` — preserve this interface
- External content passed to Bobby's brain is wrapped in `<data>` XML tags (prompt injection defense)
- Threading: pipeline uses `_processing_lock` to serialize commands — be careful with any new async/threading code
- Config lives in `config.yaml` + `.env` — never hardcode keys or paths

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore

## Learning Explanations (Non-Negotiable)

After every planning session or implementation slice, include a **Design Rationale** section:
- What decision was made and what alternatives were rejected
- Why this approach was chosen (the tradeoff)
- How the pieces fit together conceptually

This is not optional. Kenny is actively learning agentic system design, RAG/retrieval, and evaluation — not just shipping features. If you skip this, the work has no learning value.

## GBrain Configuration (configured by /setup-gbrain)
- Mode: local-stdio
- Engine: pglite at ~/.gbrain/brain.pglite
- gbrain version: 0.42.10.0
- Embedding: voyage:voyage-3-large (1024d) — key in config.yaml `gbrain.voyage_api_key`
- MCP registered: yes (user scope, /home/keni/.bun/bin/gbrain serve)
- Repo policy: read-write (cs-keni/bobby)
- Brain trust: personal
- Setup date: 2026-06-03

## GBrain Search Guidance
<!-- gstack-gbrain-search-guidance:start -->
GBrain is set up on this machine. Prefer `gbrain search`/`gbrain query` over Grep for
semantic questions about code or vault content. Use `gbrain code-def`/`code-refs` for
symbol-aware lookup. Run `/sync-gbrain` to ingest the Obsidian vault.

Prefer gbrain when:
- "Where is X handled?" — `gbrain search "<terms>"` or `gbrain query "<question>"`
- "What do I know about Y?" — `gbrain query "<question>"` (searches vault after sync)
- Past decisions, plans — `gbrain search "<terms>"`

Grep is still right for exact strings and regex. VOYAGE_API_KEY must be set in env for
semantic search (add to shell: `export VOYAGE_API_KEY=$(cat config.yaml | grep voyage | ...)`)
or sourced from config.yaml at Bobby startup.
<!-- gstack-gbrain-search-guidance:end -->

## Commit and Push After Every Slice

Stage specific files → commit with clear message → `git push` → log the hash in `docs/ENGINEERING_LOG.md`.
