"""Application configuration, loaded from environment variables (.env supported).

Secrets are only ever read from the environment. They are never written to the
database, logs, or the UI.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional at runtime
    pass

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    openai_api_key: str
    default_provider: str
    anthropic_model: str
    openai_model: str
    stt_model: str
    tts_model: str
    database_url: str
    log_level: str
    max_answer_chars: int
    llm_timeout: int

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def any_llm(self) -> bool:
        return self.has_anthropic or self.has_openai


def load_settings() -> Settings:
    return Settings(
        anthropic_api_key=_env("ANTHROPIC_API_KEY"),
        openai_api_key=_env("OPENAI_API_KEY"),
        default_provider=_env("DEFAULT_PROVIDER", "anthropic").lower(),
        anthropic_model=_env("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        openai_model=_env("OPENAI_MODEL", "gpt-4o-mini"),
        stt_model=_env("OPENAI_STT_MODEL", "whisper-1"),
        tts_model=_env("OPENAI_TTS_MODEL", "tts-1"),
        database_url=_env("DATABASE_URL", f"sqlite:///{DATA_DIR / 'mentor.db'}"),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
        max_answer_chars=int(_env("MAX_ANSWER_CHARS", "6000")),
        llm_timeout=int(_env("LLM_TIMEOUT_SECONDS", "90")),
    )


base_settings = load_settings()

# Keys a visitor types into the app live only in their Streamlit session (never the DB or disk).
SESSION_KEYS = "api_keys"
_KNOWN_SECRETS: set[str] = set()


def _session_keys() -> dict[str, str]:
    """API keys entered in this browser session, if we are inside a Streamlit script run."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        if get_script_run_ctx(suppress_warning=True) is None:
            return {}
        import streamlit as st

        return dict(st.session_state.get(SESSION_KEYS) or {})
    except Exception:  # noqa: BLE001 - outside Streamlit (API, tests, threads)
        return {}


def remember_secret(value: str) -> None:
    """Register a key so the log filter redacts it even from background threads."""
    if value:
        _KNOWN_SECRETS.add(value)


def current_settings() -> Settings:
    """Server settings with any keys the visitor entered in this session layered on top."""
    keys = _session_keys()
    if not keys:
        return base_settings
    return replace(base_settings,
                   anthropic_api_key=keys.get("anthropic") or base_settings.anthropic_api_key,
                   openai_api_key=keys.get("openai") or base_settings.openai_api_key)


def key_source(provider: str) -> str:
    """'session', 'server' or '' for where a provider's key comes from."""
    if _session_keys().get(provider):
        return "session"
    return "server" if getattr(base_settings, f"{provider}_api_key") else ""


class _SettingsProxy:
    """`settings.x` always reads the current session's view, so existing imports keep working."""

    def __getattr__(self, name: str):
        return getattr(current_settings(), name)


settings = _SettingsProxy()


def resolve(cfg) -> Settings:
    """Freeze the proxy into a concrete Settings (safe to hand to worker threads)."""
    return current_settings() if isinstance(cfg, _SettingsProxy) else cfg


class _SecretFilter(logging.Filter):
    """Redacts API keys if they ever end up in a log message."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage())
        for secret in (base_settings.anthropic_api_key, base_settings.openai_api_key, *_KNOWN_SECRETS):
            if secret and secret in msg:
                record.msg = msg.replace(secret, "***")
                record.args = ()
        return True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handler.addFilter(_SecretFilter())
        logger.addHandler(handler)
        logger.setLevel(base_settings.log_level)
        logger.propagate = False
    return logger
