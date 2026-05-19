# Current Task — Phase 11A: Obsidian Integration (Phase A)

**Status:** WSL gate PASSED ✓ — ready to implement T1–T8.

**Before starting:** Paste the Obsidian API key and vault path into `config.yaml`, then set `obsidian.enabled: true`.

**WSL networking confirmed (2026-05-19):**
```bash
curl http://172.18.144.1:27123/  # returns {"status":"OK"}
```
Use `172.18.144.1` as `api_host` — it's the WSL2 gateway, not `10.255.255.254`.
If it stops working: `ip route show default | awk '{print $3}'` gives the current gateway IP.

---

## What to Build

Full spec is in: `~/.gstack/projects/cs-keni-bobby/keni-main-design-20260519-102214.md`

Phase A adds three tools Bobby can call:
1. `capture_to_obsidian` — creates a timestamped note in Obsidian inbox
2. `read_obsidian_note` — reads a specific note by vault-relative path
3. `search_obsidian` — searches the vault by query

And the infrastructure to support them:
- Dotted-path config accessor (so `config.get("obsidian.api_key")` works)
- Notification queue (so background threads can make Bobby speak when done)
- vault_context injection into brain.py (for Phase B index — wire up now so Phase B is additive)

---

## Tasks in Order

### T1 — `core/config.py`: dotted-path accessor

Add to `get()`:
```python
def get(key: str, default: Any = None) -> Any:
    cfg = _load()
    # Support dotted paths: "obsidian.api_key" → cfg["obsidian"]["api_key"]
    if "." in key:
        parts = key.split(".")
        val = cfg
        for part in parts:
            if not isinstance(val, dict):
                return default
            val = val.get(part)
            if val is None:
                return default
        return val
    return cfg.get(key, default)
```

Add `OBSIDIAN_API_KEY` to env_overrides in `_load()`:
```python
"obsidian.api_key": "OBSIDIAN_API_KEY",
```

Note: the env_override must set `_config["obsidian"]["api_key"]` (nested), not `_config["obsidian.api_key"]` (flat). Handle this in `_load()` when processing env_overrides — dotted keys need to drill into the nested dict.

### T2 — `core/notifications.py`: notification queue

New file, ~5 lines:
```python
"""Shared notification queue for background threads → voice pipeline."""
import queue

_tts_queue: queue.Queue[str] = queue.Queue()
```

That's all. pipeline.py and tools/obsidian.py both import from here.

### T3 — `tools/obsidian.py`: three tools

See design doc for full signatures. Key constraints:
- Check `config.get("obsidian.enabled", False)` at the top of every tool function — return clear ToolResult if False
- All httpx calls: `timeout=5.0` (not 30s)
- `read_obsidian_note`: reject paths containing `../`, starting with `/`, or containing `%2e` (encoded dot) before any HTTP call
- `read_obsidian_note`: wrap returned note content with `wrap_external()` from `core.brain`
- `capture_to_obsidian`: after creating note, check if `VAULT_INDEX.md` exists before trying to append to Recent Captures — silently skip if not
- `build_vault_index` (Phase B, wire stub now): returns immediately, starts daemon thread, posts "done" to `core.notifications._tts_queue`

API base URL: `http://{config.get("obsidian.api_host")}:{config.get("obsidian.api_port", 27123)}`
Auth header: `Authorization: Bearer {config.get("obsidian.api_key")}`

If Obsidian unreachable: `ToolResult(success=False, message="Obsidian isn't running — open it and try again.", data={})`

### T4 — `core/brain.py`: vault_context param

Add `vault_context: str = ""` to `think()` signature.

When non-empty, change `system` from string to list of blocks:
```python
system_payload: str | list
if vault_context:
    system_payload = [
        {"type": "text", "text": SYSTEM_PROMPT},
        {"type": "text", "text": f"[VAULT INDEX — surface relevant notes naturally]\n{vault_context}\n[END VAULT INDEX]"},
    ]
else:
    system_payload = SYSTEM_PROMPT

response = _get_client().messages.create(
    model=model,
    max_tokens=1024,
    system=system_payload,
    ...
)
```

Also add this instruction to `SYSTEM_PROMPT`:
> "Before responding, check the vault index for notes related to this conversation. If relevant notes exist, mention them naturally — don't make it feel like a search result, make it feel like you remembered something."

### T5 — `core/pipeline.py`: wire vault_context + drain _tts_queue

