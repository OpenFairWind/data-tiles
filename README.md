# DataTiles

**DataTiles is MBTiles for multidimensional data: an SQLite container that stores both raster matrices and vector feature tiles.** It is inspired by the Data Tiles/Diles research model and extends [MBTiles 1.3](https://github.com/mapbox/mbtiles-spec/blob/master/1.3/spec.md). A tile is addressed by the conventional spatial coordinate `(z, x, y)` plus an arbitrary typed set of scientific coordinates such as valid time, elevation, pressure level, ensemble member, model run, scenario, variable, or band.

The format keeps the required MBTiles `metadata` and four-column `tiles` interfaces. `tiles` is a view exposing one selected multidimensional slice, so an ordinary MBTiles reader can consume a coherent raster or vector slice without understanding the extension. For conservative OpenLayers/MBTiles adapters, `export-mbtiles` materializes that slice into a standalone file with physical standard tables and no extension objects. DataTiles-aware readers can discover every slice, its typed coordinates, raster/vector content type, IETF media type, encoding, schema, CRS, and provenance.

![DataTiles information model](docs/figures/datatiles-information-model.svg)

*Figure 1. A spatial MBTiles address and an unordered canonical set of typed scientific coordinates resolve to an explicitly declared payload. Only a compatible selected slice is projected through the conventional MBTiles interface; scientific arrays are not silently presented as imagery.*

## Coordinate model

```text
tile = (z, x, y, {dimension-name: typed-point-or-interval, ...})
       -> (raster | vector, media-type, encoding, schema, BLOB)
```

Dimension order is immaterial. Coordinate sets are canonicalized and shared between tiles. Values are typed and searchable; no JSON parsing is required in the tile lookup path.

## Quick start

```bash
python -m pip install -e .
datatiles init weather.datatiles --name "WRF forecast" --format png
datatiles add-dimension weather.datatiles valid_time datetime --axis T --extent interval
datatiles add-dimension weather.datatiles pressure float --unit hPa --axis Z
datatiles add-crs weather.datatiles horizontal --authority EPSG --code 3857 \
  --uri http://www.opengis.net/def/crs/EPSG/0/3857
datatiles put weather.datatiles 5 17 12 tile.png \
  --coord 'valid_time=[2026-08-26T12:00:00Z,2026-08-26T18:00:00Z)' --coord pressure=850
datatiles select weather.datatiles \
  --coord 'valid_time=[2026-08-26T12:00:00Z,2026-08-26T18:00:00Z)' --coord pressure=850
datatiles validate weather.datatiles
datatiles-serve weather.datatiles --port 8080
```

The spatial row follows MBTiles/TMS convention. Use `--xyz` on `put` and `get` to convert an XYZ row.

Version 0.10 adds conservative physical-table MBTiles fallback, a self-sufficient implementation specification, and an onboard edge-intelligence manifesto/white paper. It also includes mixed raster/vector content profiles, a tested five-lesson zero-to-hero curriculum, FAIR-by-design publication profile, OpenLayers scientific playground, comprehensive quality suite, protected CI/CD release path, interval axes, PROV-inspired provenance, scientific CRS records, bounded numeric-array decoding, OpenAPI description, and read-only OGC-style access.

## Raster and vector content

- Numeric raster matrices use the dependency-free DNT1 encoding and retain dtype, shape, byte order, nodata, scale, offset, unit, and compression.
- Raster portrayals may use PNG, JPEG, WebP, or another declared media type.
- Vector feature tiles may use gzip-compressed Mapbox Vector Tile with MBTiles `vector_layers` metadata, tiled GeoJSON, or another explicitly declared vector encoding.
- Different multidimensional coordinate sets in the same file may use different content types and encodings.
- Selecting a slice updates standard MBTiles `format` and MVT `json` metadata transactionally.

See [multidimensional vector tiles](docs/vector-tiles.md) and the normative [content-profile specification](docs/specification.md#8-content-profiles).

## MBTiles fallback

Select a PNG/JPEG/WebP portrayal or gzip MVT slice, then export it for an OpenLayers stack that understands MBTiles but not DataTiles:

```bash
datatiles select ocean.datatiles --coord variable=seabed_portrayal
datatiles export-mbtiles ocean.datatiles ocean.mbtiles
```

The exporter preserves TMS rows and BLOB bytes and creates physical `metadata` and `tiles` tables. DNT1 numeric arrays are never dishonestly relabeled as pictures: create a documented, provenance-linked portrayal first. See the [fallback contract](docs/mbtiles-fallback.md).

## Bay of Naples reference demo

[`demo/bay-of-naples`](demo/bay-of-naples) provides a fully locked workflow using EMODnet DTM 2024 bathymetry, EMODnet Geology seabed substrate, and EUSeaMap 2025 habitats. It produces numeric depth, substrate, habitat, and deterministically fused seafloor-class tiles together with an immutable evidence bundle.

The playground proves that DataTiles contains queryable multidimensional data rather than a pyramid of finished pictures. It derives cursor observations, profiles, contours, compound predicates, depth-colored seabed textures, dynamic hillshade, and a rotatable 3D bathymetric mesh directly from coincident DNT1 depth and classification arrays. Run the server and open `/playground`.

Repository guidance is in [`AGENTS.md`](AGENTS.md), and the Markdown license notice is in [`LICENSE.md`](LICENSE.md). The complete Apache-2.0 legal text remains in `LICENSE`.

## Quality assurance and releases

Pull requests run the complete suite on Python 3.10–3.13, validate playground JavaScript, build and install the distributions, and repeat the deterministic scientific-fixture build. Version tags additionally produce checksums, a GitHub build-provenance attestation, a GitHub Release, and—after the protected environment gate—a PyPI Trusted Publishing deployment. See [`docs/testing-and-release.md`](docs/testing-and-release.md) for the local protocol and repository configuration.

```bash
python -m pip install -e '.[demo]'
cd demo/bay-of-naples
make all
```

The demo and source products are for research and visualization only and must not be used for navigation.

After building the Bay of Naples artifact, start its server and open the numeric transect demo:

```bash
datatiles-serve work/bay-of-naples.datatiles --port 8080
# Open http://127.0.0.1:8080/playground
```

The user supplies two longitude/latitude points. DataTiles resolves the depth and classification coordinate sets, decodes the corresponding numeric DNT1 tiles, samples the great-circle transect, and renders the resulting depth profile with seabed-class colors. JSON, CSV, and SVG representations are computed from the same samples.

An offline SVG can be produced without the HTTP service:

```bash
datatiles-profile work/bay-of-naples.datatiles \
  14.190,40.810 14.235,40.555 --samples 256 \
  --format svg --output depth-profile.svg
```

See the [documentation index](docs/README.md), especially the normative [specification](docs/specification.md), [FAIR-by-design profile](docs/fair-by-design.md), exact [reproducibility protocol](docs/reproducibility.md), and independent-dataset [replicability protocol](docs/replicability.md).

The [onboard intelligence white paper](docs/white-paper.md) presents DataTiles as an offline-first evidence substrate for marine and automotive data-driven AI. It covers feature contracts, uncertainty, provenance, fallback, cybersecurity, human authority, environmental protection, and a practical assurance lifecycle. DataTiles itself is not an approved nautical chart, ECDIS, automated-driving function, or certified safety component.

New users can follow the [five-lesson DataTiles zero-to-hero tutorial](docs/tutorial/README.md), which combines formal discussion with a fully offline mixed raster/vector laboratory dataset.

## How to cite DataTiles

Research using the software SHOULD cite the released software described by [`CITATION.cff`](CITATION.cff). Also cite the paper(s) that support the part of the scientific lineage or application you use:

- For reproducible Internet of Floating Things workflows: R. Montella et al., “Workflow-based automatic processing for Internet of Floating Things crowdsourced data,” *Future Generation Computer Systems* 94 (2019), 103–119 ([publisher record](https://www.sciencedirect.com/science/article/abs/pii/S0167739X18307672)).
- For onboard marine acquisition and edge/cloud crowdsourcing: R. Montella, S. Kosta, and I. Foster, “DYNAMO: Distributed leisure yacht-carried sensor-network for atmosphere and marine data crowdsourcing applications,” IC2E 2018, 333–339, [doi:10.1109/IC2E.2018.00064](https://doi.org/10.1109/IC2E.2018.00064).
- For crowdsourced bathymetry in coastal environmental modeling: D. Di Luccio et al., “Coastal marine data crowdsourcing using the Internet of Floating Things: Improving the results of a water quality model,” *IEEE Access* 8 (2020), 101209–101223, [doi:10.1109/ACCESS.2020.2996778](https://doi.org/10.1109/ACCESS.2020.2996778).

These papers establish relevant scientific lineage and application context; they do not specify the current DataTiles 1.0-draft SQLite format. See the complete [references](docs/references.md).

## Status

This repository is a working reference implementation and a draft format specification, not yet a registered standard. The on-disk application identifier and extension metadata make the dialect detectable without preventing normal SQLite access.

## License

Apache-2.0.
