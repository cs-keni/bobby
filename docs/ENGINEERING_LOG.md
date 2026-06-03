# Bobby — Engineering Log

---

## 2026-06-03 — Wake word + repo cleanup (Claude Sonnet 4.6)

Trained custom "hey bobby" wake word via OpenWakeWord Colab (5k examples, 20k steps, T4 GPU).
Model: `models/hey_bobby.onnx` — verified loads correctly, model key = `hey_bobby`.
Activated in `config.yaml` via `wake_word_path: "models/hey_bobby.onnx"`.

Repo cleanup:
- Deleted `topics-for-bobby.txt` (vault reference list, gitignored anyway)
- Moved `TODOS.md` → `docs/TODOS.md`

Commit hash: TBD

---

## 2026-06-03 — Phase 11B remaining + Phase 11C scaffold (Claude Sonnet 4.6)

**`build_vault_index()` full implementation (`tools/obsidian.py`)**

Replaced 100-note-capped stub with full implementation:
- `ThreadPoolExecutor(max_workers=10)` for concurrent note fetches — no 100-note cap
- `chunk_markdown()` from `memory/ingestion.py` extracts H2/H3 sections per note
- Index format: `- \`path\` — intro...` with `  ## Section — preview` sub-lines for sectioned notes
- Header: `Notes: N | Sections: M` for at-a-glance vault metrics
- 3 new tests in `tests/test_phase11.py` — total: 125 passing, 1 skipped

**`ensure_daily_note()` — startup daily note creation (`tools/obsidian.py`)**

New function: creates `Areas/Daily/YYYY-MM-DD.md` on Bobby startup if it doesn't exist.
- Runs in daemon thread at `main()` startup (non-blocking, ~50ms)
- Template: frontmatter + ## Morning / ## Notes / ## Evening sections
- Configurable via `obsidian.daily_folder` (default: `Areas/Daily`)
- Silent on failure — Obsidian may not be open at startup

**Phase 11C personality profile scaffold (`tools/profile.py` — new file)**

New module `tools/profile.py`:
- `build_personality_profile()`: full build — gbrain search for opinion/belief/decision/mental-model notes, reads top-50, feeds to Claude Sonnet, writes `BOBBY_PROFILE.md`
- `update_personality_profile()`: incremental — inbox notes from last 30 days + existing profile → Claude update
- `load_profile_context()`: reads `BOBBY_PROFILE.md` from vault, cached per process (one Obsidian fetch)
- Both builders run in daemon threads, silent on failure
- Gated by `personality_profile_enabled: true` in config (default: false)
- **DO NOT trigger automatically** — Kenny runs manually when ready for E2E test

**`core/brain.py`: `profile_context` param**

Added `profile_context: str = ""` to `think()`. When non-empty, appended as a third system block:
`[PERSONALITY PROFILE]\n{content}\n[END PERSONALITY PROFILE]` (~1,000-token budget, 4000-char cap).
Safe append pattern established in T5 (system is always `list[dict]`) makes this a one-liner.

**`core/pipeline.py`: plumbing**

`_run_command()` now calls `load_profile_context()` and passes it to both `think()` calls.
`main()` pre-warms the cache at startup (returns "" immediately when feature is disabled).

Commit hash: `8d84f60`

---

## 2026-06-03 — Phase 11B/C test coverage + PHASES.md success gate (Claude Sonnet 4.6)

Added 7 missing unit tests for `ensure_daily_note` and `load_profile_context` (both landed in 8d84f60 without tests).

**`ensure_daily_note` tests (3)**
- Creates today's note at `Areas/Daily/YYYY-MM-DD.md` when GET returns 404
- Skips PUT when note already exists (GET 200)
- Silent on `ConnectError` — no raise

**`load_profile_context` tests (4)**
- Returns `""` when `personality_profile_enabled: false`
- Returns profile markdown when BOBBY_PROFILE.md exists (200)
- Returns `""` when profile doesn't exist yet (404)
- Caches result: second call makes no HTTP request (`call_count == 1`)

Test baseline: 132 passed, 1 skipped (up from 125 after 8d84f60).

Updated PHASES.md Phase B success gate: *code ready; awaiting daily use observation by Kenny*.

Commit hash: `893fcd5`

---

## 2026-06-03 — Setup artifacts commit (Claude Sonnet 4.6)

Committed leftover gbrain setup files: `.gitignore` (add topics-for-bobby.txt exclusion),
`CLAUDE.md` (gbrain config + search guidance), `AGENTS.md` (new — Codex instructions),
`phone/` (React PWA source). These were all untracked after the Phase 11B-RAG sessions.

Commit hash: `193a47b`

---

## 2026-06-03 — T6-T8: ingestion chunker, gbrain capture hook, eval run (Claude Sonnet 4.6)

