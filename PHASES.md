# Bobby — Personal AI Assistant

> Jarvis-style voice assistant: PC control, memory, remote access, and phone bridge.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                        BOBBY CORE                        │
│                                                         │
│  [Wake Word] → [STT] → [Claude Brain] → [TTS]          │
│                              ↓                          │
│                    [Tool Dispatcher]                     │
│                    /     |      \                       │
│              [OS]  [Files] [Memory] [Browser] [System]  │
└─────────────────────────────────────────────────────────┘
          ↕ WebSocket / REST
┌───────────────────────────┐
│      BOBBY SERVER         │  ← FastAPI, runs on PC
│  Local network + tunnel   │
└───────────────────────────┘
          ↕
┌───────────────────────────┐
│      PHONE / REMOTE       │  ← Web app (React PWA)
│  Voice input + screen view│
└───────────────────────────┘
```

**Core Tech Stack:**
- Language: Python (backend), React (phone web app)
- Wake word: Porcupine (Picovoice) — custom "hey bobby" / "yo bobby"
- STT: Whisper (local, fast) → fallback Deepgram (cloud, faster)
- LLM: Claude API (Sonnet for complex, Haiku for fast/simple commands)
- TTS: ElevenLabs (natural, personality-driven voice)
- OS control: `subprocess`, `pywinauto`, `win32api`, `keyboard`
- Server: FastAPI + WebSockets
- Memory: SQLite (structured) + ChromaDB (semantic/vector)
- Screen stream: MJPEG (HTTP streaming, ~300ms latency) → upgrade to WebRTC in Phase 10 if needed
- Tunnel: Cloudflare Tunnel (for outside-home phone access)
- Auto-start: Task Scheduler (user session, not Windows Service — Bobby needs desktop access)

---

## Phase 0 — Project Setup & Architecture
*Goal: Clean foundation before any code.*

- [x] Initialize git repo and project structure
- [x] Set up Python virtual environment + `pyproject.toml`
- [x] Create config system (`config.yaml` + `.env` for API keys)
- [x] Set up logging infrastructure (structured logs, log levels)
- [x] Define tool interface: every action Bobby can take is a typed Python function returning `ToolResult(success, message, data)`
- [x] Write a `README.md` with setup instructions
- [x] Set up basic CI (lint, type check with mypy) — GitHub Actions, added in commit `b8f4ab6`
- [x] Add prompt injection defense to system prompt: all external content wrapped in `<data>` XML tags
- [ ] **[WoL prerequisite — DEFERRED]** Validate Wake-on-LAN support: enable in BIOS, check NIC settings in Device Manager, confirm router passes broadcast packets — waiting on Raspberry Pi Zero 2 stock before designing Phase 4

**Project structure:**
```
bobby/
├── core/
│   ├── wake_word.py       # always-on wake word listener
│   ├── stt.py             # speech-to-text
│   ├── brain.py           # Claude integration + tool dispatch
│   ├── tts.py             # text-to-speech
│   └── pipeline.py        # orchestrates the full loop
├── tools/
│   ├── os_control.py      # open apps, windows, system
│   ├── file_ops.py        # search, preview, move files
│   ├── browser.py         # browser automation (Playwright)
│   ├── media.py           # Spotify, YouTube, volume
│   └── memory.py          # read/write Bobby's memory
├── memory/
│   ├── db.py              # SQLite interface
│   ├── vector.py          # ChromaDB semantic memory
│   └── schema.py          # data models
├── server/
│   ├── main.py            # FastAPI app
│   ├── routes/            # API endpoints
│   └── stream.py          # WebRTC screen streaming
├── phone/                 # React PWA
│   └── src/
├── config.yaml
└── .env.example
```

---

## Phase 1 — Core Voice Pipeline (PC)
*Goal: Bobby hears you, thinks, and talks back.*

- [x] Wake word detection via OpenWakeWord ("hey jarvis" placeholder — same rhythm as "hey bobby")
  - [x] Always-on background thread, minimal CPU usage
  - [ ] Visual indicator (system tray icon pulses when listening)
- [x] Voice Activity Detection (VAD) — stop recording when you stop talking (`record_until_silence`)
- [x] STT: Whisper (local, `whisper-small` model for speed)
  - [ ] Fallback to Deepgram if Whisper is too slow on hardware
- [x] Claude integration via Anthropic SDK
  - [x] System prompt defining Bobby's personality (eager junior, efficient, slightly sarcastic)
  - [x] Tool use: Claude decides which tool to call based on your command
  - [ ] Streaming responses for faster TTS onset (currently downloads full audio then plays)
- [x] TTS: ElevenLabs (REST API via httpx, pyttsx3 fallback)
  - [x] Voice configured via `elevenlabs_voice_id` in config
  - [ ] True streaming (chunk-by-chunk) — currently full-response download
- [x] Full loop test: wake → speak → response → speak back ✓ (verified 2026-05-08)
- [x] Stop commands after wake word: "stop", "never mind", "cancel" → Bobby says "Got it." and resets
- [ ] Interrupt support: saying "bobby stop" *mid-response* cancels ongoing speech
- [ ] **[MANDATORY TESTS — Phase 1]** *(tests written in `tests/test_pipeline.py` + `tests/test_os_control.py`; verify they pass before Phase 2 ships)*
  - [x] Empty audio / silence → STT returns `""` → LLM is NOT called
  - [x] Claude API timeout → Bobby says "I'm having trouble, try again" (no crash)
  - [x] ElevenLabs down → fallback TTS activates, Bobby still responds

**UX polish:**
- [ ] Subtle audio cue when wake word fires (soft chime) — `_play_chime()` is a stub
- [ ] Different audio cue for "thinking" vs "done"
- [ ] Response latency target: < 2s for simple commands, < 4s for complex
  - Note: Claude tool-use requires 2 API round trips — budget ~300ms Whisper + ~400ms Haiku + ~300ms ElevenLabs first chunk = ~1s minimum for simple commands. Sonnet adds ~700ms. These are real numbers, not aspirational.

---

## Phase 2 — OS Control & App Automation
*Goal: Bobby can actually do things on your PC.*

- [x] **App launcher**: open any installed app by name
  - [x] Fuzzy match: "open vs" → VSCode (`_resolve_app`: exact → substring → difflib → passthrough)
  - [ ] Admin mode support: `open riot in admin mode`
  - [x] Note: pywinauto/Win32 accessibility APIs work well for native Windows apps but are unreliable for Electron apps (VS Code, Discord, Slack). For those, use `subprocess` to launch and rely on voice/keyboard control rather than UI automation.
- [x] **Named shortcuts system** (`tools/shortcuts.py`)
  - [x] "The usual" → Chrome + Discord + Spotify (seeded default; user can edit)
  - [x] User can teach Bobby new shortcuts: "bobby, save this combo as 'work mode'"
  - [x] Shortcuts stored in SQLite (`~/.bobby/shortcuts.db`)
  - [x] Tools: `open_shortcut`, `save_shortcut`, `list_shortcuts`, `delete_shortcut`
- [x] **Window management** (`manage_window`, `get_active_window`)
  - [x] Snap windows left/right/fullscreen/minimize (`_WINDOW_KEYS` + keyboard shortcuts)
  - [x] Switch focus to a specific app (win32gui on Windows, PowerShell fallback from WSL)
  - [x] Close app (alt+f4 via `press_keys`)
- [x] **System controls**
  - [x] Volume up/down/mute/set to X% (`get_volume` + `set_volume(level, mute)` — pycaw on Windows, PowerShell WASAPI fallback on WSL)
  - [x] Screen brightness (`set_brightness` via WMI PowerShell)
  - [x] Lock/sleep/restart/shutdown PC (`system_power` — hard voice confirmation gate)
- [x] **Terminal execution**
  - [x] Run commands in a new terminal window
  - [x] Run commands silently and report output
  - [x] **[CRITICAL TEST]** Dangerous command blocklist: `rm -rf`, `format`, `del /f /s /q`, `reg delete`, `shutdown /f`, `taskkill /f` → hard confirmation gate in pipeline, never auto-runs
  - [x] Safety confirmation for destructive commands (`_confirm_via_voice` + `confirm_and_retry_tool` pattern)
- [x] **Keyboard/mouse automation**
  - [x] Type text for you (`type_text` via `keyboard.write`)
  - [x] Press hotkeys (`press_keys` via `keyboard.send`)
  - [ ] Click coordinates or UI elements (pywinauto — deferred to Phase 9 screen awareness)
- [x] **Active window awareness**
  - [x] Bobby knows what app is currently in focus (`get_active_window`)
  - [ ] Commands can be context-aware: "make this fullscreen" → acts on active window (Phase 9)

**Phase 2 tests:** `tests/test_phase2.py` — 14 passed, 1 skipped (Windows-only) ✓

---

## Phase 3 — Memory Layer
*Goal: Bobby remembers who you are and what you like.*

- [x] **Structured memory (SQLite)**
  - [x] Shortcuts table (name → app list / action list) — covered by Phase 2 shortcuts.py
  - [x] Facts table (key-value: "my favorite Spotify playlist = X") — `memory/db.py` `facts` table
  - [x] Conversation history (last N turns, with timestamps) — `memory/db.py` `history` table + `save_turn` / `get_recent_history`
  - [x] User preferences (preferred browser, default VSCode directory, etc.) — stored as facts via `remember_fact`
- [x] **Memory commands**
  - [x] "Bobby, remember that..." → `remember_fact` tool saves a fact
  - [x] "Bobby, what do you know about me?" → `recall_facts` tool lists stored facts
  - [x] "Bobby, forget X" → `forget_fact` tool removes a memory
  - [x] "Bobby, update 'the usual' to also include Slack" → update via `save_shortcut` (Phase 2) or `remember_fact`
- [ ] **Semantic memory (ChromaDB)** — deferred (heavy dependency, no clear latency budget yet)
  - [ ] Embed past conversations and facts as vectors
  - [ ] Relevant memories surface automatically when related topics come up
  - [ ] "Bobby, what was that thing I mentioned about the animation library?" → finds it
  - [ ] **[CRITICAL TEST]** Memory injection bounded: `get_relevant_memories(query, max_tokens=4000)` — never overflow Claude's context window regardless of memory volume
  - [ ] Run ChromaDB query in parallel with Claude API call to hide latency
- [x] **Session context**
  - [x] Bobby carries context across a session (remembers what you asked 10 min ago) — `_history` list in pipeline
  - [~] Summaries of old sessions stored for long-term recall — raw turns persisted to DB per session; summarization deferred
- [ ] **Proactive memory**
  - [ ] Bobby learns patterns: "You usually open Riot on Friday evenings — want me to open it?"
  - [ ] Opt-in behavior, configurable

---

## Phase 4 — Phone Bridge & Remote Voice
*Goal: Control Bobby from your phone, anywhere.*

- [x] **FastAPI server on PC** (`server/main.py`, `server/auth.py`, `server/routes/`)
  - [x] REST endpoints: `POST /api/command` (text → response + audio), `POST /api/voice` (audio upload → transcribe → respond)
  - [x] `GET /api/health` (no auth — for connection status polling)
  - [ ] WebSocket for real-time streaming — deferred; REST polling is sufficient for MVP
  - [x] Auth (Bearer token from `config.yaml` `server_token`)
  - [x] Server starts automatically on `bobby` launch (daemon thread, `server_enabled: true`)
  - [x] Logs local IP + port on startup for easy phone setup
- [x] **Local network access**
  - [x] Phone connects to PC via local IP (printed on Bobby startup)
  - [ ] mDNS: `bobby.local` — deferred (requires `zeroconf` install + platform testing)
- [ ] **Cloudflare Tunnel (external access)**
  - [ ] Install `cloudflared`, run `cloudflared tunnel --url http://localhost:8765`
  - [ ] No port forwarding, no exposed public IP
