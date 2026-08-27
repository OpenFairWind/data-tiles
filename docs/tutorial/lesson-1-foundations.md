# Lesson 1 — From maps to data tiles

## Objectives

By the end of this lesson you will distinguish tiled *data* from tiled *portrayal*, explain the compatibility relationship between MBTiles and DataTiles, build a numeric container, and inspect its standard and extension interfaces.

## Theory: a tile is an addressable partition

A spatial tile matrix partitions a two-dimensional domain at discrete zoom levels. For Web Mercator, zoom `z` contains `2^z × 2^z` cells. MBTiles stores the address `(z,x,y)` in SQLite, using Tile Map Service row orientation: its row increases from south to north. Most web URLs use XYZ orientation, whose row increases from north to south. The conversion is `y_tms = 2^z - 1 - y_xyz`.

MBTiles is deliberately a container interface. Its `metadata` relation has exactly `name,value`; its `tiles` relation has exactly `zoom_level,tile_column,tile_row,tile_data`. The BLOB may be a raster image or vector tile. This simplicity makes MBTiles portable, but its address has no time, vertical level, ensemble, variable, or scenario.

DataTiles extends the address rather than replacing it:

```text
(z, x, y, {dimension → typed point or interval}) → typed content BLOB
```

The extra coordinate set selects a scientific slice. One slice is projected through the ordinary four-column `tiles` view, so an unaware MBTiles program still sees a coherent 2D tileset. Compatibility is therefore a *projection*, not a claim that MBTiles understands N dimensions.

The second conceptual distinction is data versus portrayal. A PNG bathymetric tile stores colors chosen by a style. A DNT1 bathymetric tile stores numeric samples, their dtype, matrix shape, nodata value, scale, offset, unit, byte order, and compression. The former answers “what should be drawn?”; the latter supports “what value is here?” and new derivations.

## Laboratory

Build the course dataset:

```bash
python docs/tutorial/examples/build_tutorial.py build tutorial.datatiles
```

Inspect its SQLite identity and interfaces:

```bash
python - <<'PY'
import sqlite3
db=sqlite3.connect('tutorial.datatiles')
print('application_id:', hex(db.execute('PRAGMA application_id').fetchone()[0]))
print('schema revision:', db.execute('PRAGMA user_version').fetchone()[0])
print('metadata columns:', [r[1] for r in db.execute('PRAGMA table_info(metadata)')])
print('tiles columns:', [r[1] for r in db.execute('PRAGMA table_info(tiles)')])
print('visible tile count:', db.execute('SELECT count(*) FROM tiles').fetchone()[0])
PY
```

Expected invariants are application ID `0x44415441`, schema revision `3`, two metadata columns, four tile columns, and one visible selected tile.

Now decode the selected numeric matrix:

```bash
python - <<'PY'
from datatiles import DataTiles, decode_numeric_tile
with DataTiles('tutorial.datatiles',read_only=True) as store:
    blob=store.db.execute('SELECT tile_data FROM tiles').fetchone()[0]
    tile=decode_numeric_tile(blob)
    print(tile.shape,tile.dtype,tile.unit)
    print(tile.values)
PY
```

The result is a `4 × 4` `float32` matrix in metres. Nothing in the `tiles` view reveals its time or variable; that information belongs to the DataTiles extension.

## Verification and reflection

Run `datatiles validate tutorial.datatiles`. Then answer:

1. Why would adding `time` directly to the MBTiles `tiles` view break unaware clients?
2. Why can two PNG tiles with identical pixels still represent different scientific data?
3. At zoom zero, why are TMS and XYZ row values equal?
4. Which guarantee is provided by SQLite, and which requires the DataTiles specification?

Do not continue until you can explain the compatibility view as a lossful 2D projection of an N-dimensional object.
