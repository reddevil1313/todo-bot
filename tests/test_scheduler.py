from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from bot import scheduler, services
from bot.models import Task, make_sessionmaker
from bot.parser import ParsedTask
from bot.scheduler import ALERT, DIGEST, REVIEW, build_message, due_notifications, due_soon, mark_sent

SGT = ZoneInfo("Asia/Singapore")
MON = date(2026, 10, 5)


def at(day, hh, mm=0):
    return datetime.combine(day, time(hh, mm), SGT)


def test_digest_fires_once_per_day(user):
    assert due_notifications(user, at(MON, 7, 59)) == []
    assert due_notifications(user, at(MON, 8, 0)) == [DIGEST]
    mark_sent(user, DIGEST, MON)
    assert due_notifications(user, at(MON, 12)) == []
    assert due_notifications(user, at(MON + timedelta(days=1), 8, 1)) == [DIGEST]


def test_catches_up_after_downtime(user):
    # bot was down all day
    assert due_notifications(user, at(MON, 21)) == [DIGEST, ALERT]


def test_weekly_review_only_on_sunday(user):
    sunday = MON + timedelta(days=6)
    assert REVIEW not in due_notifications(user, at(MON, 21))
    assert REVIEW in due_notifications(user, at(sunday, 20))
    assert REVIEW not in due_notifications(user, at(sunday, 19))


async def test_alert_lists_only_tasks_due_tomorrow(session, user):
    assert await build_message(session, user, ALERT, MON) is None
    await services.add_task(session, user, ParsedTask("Tomorrow thing", due_date=MON + timedelta(days=1)))
    await services.add_task(session, user, ParsedTask("Later thing", due_date=MON + timedelta(days=4)))
    text = await build_message(session, user, ALERT, MON)
    assert "Tomorrow thing" in text and "Later thing" not in text


async def test_digest_flags_overdue(session, user):
    await services.add_task(session, user, ParsedTask("Old", due_date=MON - timedelta(days=2), important=True))
    text = await build_message(session, user, DIGEST, MON)
    assert "1 overdue" in text and "Q1" in text and "Old" in text


async def test_tick_sends_and_does_not_repeat(session, user, monkeypatch):
    await services.add_task(session, user, ParsedTask("Thing", due_date=MON + timedelta(days=1)))
    user.digest_time, user.alert_time = time(0, 0), time(0, 0)
    await session.commit()
    bot = SimpleNamespace(send_message=AsyncMock())
    ctx = SimpleNamespace(bot=bot, bot_data={"sessionmaker": make_sessionmaker(session.bind)})
    await scheduler.tick(ctx)
    first = bot.send_message.await_count
    assert first >= 1
    await scheduler.tick(ctx)
    assert bot.send_message.await_count == first


def test_reminder_an_hour_before():
    t = Task(title="call", due_date=MON, due_time=time(17, 0))
    assert due_soon([t], at(MON, 15, 59)) == []
    assert due_soon([t], at(MON, 16, 0)) == [t]
    assert due_soon([t], at(MON, 17, 0)) == []  # too late
    assert due_soon([Task(title="no time", due_date=MON)], at(MON, 16, 30)) == []


def test_reminder_only_once_unless_rescheduled():
    t = Task(title="call", due_date=MON, due_time=time(17, 0))
    t.reminded_for = datetime.combine(MON, time(17, 0))
    assert due_soon([t], at(MON, 16, 30)) == []
    t.due_time = time(17, 15)
    assert due_soon([t], at(MON, 16, 30)) == [t]


async def test_tick_sends_reminder_once(session, user):
    now = datetime.now(SGT)
    due = now + timedelta(minutes=30)
    await services.add_task(session, user, ParsedTask("Soon", due_date=due.date(), due_time=due.time()))
    user.last_digest_on = user.last_alert_on = user.last_review_on = now.date()
    await session.commit()
    bot = SimpleNamespace(send_message=AsyncMock())
    ctx = SimpleNamespace(bot=bot, bot_data={"sessionmaker": make_sessionmaker(session.bind)})
    await scheduler.tick(ctx)
    await scheduler.tick(ctx)
    assert bot.send_message.await_count == 1
    assert "Soon" in bot.send_message.await_args[0][1]