- [x] **React PWA (phone web app)** (`phone/`)
  - [x] Voice input via browser mic (MediaRecorder API → WebM/Opus → POST /api/voice)
  - [x] Text fallback input with send button
  - [x] Response playback (MP3 audio from ElevenLabs decoded + played on phone)
  - [x] "Add to Home Screen" — PWA manifest + iOS/Android meta tags
  - [x] Settings modal (server URL + token stored in localStorage)
  - [x] Connection status badge (polls /api/health every 15s)
  - [x] Processing state with animated thinking dots
  - [x] Conversation history displayed as chat bubbles
- [ ] **Wake-on-LAN** — deferred (needs Raspberry Pi or always-on device)
- [x] **Remote command parity** — all Phase 2/3 tools accessible via API

**UX polish:**
- [ ] Haptic feedback on phone when Bobby starts responding
- [x] Connection status indicator (green = online, amber = checking, red = offline)

**Build & run:**
- Dev: `cd phone && npm install && npm run dev` (proxies `/api` to `localhost:8765`)
- Production: `npm run build` → FastAPI auto-serves `phone/dist/` at `/`

---

## Phase 5 — Remote Screen View & File Access
*Goal: See and search your PC from your phone.*

- [ ] **Screen streaming (MJPEG)**
  - [ ] PC screen visible on phone browser via MJPEG HTTP stream (~300ms latency, sufficient for file browsing)
  - [ ] FastAPI endpoint: `GET /stream/screen` → multipart JPEG frames at ~10 FPS
  - [ ] Pause/resume stream to save bandwidth
  - [ ] View-only mode by default (no remote mouse yet)
  - [ ] Note: WebRTC upgrade deferred to Phase 10+ — MJPEG is 30 lines of code vs weeks of signaling setup
  - [ ] Generate video thumbnails on-demand (NOT pre-generating all at once — avoids server lockup)
