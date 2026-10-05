from datetime import date, time

import pytest

from bot.llm import parse_llm_json
from bot.parser import add_months, parse_task

MON = date(2026, 10, 5)  # a Monday


def test_full_sentence():
    p = parse_task("Submit report fri 5pm urgent important", MON)
    assert (p.title, p.due_date, p.due_time) == ("Submit report", date(2026, 10, 9), time(17, 0))
    assert p.urgent and p.important


@pytest.mark.parametrize("text,expected", [
    ("Call mum today", MON),
    ("Call mum tmr", date(2026, 10, 6)),
    ("Call mum by tomorrow", date(2026, 10, 6)),
    ("Call mum monday", date(2026, 10, 12)),
    ("Call mum next wed", date(2026, 10, 7)),
    ("Call mum in 3 days", date(2026, 10, 8)),
    ("Call mum in 2 weeks", date(2026, 10, 19)),
    ("Call mum 12 oct", date(2026, 10, 12)),
    ("Call mum on Oct 12th", date(2026, 10, 12)),
    ("Call mum 2026-12-25", date(2026, 12, 25)),
    ("Call mum 25/12", date(2026, 12, 25)),
    ("Call mum 1/2", date(2027, 2, 1)),  # already passed
    ("Call mum 1/2/27", date(2027, 2, 1)),
    ("Call mum", None),
])
def test_dates(text, expected):
    p = parse_task(text, MON)
    assert p.due_date == expected
    assert p.title == "Call mum"


@pytest.mark.parametrize("text,expected", [
    ("Gym 7am", time(7, 0)), ("Gym at 7:30pm", time(19, 30)),
    ("Gym 12am", time(0, 0)), ("Gym 12pm", time(12, 0)), ("Gym 18:45", time(18, 45)),
])
def test_times_default_to_today(text, expected):
    p = parse_task(text, MON)
    assert (p.title, p.due_time, p.due_date) == ("Gym", expected, MON)


@pytest.mark.parametrize("flag,urgent,important", [
    ("q1", True, True), ("q2", False, True), ("q3", True, False), ("q4", False, False),
    ("!u", True, False), ("!i", False, True), ("!u !i", True, True),
])
def test_quadrant_flags(flag, urgent, important):
    p = parse_task(f"Fix bike {flag}", MON)
    assert (p.title, p.urgent, p.important) == ("Fix bike", urgent, important)


def test_recurrence():
    p = parse_task("Pay rent 1 nov every month !i", MON)
    assert (p.title, p.due_date, p.recurrence, p.important) == ("Pay rent", date(2026, 11, 1), "monthly", True)
    assert parse_task("Stretch daily", MON).due_date == MON


def test_words_containing_keywords_are_left_alone():
    p = parse_task("Buy sunscreen and monitor", MON)
    assert (p.title, p.due_date) == ("Buy sunscreen and monitor", None)


def test_invalid_date_is_not_a_deadline():
    assert parse_task("Review 31/2 figures", MON).due_date is None


def test_add_months_clamps_day():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)


def test_llm_json_validation():
    p = parse_llm_json('Sure: {"title": "Book flights", "due_date": "2026-11-01", "due_time": null, '
                       '"urgent": false, "important": true, "recurrence": "yearly"}')
    assert (p.title, p.due_date, p.important, p.recurrence) == ("Book flights", date(2026, 11, 1), True, None)
    assert parse_llm_json("no json here") is None
    assert parse_llm_json('{"title": "x", "due_date": "not-a-date"}') is None
