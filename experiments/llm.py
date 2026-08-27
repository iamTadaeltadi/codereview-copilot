"""A thin provider client that records what every call cost.

The cost accounting is not incidental. One of the paper's three claims is cost
per true finding across retrieval strategies, so every call's input and output
tokens are recorded against the condition that made it.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_TIMEOUT = 180
DEFAULT_MAX_RETRIES = 4


def load_env(path=None) -> dict:
    root = Path(__file__).resolve().parents[1]
    env_path = Path(path) if path else root / ".env"
    values = {}
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, value = stripped.partition("=")
                values[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in os.environ.items():
        if value:
            values[key] = value
    return values


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cost_usd += other.cost_usd
        self.calls += other.calls

    def as_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "calls": self.calls,
        }


@dataclass
class Completion:
    text: str
    usage: Usage
    tool_calls: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)


class LLMError(RuntimeError):
    pass


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport=None,
    ):
        if not api_key:
            raise LLMError("no API key: set OPENROUTER_API_KEY in .env")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._transport = transport

    def _post(self, path: str, payload: dict) -> dict:
        if self._transport is not None:
            return self._transport(path, payload)
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def complete(
        self,
        model: str,
        messages,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        tools=None,
        seed=None,
    ) -> Completion:
        payload = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "usage": {"include": True},
        }
        if tools:
            payload["tools"] = tools
        if seed is not None:
            payload["seed"] = seed

        last_error = None
        for attempt in range(self.max_retries):
            try:
                body = self._post("/chat/completions", payload)
                break
            except urllib.error.HTTPError as error:
                last_error = error
                if error.code in (400, 401, 403, 404):
                    raise LLMError(f"{model}: HTTP {error.code} {error.reason}") from error
                time.sleep(min(30, 2 ** attempt))
            except Exception as error:
                last_error = error
                time.sleep(min(30, 2 ** attempt))
        else:
            raise LLMError(f"{model}: giving up after {self.max_retries} attempts: {last_error}")

        if "error" in body and body["error"]:
            raise LLMError(f"{model}: {body['error']}")

        choices = body.get("choices") or []
        if not choices:
            raise LLMError(f"{model}: response contained no choices")
        message = choices[0].get("message") or {}

        raw_usage = body.get("usage") or {}
        usage = Usage(
            input_tokens=int(raw_usage.get("prompt_tokens") or 0),
            output_tokens=int(raw_usage.get("completion_tokens") or 0),
            cost_usd=float(raw_usage.get("cost") or 0.0),
            calls=1,
        )
        return Completion(
            text=message.get("content") or "",
            usage=usage,
            tool_calls=list(message.get("tool_calls") or []),
            raw=body,
        )


def client_from_env(env=None) -> OpenRouterClient:
    env = env or load_env()
    return OpenRouterClient(
        api_key=env.get("OPENROUTER_API_KEY", ""),
        base_url=env.get("OPENROUTER_API_BASE_URL") or "https://openrouter.ai/api/v1",
    )
