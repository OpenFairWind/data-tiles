# DataTiles Online Delivery profile

The Online Delivery profile adds network publication without changing the scientific identity of a DataTiles tile. The same canonical `(z,x,y,{dimensions})` address MAY be exposed as a scientific representation for client-side portrayal and as one or more server-rendered portrayals.

## Rendering modes

**Client rendering** returns the declared DataTiles content profile unchanged (for example DNT1). The client decodes values and applies the portrayal.

**Server rendering** resolves the same scientific tile, applies a deterministic portrayal recipe, and returns a display representation such as PNG/WebP or a derived vector portrayal.

![OpenLayers client receiving server-derived bathymetry](images/server/openlayers-online-delivery.jpg)

*Figure 1. Executed OpenLayers client receiving XYZ WebP tiles derived by the reference server from the Gaeta-to-Maratea DNT1 bathymetry coordinate set. The surrounding blank area lies outside the declared dataset extent. The screenshot is registered with its [capture inputs and limitations](images/server/README.md).*

A service SHOULD publish both modes when feasible. Rendering mode is a delivery capability, not a dataset property; clients MAY mix modes among layers or switch mode at runtime.

## Discovery

Published map layers expose TileJSON 3.x plus namespaced fields:

- `datatiles:representations.server` - ready-to-display media types;
- `datatiles:representations.client` - scientific media types and URL template;
- `datatiles:dimensions` - fixed/default dimensions and discoverable dynamic axes;
- `datatiles:portrayal` - deterministic portrayal recipe.

## Canonical endpoints

- `GET /api/datasets/{dataset}/tiles/{z}/{x}/{y}` scientific/client representation;
- `GET /maps/{layer}/{z}/{x}/{y}.{format}` server portrayal;
- `GET /maps/{layer}/tilejson.json` discovery;
- `GET /maps/{layer}/portrayal.json` portrayal recipe.

Dimensions are query parameters and MUST use the same canonicalization semantics as the container.

The reference implementation additionally exposes:

- `GET /` service identity and rendering limits;
- `GET /healthz` process liveness and `GET /readyz` layer-configuration readiness;
- `GET /metrics` per-worker Prometheus text metrics;
- `GET /api/datasets` available container identifiers;
- `GET /maps` published-layer discovery and `GET /maps/{layer}` layer detail with the canonical portrayal digest;
- `GET /maps/{layer}/dimensions` fixed and declared dimensions;
- `GET /maps/{layer}/times` declared `valid_time` values;
- `GET /maps/{layer}/legend.json` and `legend.png` machine- and human-displayable palette legends.

These convenience resources describe the reference implementation; they do not enlarge the normative minimum endpoint set above. FastAPI also publishes generated OpenAPI and interactive documentation at `/openapi.json` and `/docs`.

## Reference layer configuration

The reference server reads a JSON object keyed by stable public layer identifier. Each layer MUST identify `dataset` and a deterministic scalar `portrayal.palette`. `formats` is an allow-list of `png` and/or `webp`; `bounds`, `minzoom`, `maxzoom`, `title`, `dataset_release`, `dimensions`, `fixed_dimensions`, `catalog`, `tileSize`, and `resampling` supply discovery or cache identity.

A compact `dimensions` value is fixed. An object-valued dimension describes an exposed query axis; `exposed: false` prevents HTTP callers from selecting it. The optional `source` object can fix coordinates too. Request values override configured fixed values only for exposed axes. Unknown query dimensions are rejected where an exposed-axis declaration exists; storage still performs exact coordinate-set resolution and never silently chooses a nearest value.

```json
{
  "temperature": {
    "dataset": "weather",
    "dataset_release": "2026-09-07T12Z",
    "title": "Air temperature",
    "dimensions": {
      "variable": "air_temperature",
      "valid_time": {
        "exposed": true,
        "values": ["2026-09-07T12:00:00Z"]
      }
    },
    "portrayal": {
      "type": "scalar",
      "unit": "degC",
      "palette": [[-20, "#313695"], [15, "#ffffbf"], [45, "#a50026"]]
    },
    "formats": ["png", "webp"],
    "minzoom": 0,
    "maxzoom": 14,
    "bounds": [5.0, 35.0, 20.0, 48.0]
  }
}
```

`dataset_release` SHOULD be an immutable release identifier. The special values `mutable`, `latest`, and null receive short-lived portrayal caching; other values receive one-year immutable caching. Operators MUST update the release identifier whenever source bytes or release semantics change.

## Cache identity

A rendered tile cache key MUST depend on dataset release identity, layer/published-view identity, canonical dimension selection, z/x/y, canonical portrayal digest, output format, and any output parameters affecting pixels. Immutable releases SHOULD use strong ETags and long-lived immutable cache control.

