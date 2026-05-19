# Bobby — Engineering Log

---

## 2026-05-19 (continued — WSL2 audio fix + Phase 11A)

### Session: Phase 11A implementation + WSL2 audio fix (Claude Sonnet 4.6)

**Commits:**
- `fd1b2b1` (approx) — feat: implement Phase 11A Obsidian integration (T1–T8, 102 tests)
- `cdcbf1b` — fix: replace sounddevice/PortAudio with parecord+ffplay for WSL2 audio

**Root cause: PortAudio in WSL2**
Conda's `libportaudio.so` links against conda's own `libasound.so.2` (ALSA-only, compiled without PulseAudio support). WSL2 has no ALSA devices, so `sd.query_hostapis()` returns `[{'name': 'ALSA', 'devices': []}]`. The standard fix (install `libasound2-plugins` to bridge ALSA→Pulse) doesn't reach conda's ALSA because it links the conda copy, not the system one.

**Fix: replace sounddevice entirely**
- `wake_word.py`: stream 80ms int16 chunks from `parecord` subprocess → directly fed to openwakeword
- `stt.py`: `record_until_silence()` reads from `parecord` pipe, same silence detection logic
- `tts.py`: ElevenLabs MP3 bytes piped to `ffplay -f mp3 -i pipe:0` — no miniaudio/sounddevice needed
- `pyproject.toml`: removed `sounddevice` and `miniaudio` dependencies
- Configurable via `audio_device` in config.yaml (defaults to PulseAudio default source = RDPSource in WSLg)

**Confirmed working:**
- `parecord` captures 0.5s = 7990 samples @ 16kHz via WSLg RDPSource
- `ffplay` plays test tone via WSLg RDPSink
- 102 tests pass (stt/tts use subprocess mocks, unaffected)

**Phase 11A (Obsidian integration) — shipped at fd1b2b1:**
- T1: dotted-path config accessor + OBSIDIAN_API_KEY env override
- T2: `core/notifications.py` — shared TTS queue for background threads
- T3: `tools/obsidian.py` — capture_to_obsidian, read_obsidian_note, search_obsidian, build_vault_index
- T4: `core/brain.py` — vault_context param, system becomes list of 2 blocks when non-empty
- T5: `core/pipeline.py` — _load_vault_context(), vault_context to both think() calls, TTS queue drain
- T6: `config.yaml` — obsidian block with api_host=172.18.144.1, api_key, vault_path=/mnt/c/obsidian
- T7: `tests/test_phase11.py` — 19 tests for all obsidian tools and brain vault_context behavior
- T8: `tests/test_pipeline.py` — updated for vault_context-aware think() calls

**WSL2 networking for Obsidian:**
- Obsidian Local REST API only binds to 127.0.0.1:27123 on Windows
- Firewall rule: allow inbound TCP 27123 from WSL subnet (172.18.128.0/24)
- Port proxy: `netsh interface portproxy add v4tov4 listenport=27123 listenaddress=0.0.0.0 connectport=27123 connectaddress=127.0.0.1`
- WSL2 gateway IP: 172.18.144.1 (from `ip route show default | awk '{print $3}'`)

---

## 2026-05-19 (continued — /review session)

### Session: /review of existing codebase before Phase 11 (Claude Sonnet 4.6)

**Commits:**
- `cb96fa1` — feat: add phone server bridge + fix review bugs

**Bugs found and fixed:**
- `brain.py` `think()`: appended empty `user: ""` turn after `user: [tool_results]` on second call — consecutive user messages violated Anthropic API contract. Fixed: skip append when both `user_message` and `memory_context` are empty.
- `pipeline.py` `main()`: `server_enabled` defaulted to `True` — Bobby would crash silently if uvicorn not installed. Fixed to `False`; user's config.yaml now has explicit `server_enabled: true`.
- `pipeline.py` `_start_server_thread()`: uvicorn import in daemon thread failed silently on ImportError. Fixed with try/except + log.error.
- `pipeline.py` second `think()` call: was re-injecting `memory_context` with `user_message=""`, producing `"<data>memory</data>\n\nUser said: "` — broken content. Fixed: pass `memory_context=""` for the tool follow-up call.
- `server/main.py`: `allow_credentials=True` + `allow_origins=["*"]` is CORS spec violation. Removed `allow_credentials`.
- `stt.py` `transcribe()`: `result["text"]` (KeyError risk) vs `result.get("text","")` in `transcribe_from_bytes()`. Unified to `.get()`.

**New files shipped (pre-existing uncommitted work):**
- `server/auth.py`, `server/main.py`, `server/routes/` — FastAPI server bridge for phone PWA
- `core/stt.py` `transcribe_from_bytes()` — WebM/Opus from browser MediaRecorder
- `core/tts.py` `synthesize()` — returns MP3 bytes without playing locally
- `docs/AI_CONTEXT.md` — AI model routing doc for agent handoffs

**Warnings (not fixed — low priority):**
- `tts.py`: `synthesize()` duplicates ElevenLabs call setup from `_try_elevenlabs()` — DRY issue, same URL/model/format in two places.
- `phone/` directory (React PWA) left untracked — needs `dist/` build before it's useful; commit when ready to deploy.

**Status at handoff:**
- Pre-existing uncommitted changes are now committed and pushed (`cb96fa1`).
- Phase 11 prerequisites remain: install Obsidian Local REST API plugin, run WSL curl test.
- Phase 11 T1–T8 tasks ready to implement after WSL gate passes.

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
