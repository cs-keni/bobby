# Bobby — Handoff

## Last Updated: 2026-05-19 (Claude Sonnet 4.6 — post /review)

---

## Current State

**Everything is committed and pushed (`3a19cd4` is HEAD on main).**

The pre-existing uncommitted changes (pipeline.py, stt.py, tts.py) have been reviewed and committed as part of the phone server bridge feature. The codebase is clean.

**Next action:** Phase 11A implementation — but ONLY after the WSL networking gate passes (see below).

---

## What Shipped This Session

### cb96fa1 — Phone server bridge + review bug fixes
- Split pipeline into `_run_command` (no audio), `_process_command` (voice), `process_text_command` (API path)
- Added FastAPI server: `server/auth.py`, `server/main.py`, `server/routes/`
- Added `transcribe_from_bytes()` to `stt.py` for WebM/Opus from browser
- Added `synthesize()` to `tts.py` for MP3 bytes without playing

**Bugs fixed in /review:**
- `brain.py`: `think()` was appending `user: ""` after `user: [tool_results]` — consecutive user messages violating Anthropic API. Fixed: skip append when both `user_message` and `memory_context` are empty.
- `pipeline.py`: `server_enabled` defaulted `True` — Bobby crashed silently if uvicorn missing. Fixed to `False` default; user config.yaml has explicit `server_enabled: true`.
- `server/main.py`: `allow_credentials=True` + `allow_origins=["*"]` is CORS spec violation. Removed.
- `stt.py`: `result["text"]` KeyError risk → `.get("text", "")`.

### Earlier this session: Phase 11 design + planning
- `79f113d` — Model routing docs added
- `4882977` — Phase 11 added to PHASES.md
- `9578f2e` — Initial HANDOFF.md and ENGINEERING_LOG.md
- `4f186dc` — GSTACK review report updated

---

## Phase 11 — Second Brain (Obsidian Integration)

### Prerequisite Gate (must pass before ANY code is written)

1. Open Obsidian on Windows
2. Install "Local REST API" community plugin (Settings → Community Plugins → Browse → search "Local REST API")
3. Enable it and copy the API key from its settings panel
4. With Obsidian open, run this WSL test:
   ```bash
   curl http://10.255.255.254:27123/
   # Must return: {"status":"OK"}
   ```
5. Only after this returns OK: add to config.yaml and begin T1

### Design Artifacts (full specs — read these before implementing)

- **Design doc (APPROVED):** `~/.gstack/projects/cs-keni-bobby/keni-main-design-20260519-102214.md`
- **Test plan:** `~/.gstack/projects/cs-keni-bobby/keni-main-eng-review-test-plan-20260519-112232.md`
- **Task list (JSONL):** `~/.gstack/projects/cs-keni-bobby/tasks-eng-review-20260519-112342.jsonl`

### Architecture Decisions — ALL LOCKED (do not re-litigate)

| Decision | What to do |
|----------|-----------|
| @register_tool format | Flat dict: `{"field": {"type":..., "required": True}}` — NOT JSON Schema object |
| vault_context injection | Add `vault_context: str = ""` to `think()`. When non-empty, `system` becomes list of blocks (not string). Pass to BOTH think() calls in `_run_command` (lines ~98 and ~146). |
| Notification queue | Create `core/notifications.py` with `_tts_queue: Queue[str]`. Both pipeline.py and tools/obsidian.py import from it. Never import `_tts_queue` from pipeline (circular). |
| Nested config keys | Add dotted-path accessor to `config.py`. `config.get("obsidian.api_key")` must resolve nested YAML. Add `OBSIDIAN_API_KEY` to env_overrides. |
| WSL host IP | Always `10.255.255.254` (from /etc/resolv.conf). `localhost` does NOT work in WSL2. |
| HTTP timeout | All httpx calls use `timeout=5.0` (not the ElevenLabs 30s) |
| Trust model | Vault INDEX (Bobby-generated) = system block (trusted). Note content from `read_obsidian_note` = wrapped with `wrap_external()` (untrusted). |
| enabled flag | Each Obsidian tool checks `config.get("obsidian.enabled", False)` first |
| Index guard | `capture_to_obsidian` skips Recent Captures append if VAULT_INDEX.md doesn't exist yet |
| Path traversal | `read_obsidian_note` rejects `../`, absolute paths, encoded traversal before any HTTP call |

### Implementation Tasks (in order)

**Phase A — P1 (required to ship Phase A):**

| Task | File | What to implement |
|------|------|-------------------|
| T1 | `core/config.py` | Add dotted-path accessor: `config.get("obsidian.api_key")` resolves nested keys. Add `OBSIDIAN_API_KEY` to env_overrides. |
| T2 | `core/notifications.py` | New file. `_tts_queue: queue.Queue[str] = queue.Queue()`. That's it. |
| T3 | `tools/obsidian.py` | New file. `capture_to_obsidian`, `read_obsidian_note`, `search_obsidian`. See design doc for signatures and error handling. |
| T4 | `core/brain.py` | Add `vault_context: str = ""` to `think()`. When non-empty, build system as list of blocks. |
| T5 | `core/pipeline.py` | Load vault_context from disk. Pass to BOTH think() calls in `_run_command`. Drain `_tts_queue` in `run()` idle loop. |

**Phase A — P2 (needed for full phase, not hard-blocked):**

| Task | File | What to implement |
|------|------|-------------------|
| T6 | `config.yaml` | Add `obsidian:` nested block (enabled, api_host, api_port, api_key, vault_path, inbox_folder, index_file, max_index_tokens) |
| T7 | `tests/test_phase11.py` | 13 test paths. Mock httpx. Pattern: same as `tests/test_phase3.py`. |
| T8 | `tests/test_pipeline.py` | Update existing think() tests for `system=list` format change. |

---

## Known Risks for Implementer

1. **vault_context to BOTH think() calls** — easy to add to line 98 and miss line 146. Don't.
2. **Circular import** — `tools/obsidian.py` must not import from `core.pipeline`. Use `core.notifications` instead.
3. **`_processing_lock` is non-reentrant** — never acquire it inside a function called while it's held. The `_run_command` function is always called under this lock.
4. **`think()` system param type change** — when `vault_context` is added, `system` becomes `list[dict]` instead of `str`. Any test that asserts `system=SYSTEM_PROMPT` (a string) will need updating (T8).
5. **Background thread in `build_vault_index`** — must hold no pipeline locks, must use `core.notifications._tts_queue` to signal completion.

---

## File Map

```
core/
  brain.py          — Claude integration. think() lives here. T4 modifies this.
  config.py         — Config loader. T1 modifies this.
  notifications.py  — NEW (T2). Notification queue for background threads.
  pipeline.py       — Main loop. T5 modifies this.
  stt.py            — Whisper STT + transcribe_from_bytes()
  tts.py            — ElevenLabs TTS + synthesize()
  tool_result.py    — ToolResult dataclass. Don't touch.
tools/
  registry.py       — @register_tool decorator. Don't touch.
  obsidian.py       — NEW (T3). All Obsidian tools.
  memory.py         — Phase 3 memory tools. Reference for @register_tool pattern.
  os_control.py     — Phase 2 OS tools. Reference for @register_tool pattern.
server/
  auth.py           — Bearer token auth dependency
  main.py           — FastAPI app
  routes/command.py — /api/command and /api/voice endpoints
tests/
  test_phase3.py    — Reference for mock patterns (monkeypatch, tmp_path)
  test_pipeline.py  — Existing pipeline tests. T8 may need to update think() assertions.
```
