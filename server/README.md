# DataTiles Online Reference Server

This is the reference implementation of the DataTiles Online Delivery profile. It serves both representations of the same logical tile:

- `/api/datasets/{dataset}/tiles/{z}/{x}/{y}` - original scientific payload for client-side rendering;
- `/api/netcdf/{product}/{domain}/{time}/tiles/{z}/{x}/{y}?variable={name}` - a DNT1 tile sampled directly from a configured NetCDF archive;
- `/maps/{layer}/{z}/{x}/{y}.png|webp` - server-rendered portrayal;
- `/maps/{layer}/tilejson.json` - discovery of both representations;
- `/maps/{layer}/portrayal.json` - shared deterministic portrayal recipe.

Dimension names are query parameters on both endpoints. A published layer may fix some dimensions in `layers.json`; request parameters add or override dynamic dimensions such as `valid_time`, pressure, ensemble member, or scenario.

The service reads containers without modifying them. Scientific responses preserve stored bytes and content metadata. PNG/WebP responses are explicitly derived portrayals: the server decodes DNT1, applies declared scale, offset, nodata, and palette semantics, and caches the result without writing it into the source container.

![OpenLayers Online Delivery client](../docs/images/server/openlayers-online-delivery.jpg)

*Executed reference client over the Gaeta-to-Maratea DNT1 bathymetry release. The OpenLayers map requested live XYZ WebP portrayals from this server; screenshot identity, configuration, inputs, and limitations are recorded in the [capture provenance register](../docs/images/server/README.md).*

## HTTP resources

| Resource | Purpose |
|---|---|
| `GET /` | service version, render-thread and admission limits, and principal links |
| `GET /healthz` | process liveness |
| `GET /readyz` | layer-file existence, JSON syntax, and top-level-object readiness |
| `GET /metrics` | process-local Prometheus text metrics |
| `GET /api/datasets` | sorted identifiers of `.datatiles`, `.mbtiles`, and `.sqlite` files |
| `GET /api/datasets/{dataset}/tiles/{z}/{x}/{y}` | exact stored scientific payload selected by query dimensions |
| `GET /api/netcdf` | configured product allowlists and archive frames discovered on disk |
| `GET /api/netcdf/{product}/{domain}/{time}/tiles/{z}/{x}/{y}?variable={name}` | numeric DNT1 sampled on demand from one NetCDF frame; optional `compression=none|zlib` |
| `GET /maps` | published layers, excluding the full portrayal definition |
| `GET /maps/{layer}` | complete layer configuration plus portrayal SHA-256 |
| `GET /maps/{layer}/dimensions` | declared dimensions and `fixed_dimensions` |
| `GET /maps/{layer}/times` | declared values for the `valid_time` axis |
| `GET /maps/{layer}/legend.json` | unit, palette, and portrayal SHA-256 |
| `GET /maps/{layer}/legend.png` | 256 × 24 interpolated palette strip |
| `GET /maps/{layer}/tilejson.json` | TileJSON 3.0 with both representation templates |
| `GET /maps/{layer}/portrayal.json` | deterministic portrayal recipe |
| `GET /maps/{layer}/{z}/{x}/{y}.{format}` | derived XYZ PNG/WebP portrayal |

FastAPI publishes the generated schema at `/openapi.json` and interactive documentation at `/docs`. The health probe does not validate configuration; readiness parses `layers.json` and the NetCDF product allowlist when present, but does not open every container or NetCDF frame or render test tiles.

## Direct NetCDF archive delivery

Set `DATATILES_NETCDF_ROOT` to the root of an immutable or operationally managed archive and `DATATILES_NETCDF_PRODUCTS` to a JSON product allowlist. The default locations are `/netcdf` and `/config/netcdf-products.json`; `server/netcdf-products.example.json` is a starting configuration. Each source file MUST have this exact layout:

```text
<root>/<product>/<domain>/archive/<YYYY>/<MM>/<DD>/<product>_<domain>_<YYYYMMDD>Z<hhmm>.nc
```

