# Bobby — Engineering Log

---

## 2026-06-04 — Phase 12: orb fade-to-gray removal + open_app + list_running_apps (Claude Sonnet 4.6)

**Orb: removed fade-to-gray**
- Removed `fading` state from `App.tsx` entirely — orb now simply slides right after 500ms idle
- `HIDE_DELAY` reduced 1500ms → 500ms; no CSS filter transition, no gray circle
- Removed all `.orb-wrapper.fading` CSS rules and `filter` transition on `.orb-glow-ring`

**open_app: Obsidian + verification**
- `tools/os_control.py`: added `"obsidian": "Obsidian"`, `"notion"`, `"figma"`, `"cursor"` to APP_MAP
- Added `list_running_apps` tool: calls PowerShell `Get-Process`, accepts optional partial-name filter, returns `ToolResult(success, message, data={"running": bool})`
- Shell injection sanitized: `filter.replace("'","").replace('"',"")[:64]`

**Tests**
- `tests/test_os_control.py`: added `TestListRunningApps` (5 tests), `TestAppMap` (1 test)
- Fixed `test_sanitizes_filter_input`: assertion was checking for `'` in the entire PS command (which contains template literals like `'not running'`). Changed to assert the injection payload `'; DROP` is not present.
- All 34 tests passing.

Commit hash: (pending)

---

## 2026-06-04 — Phase 12: click-through fix (setIgnoreCursorEvents) (Claude Sonnet 4.6)

**Bug**: Tauri window covered the right edge of the screen even when the orb was invisible/idle, blocking all mouse clicks in that region. Root cause: the window itself (not just CSS opacity) was capturing events.

**Fix**:
- Added `"window:allow-set-ignore-cursor-events"` to `desktop/src-tauri/capabilities/default.json`
- `App.tsx`: call `appWindow.setIgnoreCursorEvents(true)` on initial mount and when orb hides; `setIgnoreCursorEvents(false)` when orb becomes visible
- `appWindow` is `getCurrentWindow()` from `@tauri-apps/api/window` (already in package.json)
- `.catch(() => {})` swallows the error gracefully in dev (before Tauri API is fully initialized)

Commit hash: 4134181

---

## 2026-06-04 — Phase 12 orb v3: sparkle particles + 3D jelly sphere + fade-to-gray (Claude Sonnet 4.6)

Orb redesign based on Asha blob reference (Genshin Impact / Natlan). Key changes:

### Sparkle field (replaces conic gradient rings)
- 8 `<div>` sparkle elements inside `.sparkle-field`, each orbiting in its own tilted 3D plane
- Orbit trick: `rotateX(sx) rotateY(sy) rotateZ(angle) translateX(r)` — tilting the plane before sweeping produces elliptical orbits that read as 3D
- `@keyframes sparkle-depth`: opacity 0.95→0.10→0.95 over one orbit, simulates passing behind the orb
- Each sparkle has unique tilt angles, radius, size, duration, delay, and hue offset (`--dh`)
- `@property --orb-h` changed to `inherits: true` so sparkles and orb body inherit the hue from `.orb-glow-ring` without needing explicit redeclaration

### 3D jelly sphere
- Orb body now uses 3 stacked radial-gradients: sharp specular highlight (top-left), rim light (bottom-right), main body (bright core → deep dark edge)
- `inset` box-shadow for subsurface scattering illusion (translucency/jelly depth)
- `orb-squish` keyframes: 8 stops with squash/stretch/rotate synchronized to the float arc timing. Squash peak at 82% (matches float dip at 80%)
- `blob-morph` keyframes: 7 stops, more extreme border-radius swings
- Float on `.orb-glow-ring` (translateY -7px), squish+blob on `.orb` — no transform conflicts

### Fade-to-gray before hide
- `fading` state (bool) added to App.tsx
- Set `fading=true` immediately when state→idle; cleared on any active event
- `.orb-wrapper.fading` applies `filter: saturate(0.04) brightness(0.45) blur(0.5px)` to glow ring with 0.9s ease, fades sparkles and text to opacity:0
- After `HIDE_DELAY` (1500ms), `visible=false` triggers slide-out

### Ambient aura
- `::before` on `.orb-glow-ring`: soft radial glow (not a structured ring), pulses with `@keyframes aura-pulse`

Commit hash: e8659b8

---

## 2026-06-04 — Phase 12 T6+T7: Tauri scaffold + Bobby orb UI v2 (Claude Sonnet 4.6)

Shipped the Tauri desktop overlay with animated Bobby orb. Volume halved from 100% → 50% default.

### T6 — Tauri scaffold (earlier in session)
Already committed (`caa2745`). Port 3000, Defender exclusions, right-edge positioning in `lib.rs`.

