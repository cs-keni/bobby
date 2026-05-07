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

## [ ] Plugin/Skills Interface

**What:** Design a plugin interface so skills can be added without modifying Bobby's core code. Each skill is a Python file with a `register_tools() -> list[Tool]` function.

**Why:** If Bobby gets open-sourced, contributors will want to add Spotify, home automation, custom scripts, etc. Without a plugin interface, every PR touches core files and risks breaking things. With it, a new skill is a single file drop.

**When to pick up:** Phase 0 — before the tool dispatcher is built.

**How to start:**
```python
# tools/base.py
class Tool:
    name: str
    description: str
    handler: Callable
    parameters: dict  # JSON Schema

# Each skill file:
def register_tools() -> list[Tool]:
    return [Tool(name="open_spotify", ...)]

# core/brain.py discovers plugins:
tools = load_tools_from_directory("tools/skills/")
```

**Depends on:** Phase 0 project structure.

---