- [ ] **File search & surfacing**
  - [ ] "Bobby, find my video clip from last Tuesday" → searches by date + type
  - [ ] "Bobby, find any file named 'invoice'" → full-text + filename search
  - [ ] Results shown on phone with previews (thumbnails for images/videos, icons for docs)
- [ ] **File preview on phone**
  - [ ] Images: inline preview
  - [ ] Videos: streamable preview clip
  - [ ] PDFs, docs: rendered preview
  - [ ] Bobby streams the file to your phone on demand
- [ ] **File actions from phone**
  - [ ] "Open this on my PC" → Bobby opens the file in the right app
  - [ ] "Send this to my phone" → download link generated
  - [ ] "Move this to X folder" → Bobby moves it
- [ ] **Remote mouse/keyboard (optional, gated behind confirmation)**
  - [ ] Tap-to-click on screen stream
  - [ ] Virtual keyboard for text input

---

## Phase 6 — Browser Automation & Web Tasks
*Goal: Bobby can use the internet for you.*

- [ ] **Browser control via Playwright**
  - [ ] Open URLs ("bobby, open youtube")
  - [ ] Navigate to specific pages
  - [ ] Click elements by description (Claude Vision identifies them)
  - [ ] Fill forms
- [ ] **YouTube integration**
  - [ ] "Play me a lo-fi playlist on YouTube" → finds and plays it
  - [ ] "Play [song name]" → searches and plays
  - [ ] Pause/skip/volume via voice
