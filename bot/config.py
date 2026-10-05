from __future__ import annotations

import os
from dataclasses import dataclass


def _normalise_db_url(url: str) -> str:
    # hosted postgres gives postgres:// urls, sqlalchemy wants the driver in there
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


@dataclass(frozen=True)
class Config:
    bot_token: str
    database_url: str
    default_timezone: str
    webhook_url: str | None  # uses polling if not set
    port: int
    anthropic_api_key: str | None
    llm_model: str

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            bot_token=os.environ["BOT_TOKEN"],
            database_url=_normalise_db_url(
                os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///todo.db")
            ),
            default_timezone=os.environ.get("DEFAULT_TZ", "Asia/Singapore"),
            webhook_url=os.environ.get("WEBHOOK_URL") or None,
            port=int(os.environ.get("PORT", "8080")),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
            llm_model=os.environ.get("LLM_MODEL", "claude-haiku-4-5"),
        )
