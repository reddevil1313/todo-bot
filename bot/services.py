from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Task, User
from .parser import ParsedTask, add_months


def local_today(user: User) -> date:
    return datetime.now(ZoneInfo(user.timezone)).date()


async def get_or_create_user(s: AsyncSession, user_id: int, chat_id: int, default_tz: str) -> User:
    user = await s.get(User, user_id)
    if user is None:
        user = User(id=user_id, chat_id=chat_id, timezone=default_tz)
        # otherwise new users get a digest the minute they sign up
        user.last_digest_on = local_today(user)
        s.add(user)
        await s.flush()
    elif user.chat_id != chat_id:
        user.chat_id = chat_id
    return user


async def add_task(s: AsyncSession, user: User, parsed: ParsedTask) -> Task:
    task = Task(
        user_id=user.id,
        title=parsed.title,
        due_date=parsed.due_date,
        due_time=parsed.due_time,
        urgent=parsed.urgent,
        important=parsed.important,
        recurrence=parsed.recurrence,
    )
    s.add(task)
    await s.flush()
    return task


async def open_tasks(s: AsyncSession, user: User) -> list[Task]:
    rows = await s.scalars(
        select(Task).where(Task.user_id == user.id, Task.done.is_(False)).order_by(Task.id)
    )
    return list(rows)


async def get_task(s: AsyncSession, user: User, task_id: int) -> Task | None:
    task = await s.get(Task, task_id)
    return task if task and task.user_id == user.id else None


def next_due(task: Task, today: date) -> date:
    step = {
        "daily": lambda d: d + timedelta(days=1),
        "weekly": lambda d: d + timedelta(days=7),
        "monthly": lambda d: add_months(d, 1),
    }[task.recurrence]
    nxt = step(task.due_date or today)
    while nxt <= today:  # done late, skip the ones already missed
        nxt = step(nxt)
    return nxt


async def complete_task(s: AsyncSession, user: User, task: Task, today: date) -> Task | None:
    # returns the next task if this one repeats
    if task.done:
        return None
    task.done = True
    task.completed_on = today

    if user.last_completed_on != today:
        continuing = user.last_completed_on == today - timedelta(days=1)
        user.streak = user.streak + 1 if continuing else 1
        user.best_streak = max(user.best_streak, user.streak)
        user.last_completed_on = today

    if not task.recurrence:
        return None
    follow_up = Task(
        user_id=user.id, title=task.title, due_date=next_due(task, today),
        due_time=task.due_time, urgent=task.urgent, important=task.important,
        recurrence=task.recurrence,
    )
    s.add(follow_up)
    await s.flush()
    return follow_up


def postpone(task: Task, today: date, days: int = 1) -> None:
    task.due_date = max(task.due_date or today, today) + timedelta(days=days)


async def completed_since(s: AsyncSession, user: User, since: date) -> int:
    return await s.scalar(
        select(func.count()).select_from(Task).where(
            Task.user_id == user.id, Task.done.is_(True), Task.completed_on >= since
        )
    ) or 0
