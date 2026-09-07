FROM python:3.11.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 battleship

COPY pyproject.toml .
RUN pip install --no-cache-dir uv && uv pip install --system -r pyproject.toml

COPY app app/
COPY migrations migrations/
COPY migrations.ini .

ENV PYTHONPATH=/app

USER battleship

CMD ["python", "-m", "app.main"]