**Load vault_context at start of `_run_command`:**
```python
def _load_vault_context() -> str:
    """Read VAULT_INDEX.md if it exists and obsidian is enabled. Returns "" if not."""
    if not config.get("obsidian.enabled", False):
        return ""
    index_path = config.get("obsidian.index_file", "VAULT_INDEX.md")
    vault_path = config.get("obsidian.vault_path", "")
    if not vault_path:
        return ""
    full_path = Path(vault_path) / index_path
    try:
        content = full_path.read_text(encoding="utf-8")
        max_tokens = config.get("obsidian.max_index_tokens", 3000)
        # Rough token estimate: 4 chars ≈ 1 token
        if len(content) > max_tokens * 4:
            content = content[:max_tokens * 4]
        return content
    except OSError:
        return ""
```

**Pass vault_context to BOTH think() calls in `_run_command`:**
```python
vault_context = _load_vault_context()

# First call (line ~98):
response_text, tool_calls = think(
    ...,
    vault_context=vault_context,
)

# Second call (line ~146):
response_text, _ = think(
    user_message="",
    ...,
    memory_context="",
    vault_context=vault_context,
)
```

**Drain `_tts_queue` in `run()` idle loop:**
```python
# In run() while loop, replace:
#   if not _listening.wait(timeout=0.5):
#       continue
# with:
if not _listening.wait(timeout=0.5):
    from core.notifications import _tts_queue
    while not _tts_queue.empty() and not _speaking.is_set():
        msg = _tts_queue.get_nowait()
        _speaking.set()
        try:
            speak(msg)
        finally:
            _speaking.clear()
    continue
```

### T6 — `config.yaml`: add obsidian block

```yaml
# Obsidian second brain (already in config.yaml — just fill in api_key and vault_path)
obsidian:
  enabled: true
  api_host: "172.18.144.1"              # WSL2 gateway — already correct in config.yaml
  api_port: 27123
  api_key: "your-key-here"             # strip "Bearer " prefix — just the token
  vault_path: "/mnt/c/Users/keni/..."  # fill in your actual vault WSL path
  inbox_folder: "Inbox"
  index_file: "VAULT_INDEX.md"
  max_index_tokens: 3000
```

### T7 — `tests/test_phase11.py`: unit tests

13 test paths from test plan. Use `unittest.mock.patch('httpx.post')` / `unittest.mock.patch('httpx.get')`.
Pattern: copy monkeypatch + fixture style from `tests/test_phase3.py`.

Tests to cover:
- `capture_to_obsidian`: enabled=False → no HTTP call
- `capture_to_obsidian`: happy path → note created at correct vault path
- `capture_to_obsidian`: Obsidian unreachable → ToolResult(success=False) within timeout
- `capture_to_obsidian`: index exists → appends to ## Recent Captures
- `capture_to_obsidian`: index doesn't exist → note created, no crash
- `read_obsidian_note`: happy path → content wrapped in wrap_external()
- `read_obsidian_note`: 404 → clear ToolResult error
- `read_obsidian_note`: path traversal `../` → rejected with error before HTTP
- `search_obsidian`: happy path → results list returned
- `search_obsidian`: no results → success=True, empty results
- `search_obsidian`: unreachable → ToolResult(success=False)
- `think()` with vault_context="" → system is a plain string
- `think()` with vault_context="content" → system is list of 2 blocks

### T8 — `tests/test_pipeline.py`: update think() tests

Any test that asserts `system=SYSTEM_PROMPT` (string) will need updating to allow `system` to be either a string or list depending on vault_context. Check all think() call assertions.

---

## Commit Sequence

After each task passes tests:
1. `git add <specific files>` (never `git add .`)
2. Commit with message describing what and why
3. `git push`
4. Log commit hash in `docs/ENGINEERING_LOG.md`

Don't bundle all 8 tasks into one commit — T1 and T2 are infrastructure and should ship independently. T3 depends on T1. T4 can ship independently. T5 depends on T4.

---

## Done Criteria for Phase A

- [ ] WSL curl test returns `{"status":"OK"}`
- [ ] T1–T8 implemented and tests pass
- [ ] `config.yaml` has `obsidian.enabled: true` and real API key
- [ ] Manual test: "Bobby, note that I want to look into WebRTC" → note appears in Obsidian inbox within 3s
- [ ] Manual test: "Bobby, what do I know about X?" → reads relevant note
- [ ] Used at least 3 days in a row without thinking about it
