from __future__ import annotations

import logging

from telegram.ext import Application

from . import handlers, scheduler
from .config import Config
from .models import init_db, make_engine, make_sessionmaker


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = Config.from_env()
    engine = make_engine(config.database_url)

    async def post_init(app: Application) -> None:
        await init_db(engine)

    app = Application.builder().token(config.bot_token).post_init(post_init).build()
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