For example, `wrf5/d02/archive/2026/09/07/wrf5_d02_20260907Z1200.nc` is addressed as:

```text
/api/netcdf/wrf5/d02/20260907Z1200/tiles/6/34/24?variable=T2C
```

The product and variable MUST be declared in the configuration; an undeclared NetCDF variable is not served. The initial implementation accepts variables with rectilinear one-dimensional `latitude` and `longitude` dimensions and either no `time` dimension or a singleton `time` dimension. Other dimensions are rejected because selecting them implicitly would alter scientific meaning. Configure `DATATILES_NETCDF_TILE_SIZE` between 8 and 1024 (default 256).

The response is an `application/vnd.datatiles.dnt1` numeric array, never an image. Values are CF-decoded by xarray, sampled at WebMercatorQuad pixel centres with the declared nearest-neighbour algorithm, converted to `float32`, and marked nodata outside the source extent. DNT1 uses zlib by default; `compression=none` supports the dependency-free browser preview. Response headers identify `EPSG:4326` as the source CRS, `EPSG:3857` as the output grid CRS, and `nearest-neighbour-at-Web-Mercator-pixel-centres-v1` as the algorithm. This is an on-demand scientific derivation; the service does not modify the NetCDF file or create an intermediate container. Operators MUST retain source identity, checksum, licence, provenance, datum, resolution, and limitations outside this transport response and MUST NOT describe the result as navigation-authoritative.

Opening `/` in a browser returns the interactive direct-NetCDF preview. Clients requesting JSON continue to receive the machine-readable service landing resource. The preview MUST normally be opened through the running HTTP service. When the HTML asset is opened directly with `file://`, it targets `http://127.0.0.1:8080` explicitly and reports an actionable launch instruction if that loopback service is absent.

Scientific responses have a content SHA-256 ETag and a 300-second public cache lifetime. Portrayals have an identity ETag: immutable `dataset_release` values receive `public, max-age=31536000, immutable`, while `mutable`, `latest`, or null receive `public, max-age=60`. Matching `If-None-Match` requests return `304`.

## Layer configuration

`DATATILES_LAYERS` names a UTF-8 JSON object keyed by public layer id. Each entry requires a `dataset` resolvable below `DATATILES_DATA_DIR` and, for current server portrayal, a scalar palette. A complete example is supplied in `server/layers.example.json`.

| Member | Meaning |
|---|---|
| `dataset` | container basename or filename; path components are discarded defensively |
| `dataset_release` | cache identity; use a stable immutable release id, not `latest`, for immutable caching |
| `title` | TileJSON display name |
| `dimensions` | compact fixed values or object-valued exposed-axis definitions |
| `fixed_dimensions` | additional fixed coordinates |
| `source` | optional fixed source coordinates; `dataset` and `variables` are not coordinates |
| `portrayal` | deterministic recipe; current renderer requires numeric `palette` stops |
| `formats` | allowed `png` and/or `webp` output formats |
| `minzoom`, `maxzoom`, `bounds` | TileJSON discovery limits; bounds use west, south, east, north |
| `catalog` | Store catalogue eligibility, priority, and deterministic preview query |
| `tileSize`, `resampling` | declared output parameters included in cache identity |

A compact dimension such as `"variable": "air_temperature"` is fixed. To expose an axis, use an object definition such as `"valid_time": {"exposed": true, "values": [...]}`. Object-valued definitions with `exposed: false` cannot be supplied by a caller. When exposed axes are declared, unknown query dimensions produce `400`. Exact coordinate-set lookup remains authoritative: the server does not select nearest values, interpolate dimensions, or invent defaults beyond those explicitly configured.

Query keys `format`, `representation`, and `style` are reserved and are not passed as scientific dimensions. Tile paths use XYZ rows at the HTTP boundary; DataTiles retains TMS rows internally.

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

### Environment reference

