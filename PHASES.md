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
- [ ] **[MANDATORY TESTS — Phase 1]**
  - [x] Empty audio / silence → STT returns `""` → LLM is NOT called (handled in `pipeline.py` + `stt.py`)
  - [ ] Claude API timeout → Bobby says "I'm having trouble, try again" (no crash)
  - [ ] ElevenLabs down → fallback TTS activates, Bobby still responds (fallback exists, test not written)

**UX polish:**
- [ ] Subtle audio cue when wake word fires (soft chime) — `_play_chime()` is a stub
- [ ] Different audio cue for "thinking" vs "done"
- [ ] Response latency target: < 2s for simple commands, < 4s for complex
  - Note: Claude tool-use requires 2 API round trips — budget ~300ms Whisper + ~400ms Haiku + ~300ms ElevenLabs first chunk = ~1s minimum for simple commands. Sonnet adds ~700ms. These are real numbers, not aspirational.

---

## Phase 2 — OS Control & App Automation
*Goal: Bobby can actually do things on your PC.*

- [ ] **App launcher**: open any installed app by name
  - [ ] Fuzzy match: "open vs" → VSCode
  - [ ] Admin mode support: `open riot in admin mode`
  - [ ] Note: pywinauto/Win32 accessibility APIs work well for native Windows apps but are unreliable for Electron apps (VS Code, Discord, Slack). For those, use `subprocess` to launch and rely on voice/keyboard control rather than UI automation.
- [ ] **Named shortcuts system**
  - [ ] "The usual" → Discord + Chrome + YouTube tab + Riot (admin)
  - [ ] User can teach Bobby new shortcuts: "bobby, save this combo as 'work mode'"
  - [ ] Shortcuts stored in SQLite memory
- [ ] **Window management**
  - [ ] Snap windows left/right/fullscreen
  - [ ] Switch focus to a specific app
  - [ ] Close app or all windows
- [ ] **System controls**
  - [ ] Volume up/down/mute/set to X%
  - [ ] Screen brightness
  - [ ] Lock/sleep/restart/shutdown PC
- [ ] **Terminal execution**
  - [ ] Run commands in a new terminal window
  - [ ] Run commands silently and report output
  - [ ] **[CRITICAL TEST]** Dangerous command blocklist: `rm -rf`, `format`, `del /f /s /q`, `reg delete`, `shutdown /f` → Bobby asks confirmation BEFORE executing, never auto-runs
  - [ ] Safety confirmation for destructive commands
- [ ] **Keyboard/mouse automation**
  - [ ] Type text for you
  - [ ] Press hotkeys
  - [ ] Click coordinates or UI elements (pywinauto)
- [ ] **Active window awareness**
  - [ ] Bobby knows what app is currently in focus
  - [ ] Commands can be context-aware: "make this fullscreen" → acts on active window

---

## Phase 3 — Memory Layer
*Goal: Bobby remembers who you are and what you like.*

- [ ] **Structured memory (SQLite)**
  - [ ] Shortcuts table (name → app list / action list)
  - [ ] Facts table (key-value: "my favorite Spotify playlist = X")
  - [ ] Conversation history (last N turns, with timestamps)
  - [ ] User preferences (preferred browser, default VSCode directory, etc.)
- [ ] **Memory commands**
  - [ ] "Bobby, remember that..." → saves a fact
  - [ ] "Bobby, what do you know about me?" → lists stored facts
  - [ ] "Bobby, forget X" → removes a memory
  - [ ] "Bobby, update 'the usual' to also include Slack"
- [ ] **Semantic memory (ChromaDB)**
  - [ ] Embed past conversations and facts as vectors
  - [ ] Relevant memories surface automatically when related topics come up
  - [ ] "Bobby, what was that thing I mentioned about the animation library?" → finds it
  - [ ] **[CRITICAL TEST]** Memory injection bounded: `get_relevant_memories(query, max_tokens=4000)` — never overflow Claude's context window regardless of memory volume
  - [ ] Run ChromaDB query in parallel with Claude API call to hide latency
- [ ] **Session context**
  - [ ] Bobby carries context across a session (remembers what you asked 10 min ago)
  - [ ] Summaries of old sessions stored for long-term recall
- [ ] **Proactive memory**
  - [ ] Bobby learns patterns: "You usually open Riot on Friday evenings — want me to open it?"
  - [ ] Opt-in behavior, configurable

