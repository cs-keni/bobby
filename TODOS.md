# Bobby — TODOS

Deferred work captured during plan-eng-review. Pick these up when the time is right.

---

## [!] MANUAL PREREQUISITE — WoL BIOS Validation (before Phase 4)

**Must do this yourself before Phase 4 (phone bridge).** Bobby cannot check this for you.

1. **BIOS:** Reboot → enter BIOS/UEFI → find "Wake on LAN" or "Power On by PCI-E" → enable it
2. **Windows NIC:** Device Manager → Network Adapters → your Ethernet NIC → Properties → Power Management → check "Allow this device to wake the computer" and "Only allow a magic packet to wake the computer"
3. **Test it:** From another device on the same network, use a WoL tool (e.g., [WakeMeOnLan](https://www.nirsoft.net/utils/wake_on_lan.html)) with your PC's MAC address. If it wakes up, you're good.

**Note on NordVPN + apartment ethernet:** Cloudflare Tunnel works fine on any network — it's outbound-only, no port forwarding or router config needed. WoL works on local network (same apartment subnet). Remote WoL (from phone outside the network) requires a device that stays on to relay the magic packet — a Raspberry Pi or similar is the easiest solution for this. This is a Phase 4 concern, not Phase 0.

---

## [x] Plugin/Skills Interface — RESOLVED

The `@register_tool` decorator in `tools/registry.py` satisfies this requirement. Drop a new `.py` file in `tools/` with `@register_tool`-decorated functions; `get_tools()` auto-discovers it via `pkgutil.iter_modules`. No core changes needed.

---

## [ ] Model Routing — Refine Heuristic (Phase 10)

**What:** The `complex_triggers` keyword list in `pipeline.py` is too broad — common words like "find" and "help" push simple tool calls to Claude Sonnet instead of Haiku, burning ~4x tokens unnecessarily.

**Why:** "Find chrome" or "help me open discord" are trivially simple tool dispatches. They don't need Sonnet's reasoning. The current list was written before real usage data existed.

**When to pick up:** Phase 10 (polish). After real daily-driver usage, look at the logs and find which commands are being escalated unnecessarily. Tune the list based on actual data, not guesses.

**How to start:** Add logging of which model was used per command, then grep the logs after a week of use. Alternatively, test whether Haiku can handle all Phase 2 commands reliably — if so, remove `complex_triggers` entirely and only escalate explicitly (e.g., "bobby, think hard about...").

**Depends on:** Sufficient usage history from Phase 2+.

---

## [ ] Speech-Start Timeout UX — "I didn't catch that" (Phase 1 polish)

**What:** `record_until_silence` now has a 3-second speech-start timeout (`SPEECH_START_TIMEOUT`). When the mic doesn't pick up audio in 3s, Bobby speaks "I didn't catch that." and resets.

**Status:** Implemented in `core/stt.py` and `core/pipeline.py`. The feedback is minimal — just the spoken phrase.

**When to pick up:** Phase 1 polish, alongside audio chimes. Could be improved with a subtle audio cue instead of a spoken phrase, or by distinguishing "mic failure" from "you were too quiet" with different messages.

**Depends on:** Audio chime implementation (same Polish pass).

---

## [ ] Manual Testing Checklist

Things automated tests cannot cover — must be verified on real hardware.

1. **Volume control (pycaw on Windows)** — run Bobby in native Windows Python (not WSL), say "set volume to 30" and "get volume", verify Windows audio changes
2. **End-to-end voice loop** — say "hey jarvis" (wake word), speak "open notepad", verify Notepad opens and Bobby confirms
3. **"The usual" shortcut** — say "open the usual", verify Chrome, Discord, and Spotify all launch
4. **system_power confirmation gate** — say "restart my PC", say "no" when prompted, verify PC does NOT restart
5. **Memory persistence across sessions** — say "remember that my name is [name]", restart Bobby (`Ctrl+C` then re-run), say "what's my name?" — verify Bobby recalls it from DB
6. **Screenshot** — say "take a screenshot", verify `~/Pictures/Bobby/` contains the PNG
7. **Media keys** — say "pause music" while Spotify is playing, verify it pauses