- [ ] **Web search**
  - [ ] "Bobby, look up X" → searches and summarizes result
  - [ ] "Bobby, what's the weather today?" → fetches and reads aloud
- [ ] **Tab management**
  - [ ] "What tabs do I have open?" → lists them
  - [ ] "Close the Stack Overflow tab"
  - [ ] "Open a new tab and go to X"
- [ ] **Download manager**
  - [ ] "Bobby, download that YouTube video" → yt-dlp integration
  - [ ] "Save this page as PDF"
  - [ ] Progress reported back via TTS

---

## Phase 7 — Media & Smart Integrations
*Goal: Bobby plugs into the apps you actually use.*

- [ ] **Spotify control** — deferred (requires Spotify Web API OAuth setup)
  - [ ] Play/pause/skip/volume
  - [ ] "Play something chill" → mood-based playlist
  - [ ] "What's this song?" → reads current track
- [x] **System media controls** (`tools/media.py` `system_media`)
  - [x] Global play/pause (works on any media)
  - [x] Next/previous track
- [ ] **Google Calendar integration** — deferred (OAuth setup required)
  - [ ] "What do I have today?" → reads schedule
  - [ ] "Add a meeting at 3pm called X"
  - [ ] Proactive: Bobby announces upcoming events 10 min before
- [x] **Clipboard sync** (`tools/media.py` `get_clipboard` / `set_clipboard`)
  - [x] "Bobby, what's in my clipboard?" → reads it aloud
  - [ ] Copy on PC → accessible from phone (Phase 4 concern)
- [ ] **Notifications**
  - [ ] Bobby monitors PC notifications and can surface important ones to phone
  - [ ] Configurable per-app rules ("only bug me about Discord DMs, not server messages")
- [x] **Screenshot workflow** (`tools/media.py` `take_screenshot`)
  - [x] "Bobby, screenshot this" → captures full desktop via mss, saves to ~/Pictures/Bobby/
  - [ ] Annotate with Claude Vision before saving (Phase 9)

---

## Phase 8 — Routines & Proactive Behavior
*Goal: Bobby anticipates what you need.*

- [ ] **Named routines**
  - [ ] "Start my work routine" → opens VSCode, Slack, Notion, plays focus music
  - [ ] "Gaming mode" → opens Discord, Riot (admin), sets volume to 60%, DND on
  - [ ] "Wind down" → closes everything, plays chill music, dims screen
  - [ ] User defines routines via voice: "bobby, create a routine called 'deep work'"
