FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY . /app
RUN python -m pip install --upgrade pip \
    && python -m pip install ".[prod]" \
    && groupadd --system --gid 10001 datatiles \
    && useradd --system --uid 10001 --gid datatiles --home-dir /app datatiles \
    && mkdir -p /data/catalog /data/state /data/branding \
    && chown -R datatiles:datatiles /data

USER datatiles
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).read()"]
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--access-logfile", "-", "--error-logfile", "-", "datatiles_store:create_app()"]
