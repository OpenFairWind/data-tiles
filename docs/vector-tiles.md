# Multidimensional vector tiles

DataTiles stores vector feature tiles alongside raster matrices by assigning each populated coordinate set a typed content profile. The spatial key remains MBTiles/TMS; dimensions identify the feature collection’s valid time, vertical interval, scenario, release, thematic variable, or other scientific coordinates.

The recommended interoperable encoding is gzip-compressed Mapbox Vector Tile 2.1 with media type `application/vnd.mapbox-vector-tile` and encoding `MVT+gzip`. Its content schema uses the MBTiles `vector_layers` object. Tiled GeoJSON uses `application/geo+json` and encoding `GeoJSON`. Other vector encodings may be registered with an IETF media type and an explicit codec name, but consumers are not required to understand them.

```bash
datatiles init mixed.datatiles --name "Forecast and observations" \
  --format application/vnd.datatiles.numeric
datatiles add-dimension mixed.datatiles variable text --axis C
datatiles add-dimension mixed.datatiles valid_time datetime --axis T

datatiles put mixed.datatiles 8 138 103 observations.mvt.gz --xyz \
  --coord variable=observations \
  --coord valid_time=2026-08-27T12:00:00Z \
  --data-type vector \
  --media-type application/vnd.mapbox-vector-tile \
  --encoding MVT+gzip \
  --schema vector-layers.json
```

Selection is the MBTiles interoperability boundary. Selecting an `MVT+gzip` vector coordinate set exposes its BLOBs through the conventional four-column `tiles` view, sets `metadata.format` to `pbf`, and projects the profile schema to `metadata.json`. Selecting tiled GeoJSON uses `application/geo+json` without MVT metadata. Selecting a numeric raster coordinate set exposes the same interface with its raster media type and removes stale MVT metadata.

DataTiles validates content declarations and framing; it does not semantically decode MVT geometry in the dependency-free core. Independent producers should additionally validate protobuf structure, layer extent, geometry commands, property types, clipping, winding order, and zoom-dependent generalization with an MVT conformance tool.