---

## Phase 4 — Phone Bridge & Remote Voice
*Goal: Control Bobby from your phone, anywhere.*

- [ ] **FastAPI server on PC**
  - [ ] REST endpoints for commands
  - [ ] WebSocket for real-time voice streaming
  - [ ] Auth (simple token-based — this is personal use)
- [ ] **Local network access**
  - [ ] Phone connects to PC via local IP
  - [ ] mDNS: phone finds Bobby at `bobby.local` automatically
- [ ] **Cloudflare Tunnel (external access)**
  - [ ] Bobby reachable from anywhere via a private domain (e.g., `bobby.yourdomain.com`)
  - [ ] No port forwarding, no exposed public IP
- [ ] **React PWA (phone web app)**
  - [ ] Voice input via browser mic (Web Speech API or MediaRecorder)
  - [ ] Text fallback input
  - [ ] Response playback (TTS audio streamed back to phone)
  - [ ] Works offline for cached commands
  - [ ] "Add to Home Screen" for app-like experience
- [ ] **Wake-on-LAN**
  - [ ] "Bobby, turn on my PC" from phone
  - [ ] Sends WoL magic packet via your router or a always-on device (Raspberry Pi / router script)
- [ ] **Remote command parity**
  - [ ] Every Phase 2 command works from the phone too

**UX polish:**
- [ ] Haptic feedback on phone when Bobby starts responding
- [ ] Connection status indicator (green = online, yellow = local only, red = offline)

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

- [ ] **Spotify control**
  - [ ] Play/pause/skip/volume
  - [ ] "Play something chill" → mood-based playlist
  - [ ] "What's this song?" → reads current track
- [ ] **System media controls**
  - [ ] Global play/pause (works on any media)
  - [ ] Next/previous track
- [ ] **Google Calendar integration**
  - [ ] "What do I have today?" → reads schedule
  - [ ] "Add a meeting at 3pm called X"
  - [ ] Proactive: Bobby announces upcoming events 10 min before
- [ ] **Clipboard sync**
  - [ ] Copy on PC → accessible from phone (and vice versa)
  - [ ] "Bobby, what's in my clipboard?" → reads it aloud
- [ ] **Notifications**
  - [ ] Bobby monitors PC notifications and can surface important ones to phone
  - [ ] Configurable per-app rules ("only bug me about Discord DMs, not server messages")
- [ ] **Screenshot workflow**
  - [ ] "Bobby, screenshot this" → captures active window or full screen
  - [ ] Optionally: annotate with Claude Vision before saving

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
- [ ] **Obsidian integration**: Bobby reads your notes and second brain
- [ ] **Email/Slack**: Read and draft messages via voice
- [ ] **Code assistant mode**: Bobby runs tests, reads terminal errors, suggests fixes in VSCode
- [ ] **Native mobile app** (React Native / Expo): background wake word on phone
- [ ] **Smart home**: Control lights, thermostat via Bobby (Home Assistant integration)
- [ ] **Custom wake word training**: Train Porcupine on your exact voice for better accuracy
- [ ] **Emotion detection**: Bobby picks up frustration in your voice and adjusts tone

---

## Current Status

- [x] Phase 0 — Project Setup (CI done, WoL prereq deferred — waiting on Pi Zero 2)
- [~] Phase 1 — Core Voice Pipeline (core loop working; streaming TTS, mid-response interrupt, chimes, timeout tests remaining)
- [ ] Phase 2 — OS Control
- [ ] Phase 3 — Memory Layer
- [ ] Phase 4 — Phone Bridge
- [ ] Phase 5 — Remote Screen & Files
- [ ] Phase 6 — Browser Automation
- [ ] Phase 7 — Smart Integrations
- [ ] Phase 8 — Routines & Proactive
- [ ] Phase 9 — Screen Awareness
- [ ] Phase 10 — Polish & Daily Driver

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Outside Voice | `/office-hours` + subagent | Independent 2nd opinion | 1 | issues_found | 5 findings, 3 cross-model tensions resolved |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 4 issues resolved, 2 critical gaps addressed, 20 test paths mapped |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**VERDICT:** ENG REVIEW CLEARED — 4 architecture decisions locked, 2 critical safety tests mandated, outside voice integrated. Ready to implement Phase 0.