The reference implementation uses canonical, sorted JSON and SHA-256 for portrayal and cache identities. It writes cache objects atomically, coalesces identical misses inside each process, returns `304 Not Modified` for a matching `If-None-Match`, and uses a 300-second cache lifetime for unchanged scientific payloads. Its portrayal cache is safe to share among worker processes, although a reverse-proxy or CDN cache is preferable for larger replicated deployments.

## Performance and concurrency requirements

A DataTiles Online server is expected to sustain highly concurrent map workloads where a single viewport may request dozens of tiles and many users may change time, level, variable, or style simultaneously. The reference architecture therefore uses a hybrid process/thread execution model rather than a single event loop or a single rendering thread.

Implementations SHOULD provide process-level parallelism across CPU cores and MAY additionally use bounded worker threads for tile decoding, portrayal, compression, storage, and cache operations. Work queues MUST be bounded or otherwise apply back-pressure so that a burst of uncached tile requests cannot create unbounded memory growth.

Renderers SHOULD avoid per-pixel interpreter loops when vectorized, native, SIMD, GPU, or otherwise optimized implementations are available. Identical simultaneous render requests SHOULD be coalesced when practical, and cache writes MUST be atomic if multiple workers or replicas share a cache namespace.

Server-rendered portrayals SHOULD be deterministic for a fixed source tile, dimension selection, portrayal definition, format, and encoder profile so that strong cache identities and reproducible results can be used across workers and replicas.

The protocol does not mandate a specific server implementation. Multi-process, multithreaded, asynchronous, native-code, GPU-accelerated, or distributed implementations are all conformant provided the representation and semantic requirements are preserved.

The reference implementation runs Gunicorn/Uvicorn worker processes and a bounded rendering thread pool in each process. `DATATILES_WORKERS` controls processes, `DATATILES_RENDER_THREADS` controls render threads per process, and `DATATILES_MAX_INFLIGHT_RENDERS` controls per-process admission. A saturated worker rejects an uncached render with `503` and `Retry-After: 1`; it does not create an unbounded queue. Operators SHOULD tune these values from warm- and cold-cache latency, throughput, CPU, and memory observations.

## Scientific and portrayal limits

The scientific endpoint returns the stored payload with its declared content media type and does not portray, resample, classify, fuse, or transform it. The current server portrayal renderer accepts DNT1 scalar arrays with a two-dimensional shape, the ten integer/float dtypes supported by DNT1, `none` or `zlib` compression, and at most 16,777,216 elements. It applies the header's scale and offset, makes nodata and non-finite values transparent, interpolates configured RGBA palette stops, and encodes lossless PNG or WebP. It rejects unsupported payloads, compression, malformed headers, excess elements, palettes, and formats explicitly.

Consequently, the current reference portrayal renderer does not portray vector tiles, classify scientific values, reproject or resample arrays, or resolve partial/nearest dimension selections. Such capabilities require separately declared algorithms and provenance. Tile paths use XYZ coordinates at the HTTP boundary while stored Web Mercator rows remain TMS.

## Operations, security, and observability

Datasets SHOULD be immutable releases mounted read-only. The layer configuration and cache require separate read-only and writable mounts respectively. Public deployments SHOULD configure a concrete external `DATATILES_PUBLIC_BASE`, enumerate trusted `DATATILES_CORS_ORIGINS`, terminate TLS at a maintained proxy, restrict access to `/metrics` where operational data are sensitive, and place authorization enforcement in a gateway for protected products. CORS is not authorization.

`/healthz` proves that the process can answer; `/readyz` additionally parses the layer file but does not open every dataset or pre-render tiles. Metrics are process-local, so a multi-worker deployment requires proxy-side aggregation or a Prometheus multiprocess strategy if totals are required. The emitted counters/gauges cover requests, renders, cache hits, cache misses, render-capacity rejections, cumulative render seconds, current in-flight renders, and worker PID identity.

## Catalogue and Store discovery

An Online Delivery layer can advertise that it is suitable for lightweight catalogue browsing with the optional `catalog` object in the layer configuration. The reference server exposes this object in `/maps` and as `datatiles:catalog` in TileJSON. `bounds` is also emitted in TileJSON when configured, allowing catalogue clients to fit a preview without opening the DataTiles container.

```json
"catalog": {
  "enabled": true,
  "priority": 100,
  "query": {"valid_time": "2026-09-07T12:00:00Z"}
}
```

This mechanism is intended for server-rendered visual discovery. Scientific DNT1 delivery remains independently available to DataTiles-aware clients.