- [ ] **Scheduled routines**
  - [ ] "Every weekday at 9am, start my work routine"
  - [ ] "Remind me to drink water every hour"
  - [ ] Stored as cron jobs managed by Bobby
- [ ] **Focus / Do Not Disturb mode**
  - [ ] "Bobby, I'm in focus mode" → suppresses non-critical notifications
  - [ ] Auto-cancels after a set time or when you say "okay I'm back"
- [ ] **Proactive suggestions (opt-in)**
  - [ ] "It's been 2 hours since you last took a break"
  - [ ] "You usually start gaming around now — want me to set it up?"
  - [ ] Configurable sensitivity / personality level
- [ ] **System health monitoring**
  - [ ] "How's my PC doing?" → CPU, RAM, GPU temp, disk space
  - [ ] Alert Bobby if temp spikes during gaming

---

## Phase 9 — Screen Awareness & Vision
*Goal: Bobby can see what you're looking at.*

- [ ] **On-demand screenshot + Claude Vision**
  - [ ] "Bobby, what's on my screen right now?" → describes it
  - [ ] "Bobby, help me fill out this form" → reads the form fields, assists
- [ ] **Active app context**
  - [ ] Bobby knows what app is focused and adjusts help accordingly
  - [ ] In VSCode: can help with code
  - [ ] In browser: can help navigate
- [ ] **Error detection**
  - [ ] "Bobby, I'm getting a weird error" → screenshots screen, reads error, suggests fix
- [ ] **Game awareness (optional)**
  - [ ] Detects if a game is running (via process name)
  - [ ] Adjusts behavior (quieter, less interruptive in gaming mode)

---

## Phase 10 — Polish, Performance & Daily Driver
*Goal: Smooth enough to use every single day.*

- [ ] **Response speed optimization**
  - [ ] Route simple/fast commands to Claude Haiku
  - [ ] Complex reasoning/memory to Claude Sonnet
  - [ ] Local fallback for ultra-fast commands (no LLM needed for "open chrome")
- [ ] **Error handling & graceful degradation**
  - [ ] If ElevenLabs is down → fall back to local TTS (pyttsx3)
  - [ ] If Claude API is down → cached common responses
  - [ ] Bobby always responds, even if just "I'm having trouble with that right now"
- [ ] **Startup behavior**
  - [ ] Bobby auto-starts with Windows (background service)
  - [ ] System tray icon with status, settings, and "mute Bobby" option
- [ ] **Settings UI (optional)**
  - [ ] Simple web UI at `localhost:8080` for config
  - [ ] Manage shortcuts, routines, memory, voice settings
- [ ] **Logging & observability**
  - [ ] All commands logged with timestamps
  - [ ] "Bobby, what did I ask you to do today?" → reads command history
- [ ] **Privacy controls**
  - [ ] Local-only mode (no cloud STT/TTS if desired)
  - [ ] Clear conversation history command
  - [ ] Explicit opt-in for all "learning" features

---

## Future Ideas (Backlog)

- [ ] **Voice cloning**: Make Bobby sound like a specific character or voice
- [ ] **Multi-room**: Bobby on a Raspberry Pi in other rooms, connects to same brain
- [ ] **Email/Slack**: Read and draft messages via voice
- [ ] **Code assistant mode**: Bobby runs tests, reads terminal errors, suggests fixes in VSCode
- [ ] **Native mobile app** (React Native / Expo): background wake word on phone
- [ ] **Smart home**: Control lights, thermostat via Bobby (Home Assistant integration)
- [ ] **Custom wake word training**: Train Porcupine on your exact voice for better accuracy
- [ ] **Emotion detection**: Bobby picks up frustration in your voice and adjusts tone

---

## Phase 11 — Second Brain (Obsidian Integration)
*Goal: Bobby becomes a queryable version of your mind.*

Design doc: [`~/.gstack/projects/cs-keni-bobby/keni-main-design-20260519-102214.md`](~/.gstack/projects/cs-keni-bobby/keni-main-design-20260519-102214.md)
CEO plan: [`~/.gstack/projects/cs-keni-bobby/ceo-plans/20260519-second-brain.md`](~/.gstack/projects/cs-keni-bobby/ceo-plans/20260519-second-brain.md)

**Prerequisites (before any code):**
- [ ] Install "Local REST API" Obsidian community plugin + copy API key
- [ ] WSL networking test: `curl http://$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):27123/` → `{"status":"OK"}`
- [ ] Add `obsidian:` block to `config.yaml` (enabled: false until WSL test passes)
- [ ] Run `/plan-eng-review` on Phase A before writing code

