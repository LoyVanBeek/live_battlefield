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

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 CMD ["python", "-c", "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/' % os.getenv('PORT', '8000'), timeout=4).status == 200 else 1)"]

CMD ["python", "-m", "app.main"]