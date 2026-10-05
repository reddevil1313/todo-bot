from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from telegram.ext import Application

from . import handlers, scheduler
from .config import Config
from .models import make_engine, make_sessionmaker


def migrate(url: str) -> None:
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    cfg.attributes["url"] = url
    command.upgrade(cfg, "head")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = Config.from_env()
    migrate(config.database_url)
    engine = make_engine(config.database_url)

    app = Application.builder().token(config.bot_token).build()
    app.bot_data["config"] = config
    app.bot_data["sessionmaker"] = make_sessionmaker(engine)
    handlers.register(app)
    app.job_queue.run_repeating(scheduler.tick, interval=60, first=5)

    if config.webhook_url:
        app.run_webhook(
            listen="0.0.0.0", port=config.port, url_path=config.bot_token,
            webhook_url=f"{config.webhook_url.rstrip('/')}/{config.bot_token}",
        )
    else:
        app.run_polling()


if __name__ == "__main__":
    main()
