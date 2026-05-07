import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

_config: dict[str, Any] = {}


def _load() -> dict[str, Any]:
    global _config
    if _config:
        return _config

    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            "config.yaml not found. Copy config.yaml.example to config.yaml and fill in your keys."
        )

    with open(config_path) as f:
        _config = yaml.safe_load(f) or {}

    # Environment variables override config file
    env_overrides = {
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "elevenlabs_api_key": "ELEVENLABS_API_KEY",
        "porcupine_access_key": "PORCUPINE_ACCESS_KEY",
        "deepgram_api_key": "DEEPGRAM_API_KEY",
        "server_token": "BOBBY_SERVER_TOKEN",
    }
    for config_key, env_key in env_overrides.items():
        if val := os.getenv(env_key):
            _config[config_key] = val

    return _config


def get(key: str, default: Any = None) -> Any:
    return _load().get(key, default)


def require(key: str) -> Any:
    val = _load().get(key)
    if val is None:
        raise ValueError(f"Required config key '{key}' is missing from config.yaml")
    return val
