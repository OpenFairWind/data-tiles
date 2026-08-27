# Getting started

Install Python 3.10 or later and run `python -m pip install -e .`.

Create a file and define its axes before inserting tiles:

```bash
datatiles init ocean.datatiles --name "Ocean forecast" --format image/png
datatiles add-dimension ocean.datatiles valid_time datetime --axis T --extent interval
datatiles add-dimension ocean.datatiles depth float --axis Z --unit m --extent point_or_interval
datatiles add-dimension ocean.datatiles variable text --axis C
datatiles add-crs ocean.datatiles horizontal --authority EPSG --code 3857 \
  --uri http://www.opengis.net/def/crs/EPSG/0/3857
```

Insert and retrieve a tile. Coordinate order does not matter.

```bash
datatiles put ocean.datatiles 6 34 22 temperature.png --xyz \
  --coord variable=temperature \
  --coord depth=10 \
  --coord 'valid_time=[2026-08-26T12:00:00Z,2026-08-26T18:00:00Z)'

datatiles get ocean.datatiles 6 34 22 copy.png --xyz \
  --coord 'valid_time=[2026-08-26T12:00:00Z,2026-08-26T18:00:00Z)' \
  --coord depth=10 \
  --coord variable=temperature
```

Each first insertion for a coordinate set creates a content profile. The default above is raster PNG. Mixed files declare vector or numeric raster content explicitly with `datatiles put --data-type`, `--media-type`, `--encoding`, and optional `--schema`; inspect profiles with `datatiles contents ocean.datatiles`. See [vector tiles](vector-tiles.md) and the [zero-to-hero tutorial](tutorial/README.md).

Expose that coordinate set to legacy MBTiles software:

```bash
datatiles select ocean.datatiles \
  --coord 'valid_time=[2026-08-26T12:00:00Z,2026-08-26T18:00:00Z)' \
  --coord depth=10 --coord variable=temperature
```

The `tiles` view now returns that slice. Selection persists in the file until changed.

If the consuming OpenLayers/MBTiles adapter requires physical tables, export the selected PNG slice:

```bash
datatiles export-mbtiles ocean.datatiles ocean.mbtiles
```

The standalone file contains only standard MBTiles interfaces. DNT1 and tiled GeoJSON require an explicit portrayal or MVT conversion first; see [MBTiles fallback](mbtiles-fallback.md).

Serve it through HTTP:

```bash
datatiles-serve ocean.datatiles --host 127.0.0.1 --port 8080
curl 'http://127.0.0.1:8080/collections/ocean/tiles/WebMercatorQuad/6/34/22?valid_time=2026-08-26T12:00:00Z/2026-08-26T18:00:00Z&depth=10&variable=temperature'
```

Before publishing, adopt the FAIR profile in [fair-by-design.md](fair-by-design.md): assign a persistent identifier, record an explicit licence and access rights, identify creators and controlled keywords, retain source checksums and qualified provenance, register catalogue metadata, and verify the `/collections/{id}/fair` report. A locally valid SQLite file is not automatically a FAIRly published research object.

Use the supported metadata interface rather than writing the SQLite table directly:

```bash
datatiles set-metadata ocean.datatiles description "Six-hour ocean forecast tiles"
datatiles set-metadata ocean.datatiles datatiles:license https://spdx.org/licenses/CC-BY-4.0.html
datatiles set-metadata ocean.datatiles datatiles:access_rights public
```

`format`, `datatiles:dimensions`, and `datatiles:default_media_type` are managed keys and cannot be overwritten through this command. Content insertion, dimension definition, and slice selection update them consistently.
