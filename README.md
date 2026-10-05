# todo-bot

A Telegram bot for my to-do list. I kept abandoning Notion, but I'm on Telegram
all day, so the list lives there now and the bot nags me about it.

Tasks are sorted with the Eisenhower matrix (urgent / important).

```
me:   Submit report fri 5pm urgent important
bot:  Added ✓
      Submit report  #1
      Due: Fri 17:00
      🔴 Q1 · Do first (urgent + important)
```

## What it does

- Add a task by just typing it. It picks up dates (`fri`, `tomorrow`, `12 oct`,
  `25/12`, `in 3 days`), times (`5pm`, `17:00`), the quadrant (`urgent`,
  `important`, `!u`, `!i`, `q1`-`q4`) and repeats (`daily`, `weekly`, `monthly`).
- `/list` shows the matrix. Tap a task to change urgent/important, mark it done,
  push it back a day or delete it.
- Tasks become urgent on their own when the deadline is 2 days away
  (`/escalate` to change). These show up with ⏫.
- Sends the list every morning (`/digest 08:00`) and a reminder the evening
  before something is due (`/alert 20:00`). Weekly summary on Sundays.
- Repeating tasks come back after you finish them. `/stats` shows your streak.
- Works for more than one person. Everyone gets their own tasks, timezone and
  notification times.
- If `ANTHROPIC_API_KEY` is set, messages the regex parser can't find a date in
  go to an LLM instead. Without the key the bot works the same, minus that.

## How it's put together

```
bot/
  handlers.py    telegram commands and buttons
  services.py    adding/completing tasks, streaks, recurrence
  parser.py      text -> task
  llm.py         optional LLM parser
  matrix.py      quadrants and message formatting
  scheduler.py   digest, alerts, weekly review
  models.py      sqlalchemy models
```

Stack: python-telegram-bot, SQLAlchemy (async), Postgres in production and
SQLite locally.

A few things I did on purpose:

- Only `handlers.py` and `scheduler.py` touch Telegram. The rest is plain
  Python, which is why most of the tests don't need any mocking.
- Notifications run off one job that fires every minute and checks each user's
  local time. What was already sent today is saved on the user row, so
  restarting or redeploying doesn't send things twice, and if the bot was down
  at 8am the digest goes out when it comes back.
- The "auto urgent" thing is calculated when the list is shown. It never
  changes the flag you set, so pushing a deadline back un-escalates the task.
- Due dates are saved as plain dates in the user's own timezone. Makes "due
  tomorrow" easy to get right.

## Running it

Get a token from [@BotFather](https://t.me/BotFather) (`/newbot`), then:

```bash
cp .env.example .env    # put the token in BOT_TOKEN
python3 -m venv .venv && source .venv/bin/activate    # needs python 3.11+
python -m pip install -e ".[dev,llm]"
set -a && source .env && set +a
python -m bot.main
```

Or with Docker and Postgres:

```bash
docker compose up --build -d
```

## Deploying

It has to stay running for the reminders to work, so don't use a host that
sleeps idle apps. Build the Dockerfile, set `BOT_TOKEN` and `DATABASE_URL`.
It uses polling by default. Set `WEBHOOK_URL` (and `PORT`) for webhooks.

## Tests

```bash
ruff check .
pytest -q
```

GitHub Actions runs both on every push.

## Todo

- migrations (tables are just created on startup right now)
- reminder an hour before a task with a time
- edit a task's title or date
- Google Calendar sync
- voice notes