### Phase A — Local REST API + Voice Capture

- [ ] `tools/obsidian.py`: `capture_to_obsidian`, `read_obsidian_note`, `search_obsidian`
  - [ ] All tools use `@register_tool(name=..., description=..., parameters=...)` — explicit args required
  - [ ] HTTP calls wrapped in try/except; unreachable Obsidian → spoken error message
  - [ ] API host from config (NOT localhost — WSL2 networking)
- [ ] Register obsidian tools in `tools/__init__.py` / loader
- [ ] `config.yaml` obsidian block: `enabled`, `api_host`, `api_port`, `api_key`, `vault_path`, `inbox_folder`, `index_file`, `max_index_tokens`
- [ ] **Success gate:** "Bobby, note that I want to look into WebRTC" → note in Obsidian inbox within 3s; used daily for 1 week

### Phase B — Karpathy Index + Proactive Surfacing

- [ ] `build_vault_index()` tool: list note titles + first 3 lines via REST, Claude generates `VAULT_INDEX.md`
  - [ ] Runs in background thread (NOT in `_run_command()` — would hold `_processing_lock`)
  - [ ] Bobby speaks progress + completion via TTS
- [ ] Auto-update: `capture_to_obsidian` appends one line to `## Recent Captures` in VAULT_INDEX.md
- [ ] `vault_context: str = ""` param added to `think()` in `brain.py`
  - [ ] Injected as system role message (trusted — NOT via `<data>` XML tags)
  - [ ] `MAX_INDEX_TOKENS = 3000` guard before injection
- [ ] Proactive surfacing instruction added to system prompt
- [ ] **CP2:** Bobby creates/opens today's daily note on startup (all captures default-link to it)
- [ ] **Auto-session-capture:** End-of-session summary appended to daily note automatically
- [ ] **Morning brief:** "Good morning Bobby" → synthesizes inbox + recent captures
- [ ] **Success gate:** Bobby mentions a relevant note unprompted at least once per day

### Phase C — Personality Profile

- [ ] `build_personality_profile()`: batched note reads + Claude synthesis → writes `BOBBY_PROFILE.md`
- [ ] `update_personality_profile()`: last-30-days incremental refresh (manual trigger only)
- [ ] `BOBBY_PROFILE.md` injected into system prompt (~1,000 token budget, separate section)
- [ ] **CP1:** Proactive capture suggestions mid-conversation ("Want me to save that to Obsidian?")
- [ ] **Success gate:** "Bobby, how would I think about X?" sounds like you. Profile has ≥10 documented opinions with note citations.

---

## Current Status

- [x] Phase 0 — Project Setup (CI done, WoL prereq deferred — waiting on Pi Zero 2)
- [~] Phase 1 — Core Voice Pipeline (core loop working; streaming TTS, mid-response interrupt, chimes, timeout tests remaining)
- [~] Phase 2 — OS Control (core done; volume control + context-aware window targeting deferred)
- [~] Phase 3 — Memory Layer (core SQLite facts + history done, memory injection wired into pipeline; ChromaDB semantic search deferred)
- [~] Phase 4 — Phone Bridge (server + PWA done; Cloudflare Tunnel + mDNS + WoL deferred)
- [ ] Phase 5 — Remote Screen & Files
- [ ] Phase 6 — Browser Automation
- [~] Phase 7 — Smart Integrations (quick wins done: media keys, clipboard, screenshot; Spotify API + Google Calendar deferred)
- [ ] Phase 8 — Routines & Proactive
- [ ] Phase 9 — Screen Awareness
- [ ] Phase 10 — Polish & Daily Driver
- [ ] Phase 11 — Second Brain (Obsidian) — prerequisites pending; eng review required before Phase A

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | APPROVED | Phase 11 scoped; 3 arch fixes (decorator, vault_context param, background indexing); 2 cherry-picks (auto-session-capture, morning brief, CP1 proactive capture, CP2 daily note) |
| Outside Voice | `/office-hours` + subagent | Independent 2nd opinion | 1 | issues_found | 5 findings, 3 cross-model tensions resolved |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 4 issues resolved, 2 critical gaps addressed, 20 test paths mapped |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**VERDICT:** ENG REVIEW CLEARED — 4 architecture decisions locked, 2 critical safety tests mandated, outside voice integrated. Ready to implement Phase 0.
