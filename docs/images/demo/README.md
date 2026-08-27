# Bay of Naples playground screenshot provenance

These screenshots document an executed DataTiles demonstration; they are not stored scientific variables, source evidence, navigational products, or substitutes for the reproducibility checks. Every displayed map, contour, profile, query match, shadow, texture, and mesh was derived at request time from DNT1 arrays in a generated container.

Capture environment and inputs:

- capture date: 2026-08-27;
- viewport: 1280 × 720 pixels;
- DataTiles version: 0.10.0;
- generated container SHA-256: `11cdcce35ec9dd1612cbf3638750b4fcfccf538de4c6b1c6a8e4864d0eb24cac`;
- source-lock SHA-256: `508dae773a632c3c347885b14fed5f65bfcf15e0b0b973c9d4b6fd35bd95e02c`;
- host runtime: Python 3.12.10, SQLite 3.49.1, zlib 1.2.11, NumPy 2.3.5, Pillow 12.3.0;
- client: OpenLayers 10.10.0 playground served from the generated local container.

| Screenshot | Executed use case and parameters | SHA-256 |
|---|---|---|
| `playground-cursor-observation.jpg` | cursor inspection; observed 51.8 m depth, unknown class, no north-west shelter, and tile/pixel evidence | `f79be248363c262516c274251b6fc7806504dbd015b4a6c45feb22b44f8036e6` |
| `playground-depth-profile.jpg` | two map points; 55.56 km great-circle profile, 256 nearest-cell samples, profile prefix `e1ba503a9aa2be9c` | `9f5f5b33f5e5148456ae62de12fbbb137639b957e01f8849e4e26c8ed0604b14` |
| `playground-live-surface.jpg` | 25 m contours; texture and hillshade enabled; 225° illumination azimuth; relief strength 6; rotated 48 × 48 3D surface | `e76264bf5d29f46d041b291dc59708e95ae2f089136e792cd163eab67a88300b` |
| `playground-spatial-query.jpg` | `20 < depth < 500` m, class in `{sand, mud}`, north-west shelter true; 79 matching cells; query prefix `dfd7745990bcf7d7` | `db1f6a7ce7f3fd8512768679003b125ae7357587a8068787624ecfa81fd517bb` |

The unreferenced `playground-overview.jpg` is retained as an initial-state diagnostic. Screenshot hashes establish image identity only; the DataTiles container, source lock, request parameters, API checksums, and scientific verification remain the authoritative evidence.
