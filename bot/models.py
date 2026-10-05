from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram user id
    chat_id: Mapped[int] = mapped_column(BigInteger)
    timezone: Mapped[str] = mapped_column(String(64))
    digest_time: Mapped[time] = mapped_column(default=time(8, 0))
    alert_time: Mapped[time] = mapped_column(default=time(20, 0))
    # tasks due within this many days count as urgent
    escalate_days: Mapped[int] = mapped_column(default=2)

    streak: Mapped[int] = mapped_column(default=0)
    best_streak: Mapped[int] = mapped_column(default=0)
    last_completed_on: Mapped[date | None] = mapped_column(default=None)

    # when each notification last went out (user local date)
    last_digest_on: Mapped[date | None] = mapped_column(default=None)
    last_alert_on: Mapped[date | None] = mapped_column(default=None)
    last_review_on: Mapped[date | None] = mapped_column(default=None)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    # in the user's local time
    due_date: Mapped[date | None] = mapped_column(default=None)
    due_time: Mapped[time | None] = mapped_column(default=None)
    urgent: Mapped[bool] = mapped_column(default=False)
    important: Mapped[bool] = mapped_column(default=False)
    recurrence: Mapped[str | None] = mapped_column(String(16), default=None)
    done: Mapped[bool] = mapped_column(default=False, index=True)
    completed_on: Mapped[date | None] = mapped_column(default=None)
    # the due datetime we already sent a reminder for
    reminded_for: Mapped[datetime | None] = mapped_column(default=None)


def make_engine(url: str) -> AsyncEngine:
    return create_async_engine(url)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
