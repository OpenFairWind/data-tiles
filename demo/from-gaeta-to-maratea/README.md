# From Gaeta to Maratea reference demo

This production workflow creates `gaeta-to-maratea.datatiles` for the explicit CRS84 extent `12.85–15.71851° E, 39.99852–41.21408° N`. The playground is downstream: it shows and tests the created DataTiles object but is not a substitute for acquisition, source validation, composition, tiling, provenance, or verification.

The deterministic build also clips `../../resources/ports.json` to these bounds and stores the selected points as a separate tiled-GeoJSON `ports` variable. The evidence bundle includes the checksum-identified source snapshot. These descriptive port records and the playground's anchor symbols are unofficial and MUST NOT be used as a chart, port authority register, or navigation aid.

1. Seven checksum-locked JammeGaia22/MGDS grids at 2, 5, 10, 15, 20, 30, and 40 m horizontal spacing, selected by finest finite cell.
2. EMODnet DTM 2024 native regional elevation, converted explicitly to positive water depth and used only where JammeGaia22 has no finite cell.
3. GSHHG 2.3.7 full-resolution L1 polygons as the separate, authoritative land/ocean mask, applied after bathymetry composition.
4. EMODnet Geology 1:100,000 seabed substrate polygons using the harmonized Folk classification.
5. EUSeaMap 2025 EUNIS 2007 habitat polygons, used to retain biogenic habitats such as coralligenous reef, algae/maerl/kelp, and Posidonia/seagrass.
6. OpenStreetMap nodes and ways carrying `seamark:*` tags, using the checksum-locked Mediterranean Chart Builder navigation-context acquisition and stored as OpenSeaMap-ecosystem vector items under ODbL 1.0.

The west bound includes Palmarola, Ponza, Zannone, Ventotene, and Santo Stefano with an approximately `0.11°` western halo beyond Palmarola and Ponza. Inclusion is a geometric scope guarantee, not a claim of feature completeness or harbor-scale accuracy.

The result is an open-source research and recreational nautical-chart aid. It is **not an official ENC or ECDIS product and must never be the sole source used for navigation**.

## Reproduce

```bash
python3.12 -m venv .venv  # Python 3.12.13
. .venv/bin/activate
python -m pip install -e '../..[demo]'
make all
```

To use existing frozen acquisitions, run `make acquire` for the thematic inputs and then import the bathymetry, GSHHG topology, navigation context, and Jamme grids before `make build`:

```bash
python -m datatiles.demo import-medchart --config config.json --work work \
  --source-root /path/to/mediterranean-chart-builder/data
```

The import verifies the upstream acquisition manifests and all seven original JammeGaia22 checksums, records them in `medchart-import.json`, and deterministically reprojects each UTM grid with nearest-neighbour sampling. It rasterizes GSHHG full-resolution L1 polygons on the compositing grid. A frozen regional EMODnet or OSM snapshot is imported only when its declared bounds contain the complete publication extent; otherwise the importer retains the newly acquired wide-area source and records that decision. Composition selects the finest finite Jamme cell, uses EMODnet only as fallback, and finally forces GSHHG land cells to nodata. Because Jamme coverage is regional, the Pontine islands and other areas outside it use the approximately 115 m EMODnet source spacing and are not harbor-scale soundings. Pre-rendered chart MBTiles are never treated as numeric scientific arrays.

