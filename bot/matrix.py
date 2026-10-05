from __future__ import annotations

from datetime import date
from html import escape

from .models import Task

QUADRANT_LABELS = {
    1: "🔴 Q1 · Do first (urgent + important)",
    2: "🟡 Q2 · Schedule (important)",
    3: "🟠 Q3 · Delegate / quick win (urgent)",
    4: "⚪ Q4 · Drop or defer",
}


def auto_escalated(task: Task, today: date, escalate_days: int) -> bool:
    # not marked urgent by the user, but the deadline is close
    return (
        not task.urgent
        and task.due_date is not None
        and (task.due_date - today).days <= escalate_days
    )


def effective_urgent(task: Task, today: date, escalate_days: int) -> bool:
    return task.urgent or auto_escalated(task, today, escalate_days)


def quadrant(task: Task, today: date, escalate_days: int) -> int:
    urgent = effective_urgent(task, today, escalate_days)
    if task.important:
        return 1 if urgent else 2
    return 3 if urgent else 4


def due_label(task: Task, today: date) -> str:
    if task.due_date is None:
        return "no deadline"
    days = (task.due_date - today).days
    if days < 0:
        label = f"⚠️ overdue {-days}d"
    elif days == 0:
        label = "today"
    elif days == 1:
        label = "tomorrow"
    elif days < 7:
        label = task.due_date.strftime("%a")
    else:
        label = task.due_date.strftime("%-d %b")
    if task.due_time:
        label += f" {task.due_time.strftime('%H:%M')}"
    return label


def task_line(task: Task, today: date, escalate_days: int) -> str:
    marks = ""
    if auto_escalated(task, today, escalate_days):
        marks += " ⏫"
    if task.recurrence:
        marks += " 🔁"
    return f"<code>#{task.id}</code> {escape(task.title)} — <i>{due_label(task, today)}</i>{marks}"


def render_matrix(tasks: list[Task], today: date, escalate_days: int) -> str:
    if not tasks:
        return "Nothing on your list. Send me a task to add one."
    groups: dict[int, list[Task]] = {1: [], 2: [], 3: [], 4: []}
    for t in tasks:
        groups[quadrant(t, today, escalate_days)].append(t)
    parts = []
    for q, items in groups.items():
        if not items:
            continue
        items.sort(key=lambda t: (t.due_date is None, t.due_date or today, t.id))
        lines = "\n".join(task_line(t, today, escalate_days) for t in items)
        parts.append(f"<b>{QUADRANT_LABELS[q]}</b>\n{lines}")
    return "\n\n".join(parts)


def render_task(task: Task, today: date, escalate_days: int) -> str:
    q = quadrant(task, today, escalate_days)
    lines = [
        f"<b>{escape(task.title)}</b>  <code>#{task.id}</code>",
        f"Due: {due_label(task, today)}",
        QUADRANT_LABELS[q],
    ]
    if auto_escalated(task, today, escalate_days):
        lines.append("⏫ Auto-escalated to urgent: the deadline is close.")
    if task.recurrence:
        lines.append(f"🔁 Repeats {task.recurrence}")
    return "\n".join(lines)
