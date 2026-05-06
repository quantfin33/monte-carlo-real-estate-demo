from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PRESET_DIR = Path(__file__).resolve().parent / "demo_presets"
REQUIRED_PRESET_KEYS = {"name", "label", "description", "params"}


def list_presets() -> list[str]:
    return sorted(path.stem for path in PRESET_DIR.glob("*.json"))


def load_preset(name: str) -> dict[str, Any]:
    safe_name = name.strip().lower().replace("_", "-")
    path = PRESET_DIR / f"{safe_name}.json"
    if not path.exists():
        available = ", ".join(list_presets())
        raise ValueError(f"Unknown preset '{name}'. Available presets: {available}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_PRESET_KEYS - set(payload)
    if missing:
        raise ValueError(f"Preset '{name}' is missing required keys: {sorted(missing)}")
    if not isinstance(payload["params"], dict):
        raise ValueError(f"Preset '{name}' params must be an object")
    return payload


def load_preset_params(name: str) -> dict[str, Any]:
    return dict(load_preset(name)["params"])

