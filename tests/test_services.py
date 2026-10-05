from datetime import date, timedelta

from bot import services
from bot.matrix import quadrant, render_matrix
from bot.models import Task, User
from bot.parser import ParsedTask

TODAY = date(2026, 10, 5)


async def add(session, user, title="T", **kw):
    return await services.add_task(session, user, ParsedTask(title=title, **kw))


def test_quadrants_and_auto_escalation():
    far, near = TODAY + timedelta(days=10), TODAY + timedelta(days=2)
    assert quadrant(Task(title="a", urgent=True, important=True), TODAY, 2) == 1
    assert quadrant(Task(title="a", urgent=False, important=True, due_date=far), TODAY, 2) == 2
    assert quadrant(Task(title="a", urgent=False, important=True, due_date=near), TODAY, 2) == 1
    assert quadrant(Task(title="a", urgent=False, important=False, due_date=near), TODAY, 2) == 3
    assert quadrant(Task(title="a", urgent=False, important=False), TODAY, 2) == 4


async def test_matrix_render_escapes_html(session, user):
    await add(session, user, "<b>x</b> & y", important=True)
    text = render_matrix(await services.open_tasks(session, user), TODAY, 2)
    assert "&lt;b&gt;x&lt;/b&gt; &amp; y" in text and "Q2" in text


async def test_streak_counts_days_not_tasks(session, user):
    a, b, c, d = [await add(session, user) for _ in range(4)]
    await services.complete_task(session, user, a, TODAY)
    await services.complete_task(session, user, b, TODAY)
    assert user.streak == 1
    await services.complete_task(session, user, c, TODAY + timedelta(days=1))
    assert user.streak == 2
    await services.complete_task(session, user, d, TODAY + timedelta(days=5))
    assert (user.streak, user.best_streak) == (1, 2)


async def test_recurring_task_spawns_next(session, user):
    t = await add(session, user, "Rent", due_date=date(2026, 1, 31), recurrence="monthly", important=True)
    nxt = await services.complete_task(session, user, t, date(2026, 1, 31))
    assert (nxt.due_date, nxt.important, nxt.recurrence) == (date(2026, 2, 28), True, "monthly")
    # done 3 weeks late
    w = await add(session, user, "Review", due_date=TODAY - timedelta(days=20), recurrence="weekly")
    assert (await services.complete_task(session, user, w, TODAY)).due_date == TODAY + timedelta(days=1)
    assert [t.title for t in await services.open_tasks(session, user)] == ["Rent", "Review"]


async def test_completing_twice_is_a_noop(session, user):
    t = await add(session, user, recurrence="daily", due_date=TODAY)
    await services.complete_task(session, user, t, TODAY)
    assert await services.complete_task(session, user, t, TODAY) is None
    assert len(await services.open_tasks(session, user)) == 1


async def test_users_cannot_see_each_others_tasks(session, user):
    other = User(id=2, chat_id=2, timezone="UTC")
    session.add(other)
    t = await add(session, user)
    assert await services.get_task(session, other, t.id) is None
    assert await services.open_tasks(session, other) == []


async def test_postpone_and_weekly_count(session, user):
    t = await add(session, user, due_date=TODAY - timedelta(days=3))
    services.postpone(t, TODAY)
    assert t.due_date == TODAY + timedelta(days=1)  # counted from today, not the old date
    await services.complete_task(session, user, t, TODAY)
    assert await services.completed_since(session, user, TODAY - timedelta(days=6)) == 1
    assert await services.completed_since(session, user, TODAY + timedelta(days=1)) == 0


async def test_new_user_gets_defaults(session):
    u = await services.get_or_create_user(session, 99, 99, "Asia/Singapore")
    assert u.timezone == "Asia/Singapore" and u.last_digest_on is not None
    assert (await services.get_or_create_user(session, 99, 100, "UTC")).chat_id == 100
