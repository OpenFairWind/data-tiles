# DataTiles Online Reference Server

This is the reference implementation of the DataTiles Online Delivery profile. It serves both representations of the same logical tile:

- `/api/datasets/{dataset}/tiles/{z}/{x}/{y}` - original scientific payload for client-side rendering;
- `/maps/{layer}/{z}/{x}/{y}.png|webp` - server-rendered portrayal;
- `/maps/{layer}/tilejson.json` - discovery of both representations;
- `/maps/{layer}/portrayal.json` - shared deterministic portrayal recipe.

Dimension names are query parameters on both endpoints. A published layer may fix some dimensions in `layers.json`; request parameters add or override dynamic dimensions such as `valid_time`, pressure, ensemble member, or scenario.

## High-performance execution model

The reference server is designed for demanding interactive-map workloads. Production execution uses **Gunicorn with multiple Uvicorn worker processes**, while each worker owns a **bounded rendering thread pool**. This hybrid model is deliberate:

1. multiple worker processes provide true CPU parallelism across cores;
2. the rendering pool allows each worker to overlap SQLite reads, decompression, image encoding, cache I/O, and vectorized portrayal work;
3. NumPy performs DNT1 decoding and palette interpolation without a Python per-pixel loop;
4. an in-process per-key lock coalesces simultaneous misses for the same tile;
5. cache writes are atomic, so multiple workers can safely share a persistent cache directory;
6. a bounded in-flight semaphore applies back-pressure rather than allowing unbounded render jobs to exhaust memory;
7. immutable rendered tiles carry long-lived `ETag` and `Cache-Control` headers and are suitable for CDN/reverse-proxy caching.

The important tuning relationship is:

```text
host/container CPU cores
      |
      +-- DATATILES_WORKERS          process-level CPU parallelism
      |
      +-- DATATILES_RENDER_THREADS   concurrent render/decode work per process
      |
      +-- DATATILES_MAX_INFLIGHT_RENDERS
                                      hard per-process admission limit
```

A good starting point for a dedicated 8-core container is 4 workers, 4 render threads per worker, and 8 in-flight renders per worker. Benchmark against the real dataset before increasing concurrency: image encoding, tile dimensions, compression, storage latency, cache hit ratio, and available RAM all affect the optimum.

Do not simply set every value to the CPU count. Cached responses are cheap, while first-time DNT1 portrayals are substantially more expensive.

## Native installation

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[server]'
export DATATILES_DATA_DIR=$PWD/server/data
export DATATILES_LAYERS=$PWD/server/layers.json
export DATATILES_CACHE_DIR=$PWD/server/cache
export DATATILES_WORKERS=4
export DATATILES_RENDER_THREADS=4
export DATATILES_MAX_INFLIGHT_RENDERS=8
gunicorn -c server/gunicorn.conf.py server.app:app
```

For development only, a single Uvicorn instance can still be used:

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8080
```

Copy `layers.example.json` to `layers.json` and place a DataTiles container such as `weather.datatiles` in `server/data/`.

## Docker

From repository root:

```bash
cp server/layers.example.json server/layers.json
mkdir -p server/data server/cache
cp /path/to/weather.datatiles server/data/
docker build -f server/Dockerfile -t datatiles-server .
docker run --rm -p 8080:8080 \
  --cpus=8 \
  -e DATATILES_WORKERS=4 \
  -e DATATILES_RENDER_THREADS=4 \
  -e DATATILES_MAX_INFLIGHT_RENDERS=8 \
  -v "$PWD/server/data:/data:ro" \
  -v "$PWD/server/layers.json:/config/layers.json:ro" \
  -v "$PWD/server/cache:/cache" \
  datatiles-server
```

## Docker Compose

```bash
cp server/layers.example.json server/layers.json
mkdir -p server/data server/cache
cp /path/to/weather.datatiles server/data/
cd server
docker compose up --build
```

Then open `http://localhost:8080/maps`, `http://localhost:8080/docs`, or one of the web-map examples.

The supplied `docker-compose.yml` starts with 4 worker processes, 4 rendering threads per worker, and a maximum of 8 in-flight renders per worker. Adjust these values to the CPU and memory limits assigned to the container.

For horizontal scaling, run multiple identical DataTiles server containers behind a reverse proxy or load balancer. Mount the scientific datasets read-only in every replica. A shared persistent cache is optional; an external HTTP cache/CDN is usually preferable at larger scale.

## Load testing

The supplied helper can use `hey` or ApacheBench:

```bash
URL='http://localhost:8080/maps/temperature-2m/7/67/46.webp?valid_time=2026-09-07T12:00:00Z' \
CONCURRENCY=64 REQUESTS=5000 \
./server/benchmark.sh
```

Test at least two cases separately:

- **warm cache:** measures HTTP/cache throughput;
- **cold cache:** measures DNT1 read/decode/portrayal/encode capacity.

Tune worker/thread counts from measured p50/p95/p99 latency, throughput, CPU utilization, RSS memory, and cache hit ratio rather than from a fixed formula.

## Production notes

Use immutable dataset releases where possible, mount data read-only, persist `/cache`, configure a concrete `DATATILES_PUBLIC_BASE`, and restrict `DATATILES_CORS_ORIGINS`. A CDN/reverse proxy may cache `/maps/...` aggressively because cache identity includes the layer, dimensions, portrayal, tile coordinate, and format. Dynamic aliases such as `latest` should be resolved outside the immutable cache namespace or assigned short TTLs.

For a public high-demand service, place a reverse proxy/CDN in front of the application, enable HTTP/2 or HTTP/3 there, terminate TLS at that layer, and let the proxy serve cache hits without reaching Python. The application remains responsible for canonical tile identity and deterministic rendering.

## DataTiles Store catalogue integration

The reference server can act as the visual-delivery backend for DataTiles Store. `/maps` exposes each layer's dataset id and optional `catalog` descriptor; TileJSON exposes `bounds` plus `datatiles:catalog`. The Store uses this metadata to select a server-rendered portrayal for catalogue cards and interactive map preview without opening or downloading the complete DataTiles container.

Recommended layer configuration:

```json
{
  "dataset": "weather",
  "bounds": [5.0, 35.0, 20.0, 48.0],
  "catalog": {
    "enabled": true,
    "priority": 100,
    "query": {}
  }
}
```

`catalog.query` is appended to portrayal tile requests and is useful for deterministic preview defaults such as a chosen forecast time. For protected products, do not expose a catalogue portrayal publicly unless the data rights permit it; use an authorization gateway or set `catalog.enabled` to false.
