FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install uv && uv pip install --system -r pyproject.toml

COPY app app/
COPY alembic alembic/
COPY alembic.ini .

ENV PYTHONPATH=/app

CMD ["python", "-m", "app.main"]
