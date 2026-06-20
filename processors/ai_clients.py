"""Small AI client wrappers used by crawling and analysis configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import config.settings as settings


@dataclass
class AIConfig:
    name: str
    api_key: str
    base_url: str
    model: str


class OpenAICompatibleClient:
    def __init__(self, config: AIConfig):
        self.config = config
        self.configured = bool(config.api_key)

    def masked_key(self) -> str:
        key = self.config.api_key or ""
        if not key:
            return ""
        return f"{key[:5]}...{key[-4:]}" if len(key) > 10 else "***"

    def api_url(self, path: str) -> str:
        base = self.config.base_url.rstrip("/")
        suffix = path if path.startswith("/") else f"/{path}"
        if base.endswith("/v1"):
            return base + suffix
        return base + "/v1" + suffix

    def list_models(self, timeout: int = 12) -> List[str]:
        if not self.configured:
            raise RuntimeError(f"{self.config.name} API key is not configured")

        request = Request(
            self.api_url("/models"),
            headers={"Authorization": f"Bearer {self.config.api_key}"},
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"模型列表接口返回 HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise RuntimeError(f"模型列表接口不可达: {exc.reason}") from exc

        raw_models = data.get("data", []) if isinstance(data, dict) else []
        model_ids = []
        for item in raw_models:
            if isinstance(item, dict) and item.get("id"):
                model_ids.append(str(item["id"]))
            elif isinstance(item, str):
                model_ids.append(item)
        return _filter_chat_models(model_ids)

    def chat_json(self, messages: List[Dict], temperature: float = 0.2, response_format=None) -> Dict:
        if not self.configured:
            raise RuntimeError(f"{self.config.name} API key is not configured")

        url = self.api_url("/chat/completions")
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
        )
        with urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))

        content = data["choices"][0]["message"]["content"]
        if "```json" in content:
            content = content.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in content:
            content = content.split("```", 1)[1].split("```", 1)[0]
        return json.loads(content)


def get_fetch_ai_client() -> OpenAICompatibleClient:
    return OpenAICompatibleClient(AIConfig("抓取AI", settings.FETCH_AI_API_KEY, settings.FETCH_AI_BASE_URL, settings.FETCH_AI_MODEL))


def get_analysis_gpt_client() -> OpenAICompatibleClient:
    return OpenAICompatibleClient(AIConfig("GPT分析AI", settings.ANALYSIS_GPT_API_KEY, settings.ANALYSIS_GPT_BASE_URL, settings.ANALYSIS_GPT_MODEL))


def get_analysis_ai_status() -> Dict:
    gpt = AIConfig("GPT分析AI", settings.ANALYSIS_GPT_API_KEY, settings.ANALYSIS_GPT_BASE_URL, settings.ANALYSIS_GPT_MODEL)
    claude = AIConfig("Claude分析AI", settings.ANALYSIS_CLAUDE_API_KEY, settings.ANALYSIS_CLAUDE_BASE_URL, settings.ANALYSIS_CLAUDE_MODEL)
    mode = settings.ANALYSIS_AI_MODE if settings.ANALYSIS_AI_MODE in {"gpt", "claude", "compare"} else "gpt"
    return {
        "default_mode": mode,
        "modes": [
            {"id": "gpt", "label": "GPT", "configured": bool(gpt.api_key)},
            {"id": "claude", "label": "Claude", "configured": bool(claude.api_key)},
            {"id": "compare", "label": "GPT + Claude 对比", "configured": bool(gpt.api_key and claude.api_key)},
        ],
        "providers": {
            "gpt": {
                "name": gpt.name,
                "configured": bool(gpt.api_key),
                "base_url": gpt.base_url,
                "model": gpt.model,
                "masked_key": OpenAICompatibleClient(gpt).masked_key(),
            },
            "claude": {
                "name": claude.name,
                "configured": bool(claude.api_key),
                "base_url": claude.base_url,
                "model": claude.model,
                "masked_key": OpenAICompatibleClient(claude).masked_key(),
            },
        },
    }


def get_available_ai_models() -> Dict:
    fetch_client = get_fetch_ai_client()
    analysis_client = get_analysis_gpt_client()
    cache: Dict[str, Dict] = {}

    def collect(client: OpenAICompatibleClient) -> Dict:
        cache_key = f"{client.config.base_url}|{client.masked_key()}"
        if cache_key not in cache:
            try:
                models = client.list_models()
                source = "api"
                error = ""
            except Exception as exc:
                # Fallback to known models for api.duck.cyou
                if "api.duck.cyou" in client.config.base_url:
                    models = ["gpt-5.4-mini", "gpt-5.4", "gpt-5.5"]
                else:
                    models = []
                source = "fallback"
                error = str(exc)
            current = client.config.model
            if current and current not in models:
                models.insert(0, current)
            cache[cache_key] = {
                "base_url": client.config.base_url,
                "current": current,
                "models": models,
                "source": source,
                "error": error,
            }
        return dict(cache[cache_key])

    return {
        "fetch": collect(fetch_client),
        "analysis": collect(analysis_client),
    }


def _filter_chat_models(model_ids: List[str]) -> List[str]:
    excluded = (
        "embedding",
        "embed",
        "tts",
        "stt",
        "whisper",
        "dall-e",
        "image",
        "audio",
        "moderation",
        "rerank",
        "babbage",
        "davinci",
    )
    seen = set()
    filtered = []
    for model_id in model_ids:
        value = model_id.strip()
        if not value or value in seen:
            continue
        lower = value.lower()
        if any(word in lower for word in excluded):
            continue
        filtered.append(value)
        seen.add(value)
    return sorted(filtered, key=lambda item: (not item.startswith(("gpt", "o", "claude")), item.lower()))
