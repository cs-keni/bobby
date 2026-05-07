# Bobby

Personal AI assistant — voice control, memory, and phone bridge.

Say "hey bobby" and it listens. Ask it to open apps, remember things, control your PC,
or reach it from your phone. Built in Python, powered by Claude.

## Status

🟡 Phase 0 — Project setup in progress. See [PHASES.md](PHASES.md) for the full roadmap.

## Quick Start

### Prerequisites

- Python 3.11+
- Windows (Phases 1-5 are Windows-only; Mac/Linux later)
- API keys: [Anthropic](https://console.anthropic.com), [ElevenLabs](https://elevenlabs.io), [Picovoice](https://picovoice.ai/console)

### Setup

```bash
# Clone
git clone git@github.com:cs-keni/bobby.git
cd bobby

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -e ".[dev]"

# Configure
copy config.yaml.example config.yaml
# Edit config.yaml with your API keys

# Run tests (Phase 1 safety tests)
pytest tests/

# Start Bobby
bobby
```

### Wake Word

Bobby uses [Porcupine](https://picovoice.ai) for wake word detection.

1. Sign up for a free Picovoice account
2. Get your access key and add it to `config.yaml`
3. Generate a custom "hey bobby" wake word at picovoice.io/console → download the `.ppn` file
4. Set `wake_word_path` in `config.yaml` to the `.ppn` file path

Until you have a custom wake word, Bobby defaults to "porcupine" as a placeholder.

### Phone Bridge (Phase 4)

Before setting up the phone bridge, validate Wake-on-LAN support:
1. Enable "Wake on LAN" in BIOS/UEFI settings
2. Enable "Wake on Magic Packet" in Device Manager → Network Adapters → your NIC → Power Management
3. Test with a WoL tool from another device on your network

## Architecture

```
Wake Word (Porcupine) → STT (Whisper) → Claude Brain → TTS (ElevenLabs)
                                              ↓
                                      Tool Dispatcher
                                      ↙    ↓    ↘
                                  OS    Memory  Browser
                                              ↕
                                       FastAPI Server
                                              ↕
                                       React PWA (phone)
```

See [PHASES.md](PHASES.md) for the full build plan and [TODOS.md](TODOS.md) for deferred work.

## Tech Stack

| Layer | Technology |
|---|---|
| Wake word | Porcupine (Picovoice) |
| STT | Whisper (local) |
| LLM | Claude Haiku / Sonnet (Anthropic) |
| TTS | ElevenLabs (streaming) |
| OS control | pywinauto + subprocess + win32api |
| Memory | SQLite + ChromaDB |
| Server | FastAPI + WebSockets |
| Screen stream | MJPEG via FastAPI |
| Tunnel | Cloudflare Tunnel |
| Phone app | React PWA |
