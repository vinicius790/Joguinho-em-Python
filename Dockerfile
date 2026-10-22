FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JOGUINHO_API_HOST=0.0.0.0 \
    JOGUINHO_API_PORT=8000 \
    JOGUINHO_DB=/data/joguinho.sqlite3

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[api]" \
    && useradd --create-home --uid 10001 joguinho \
    && mkdir /data \
    && chown joguinho:joguinho /data

USER joguinho
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["joguinho-api"]