| Variable | Default | Purpose |
|---|---|---|
| `DATATILES_DATA_DIR` | `/data` | read-only dataset directory |
| `DATATILES_LAYERS` | `/config/layers.json` | read-only layer configuration |
| `DATATILES_CACHE_DIR` | `/cache` | writable derived-portrayal cache |
| `DATATILES_NETCDF_ROOT` | `/netcdf` | read-only root of the product/domain/date NetCDF archive |
| `DATATILES_NETCDF_PRODUCTS` | `/config/netcdf-products.json` | read-only per-product variable allowlist; a missing file disables direct NetCDF delivery |
| `DATATILES_NETCDF_TILE_SIZE` | `256` | DNT1 tile width and height, constrained to 8–1024 pixels |
| `DATATILES_PUBLIC_BASE` | request base URL | externally visible absolute base used in TileJSON |
| `DATATILES_CORS_ORIGINS` | `*` | comma-separated exact allowed origins |
| `DATATILES_PORT` | `8080` | Gunicorn bind port |
| `DATATILES_WORKERS` | bounded CPU-count formula | Gunicorn worker processes |
| `DATATILES_RENDER_THREADS` | bounded CPU-count formula | rendering threads in each worker |
| `DATATILES_MAX_INFLIGHT_RENDERS` | twice render threads | admitted uncached renders in each worker; never below thread count |
| `DATATILES_KEEPALIVE` | `5` | Gunicorn keep-alive seconds |
| `DATATILES_REQUEST_TIMEOUT` | `60` | Gunicorn request timeout seconds |
| `DATATILES_GRACEFUL_TIMEOUT` | `30` | worker graceful-shutdown timeout seconds |
| `DATATILES_ACCESS_LOG` | `-` | Gunicorn access-log destination; `-` is standard output |

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

For direct NetCDF delivery, additionally mount the archive and allowlist read-only and set `DATATILES_NETCDF_ROOT` and `DATATILES_NETCDF_PRODUCTS` when their container paths differ from `/netcdf` and `/config/netcdf-products.json`.

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

CORS controls browser permission, not authentication. The reference server has no user, licence, agreement, payment, or entitlement enforcement. Protected datasets require an authorization gateway or private network before these routes. Restrict `/metrics` if process and workload information is sensitive. Do not expose mutable source files under immutable release identifiers: replacing bytes without changing `dataset_release` can leave semantically stale cached portrayals.

The emitted metrics are `datatiles_requests`, `datatiles_renders`, `datatiles_cache_hits`, `datatiles_cache_misses`, `datatiles_rejections`, `datatiles_render_seconds`, `datatiles_inflight`, and `datatiles_worker_info{pid=...}`. They are maintained independently in each worker process; use proxy metrics or an explicit multiprocess collector when aggregate totals are required.

## Current portrayal scope and failure behavior

The scientific endpoint can return any correctly declared stored content profile. Server portrayal currently requires DNT1 with a two-dimensional shape, a supported signed/unsigned 8/16/32/64-bit integer or 32/64-bit float dtype, explicit little/big byte order, `none` or `zlib` compression, and no more than 16,777,216 elements. Header JSON is bounded to 1 MiB and unknown header fields are rejected. The renderer applies scale and offset, makes nodata and non-finite cells transparent, linearly interpolates `#RRGGBB` or `#RRGGBBAA` palette stops, and writes PNG or lossless WebP.

It does not currently portray vectors, reproject or resample arrays, classify values, combine variables, or derive nearest dimension selections. Unsupported payloads return `415`; malformed inputs or portrayals return `422`; absent resources return `404`; disallowed formats return `406`; excess array size returns `413`; saturated render admission returns `503` with `Retry-After: 1`. New scientific derivations must declare their input variables, algorithms, parameters, CRS, and provenance before implementation.

## Verification

From the repository root, run:

```bash
python -m compileall src tests server
python -m pytest server/tests tests/test_documentation.py
```

The release workflow additionally builds and starts the image as a non-root user, checks health, readiness, and map discovery, validates browser modules, and exercises both Docker Compose models. See `docs/testing-and-release.md`.

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
