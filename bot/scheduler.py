"""Daily digest, day-before alerts and the weekly review.

One job runs every minute and checks each user's local time. What has already
been sent today is stored on the user row, so a restart doesn't double-send.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.error import Forbidden, TelegramError
from telegram.ext import ContextTypes

from . import services
from .matrix import render_matrix, task_line
from .models import User

log = logging.getLogger(__name__)

DIGEST, ALERT, REVIEW = "digest", "alert", "review"
REVIEW_WEEKDAY = 6  # sunday


def due_notifications(user: User, now_local: datetime) -> list[str]:
    today, clock = now_local.date(), now_local.time()
    kinds = []
    if clock >= user.digest_time and user.last_digest_on != today:
        kinds.append(DIGEST)
    if clock >= user.alert_time and user.last_alert_on != today:
        kinds.append(ALERT)
    if (today.weekday() == REVIEW_WEEKDAY and clock >= user.alert_time
            and user.last_review_on != today):
        kinds.append(REVIEW)
    return kinds


def mark_sent(user: User, kind: str, today: date) -> None:
    setattr(user, f"last_{kind}_on", today)


async def build_message(s: AsyncSession, user: User, kind: str, today: date) -> str | None:
    tasks = await services.open_tasks(s, user)
    if kind == DIGEST:
        header = f"☀️ <b>Your tasks for {today.strftime('%a %-d %b')}</b>"
        if user.streak and user.last_completed_on and (today - user.last_completed_on).days <= 1:
            header += f"  ·  🔥 {user.streak}-day streak"
        overdue = sum(1 for t in tasks if t.due_date and t.due_date < today)
        if overdue:
            header += f"\n⚠️ {overdue} overdue"
        return f"{header}\n\n{render_matrix(tasks, today, user.escalate_days)}"
    if kind == ALERT:
        tomorrow = today + timedelta(days=1)
        due = [t for t in tasks if t.due_date == tomorrow]
        if not due:
            return None
        lines = "\n".join(task_line(t, today, user.escalate_days) for t in due)
        return f"⏰ <b>Due tomorrow</b>\n{lines}"
    if kind == REVIEW:
        done = await services.completed_since(s, user, today - timedelta(days=6))
        return (
            f"📊 <b>Weekly review</b>\nCompleted this week: {done}\n"
            f"Still open: {len(tasks)}\nBest streak: {user.best_streak} days"
        )
    return None


async def tick(context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now(UTC)
    async with context.bot_data["sessionmaker"]() as s:
        for user in (await s.scalars(select(User))).all():
            now_local = now.astimezone(ZoneInfo(user.timezone))
            for kind in due_notifications(user, now_local):
                text = await build_message(s, user, kind, now_local.date())
                mark_sent(user, kind, now_local.date())
                if not text:
                    continue
                try:
                    await context.bot.send_message(user.chat_id, text, parse_mode="HTML")
                except Forbidden:
                    log.info("user %s blocked the bot", user.id)
                except TelegramError:
                    log.exception("failed to send %s to %s", kind, user.id)
            await s.commit()
