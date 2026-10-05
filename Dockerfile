FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY pyproject.toml .
COPY bot ./bot
RUN pip install --no-cache-dir ".[llm]"
RUN useradd --create-home app
USER app
CMD ["python", "-m", "bot.main"]
