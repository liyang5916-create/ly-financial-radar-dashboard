"""Runtime helpers for AI model configuration."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9._:/@+-]{2,120}$")


def validate_model_name(value: str) -> str:
    model = (value or "").strip()
    if not model:
        raise ValueError("模型名称不能为空")
    if not MODEL_PATTERN.match(model):
        raise ValueError("模型名称只能包含字母、数字、点、下划线、横线、斜杠、冒号、@ 或 +")
    return model


def update_ai_models(fetch_model: str | None = None, analysis_model: str | None = None) -> Dict[str, str]:
    updates: Dict[str, str] = {}
    if fetch_model is not None:
        updates["FETCH_AI_MODEL"] = validate_model_name(fetch_model)
    if analysis_model is not None:
        updates["ANALYSIS_GPT_MODEL"] = validate_model_name(analysis_model)
    if not updates:
        return {}

    _update_env_file(updates)
    os.environ.update(updates)

    import config.settings as settings

    if "FETCH_AI_MODEL" in updates:
        settings.FETCH_AI_MODEL = updates["FETCH_AI_MODEL"]
    if "ANALYSIS_GPT_MODEL" in updates:
        settings.ANALYSIS_GPT_MODEL = updates["ANALYSIS_GPT_MODEL"]
        settings.ANALYSIS_AI_MODEL = updates["ANALYSIS_GPT_MODEL"]
    return updates


def _update_env_file(updates: Dict[str, str]) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8-sig").splitlines() if ENV_PATH.exists() else []
    seen = set()
    next_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            next_lines.append(line)
            continue
        key, _ = line.split("=", 1)
        key = key.strip()
        if key in updates:
            next_lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            next_lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            next_lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
