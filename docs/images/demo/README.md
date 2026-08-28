# From Gaeta to Maratea screenshot provenance

These screenshots document an executed DataTiles demonstration; they are not stored scientific variables, source evidence, navigational products, or substitutes for the reproducibility checks. Depth portrayals are derived at request time from DNT1 arrays. Nautical symbols are portrayals of stored tiled-GeoJSON features. Every image was recaptured after the western bound was extended to `12.85° E` to include Palmarola, Ponza, Zannone, Ventotene, and Santo Stefano.

## Capture environment and inputs — 2026-08-28

- viewport: 1280 × 720 pixels;
- DataTiles version: 0.10.0;
- publication extent: `12.85–15.71851° E, 39.99852–41.21408° N`;
- generated container SHA-256: `b0f9732ce43a1b16729978b9ec8feabf82d513e1d8d71405893b1c828b4f55e2`;
- source-lock SHA-256: `20effbe5c4612492c0a1ca3a1575216f3d2bce5e5178ef56d1c49c84616308b7`;
- grid: 2,754 × 1,167 thematic cells and 5,508 × 2,334 bathymetry-composition cells;
- host-specific capture runtime: Python 3.12.13, SQLite 3.53.1, zlib 1.2.12, NumPy 2.3.5, Pillow 12.3.0;
- client: OpenLayers 10.10.0 playground served from the generated local container.

The tracked exact-reproduction runtime requires zlib 1.3.2. The available capture runtime used zlib 1.2.12, so this screenshot container is explicitly a host-specific demonstration build, not the byte-identity reference artifact. The tracked runtime lock was not modified. Source acquisition and transformation remain checksum-locked in the capture's evidence bundle.

The widened EMODnet, EMODnet Geology, EUSeaMap, and OpenStreetMap subsets were reacquired for the declared extent. The older Mediterranean Chart Builder EMODnet and OSM snapshots stopped at `13.37082° E` and were therefore rejected as spatially insufficient. GSHHG 2.3.7 and seven JammeGaia22 grids were imported from checksum-validated local acquisitions. Jamme values use the finest finite cell; EMODnet is used only where Jamme has no finite value; the separately derived GSHHG full-resolution L1 mask then forces land cells to nodata.

## Current screenshots

| Screenshot | Executed use case and parameters | SHA-256 |
|---|---|---|
| `playground-overview.jpg` | initial widened-extent diagnostic; depth color, seabed classification, shadow relief, and stored nautical vectors enabled | `0add78039ec78e224c1e60eb26b2532e2cf7849a9d1ee8a46432eb2cd620c0b8` |
| `playground-cursor-observation.jpg` | cursor inspection; 340.9 m, JammeGaia22 10 m source, unknown class, no north-west shelter, with tile/pixel evidence | `b92662385a755549d4aec4325e4bcfecc28f51200cccd47232e38b0644e15cc1` |
| `playground-depth-profile.jpg` | two map points; 86.52 km great-circle profile, 256 nearest-cell samples, profile prefix `9660634e1888026f` | `f6c29fdcca072dfd5b2d436b296161fc82e2fed5acbe4886c051132d82ef5809` |
| `playground-live-surface.jpg` | 20 m shallow contour interval; all data-verification layers enabled; 225° illumination; relief strength 6; rotated live 3D surface | `2d2efeb2afe5dc8a032fe5111780dad3ea9fc0c220d85fd5c3d6f2fd40473529` |
| `playground-spatial-query.jpg` | `0 < depth < 200` m, class in `{sand,mud}`, no shelter predicate; 820 matching cells; query prefix `e0d621598b1eccac` | `28a994864e269f75a38f8b06b469a29c9d17ccac183bd29264aa2f448896b8b8` |
| `playground-layer-controls.jpg` | depth, classification, relief, isolines, smart samples, source coverage, and stored nautical vectors enabled; 20 m interval; 225° illumination; relief strength 6 | `20c407023af8b9b816473b47eafb9d9e9e3a3985f89c42b91271c004fa034008` |
| `playground-nautical-vectors.jpg` | depth color and stored `openseamap_items` enabled; classification, relief, isolines, samples, and source coverage disabled | `3fe0bda56081f169616d74e748fa4f8826f13f3cddb154c198853b1141efbac2` |
| `gaeta-to-maratea-overview.png` | lossless version of the initial widened-extent diagnostic | `83534067caaf05862e83b8df623cbab5aaf6ce7e4ba10ad14646c8d28de6b993` |
| `gaeta-to-maratea-layers.png` | lossless all-layer verification state with source coverage visible | `795f68bbc2d6ef66b8bd997bb076149b28caa51def23c25b0244b1f4c1d1fae5` |
| `gaeta-to-maratea-profile.png` | lossless 86.52 km, 256-sample profile state | `902d1dd5847ac50e3b51b766f47cd70ebf1792a5b106617c3e829d15b505ba67` |
| `gaeta-to-maratea-query.png` | lossless `0–200 m`, sand-or-mud compound-query state with 820 matches | `dc08fdc035d1dd5969f08b65203a9740ea74e7b350b752211687befea1c7b05a` |

Screenshot hashes establish image identity only. The DataTiles container, source lock, request parameters, API checksums, provenance graph, and scientific verification remain the authoritative evidence. Visible grid cells, angular shorelines, classifications, contours, and sampled labels remain limited by their declared source resolution and algorithms. The screenshots and generated map are not official or certified sources for navigation.

C-MAP Chart Explorer was used only as a qualitative reference for visual hierarchy, contrast, and layer organization. No C-MAP pixels, data, or proprietary symbols were copied.