Before downloading data, the operator MUST open each source landing page, determine whether authentication or explicit permission is required, read the applicable licence and terms, and record acceptance, access date, account/permission reference where applicable, request URL, release, and checksum in a private acquisition ledger. Credentials and acceptance tokens MUST NOT be committed or placed in the DataTiles evidence bundle. CC BY and ODbL sources still require attribution; a public download endpoint is not evidence that licence obligations were accepted. See the [replicability protocol](../../docs/replicability.md#permission-and-licence-gate).

`make acquire` records byte-level SHA-256 checksums and exact HTTP request URLs in `work/source-lock.json`. Mutable HTTP response information is kept separately in `acquisition-report.json`, so it cannot perturb the scientific lock. `make build` consumes only the locked raw files. `make verify` validates every raw and derived checksum and the SQLite/foreign-key invariants.

For a complete repository-local execution that keeps the isolated environment, downloads, generated object, double-build checks, API outputs, and screenshots under the ignored `data/directory/`, follow the normative-supporting [step-by-step reproducibility guide](../../docs/reproducibility.md#step-by-step-execution-in-data). The guide explicitly separates an exact retained-runtime reconstruction from a host-specific demonstration build; changing the tracked runtime lock to bypass a mismatch is prohibited.

The build also creates `gaeta-to-maratea-evidence.zip`, a deterministically ordered and timestamp-normalized evidence bundle containing the configuration, source lock, raw source subsets, artifact manifest, and final DataTiles database.

Two deterministic visual checks, `bathymetry-preview.png` and `seafloor-class-preview.png`, are generated from the same numeric grids and included in the evidence bundle. They are QA previews, not additional source data.

## Interactive scientific playground

```bash
datatiles-serve work/gaeta-to-maratea.datatiles --port 8080
```

Open `http://127.0.0.1:8080/playground`. Cursor values, profile charts, contours, smart depth samples, predicate matches, shadow relief, depth color, seabed texture, and the 3D wireframe are not stored portrayals: they are generated from decoded numeric arrays after each request or viewport change. OpenSeaMap-ecosystem items are different: they are stored GeoJSON vector features in `variable=openseamap_items`, not a remote chart image.

Do not open `src/datatiles/profile-demo.html` directly in Safari or another browser. It is a server template, not a standalone file; `datatiles-serve` injects the collection identifier and provides the `/collections/...` analysis resources.

Executed browser results, parameters, checksums, and limitations are retained in the [playground documentation](../../docs/playground.md) and [screenshot provenance register](../../docs/images/demo/README.md).

The underlying evidence is available directly:

```bash
curl 'http://127.0.0.1:8080/collections/gaeta-to-maratea/profile?start=14.190,40.810&end=14.235,40.555&samples=256&f=json'
curl 'http://127.0.0.1:8080/collections/gaeta-to-maratea/profile?start=14.190,40.810&end=14.235,40.555&samples=256&f=csv'
```

To replicate independently, copy only `config.json`, install the locked environment, run the workflow in a fresh directory, and compare `work/artifact-manifest.json`. If an upstream live service has changed, acquisition stops when used with `--expect-lock`; the original raw files plus `source-lock.json` form the immutable evidence bundle needed for exact replay.

## Data variables

| Variable | Payload | Meaning |
|---|---|---|
| `depth_below_lat_m` | float32 DNT1 | metres below LAT; `-9999` nodata |
| `bathymetry_source` | uint8 DNT1 | per-cell Jamme resolution band or EMODnet fallback identity |
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

After `make all`, run `datatiles-serve work/gaeta-to-maratea.datatiles --port 8080` and open `http://127.0.0.1:8080/playground`. The client shows decoded cursor values, two-point colored profiles, adaptive bathymetric contours, separate depth color and restrained seabed texture, adjustable shadow relief, a rotatable 3D bathymetric surface, and compound depth/class/shelter queries.

EMODnet is acquired at 2,754 × 1,167 regional cells; the compositing grid is 5,508 × 2,334 (nominal 50 m target spacing) so measured Jamme detail is not first collapsed to the coarser fallback grid. Storage extends through Web Mercator zoom 12. The client requests a bounded 128 × 128 map portrayal and a separate 96 × 72 analytic surface. The source-coverage layer makes every Jamme/EMODnet decision inspectable. Contour density is scale-dependent and remains limited by the selected source resolution; no new soundings are invented.

The shelter field is a finite north-west ray test over the bathymetry water/land mask. It is a reproducible exposure proxy, not a wind-wave or atmospheric model, and must not support navigational or safety decisions.

## FAIR, provenance, and rights gate

The demo is also a publication-evidence exercise. Every upstream dataset must be represented by a checksum-identified provenance entity and an explicit source-rights record; the generated DataTiles dataset and its metadata have separate rights. The build must never infer permission from successful HTTP access. Before a scholarly release, replace illustrative identifiers with a registered PID, export DataCite 4.7 metadata and the W3C PROV-aligned graph, and archive the strict FAIR report with catalogue, landing-page, and metadata-retention evidence. `fair-publication-profile.json` lists the required evidence. The navigation warning remains independent of FAIR status: FAIRness does not establish hydrographic authority or safety fitness.

## Source-specific citation gate

`docs/data_sources_and_citation.md` is the authoritative citation register. A production run MUST record whether each acquired source actually contributed cells/features. Visible map/release acknowledgements MUST be checked against that frozen manifest: JammeGaia22 is primary bathymetry; EMODnet DTM 2024 is credited only when fallback cells are used; GSHHG topology and optional S2Coast-2023 high-water-line facts remain distinct; OpenStreetMap context retains ODbL attribution. Do not credit GMRT, GEBCO, EMODnet thematic products, ISPRA, or other candidates unless the run evidence proves contribution.

## Optional signed release

After the final source-contribution manifest, citations, rights, provenance, and FAIR checks are frozen, the demo MAY be signed with `datatiles-integrity`. Do not auto-sign intermediate NetCDF/GRIB/Zarr imports. The release should publish the detached signature and independently authenticated public key. A valid signature does not change the `Not for navigation` status.

## Optional commercial edition

The reference demo is not automatically converted into a proprietary product. A commercial edition may be created only if the frozen contribution manifest and every upstream licence permit that use. If enabled, register product/ODRL metadata in the inner DataTiles object, complete all acknowledgements, sign the frozen plaintext release if desired, and only then create `.dtpkg` packages and recipient licences. `Not for navigation` remains mandatory unless an independent competent authority establishes otherwise.
