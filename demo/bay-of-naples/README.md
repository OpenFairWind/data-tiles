# Bay of Naples reference demo

This workflow creates `bay-of-naples.datatiles` from three scientific source products and one community vector source:

1. EMODnet DTM 2024 mean water depth relative to Lowest Astronomical Tide.
2. EMODnet Geology 1:100,000 seabed substrate polygons using the harmonized Folk classification.
3. EUSeaMap 2025 EUNIS 2007 habitat polygons, used to retain biogenic habitats such as coralligenous reef, algae/maerl/kelp, and Posidonia/seagrass.
4. OpenStreetMap nodes and ways carrying `seamark:*` tags, acquired through Overpass and used as stored OpenSeaMap-ecosystem vector items under ODbL 1.0.

The products are scientific information and **must not be used for navigation**.

## Reproduce

```bash
python3.12 -m venv .venv  # Python 3.12.13
. .venv/bin/activate
python -m pip install -e '../..[demo]'
make all
```

`make acquire` records byte-level SHA-256 checksums and exact HTTP request URLs in `work/source-lock.json`. Mutable HTTP response information is kept separately in `acquisition-report.json`, so it cannot perturb the scientific lock. `make build` consumes only the locked raw files. `make verify` validates every raw and derived checksum and the SQLite/foreign-key invariants.

For a complete repository-local execution that keeps the isolated environment, downloads, generated object, double-build checks, API outputs, and screenshots under the ignored `data/directory/`, follow the normative-supporting [step-by-step reproducibility guide](../../docs/reproducibility.md#step-by-step-execution-in-data). The guide explicitly separates an exact retained-runtime reconstruction from a host-specific demonstration build; changing the tracked runtime lock to bypass a mismatch is prohibited.

The build also creates `bay-of-naples-evidence.zip`, a deterministically ordered and timestamp-normalized evidence bundle containing the configuration, source lock, raw source subsets, artifact manifest, and final DataTiles database.

Two deterministic visual checks, `bathymetry-preview.png` and `seafloor-class-preview.png`, are generated from the same numeric grids and included in the evidence bundle. They are QA previews, not additional source data.

## Interactive scientific playground

```bash
datatiles-serve work/bay-of-naples.datatiles --port 8080
```

Open `http://127.0.0.1:8080/playground`. Cursor values, profile charts, contours, smart depth samples, predicate matches, shadow relief, depth color, seabed texture, and the 3D wireframe are not stored portrayals: they are generated from decoded numeric arrays after each request or viewport change. OpenSeaMap-ecosystem items are different: they are stored GeoJSON vector features in `variable=openseamap_items`, not a remote chart image.

Do not open `src/datatiles/profile-demo.html` directly in Safari or another browser. It is a server template, not a standalone file; `datatiles-serve` injects the collection identifier and provides the `/collections/...` analysis resources.

Executed browser results, parameters, checksums, and limitations are retained in the [playground documentation](../../docs/playground.md) and [screenshot provenance register](../../docs/images/demo/README.md).

The underlying evidence is available directly:

```bash
curl 'http://127.0.0.1:8080/collections/bay-of-naples/profile?start=14.190,40.810&end=14.235,40.555&samples=256&f=json'
curl 'http://127.0.0.1:8080/collections/bay-of-naples/profile?start=14.190,40.810&end=14.235,40.555&samples=256&f=csv'
```

To replicate independently, copy only `config.json`, install the locked environment, run the workflow in a fresh directory, and compare `work/artifact-manifest.json`. If an upstream live service has changed, acquisition stops when used with `--expect-lock`; the original raw files plus `source-lock.json` form the immutable evidence bundle needed for exact replay.

## Data variables

| Variable | Payload | Meaning |
|---|---|---|
| `depth_below_lat_m` | float32 DNT1 | metres below LAT; `-9999` nodata |
| `seabed_substrate` | uint8 DNT1 | deterministic generalized substrate class |
| `seabed_habitat` | uint8 DNT1 | deterministic generalized biogenic habitat class |
| `seafloor_class` | uint8 DNT1 | habitat-over-substrate fusion using the configured precedence |
| `northwest_wind_shelter` | uint8 DNT1 | derived north-west land-interception exposure proxy |
| `openseamap_items` | tiled GeoJSON vector | checksum-locked OpenStreetMap `seamark:*` nodes and ways; ODbL 1.0; not for navigation |

The original GeoJSON attributes remain in the raw evidence bundle. Generalization rules are implemented in `datatiles.demo`, versioned in the configuration, and tested.

## Reproducibility boundary

Exact reproducibility means rebuilding byte-identical DataTiles from the same locked raw bytes, configuration, Python, NumPy, and Pillow versions. Replicability means independently reacquiring the named releases and obtaining equivalent scientific classes and tile statistics. Live OGC services are mutable, so their responses are never treated as permanent merely because the URL is stable.

`runtime-lock.json` additionally pins DataTiles, Python, SQLite, zlib, NumPy, and Pillow. The build refuses to proceed if any runtime component differs, because SQLite page layout and zlib output are part of byte-level reproducibility.

## OpenLayers scientific playground

After `make all`, run `datatiles-serve work/bay-of-naples.datatiles --port 8080` and open `http://127.0.0.1:8080/playground`. The client shows decoded cursor values, two-point colored profiles, live bathymetric contours, depth-colored seabed textures, adjustable shadow relief, a rotatable 3D bathymetric surface, and compound depth/class/shelter queries.

The shelter field is a finite north-west ray test over the bathymetry water/land mask. It is a reproducible exposure proxy, not a wind-wave or atmospheric model, and must not support navigational or safety decisions.
