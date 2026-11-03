"""Model providers.

Every agent talks to an `LLMProvider`, never to an SDK directly, so Claude and
OpenAI are interchangeable and tests can inject a fake provider.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Protocol

from config import Settings, get_logger, settings

log = get_logger(__name__)


class LLMError(RuntimeError):
    """An error with a message that is safe and useful to show the user."""


class LLMProvider(Protocol):
    name: str
    model: str

    def complete(self, system: str, messages: list[dict[str, str]], max_tokens: int = 1500,
                 temperature: float = 0.4) -> str: ...


def _friendly_error(provider: str, exc: Exception) -> LLMError:
    kind = type(exc).__name__
    if "Authentication" in kind or "PermissionDenied" in kind:
        return LLMError(f"{provider} rejected the API key. Check the key in your .env file.")
    if "RateLimit" in kind:
        return LLMError(f"{provider} rate limit reached. Wait a minute and try again.")
    if "NotFound" in kind:
        return LLMError(f"{provider} could not find the configured model. Check the model name in your .env file.")
    if "Connection" in kind or "Timeout" in kind:
        return LLMError(f"Could not reach {provider}. Check your internet connection and try again.")
    if "BadRequest" in kind:
        return LLMError(f"{provider} rejected the request: {getattr(exc, 'message', str(exc))[:200]}")
    return LLMError(f"{provider} returned an error ({kind}). Try again in a moment.")


def _with_retries(fn, provider: str, attempts: int = 3):
    delay = 2.0
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - SDK exception classes differ between versions
            kind = type(exc).__name__
            retryable = any(k in kind for k in ("RateLimit", "Connection", "Timeout", "InternalServer", "Overloaded"))
            if retryable and i < attempts - 1:
                log.warning("%s call failed (%s), retrying in %.0fs", provider, kind, delay)
                time.sleep(delay)
                delay *= 2
                continue
            log.error("%s call failed: %s", provider, kind)
            raise _friendly_error(provider, exc) from exc


class AnthropicProvider:
    name = "Claude"

    def __init__(self, cfg: Settings, model: str | None = None):
        import anthropic

        self.model = model or cfg.anthropic_model
        self._client = anthropic.Anthropic(api_key=cfg.anthropic_api_key, timeout=cfg.llm_timeout)

    def complete(self, system, messages, max_tokens=1500, temperature=0.4):
        def call():
            resp = self._client.messages.create(model=self.model, system=system, messages=messages,
                                                max_tokens=max_tokens, temperature=temperature)
            return "".join(getattr(b, "text", "") for b in resp.content)

        return _with_retries(call, "Claude")


class OpenAIProvider:
    name = "OpenAI"

    def __init__(self, cfg: Settings, model: str | None = None):
        import openai

        self.model = model or cfg.openai_model
        self._client = openai.OpenAI(api_key=cfg.openai_api_key, timeout=cfg.llm_timeout)

    def complete(self, system, messages, max_tokens=1500, temperature=0.4):
        def call():
            resp = self._client.chat.completions.create(
                model=self.model, max_tokens=max_tokens, temperature=temperature,
                messages=[{"role": "system", "content": system}, *messages])
            return resp.choices[0].message.content or ""

        return _with_retries(call, "OpenAI")


def available_providers(cfg: Settings = settings) -> list[str]:
    out = []
    if cfg.has_anthropic:
        out.append("anthropic")
    if cfg.has_openai:
        out.append("openai")
    return out


def get_provider(preferred: str | None = None, cfg: Settings = settings, model: str | None = None) -> LLMProvider:
    """Return the preferred provider, falling back to whichever has a key."""
    order = [preferred or cfg.default_provider, "anthropic", "openai"]
    for p in order:
        if p == "anthropic" and cfg.has_anthropic:
            return AnthropicProvider(cfg, model if preferred == "anthropic" else None)
        if p == "openai" and cfg.has_openai:
            return OpenAIProvider(cfg, model if preferred == "openai" else None)
    raise LLMError("No AI provider is configured. Add ANTHROPIC_API_KEY or OPENAI_API_KEY to your .env file, then restart the app.")


# --------------------------------------------------------------------------- JSON helper

_JSON_RULE = (
    "\n\nOUTPUT FORMAT: Respond with a single valid JSON object only. "
    "No markdown fences, no commentary before or after the JSON."
)


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        obj = json.loads(text[start:end + 1])
    if not isinstance(obj, dict):
        raise json.JSONDecodeError("Top-level JSON is not an object", text, 0)
    return obj


def complete_json(provider: LLMProvider, system: str, messages: list[dict[str, str]],
                  max_tokens: int = 2000, temperature: float = 0.3) -> dict[str, Any]:
    """Ask for JSON; if the reply does not parse, ask the model once to fix it."""
    raw = provider.complete(system + _JSON_RULE, messages, max_tokens=max_tokens, temperature=temperature)
    try:
        return extract_json(raw)
    except json.JSONDecodeError:
        log.warning("Model returned invalid JSON; asking it to repair the output")
        repair = messages + [
            {"role": "assistant", "content": raw[:6000]},
            {"role": "user", "content": "That was not valid JSON. Return the same content as one valid JSON object only."},
        ]
        raw2 = provider.complete(system + _JSON_RULE, repair, max_tokens=max_tokens, temperature=0)
        try:
            return extract_json(raw2)
        except json.JSONDecodeError as exc:
            raise LLMError("The AI returned a response the app could not read. Please try again.") from exc