### T7 — Orb UI v2: @property hue transitions + Siri flare corona
- `core/tts.py`: `_play_mp3` now reads `tts_volume` from config (default 50); passes `-volume` flag to ffplay. Was hardcoded to 100%.
- `desktop/src/App.tsx`: Added `.orb-glow-ring` wrapper div so the conic flare can overflow the orb without being clipped by `overflow: hidden`.
- `desktop/src/App.css` — full rewrite for smooth state transitions:
  - `@property --orb-h { syntax: '<number>'; }` — registered as a `<number>` type so CSS can actually interpolate it between states (without `@property`, custom props snap instead of transitioning).
  - `--flare-angle` registered as `<angle>` for the rotation animation.
  - `.orb-glow-ring--*` sets state hues: idle=240, listening=217, thinking=38, speaking=160. Transitions at `0.75s ease`.
  - `.orb-glow-ring::before` — rotating conic gradient flare. Positioned at `inset: -18px` (bleeds outside orb), masked with `radial-gradient` to create a ring/corona shape. `opacity: 0` when idle; `opacity: 1` on any active state. `animation: flare-rotate 4s linear infinite`.
  - Orb gradient reads from `var(--orb-h)` so color transitions are smooth through intermediate hues instead of jumping.
  - Flare hidden when idle, appears on listening/thinking/speaking.

### Why @property is required here
CSS custom properties are not typed by default — the browser treats them as opaque strings and doesn't know how to interpolate between `217` and `38`. Registering `--orb-h` as `<number>` tells the browser it's a number, enabling smooth hue interpolation via `transition`. Without this, any `transition: --orb-h` declaration is silently ignored.

Commit hash: c38bf1f

---

## 2026-06-04 — Phase 12 T1–T5: WebSocket event bus + pipeline wiring (Claude Sonnet 4.6)

Shipped the WS backend layer that Tauri depends on. Test count: 236 → 259 (23 new tests, 0 regressions).

