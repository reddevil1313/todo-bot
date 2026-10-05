"""LLM fallback for messages the regex parser can't find a date in.

Only runs if ANTHROPIC_API_KEY is set. Returns None on any error.
"""
from __future__ import annotations

import json
import logging
from datetime import date, time

from .parser import ParsedTask

log = logging.getLogger(__name__)

PROMPT = """Extract a to-do task from the user's message. Today is {today} ({weekday}).
Reply with ONLY a JSON object with these keys:
  "title": short imperative task title
  "due_date": "YYYY-MM-DD" or null
  "due_time": "HH:MM" (24h) or null
  "urgent": boolean (Eisenhower: is it time-sensitive?)
  "important": boolean (Eisenhower: does it matter for the user's goals?)
  "recurrence": "daily" | "weekly" | "monthly" | null

Message: {text}"""


def parse_llm_json(raw: str) -> ParsedTask | None:
    try:
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        title = str(data["title"]).strip()[:300]
        if not title:
            return None
        recurrence = data.get("recurrence")
        return ParsedTask(
            title=title,
            due_date=date.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            due_time=time.fromisoformat(data["due_time"]) if data.get("due_time") else None,
            urgent=bool(data.get("urgent")),
            important=bool(data.get("important")),
            recurrence=recurrence if recurrence in ("daily", "weekly", "monthly") else None,
        )
    except (ValueError, KeyError, TypeError):
        return None


async def llm_parse(text: str, today: date, api_key: str, model: str) -> ParsedTask | None:
    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=api_key, timeout=10)
        resp = await client.messages.create(
            model=model,
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": PROMPT.format(today=today.isoformat(), weekday=today.strftime("%A"), text=text),
            }],
        )
        return parse_llm_json(resp.content[0].text)
    except Exception:  # whatever went wrong, just use the regex result
        log.exception("LLM parse failed; falling back to rule-based result")
        return None
