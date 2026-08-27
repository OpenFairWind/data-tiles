# Lesson 4 — Querying and deriving live products

## Objectives

You will expose a DataTiles container through its read-only HTTP service, distinguish exact tile retrieval from derived analysis, inspect content negotiation, and evaluate the scientific assumptions behind profiles, surfaces, and contours.

## Theory: retrieval is not analysis

Exact retrieval maps a complete address to stored bytes. It is deterministic and does not change support, resolution, or meaning. A point query over a matrix is different: it converts longitude and latitude to a tile and pixel, then applies nodata, scale, and offset. A transect samples many points along a geodesic. Contouring applies marching squares to a sampled grid. A surface endpoint resamples coincident variables to a bounded client grid.

These derived operations must identify their inputs and parameters. Otherwise a chart can be mistaken for original evidence. DataTiles responses therefore state their data source and include deterministic digests where ordering is defined. The profile response reports source tile and pixel for each sample.

Interpolation is deliberately constrained. The reference point sampler uses the containing cell; it does not claim bilinear, temporal, or vertical interpolation. A scientifically stronger service may implement them, but it must define support, nodata propagation, categorical handling, uncertainty, and edge behavior. Interpolating seabed classes numerically would be meaningless because class codes are labels, not quantities.

The HTTP resource structure follows OGC API building blocks: landing page, conformance declaration, OpenAPI document, collections, tile sets, and tiles. This alignment improves discoverability but is not an OGC certification claim. DataTiles dimensions remain query parameters, and tile rows in URLs use XYZ orientation before conversion at the database boundary.

## Laboratory

Start the read-only service:

```bash
datatiles-serve tutorial.datatiles --host 127.0.0.1 --port 8080
```

In another terminal, inspect discovery resources:

```bash
curl -s http://127.0.0.1:8080/ | python -m json.tool
curl -s http://127.0.0.1:8080/collections | python -m json.tool
curl -s http://127.0.0.1:8080/collections/tutorial/contents | python -m json.tool
curl -s http://127.0.0.1:8080/api | python -m json.tool
```

The collection identifier is the filename stem. If it contains spaces or punctuation, use URL encoding; links emitted by the service are already encoded.

Retrieve the vector tile exactly. The interval URL notation is `lower/upper` and must be URL-encoded by `curl --get`:

```bash
curl --get -s \
  --data-urlencode 'variable=survey_stations' \
  --data-urlencode 'valid_time=2026-08-27T00:00:00Z/2026-08-27T06:00:00Z' \
  --data-urlencode 'release=tutorial-v1' \
  http://127.0.0.1:8080/collections/tutorial/tiles/WebMercatorQuad/0/0/0 | python -m json.tool
```

Inspect a live numeric surface:

```bash
curl -s 'http://127.0.0.1:8080/collections/tutorial/surface?bbox=13,40,15,41&width=12&height=8' | python -m json.tool
```

The response contains coincident depth and seabed matrices sampled from stored DNT1 tiles, together with grid geometry and a deterministic checksum. The tutorial explicitly declares its synthetic depth relative to LAT so the analytical variable contract and vertical datum remain coherent.

Exercise the remaining live operations without external data:

```bash
curl -s 'http://127.0.0.1:8080/collections/tutorial/point?coords=14.2,40.7' | python -m json.tool
curl -s 'http://127.0.0.1:8080/collections/tutorial/profile?start=13.8,40.9&end=14.6,40.4&samples=32' | python -m json.tool
curl -s 'http://127.0.0.1:8080/collections/tutorial/contours?bbox=13,40,15,41&cells=12&interval=5' | python -m json.tool
curl -s 'http://127.0.0.1:8080/collections/tutorial/query?bbox=13,40,15,41&cells=12&min_depth=5&max_depth=15&classes=sand,mud' | python -m json.tool
```

Open `http://127.0.0.1:8080/playground`. Move the cursor, draw a transect, pan to recompute contours and hillshade, inspect depth/seabed texture, rotate the 3D surface, and run a compound depth/class query. The north-west shelter option is meaningful only for a dataset that includes the derived shelter variable, such as the Bay of Naples demo.

## Verification and reflection

1. Which HTTP request returns stored evidence, and which returns a derived representation?
2. Why must categorical classes use nearest-cell rather than numeric interpolation?
3. Which profile parameters belong in a reproducibility record?
4. Why is a conformance declaration narrower than certification?
5. Explain why a variable name and its vertical-datum declaration must agree before an analytical endpoint consumes it.

Stop the service with `Ctrl-C`. Confirm that file modification time did not change: the server opens SQLite in read-only and query-only modes.