### T1 — `core/events.py` (new)
- Thread-safe event bus: `broadcast_state(state, text, transcript)` callable from any pipeline thread
- `subscribe()` / `unsubscribe()` for WS clients; each gets an `asyncio.Queue(maxsize=100)`
- `set_event_loop(loop)` stores the uvicorn event loop for `call_soon_threadsafe` delivery
- `get_current_state()` returns snapshot for on-connect delivery (late-joining clients aren't blank)
- `QueueFull` on a maxed-out slow client is swallowed, not raised

### T2 — `core/pipeline.py` wiring (5 call sites)
- `_on_wake()` → `broadcast_state("listening")` (before `_listening.set()`)
- `_run_command()` start → `broadcast_state("thinking")` (after empty-text guard)
- `_process_command()` before `speak()` → `broadcast_state("speaking", text=response_text)`
- `_process_command()` `finally` block → `broadcast_state("idle")`
- `process_text_command()` API path: same speaking+idle transitions after `_run_command()` returns
- Import added at module top: `from core.events import broadcast_state` (no circular import risk — `events.py` has no pipeline dependency)

### T3 — `server/ws.py` (new) + `server/main.py` mount
- `GET /ws?token=<token>` WebSocket endpoint; auth via query param (CORS doesn't protect WS)
- Uses `verify_token` logic inline (compare against `config.get("server_token")`)
- Sends state snapshot immediately on connect; then streams queued events until disconnect
- Cleanup: `unsubscribe(q)` in `finally` block — dead client never leaks a queue reference

### T4 (manual) — browser verify pending
- Run: `new WebSocket("ws://localhost:8765/ws?token=...")` in browser console
- Should receive `{"state":"idle"}` snapshot, then live events on wake word

### T5 — Tests: 23 new in `tests/test_server_ws.py` + `tests/test_pipeline_broadcast.py`
- Event bus: subscribe/unsubscribe, snapshot copy safety, broadcast delivery to 1/N clients, full-queue resilience
- WS endpoint: auth pass/fail, snapshot on connect, disconnect cleanup, reconnect
- Pipeline: `_on_wake` listening/skip-while-speaking, `_run_command` thinking, `_process_command` speaking+idle, `process_text_command` speaking+idle

### Design decisions
- **Event bus in `core/` not `server/`**: `server.routes.command` → `core.pipeline` → `core.events` is a clean DAG. `core.pipeline` → `server.ws` would create a cycle (`server.main` imports both) causing `ImportError` at startup.
- **`?token=` query param for WS auth**: `Authorization` headers can't be set by native WebSocket API in browsers. If Cloudflare Tunnel is ever enabled, open WS = live transcript leak — the token check is essential.
- **`call_soon_threadsafe` + `asyncio.Queue` over `threading.Queue`**: The WS handler is async (uvicorn event loop). Using `asyncio.Queue.put_nowait` keeps delivery in the event loop thread without extra synchronization overhead.

Commit hash: d7cfca7

---

## 2026-06-04 — Phase 6B + 7A + 7B: Browser, per-app audio, Spotify (Claude Sonnet 4.6)

Shipped three new tool modules. Test count: 177 → 229 (52 new tests, 0 regressions).
Discord config.yaml updated with real server/channel IDs (BUBBLE BUTT BOTTOM BOIS).

### Phase 6B — `tools/browser.py`
- `open_url`: opens Chrome via `cmd.exe /c start chrome "url"` on WSL
- `open_search`: constructs Google search URL with optional site restriction
- `open_site`: 30+ friendly aliases including job sites (indeed, linkedin, glassdoor, levels.fyi) and career pages (tiktok, google, meta, apple, etc.); falls back to Google search for unknowns
- Bobby (Claude) resolves friendly names to URLs from training knowledge — no URL map lookup needed for most sites

### Phase 7A — `tools/audio.py`
- PowerShell inline C# WASAPI for per-process audio session control (IAudioSessionManager2)
- `list_audio_apps`, `get_app_volume`, `set_app_volume(app, level, mute)`
- "youtube" → chrome process (all Chrome audio sessions targeted — can't distinguish tabs at OS level)
- C# type compiled once per PS session (~400ms), cached after first call

### Phase 7B — `tools/spotify.py`
- spotipy OAuth 2.0 with token cache at `~/.bobby/spotify_cache`
- First-time auth: Bobby opens Chrome to auth URL, user approves, token stored silently
- `spotify_play`: searches user's own playlists first (partial match), falls back to catalog
- `spotify_control`: pause/resume/next/previous/shuffle via Spotify Web API
- `spotify_volume`: Spotify app playback volume (independent of system/WASAPI volume)
- `spotify.enabled` gate: graceful error message if credentials not configured yet
- spotipy added to pyproject.toml dependencies

### Design decisions
- **No Playwright for URL opening**: `cmd.exe /c start chrome "url"` is sufficient and instant. Playwright is overkill until Phase 6 deeper automation (tab management, form fill, etc.)
- **Per-app audio via PowerShell WASAPI, not pycaw**: pycaw is `sys_platform == 'win32'` only; won't load in WSL. PowerShell approach is consistent with existing system volume code and avoids dual-path logic.
- **Spotify playlist search: user playlists first**: The user said "play my Vietnamese playlist" — searching their own saved playlists before the catalog respects that intent. Catalog fallback covers cases where the playlist isn't saved yet.

Commit hash: 920ef7a

---

## 2026-06-04 — Phase 2B + 2C: File ops and Discord integration (Claude Sonnet 4.6)

Shipped two new tool modules. Test count: 132 → 177 (45 new tests, 0 regressions).

### Phase 2B — `tools/file_ops.py`
- `search_files`: pathlib.glob search with folder aliases, type filter, date filter, top-10 cap
- `open_file`: opens via `cmd.exe /c start`, accepts WSL paths (converted via `_to_windows_path`)
- `list_folder`: sorted by date/name/size, capped at 20 entries
- `_win_home()`: detects Windows USERPROFILE from `cmd.exe` subprocess, lru_cache'd
- No new dependencies — pure stdlib + existing pathlib/subprocess

### Phase 2C — `tools/discord.py`
- `discord_navigate`: Discord URL scheme `discord://-/channels/{guild}/{channel}`, friendly name resolution from config with partial-match
- `discord_voice`: atomic PowerShell focus-switch (GetForegroundWindow → AppActivate Discord → SendKeys → SetForegroundWindow restore, ~250ms total)
- Screen share: custom keybind via `discord.screenshare_keybind` in config
- `_to_sendkeys`: converts human keybind notation ("ctrl+shift+s") → WScript.Shell SendKeys ("^+s")
- `config.yaml.example` updated with full `discord:` schema

### Design decisions
- **Focus-switch over Discord RPC**: The unofficial Discord local RPC (pypresence) is read-only for most voice state — it can't set mute/deafen programmatically. Focus-switch + SendKeys is more reliable and requires no additional library.
- **Single PowerShell invocation**: Saved HWND → focus → keys → restore all in one `subprocess.run` call to avoid TOCTOU races between save and restore.
- **Folder alias resolver tries partial match**: "vid" → "videos", "docs" → "documents" — matches how people speak, not just exact config key names.
- **`_win_home` cached with lru_cache**: The `cmd.exe` subprocess to detect USERPROFILE runs exactly once per process. Tests use `cache_clear()` + `monkeypatch` to isolate.

Commit hash: c23d23f

---

## 2026-06-03 — E2E test session + full RCA (Claude Sonnet 4.6)

First real daily-driver test. Volume now works. All blocking bugs resolved.
6 bugs found and fixed across 4 commits (3785102 → d4a8543).

---

### Bug 1 — Tool results silently discarded (critical)
**Where:** `core/pipeline.py:226`
**Root cause:** Condition `if tool_calls and not response_text:` controlled whether
the second `think()` call (which presents tool results to the user) ran. Claude
sometimes returns BOTH an interim spoken text ("I'll pull up what I have stored")
AND tool_calls in the same response. When it did, `response_text` was non-empty →
condition was `False` → second `think()` skipped → tool results thrown away. User
asked "what do you know about me?", Bobby said "I'll pull up..." and then went silent
for 2 minutes.
**Fix:** `if tool_calls:` — always run the second think() when tools were called.
Second think() response overwrites the interim text, which is the correct behavior.

---

### Bug 2 — Markdown read aloud by ElevenLabs
**Where:** `core/tts.py` — `speak()` passed raw Claude output to ElevenLabs
**Root cause:** Claude formats responses with markdown (`**51**`, bullets, headers).
ElevenLabs reads these as literal symbols: "asterisk asterisk 51 asterisk asterisk".
**Fix:** Added `_strip_markdown()` applied inside `speak()` before the API call.
Strips bold, italic, code, headers, bullets, horizontal rules, collapses blank lines.

---

### Bug 3 — Bobby didn't know the current time
**Where:** `core/brain.py` — `SYSTEM_PROMPT` static constant
**Root cause:** The system prompt is a fixed string with no dynamic context.
Claude has no awareness of the current date or time unless told.
**Fix:** `datetime.now()` formatted and appended to SYSTEM_PROMPT on every `think()` call.

---

### Bug 4 — Volume: C# float literal `0.1f` invalid in PowerShell
**Where:** `tools/os_control.py` — `set_volume()` building the PowerShell command
**Root cause:** `f"[AudioCtrl]::SetLevel({level / 100.0}f)"` produced
`[AudioCtrl]::SetLevel(0.1f)`. The `f` suffix is C# syntax for float literals —
PowerShell does not understand it and threw "Unexpected token '0.1f'".
**Fix:** `[AudioCtrl]::SetLevel([float]{level / 100.0})` — uses PowerShell's own
cast syntax instead of a C# literal.

---

### Bug 5 — Volume: C# `static readonly` field passed by `ref`
**Where:** `tools/os_control.py` — `_PS_AUDIO_CS` inline C#, `GetAEV()` method
**Root cause:** `dev.Activate(ref AEV_IID, ...)` passed a `static readonly Guid`
directly by `ref`. The C# spec prohibits this outside a static constructor (the
field is stored in a CPU register, not a memory location that `ref` can point to).
Older .NET versions enforce this strictly.
**Fix:** `var iid = AEV_IID; dev.Activate(ref iid, ...)` — copy to a local
mutable variable before passing by ref.

---

### Bug 6 — TTS hang froze Bobby's main loop (up to 16 minutes)
**Where:** `core/tts.py` `_play_mp3()` and `_speak_fallback()`;
`core/pipeline.py` `_process_command()`
**Root cause (three layers):**
1. `_play_mp3()` called `proc.communicate()` with no timeout. If PulseAudio
   dropped mid-session, ffplay hung indefinitely — blocking the call.
2. The pyttsx3 fallback calls `engine.runAndWait()` which hangs in WSL2
   because pyttsx3 has no audio backend in that environment.
3. `speak()` was called synchronously in the main `run()` loop. Any hang in
   TTS completely froze Bobby — wake words were detected but never processed
   because `_listening.wait()` was never reached.
**Fix (three layers):**
1. `proc.communicate(timeout=20)` + `proc.kill()` on `TimeoutExpired`.
2. `_speak_fallback()` skips immediately on WSL2 (`sys.platform != "win32"`).
3. `speak()` runs in a daemon thread with `t.join(timeout=35)` — main loop
   is capped at 35s wait regardless of what ElevenLabs or ffplay does.

---

### Optimization — Whisper preloaded at startup
`pipeline.py main()`: `_load_model()` called in a daemon thread at startup to
eliminate the 3s cold-start penalty on the first voice command after restart.

Commits: `3785102`, `87a26a7`, `fd82121`, `d4a8543`

---

## 2026-06-03 — Wake word + repo cleanup (Claude Sonnet 4.6)

Trained custom "hey bobby" wake word via OpenWakeWord Colab (5k examples, 20k steps, T4 GPU).
Model: `models/hey_bobby.onnx` — verified loads correctly, model key = `hey_bobby`.
Activated in `config.yaml` via `wake_word_path: "models/hey_bobby.onnx"`.

Repo cleanup:
- Deleted `topics-for-bobby.txt` (vault reference list, gitignored anyway)
- Moved `TODOS.md` → `docs/TODOS.md`

Commit hash: `cab4fd9`

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
