"""Parses messages like "submit report fri 5pm urgent" into a task."""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, time, timedelta

WEEKDAYS = {
    "mon": 0, "monday": 0, "tue": 1, "tues": 1, "tuesday": 1, "wed": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3, "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5, "sun": 6, "sunday": 6,
}
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
# quadrant -> (urgent, important)
QUADRANTS = {1: (True, True), 2: (False, True), 3: (True, False), 4: (False, False)}

_WD = "|".join(sorted(WEEKDAYS, key=len, reverse=True))
_MO = "|".join(sorted(MONTHS, key=len, reverse=True))
_LEAD = r"(?:\b(?:by|on|due|at|before)\s+)?"


@dataclass
class ParsedTask:
    title: str
    due_date: date | None = None
    due_time: time | None = None
    urgent: bool = False
    important: bool = False
    recurrence: str | None = None  # daily | weekly | monthly


def _take(pattern: str, text: str) -> tuple[re.Match | None, str]:
    # returns the match and the text with that bit cut out
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None, text
    return m, text[: m.start()] + " " + text[m.end():]


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _roll_forward(month: int, day: int, today: date) -> date | None:
    # no year given, so take the next time this date comes up
    d = _safe_date(today.year, month, day)
    if d and d < today:
        d = _safe_date(today.year + 1, month, day)
    return d


def add_months(d: date, months: int) -> date:
    total = d.month - 1 + months
    year, month = d.year + total // 12, total % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _parse_date(text: str, today: date) -> tuple[date | None, str]:
    m, rest = _take(_LEAD + r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if m and (d := _safe_date(int(m[1]), int(m[2]), int(m[3]))):
        return d, rest

    m, rest = _take(_LEAD + r"(?<![\d:/])(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?![\d:/])", text)
    if m:  # dd/mm
        if m[3]:
            year = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
            d = _safe_date(year, int(m[2]), int(m[1]))
        else:
            d = _roll_forward(int(m[2]), int(m[1]), today)
        if d:
            return d, rest

    m, rest = _take(_LEAD + rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MO})\b", text)
    if m and (d := _roll_forward(MONTHS[m[2].lower()], int(m[1]), today)):
        return d, rest
    m, rest = _take(_LEAD + rf"\b({_MO})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", text)
    if m and (d := _roll_forward(MONTHS[m[1].lower()], int(m[2]), today)):
        return d, rest

    m, rest = _take(_LEAD + r"\b(today|tonight|tomorrow|tmrw|tmr)\b", text)
    if m:
        return today + timedelta(days=0 if m[1].lower() in ("today", "tonight") else 1), rest

    m, rest = _take(r"\bin\s+(\d{1,3})\s+(day|week|month)s?\b", text)
    if m:
        n, unit = int(m[1]), m[2].lower()
        if unit == "month":
            return add_months(today, n), rest
        return today + timedelta(days=n * (7 if unit == "week" else 1)), rest

    m, rest = _take(_LEAD + rf"\b(?:(?:next|this)\s+)?({_WD})\b", text)
    if m:  # "mon" on a monday means next week
        ahead = (WEEKDAYS[m[1].lower()] - today.weekday()) % 7 or 7
        return today + timedelta(days=ahead), rest

    return None, text


def _parse_time(text: str) -> tuple[time | None, str]:
    m, rest = _take(_LEAD + r"\b(\d{1,2})(?::([0-5]\d))?\s*(am|pm)\b", text)
    if m and 1 <= int(m[1]) <= 12:
        hour = int(m[1]) % 12 + (12 if m[3].lower() == "pm" else 0)
        return time(hour, int(m[2] or 0)), rest
    m, rest = _take(_LEAD + r"(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])", text)
    if m:
        return time(int(m[1]), int(m[2])), rest
    return None, text


def parse_task(text: str, today: date) -> ParsedTask:
    out = ParsedTask(title="")

    m, text = _take(r"(?<!\S)q([1-4])(?!\S)", text)
    if m:
        out.urgent, out.important = QUADRANTS[int(m[1])]
    m, text = _take(r"(?<!\S)(?:!u|!urgent|urgent)(?!\S)", text)
    if m:
        out.urgent = True
    m, text = _take(r"(?<!\S)(?:!i|!important|important)(?!\S)", text)
    if m:
        out.important = True

    m, text = _take(r"\b(?:every\s*(day|week|month)|(daily|weekly|monthly))\b", text)
    if m:
        word = (m[1] or m[2]).lower()
        out.recurrence = {"day": "daily", "week": "weekly", "month": "monthly"}.get(word, word)

    out.due_time, text = _parse_time(text)
    out.due_date, text = _parse_date(text, today)
    if out.due_date is None and (out.due_time or out.recurrence):
        out.due_date = today

    title = re.sub(r"\s+", " ", text).strip(" ,.-")
    title = re.sub(r"\s+(?:by|on|due|at|before)$", "", title, flags=re.IGNORECASE)
    out.title = title[:300]
    return out
