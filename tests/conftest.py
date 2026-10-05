import pytest_asyncio

from bot.models import User, init_db, make_engine, make_sessionmaker


@pytest_asyncio.fixture
async def session():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    async with make_sessionmaker(engine)() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def user(session):
    u = User(id=1, chat_id=1, timezone="Asia/Singapore")
    session.add(u)
    await session.flush()
    return u
