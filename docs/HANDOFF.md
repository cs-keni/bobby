# Bobby — Handoff

## Last Updated: 2026-06-04 (Claude Sonnet 4.6 — Phase 12 T6+T7 Tauri orb)

---

## Current State

**HEAD is `caa2745`. T6+T7 orb changes staged, not yet committed. 259 tests passing, 1 skipped.**

Phase 12 WS backend is complete (`caa2745`). T6 Tauri scaffold is working (Defender exclusions, port 3000, right-edge positioning). T7 orb UI v2 is implemented with `@property` hue transitions + rotating Siri-style flare corona. Volume defaulted to 50%. T8 (Mica blur, tray icon, transcript scroll) remains.

---

## What Shipped This Session (2026-06-04)

### `c23d23f` — Phase 2B + 2C: File ops + Discord
- `tools/file_ops.py`: `search_files`, `open_file`, `list_folder` — pathlib glob, WSL path detection via `_win_home()`, folder aliases
- `tools/discord.py`: `discord_navigate` (URL scheme), `discord_voice` (atomic PowerShell focus-switch + SendKeys)
- `tests/test_file_ops.py`, `tests/test_discord.py` — 45 tests
- Discord config wired: server ID `1364137247250583572`, sex-havers channel `1364137247775129603`

### `920ef7a` — Phase 6B + 7A + 7B: Browser, per-app audio, Spotify
- `tools/browser.py`: `open_url`, `open_search`, `open_site` — Chrome-first, 30+ site aliases, job site shortcuts
- `tools/audio.py`: `list_audio_apps`, `get_app_volume`, `set_app_volume` — PowerShell inline C# WASAPI per-session control
- `tools/spotify.py`: `spotify_play`, `spotify_control`, `spotify_volume`, `spotify_current_track` — spotipy OAuth
- 52 new tests across the three modules
- `pyproject.toml`: added spotipy>=2.24.0
- `config.yaml`: Discord IDs + Spotify credentials set (enabled: true)

---

## Spotify Setup Status

**Credentials are in config.yaml and `spotify.enabled: true`.** The OAuth flow will trigger on first Spotify command. User has registered `http://127.0.0.1:8888/callback` as a second redirect URI in their Spotify developer app (primary is `shuckler://spotify-callback` for another app).

**First time a Spotify command is run:** Bobby opens Chrome to the Spotify auth URL. User approves. Token stored at `~/.bobby/spotify_cache`. All subsequent commands work silently.

---

## Architecture — New Tool Modules

| Module | Tools | Approach |
|---|---|---|
| `tools/file_ops.py` | search_files, open_file, list_folder | pathlib.glob, `_win_home()` detects Windows USERPROFILE from `cmd.exe` subprocess (lru_cache'd) |
| `tools/discord.py` | discord_navigate, discord_voice | URL scheme for navigation; PowerShell HWND save → focus → SendKeys → restore for voice controls |
| `tools/browser.py` | open_url, open_search, open_site | `cmd.exe /c start chrome "url"` (WSL); falls back to Google search for unknown sites |
| `tools/audio.py` | list_audio_apps, get_app_volume, set_app_volume | PowerShell inline C# IAudioSessionManager2 per-process audio sessions |
| `tools/spotify.py` | spotify_play, spotify_control, spotify_volume, spotify_current_track | spotipy SpotifyOAuth, searches user playlists first then catalog |

---

## Known Gaps / Next Actions

### Immediate (code-ready, quick wins)
1. **Interrupt support** ("bobby stop" mid-response) — ~2h. Keep wake word alive during TTS, kill ffplay subprocess, clear `_speaking`. See Phase 1 polish in PHASES.md.
2. **Obsidian capture re-test** — 10 min. Re-run with Obsidian open + REST API plugin active. Last test failed because Obsidian wasn't running.
3. **Verify `recall_facts` UX** — 5 min. "What do you know about me?" should return `favorite_boba_drink: Winter melon milk tea` from first session.
4. **Spotify first-run** — Run any Spotify command to trigger OAuth flow and confirm it works end-to-end.

### Phase 11B remaining (deferred)
- Auto-session-capture (end-of-session summary → daily note)
- Morning brief ("good morning Bobby" → inbox + captures summary)

### Phase 11C (manual trigger when ready)
```bash
python -c "from tools.profile import build_personality_profile; build_personality_profile(); import time; time.sleep(120)"
```
Gate: ≥10 documented opinions with note citations.

### Phase 8 — Gaming Mode Routine (next logical feature)
"Bobby, gaming mode" → open Discord, navigate to BBBBOYS server, open Riot (admin), set volume 60%, join voice channel. This is Phase 8 named routines — all the building blocks now exist.

---

## Key File Map

```
tools/
  os_control.py   — system volume, window management, open_app, press_keys
  media.py        — system_media (play/pause/next), clipboard, screenshot
  file_ops.py     — search_files, open_file, list_folder  [NEW 2026-06-04]
  discord.py      — discord_navigate, discord_voice       [NEW 2026-06-04]
  browser.py      — open_url, open_search, open_site      [NEW 2026-06-04]
  audio.py        — list_audio_apps, get/set_app_volume   [NEW 2026-06-04]
  spotify.py      — spotify_play/control/volume/track     [NEW 2026-06-04]
  memory.py       — remember_fact, recall_facts, forget_fact
  obsidian.py     — capture_to_obsidian, read_note, search_obsidian
  shortcuts.py    — open_shortcut, save_shortcut, list_shortcuts
core/
  pipeline.py     — main loop, _processing_lock, wake word → STT → brain → TTS
  brain.py        — Claude API, tool dispatch, vault_context injection
  tts.py          — ElevenLabs + pyttsx3 fallback, _strip_markdown, 35s daemon cap
  stt.py          — Whisper, transcribe_from_bytes
```

---

## Critical Invariants (do not break)

- All tools return `ToolResult(success, message, data)` — never raise from a tool handler
- `_processing_lock` is non-reentrant — never acquire inside a tool call
- `think()` is always called twice when tools are used (fix from Bug 1, 2026-06-03)
- TTS has 35s hard cap via daemon thread — Bobby always recovers from hang
- `config.yaml` is gitignored — never commit it
- Test baseline: 229 passed, 1 skipped — never regress
