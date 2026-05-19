# Bobby — Handoff

## Last Updated: 2026-05-19 (Claude Sonnet 4.6)

---

## What Happened This Session

1. **Model routing documented** — Added routing table (Sonnet/Opus/Codex) to `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `docs/AI_CONTEXT.md`, and `CLAUDE.md`. Committed at `79f113d`.

2. **Obsidian second brain designed and CEO-reviewed**
   - `/office-hours` produced approved design doc: `~/.gstack/projects/cs-keni-bobby/keni-main-design-20260519-102214.md`
   - `/plan-ceo-review` ran to completion: CEO plan at `~/.gstack/projects/cs-keni-bobby/ceo-plans/20260519-second-brain.md`
   - PHASES.md updated: Obsidian removed from backlog, **Phase 11** added with full A/B/C checkboxes. Committed at `4882977`.

## Architecture Decisions Locked (CEO Review)

| Decision | Outcome |
|----------|---------|
| D3 — @register_tool syntax | Explicit `(name, description, parameters)` args required. Bare `@register_tool` fails at import. Design doc fixed. |
| D4 — Vault index injection | Add `vault_context: str = ""` to `think()` in `brain.py`. Inject as **system role** message (trusted), NOT via `<data>` XML tags. |
| D5 — build_vault_index() blocking | Background thread. Tool returns immediately with spoken "building now". TTS "done" on completion. |

## Scope Accepted (beyond original Phase A/B/C)

- Auto-session-capture: Bobby saves conversation summary to Obsidian daily note at session end
- Morning brief: "Good morning Bobby" → synthesizes inbox + recent captures
- CP1: Mid-conversation proactive capture suggestions
- CP2: Bobby creates today's daily note on startup

## What's Next

1. **Install Obsidian Local REST API plugin** (search "Local REST API" in Obsidian community plugins)
2. **Run WSL networking test** (MANDATORY before code):
   ```bash
   curl http://$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):27123/
   # Must return {"status":"OK"}
   ```
3. **Run `/plan-eng-review`** — lock implementation details for Phase A before writing code
4. **Run `/review`** — review existing codebase before adding Phase 11 code
5. Then implement Phase A: `tools/obsidian.py` + `config.yaml` additions

## Known Risks

- WSL2 `localhost` does NOT reliably reach Windows host — `api_host` in config must be the Windows host IP, never `localhost`
- `build_vault_index()` takes ~30s for large vaults — must NOT run on main pipeline thread
- `_processing_lock` in `pipeline.py` serializes all commands — any long-running tool must background-thread
- `core/pipeline.py`, `core/stt.py`, `core/tts.py` have uncommitted working-tree changes (pre-existing) — review before committing

## Pre-existing Uncommitted Changes

```
M  core/pipeline.py
M  core/stt.py
M  core/tts.py
```
These were in the working tree before this session. Review what they contain before staging.
