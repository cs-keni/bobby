# Bobby — Engineering Log

---

## 2026-05-19

### Session: Model routing + Phase 11 design (Claude Sonnet 4.6)

**Commits:**
- `79f113d` — Add model routing guidance and CLAUDE.md session checklist
- `4882977` — feat: add Phase 11 — Second Brain (Obsidian Integration) to PHASES.md

**Decisions:**
- Model routing: Sonnet 4.6 default, Opus 4.7 for architecture/security/hard tradeoffs, GPT-5.5 (Codex) for large well-spec'd parallel work. Documented in `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `docs/AI_CONTEXT.md`, `CLAUDE.md`.
- Obsidian integration approach: direct REST API via httpx + @register_tool pattern (same as ElevenLabs). NOT MCP protocol layer.
- Vault index strategy: Karpathy index pattern (compact human-readable VAULT_INDEX.md, ≤3000 tokens) over ChromaDB — right tool for personal vault size.
- WSL networking: localhost does NOT reliably reach Windows host in WSL2. Must use Windows host IP from `/etc/resolv.conf`.
- @register_tool decorator: requires explicit `(name, description, parameters)` args — bare `@register_tool` fails at import.
- Vault index injection: `vault_context` param in `think()` → system role message (trusted), not `<data>` XML tags (untrusted).
- build_vault_index() must run in background thread — holds no pipeline locks, ~30s for 500 notes.

**Design artifacts:**
- Office hours doc (APPROVED): `~/.gstack/projects/cs-keni-bobby/keni-main-design-20260519-102214.md`
- CEO plan (APPROVED): `~/.gstack/projects/cs-keni-bobby/ceo-plans/20260519-second-brain.md`

**Status at handoff:**
- Phase 11 fully designed and scoped. Prerequisites not yet done (Obsidian plugin install, WSL networking test). `/plan-eng-review` required before Phase A code.
- `core/pipeline.py`, `core/stt.py`, `core/tts.py` have uncommitted pre-existing changes — not touched this session.

---

## 2026-05-08

### Earlier sessions (reconstructed from git log)

- `98d1d9a` — feat: implement Phase 3 memory layer and Phase 7 media/clipboard/screenshot
- `dbf2bb1` — feat: implement volume control with pycaw + PowerShell WASAPI fallback
- `2018636` — feat: implement Phase 2 — OS control, fuzzy app matching, named shortcuts
- `d9446ac` — feat: harden pipeline, fix history bug, expand OS control for Phase 2 prep
- `297f82a` — fix: route open_app through cmd.exe on WSL so App Paths registry is searched
