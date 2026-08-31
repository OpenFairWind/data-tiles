# Lesson 3 — Raster matrices and vector features

## Objectives

You will distinguish coverage and feature representations, understand DataTiles content profiles, inspect mixed content at one spatial address, and switch the standard MBTiles projection between raster and vector slices.

## Importing the bundled ports feature collection

Run `PYTHONPATH=src python utils/geojson2datatiles resources/ports.json ports.datatiles --name "Ports collection" --variable ports --min-zoom 0 --max-zoom 6`, then run `datatiles validate ports.datatiles`. The converter stores the original GeoJSON features in deterministic Web Mercator tile buckets using TMS rows and records the source SHA-256 and conversion provenance. It does not rasterize the points or create map imagery. The supplied records are an unofficial reproducibility fixture, not a navigation dataset.

## Theory: two complementary data models

A raster matrix samples one or more phenomena over a regular grid. Its topology is implicit: row and column position determine spatial adjacency. This makes rasters efficient for continuous or exhaustively classified fields such as elevation, temperature, probability, and seabed class. Scientific interpretation requires dtype, shape, nodata, unit, scale, offset, grid orientation, CRS, and sampling semantics.

A vector model represents discrete features with explicit geometry and properties. It is appropriate for survey stations, contours, administrative regions, tracks, and classified polygons whose boundaries matter. Interpretation requires geometry type, coordinate space, layer identity, field schema, clipping and simplification rules, and often stable feature IDs.

Neither model is universally superior. Converting a continuous depth matrix into contours discards within-band variation; rasterizing a point observation invents cell support that the observation did not originally possess. DataTiles therefore stores both without pretending they are interchangeable.

Every populated coordinate set has one `datatiles_contents` profile:

```text
(data_type, media_type, encoding, schema_json)
```

`data_type` is `raster` or `vector`. The media type identifies representation; encoding names its codec. DNT1 is a numeric raster encoding. PNG is a raster portrayal. `MVT+gzip` is the interoperable MBTiles vector encoding. `GeoJSON` is useful for small educational or analytical feature tiles. The schema describes matrix meaning or feature fields.

The profile belongs to the coordinate set because the same file can contain different representations. At `(z=0,x=0,y=0)`, the tutorial stores depth and seabed matrices, a small PNG portrayal used only for fallback practice, and survey-station features. Their `variable` coordinates distinguish them.

## Laboratory

Inspect the mixed profiles:

```bash
datatiles contents tutorial.datatiles
```

Confirm that two profiles are raster/DNT1, one is raster/PNG, and one is vector/GeoJSON. Retrieve and decode the scientific raster:

```bash
python - <<'PY'
from datatiles import DataTiles,decode_numeric_tile
t=('2026-08-27T00:00:00Z','2026-08-27T06:00:00Z',True,True)
c={'variable':'seafloor_class','valid_time':t,'release':'tutorial-v1'}
with DataTiles('tutorial.datatiles',read_only=True) as s:
    tile=decode_numeric_tile(s.get(0,0,0,c))
    print(tile.shape,tile.dtype,tile.nodata,tile.values)
PY
```

Retrieve the vector feature collection:

```bash
python - <<'PY'
import json
from datatiles import DataTiles
t=('2026-08-27T00:00:00Z','2026-08-27T06:00:00Z',True,True)
c={'variable':'survey_stations','valid_time':t,'release':'tutorial-v1'}
with DataTiles('tutorial.datatiles',read_only=True) as s:
    value=json.loads(s.get(0,0,0,c))
    for feature in value['features']:
        print(feature['id'],feature['geometry'],feature['properties'])
PY
```

Change the MBTiles compatibility slice:

```bash
datatiles select tutorial.datatiles \
  --coord variable=survey_stations \
  --coord 'valid_time=[2026-08-27T00:00:00Z,2026-08-27T06:00:00Z]' \
  --coord release=tutorial-v1
python - <<'PY'
import sqlite3
db=sqlite3.connect('tutorial.datatiles')
print(dict(db.execute('SELECT name,value FROM metadata'))['format'])
print(db.execute('SELECT count(*) FROM tiles').fetchone()[0])
PY
```

The format becomes `application/geo+json`. Selecting an `MVT+gzip` slice would instead produce `format=pbf` and standard `metadata.json.vector_layers`. Restore depth using the same command with `variable=depth_below_lat_m`.

## Verification and reflection

1. Why is a colored PNG not equivalent to the DNT1 matrix from which it was rendered?
2. Why does `schema_json` belong to a coordinate-set content profile rather than a global metadata key?
3. When would MVT be preferable to tiled GeoJSON?
4. Which information is lost when vector observations are rasterized?

Run `datatiles validate tutorial.datatiles` after each selection. Validation must reject an `MVT+gzip` declaration whose BLOB lacks gzip framing and an MVT schema without `vector_layers`.

### Legacy OpenLayers fallback

If an OpenLayers deployment can read MBTiles but not DataTiles, materialize the tutorial's explicit portrayal slice as a conservative standalone database:

```bash
datatiles export-mbtiles tutorial.datatiles tutorial-portrayal.mbtiles \
  --coord variable=depth_portrayal \
  --coord 'valid_time=[2026-08-27T00:00:00Z,2026-08-27T06:00:00Z]' \
  --coord release=tutorial-v1
```

Inspect it with SQLite. Both interfaces are physical tables and no `datatiles_*` objects remain:

```bash
sqlite3 tutorial-portrayal.mbtiles \
  "SELECT name,type FROM sqlite_master WHERE name IN ('metadata','tiles') ORDER BY name;"
sqlite3 tutorial-portrayal.mbtiles \
  "SELECT count(*) FROM sqlite_master WHERE name LIKE 'datatiles_%';"
```

Try the same command with `--coord variable=depth_below_lat_m`. It must fail: DNT1 is scientific numeric data, not an MBTiles portrayal. A producer must derive and document a PNG/WebP slice before export.
