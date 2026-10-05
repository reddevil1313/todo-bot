import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from bot.config import database_url
from bot.models import Base

# main.py passes the url in, the cli falls back to DATABASE_URL
url = context.config.attributes.get("url") or database_url()


def run(connection):
    # batch mode so sqlite can alter tables too
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        await conn.run_sync(run)
    await engine.dispose()


asyncio.run(main())
