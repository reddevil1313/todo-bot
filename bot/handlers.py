from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import time, timedelta
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import services
from .llm import llm_parse
from .matrix import render_matrix, render_task
from .models import Task
from .parser import parse_task

HELP = """<b>Just send me a task</b>, for example:
• <code>Submit report fri 5pm urgent important</code>
• <code>Pay rent 1 nov every month !i</code>
• <code>Call dentist tomorrow q2</code>

Flags: <code>urgent</code>/<code>!u</code>, <code>important</code>/<code>!i</code>, or <code>q1</code>–<code>q4</code>
Repeats: <code>daily</code>, <code>weekly</code>, <code>monthly</code>

/list – your Eisenhower matrix (tap a task to edit it)
/stats – streak and weekly progress
/settings – timezone and notification times
/timezone <code>Asia/Singapore</code>
/digest <code>08:00</code> – daily summary time
/alert <code>20:00</code> – day-before alert time
/escalate <code>2</code> – days before a deadline when a task turns urgent"""


@asynccontextmanager
async def user_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with context.bot_data["sessionmaker"]() as s:
        user = await services.get_or_create_user(
            s, update.effective_user.id, update.effective_chat.id,
            context.bot_data["config"].default_timezone,
        )
        yield s, user
        await s.commit()


def task_keyboard(task: Task) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [Btn(f"Urgent: {'on' if task.urgent else 'off'}", callback_data=f"u:{task.id}"),
         Btn(f"Important: {'on' if task.important else 'off'}", callback_data=f"i:{task.id}")],
        [Btn("✅ Done", callback_data=f"d:{task.id}"),
         Btn("⏰ +1 day", callback_data=f"p:{task.id}"),
         Btn("🗑 Delete", callback_data=f"x:{task.id}")],
        [Btn("« Back to list", callback_data="l:0")],
    ])


def list_keyboard(tasks: list[Task]) -> InlineKeyboardMarkup | None:
    rows = [[Btn(f"#{t.id} {t.title[:40]}", callback_data=f"v:{t.id}")] for t in tasks[:30]]
    return InlineKeyboardMarkup(rows) if rows else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with user_session(update, context) as (_, user):
        await update.message.reply_html(
            f"👋 I'm your to-do bot.\n\n{HELP}\n\n"
            f"Timezone is set to <b>{user.timezone}</b>. I'll send your list daily at "
            f"{user.digest_time:%H:%M} and warn you at {user.alert_time:%H:%M} the day before a deadline."
        )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(HELP)


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args) if context.args else (update.message.text or "")
    if text.startswith("/"):
        text = ""
    if not text.strip():
        await update.message.reply_html("Send the task text, e.g. <code>Submit report fri 5pm urgent</code>")
        return
    config = context.bot_data["config"]
    async with user_session(update, context) as (s, user):
        today = services.local_today(user)
        parsed = parse_task(text, today)
        if parsed.due_date is None and config.anthropic_api_key:
            parsed = await llm_parse(text, today, config.anthropic_api_key, config.llm_model) or parsed
        if not parsed.title:
            await update.message.reply_text("I couldn't find a task title in that. Try again?")
            return
        task = await services.add_task(s, user, parsed)
        await update.message.reply_html(
            "Added ✓\n" + render_task(task, today, user.escalate_days),
            reply_markup=task_keyboard(task),
        )


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with user_session(update, context) as (s, user):
        tasks = await services.open_tasks(s, user)
        await update.message.reply_html(
            render_matrix(tasks, services.local_today(user), user.escalate_days),
            reply_markup=list_keyboard(tasks),
        )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with user_session(update, context) as (s, user):
        today = services.local_today(user)
        week = await services.completed_since(s, user, today - timedelta(days=6))
        alive = user.last_completed_on and (today - user.last_completed_on).days <= 1
        await update.message.reply_html(
            f"🔥 Streak: <b>{user.streak if alive else 0}</b> days (best {user.best_streak})\n"
            f"✅ Completed in the last 7 days: <b>{week}</b>\n"
            f"📋 Open: <b>{len(await services.open_tasks(s, user))}</b>"
        )


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with user_session(update, context) as (_, user):
        await update.message.reply_html(
            f"Timezone: <b>{user.timezone}</b>  (/timezone)\n"
            f"Daily digest: <b>{user.digest_time:%H:%M}</b>  (/digest)\n"
            f"Day-before alert: <b>{user.alert_time:%H:%M}</b>  (/alert)\n"
            f"Auto-urgent within: <b>{user.escalate_days}</b> days  (/escalate)"
        )


def _setting(field: str, parse, example: str):
    # /timezone, /digest, /alert and /escalate all work the same way
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            value = parse(context.args[0])
        except (IndexError, ValueError, ZoneInfoNotFoundError):
            await update.message.reply_html(f"Usage: <code>/{update.message.text.split()[0][1:]} {example}</code>")
            return
        async with user_session(update, context) as (_, user):
            setattr(user, field, value)
        await update.message.reply_text(f"Saved: {context.args[0]}")
    return handler


def _tz(raw: str) -> str:
    ZoneInfo(raw)  # throws on a bad name
    return raw


def _days(raw: str) -> int:
    n = int(raw)
    if not 0 <= n <= 30:
        raise ValueError
    return n


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    action, _, raw_id = query.data.partition(":")
    async with user_session(update, context) as (s, user):
        today = services.local_today(user)

        async def show_list(note: str = "") -> None:
            tasks = await services.open_tasks(s, user)
            await query.edit_message_text(
                note + render_matrix(tasks, today, user.escalate_days),
                parse_mode="HTML", reply_markup=list_keyboard(tasks),
            )

        if action == "l":
            await query.answer()
            return await show_list()

        task = await services.get_task(s, user, int(raw_id))
        if task is None or task.done:
            await query.answer("That task no longer exists.")
            return await show_list()

        if action == "d":
            follow_up = await services.complete_task(s, user, task, today)
            note = f"✅ Done: {task.title}  ·  🔥 {user.streak}-day streak\n"
            if follow_up:
                note += f"🔁 Next one is due {follow_up.due_date:%a %-d %b}\n"
            await query.answer("Nice!")
            return await show_list(escape(note) + "\n")
        if action == "x":
            await s.delete(task)
            await s.flush()
            await query.answer("Deleted")
            return await show_list()

        if action == "u":
            task.urgent = not task.urgent
        elif action == "i":
            task.important = not task.important
        elif action == "p":
            services.postpone(task, today)
        await query.answer()
        await query.edit_message_text(
            render_task(task, today, user.escalate_days),
            parse_mode="HTML", reply_markup=task_keyboard(task),
        )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler(["list", "matrix", "today"], list_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("timezone", _setting("timezone", _tz, "Asia/Singapore")))
    app.add_handler(CommandHandler("digest", _setting("digest_time", time.fromisoformat, "08:00")))
    app.add_handler(CommandHandler("alert", _setting("alert_time", time.fromisoformat, "20:00")))
    app.add_handler(CommandHandler("escalate", _setting("escalate_days", _days, "2")))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add))
