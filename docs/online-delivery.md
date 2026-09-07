# DataTiles Online Delivery profile

The Online Delivery profile adds network publication without changing the scientific identity of a DataTiles tile. The same canonical `(z,x,y,{dimensions})` address MAY be exposed as a scientific representation for client-side portrayal and as one or more server-rendered portrayals.

## Rendering modes

**Client rendering** returns the declared DataTiles content profile unchanged (for example DNT1). The client decodes values and applies the portrayal.

**Server rendering** resolves the same scientific tile, applies a deterministic portrayal recipe, and returns a display representation such as PNG/WebP or a derived vector portrayal.

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

## Cache identity

A rendered tile cache key MUST depend on dataset release identity, layer/published-view identity, canonical dimension selection, z/x/y, canonical portrayal digest, output format, and any output parameters affecting pixels. Immutable releases SHOULD use strong ETags and long-lived immutable cache control.

## Performance and concurrency requirements

A DataTiles Online server is expected to sustain highly concurrent map workloads where a single viewport may request dozens of tiles and many users may change time, level, variable, or style simultaneously. The reference architecture therefore uses a hybrid process/thread execution model rather than a single event loop or a single rendering thread.

Implementations SHOULD provide process-level parallelism across CPU cores and MAY additionally use bounded worker threads for tile decoding, portrayal, compression, storage, and cache operations. Work queues MUST be bounded or otherwise apply back-pressure so that a burst of uncached tile requests cannot create unbounded memory growth.

Renderers SHOULD avoid per-pixel interpreter loops when vectorized, native, SIMD, GPU, or otherwise optimized implementations are available. Identical simultaneous render requests SHOULD be coalesced when practical, and cache writes MUST be atomic if multiple workers or replicas share a cache namespace.

Server-rendered portrayals SHOULD be deterministic for a fixed source tile, dimension selection, portrayal definition, format, and encoder profile so that strong cache identities and reproducible results can be used across workers and replicas.

The protocol does not mandate a specific server implementation. Multi-process, multithreaded, asynchronous, native-code, GPU-accelerated, or distributed implementations are all conformant provided the representation and semantic requirements are preserved.

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
