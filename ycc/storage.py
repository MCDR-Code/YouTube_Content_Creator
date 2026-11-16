"""Where things are saved: output/week_NN/ for each week, output/channel_state.json for the channel."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from ycc.config import PROJECT_ROOT

OUTPUT = PROJECT_ROOT / "output"


def week_dir(week: int) -> Path:
    d = OUTPUT / f"week_{week:02d}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _plain(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_plain(v) for v in obj]
    return obj


def save_json(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_plain(data), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
