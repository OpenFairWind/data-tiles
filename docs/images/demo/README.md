# Bay of Naples playground screenshot provenance

These screenshots document executed DataTiles demonstrations; they are not stored scientific variables, source evidence, navigational products, or substitutes for the reproducibility checks. Depth portrayals are derived at request time from DNT1 arrays. Nautical symbols in the 2026-08-28 captures are portrayals of stored tiled-GeoJSON features.

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

## Independent-layer capture — 2026-08-28

- viewport: 1280 × 720 pixels;
- generated container SHA-256: `9e011de29c6f13bd71f04a9fa9847beacf8e2e782cbe7295a148f68972a07def`;
- source-lock SHA-256: `15cb6cdee4ebc7843eff1e2db0b09ae9b48b236427afb8c2f9b5c127268270f1`;
- host runtime: Python 3.12.10, SQLite 3.49.1, zlib 1.2.11, NumPy 2.3.5, Pillow 12.3.0;
- stored nautical response: 295 deduplicated features, SHA-256 `47277e5a63f78958036e6839f7ebb9a3db690ba19e9c76cd504d27b4b245f656`;
- client: OpenLayers 10.10.0 playground served from the generated local container.

| Screenshot | Executed use case and parameters | SHA-256 |
|---|---|---|
| `playground-layer-controls.jpg` | all six layers enabled; 25 m isolines; smart 6 × 6-block depth samples; 225° illumination; relief strength 6 | `193e0bc048ba32dd565ed94f5338e554b07bf51fa5cb5eb3fa29058904ff6259` |
| `playground-nautical-vectors.jpg` | depth color and stored `openseamap_items` enabled; seabed classification, relief, isolines, and smart samples disabled | `f644c9a024b0b10a4e12b1dd60716b8bee636b3cb57f8b7aaf87011861f6b784` |

The executed browser session also produced a 47.59 km, 256-sample profile (`a9d37bb5194a7889…`) and repeated the documented compound query with 79 matching cells (`dfd7745990bcf7d7…`). Machine-readable retained outputs include profile SHA-256 `da239a60e19833a1027ff3387f5a352ed66da69c1140394b13c540cac06965c4` and surface SHA-256 `d0a5479d7bc028c4829b6102bb39758e5706875b528a1e2a538667035ddd9ac0`.
