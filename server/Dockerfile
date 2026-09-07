FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE MANIFEST.in /app/
COPY src /app/src
COPY server /app/server
RUN pip install --no-cache-dir '.[server]'
RUN groupadd --system datatiles && useradd --system --gid datatiles --home-dir /app datatiles \
    && mkdir -p /data /cache /config && chown -R datatiles:datatiles /cache
ENV DATATILES_DATA_DIR=/data \
    DATATILES_LAYERS=/config/layers.json \
    DATATILES_CACHE_DIR=/cache \
    DATATILES_PORT=8080 \
    DATATILES_WORKERS=4 \
    DATATILES_RENDER_THREADS=4 \
    DATATILES_MAX_INFLIGHT_RENDERS=8
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)" || exit 1
USER datatiles
CMD ["gunicorn","-c","/app/server/gunicorn.conf.py","server.app:app"]
