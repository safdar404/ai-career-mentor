"""Application configuration, loaded from environment variables (.env supported).

Secrets are only ever read from the environment. They are never written to the
database, logs, or the UI.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
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


settings = load_settings()


class _SecretFilter(logging.Filter):
    """Redacts API keys if they ever end up in a log message."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage())
        for secret in (settings.anthropic_api_key, settings.openai_api_key):
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
        logger.setLevel(settings.log_level)
        logger.propagate = False
    return logger