**T6: `memory/ingestion.py` — Markdown H2/H3 chunker (new file)**

`chunk_markdown(content, note_title)` → `list[Chunk]`. Strips YAML frontmatter,
extracts key-value metadata, splits on H2/H3 boundaries, flat-note fallback.
`Chunk` dataclass: title, content, section_level (0=whole note, 2=H2, 3=H3), metadata.
20 tests in `tests/test_ingestion.py` — all pass.

**T7: gbrain push hook in `tools/obsidian.py`**

After successful `capture_to_obsidian`, spawns a daemon thread calling:
`gbrain capture --stdin --slug inbox/<timestamp> --type concept --quiet`
Non-blocking (~5 lines). Silent on failure — gbrain availability never affects
capture reliability. Only fires when `gbrain.enabled: true` in config.

**T8: `evals/run_eval.py` + eval results**

Built eval runner: reads `golden_queries.yaml`, runs each query via gbrain CLI,
checks Recall@K, writes `eval_results.yaml`.

Key fix during T8: `VOYAGE_API_KEY` must be passed explicitly to the subprocess env.
Without it, gbrain falls back to BM25-only search (keyword), missing semantic matches.
Fix applied to both `_query_gbrain()` in pipeline.py and `run_eval.py`.

Also bumped pipeline timeout 5s → 8s to account for Voyage API embedding latency
under PGLite concurrency (MCP server + eval runner competing for the same DB).

**Final eval result: Recall@5 = 25/25 = 100%** across all 5 categories:
- bobby: 8/8 (100%)
- ai-ml: 8/8 (100%)
- system-design: 4/4 (100%)
- software-eng: 4/4 (100%)
- nlp: 1/1 (100%)

Results saved in `evals/eval_results.yaml`.

---

## 2026-06-03 — T3/T4: gbrain eval set + pipeline wiring (Claude Sonnet 4.6)

**T3: `evals/golden_queries.yaml` (new file)**

Created a 25-query golden eval set for measuring Recall@5 before/after RAG changes.
Covers Bobby-specific knowledge (8 queries), AI/ML concepts (7), system design (4),
software engineering (4), and NLP (1). Run with:
```
gbrain query "<query>" --limit 5 --source-id __all__
```
Pass = `expected_slug` appears in top-5. Confidence marked `high` for smoke-test-verified
slugs, `medium` for slugs inferred from vault audit headings (needs one-time verification).

**T4: Replace `_load_vault_context()` with `_query_gbrain()` in `core/pipeline.py`**

The static VAULT_INDEX.md approach (flat title list, 3000-token cap, no semantic ranking)
is replaced with a live gbrain hybrid search call per command:

- `_GBRAIN_BIN`: module-level path constant (`~/.bun/bin/gbrain`)
- Intent skip: commands matching `gbrain.intent_skip_patterns` (open, close, volume, etc.)
  skip the query entirely — no latency added for pure action commands
- Subprocess: `gbrain query <text> --limit 5 --source-id __all__` (~1.3s synchronous)
- CLI output parse: regex split on `\n(?=\[score\])` to handle multi-line chunks
- Token budget: `gbrain.max_context_tokens * 4` chars, truncates last entry to fit
- Silent fallback: timeout (5s), non-zero exit, or any exception → returns ""

**`core/brain.py` minor fixes:**
- `obsidian.max_index_tokens` → `gbrain.max_context_tokens` in `think()`
- Label: `[VAULT INDEX]` → `[VAULT CONTEXT]`
- System prompt: "vault index" wording → "semantically relevant notes retrieved from your knowledge base"

**Design note:** The gbrain CLI truncates chunk text to ~100 chars per result (display
format, not configurable). This is enough for Bobby to surface note titles and first
lines. Full chunk text retrieval is T6 (`memory/ingestion.py` vault file reader).

---

## 2026-05-21 — RAG scaling note (no code change)

Documented a known precision-vs-recall tradeoff in the current Obsidian retrieval strategy and the upgrade path when the vault outgrows it.

**Current approach:** index-based (`VAULT_INDEX.md` titles + first 3 lines) + metadata-filtered keyword search. High precision, low infra cost, appropriate for a small vault.

**Known limitation:** at ~300+ notes, the index overflows the `MAX_INDEX_TOKENS = 3000` budget and keyword search misses semantically related but differently-worded notes. Proactive surfacing coverage degrades.

**Planned upgrade (deferred — not needed yet):**
- One-time embedding pass over all vault notes (`text-embedding-3-small` ≈ $0.01, or local model)
- Store vectors in ChromaDB (already a dependency) or pgvector
- Replace `_load_vault_context()` with top-K semantic retrieval; keeps `vault_context` interface intact
- Keyword fallback for exact-match anchors

Note added to Phase B in `PHASES.md`. No files changed.

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
