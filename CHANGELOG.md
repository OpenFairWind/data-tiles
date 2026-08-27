# Changelog

## 0.10.0 — 2026-08-27

- adds deterministic `export-mbtiles` fallback with physical standard tables for conservative OpenLayers adapters;
- rejects DNT1 and other non-representable encodings instead of relabeling scientific bytes as map portrayals;
- rewrites the normative specification as a self-contained human- and agent-implementable contract with schema, algorithms, limits, conformance classes, test vectors, and implementation recipe;
- adds an onboard marine/automotive edge-intelligence manifesto and white paper with an AI evidence contract and explicit safety boundaries;
- adds software and scientific-lineage citation guidance to the main README and expands the verified bibliography;
- extends tutorial and regression coverage for legacy MBTiles fallback and specification/documentation coherence.

## 0.9.0 — 2026-08-27

- adds a five-lesson `docs/tutorial` zero-to-hero curriculum with strong theoretical treatment and executable laboratories;
- adds a deterministic, offline tutorial dataset containing numeric raster matrices and vector features;
- exercises exact retrieval, slicing, content profiles, HTTP analysis, FAIR evidence, provenance, and reproducibility in the course;
- adds a supported metadata API and `datatiles set-metadata` command so tutorials and producers do not bypass invariants;
- adds automated documentation-link, version/schema synchronization, tutorial double-build, and policy-coherence tests;
- requires all documentation to remain correct against code and specification, and all demos to remain coherent with code, documentation, and specification.

## 0.8.0 — 2026-08-27

- defines DataTiles concisely as MBTiles-compatible multidimensional raster-matrix and vector-feature storage;
- introduces schema revision 3 content profiles with explicit `raster`/`vector`, media type, encoding, and schema;
- projects selected raster and vector profiles correctly into MBTiles `format` and `json` metadata;
- adds MVT+gzip, tiled GeoJSON, mixed-content validation, content discovery, and CLI declarations;
- migrates revision 2 containers to revision 3 and canonicalizes coordinate identity by dimension name;
- opens HTTP-served containers read-only and rejects missing, unrelated, or unsupported SQLite files;
- rejects empty intervals, invalid non-Boolean values, unknown DNT1 headers, oversized encodings, and malformed numeric metadata;
- adds GitHub community, security, citation, dependency-update, and issue-template files.

## 0.7.0 — 2026-08-27

- expands tests across numeric security, CLI, HTTP, OpenAPI, playground, FAIR, packaging, and deterministic-build contracts;
- adds Python 3.10–3.13 CI, browser validation, isolated wheel installation, and reproducibility gates;
- adds tag-gated GitHub Release, build provenance, checksums, and PyPI Trusted Publishing delivery;
- adds an academic-grade testing and protected-release protocol.

## 0.6.0 — 2026-08-27

- adds a bounded, checksummed coincident depth/class surface API;
- adds live gradient-derived shadow relief with adjustable light azimuth;
- adds depth color combined with deterministic seabed-class textures;
- adds a rotatable 3D bathymetric wireframe with adjustable vertical exaggeration;
- adds repository-level contributor instructions and a Markdown Apache-2.0 license notice;
- documents the numeric-to-visual derivation pipeline and its scientific limitations.

## 0.5.0 — 2026-08-27

- establishes a normative FAIR-by-design publication and validation profile;
- adds an OpenLayers scientific playground with cursor inspection, profiles, live contours, and compound spatial predicates;
- adds point, contour, and GeoJSON query derivation APIs over decoded DNT1 values;
- adds a provenance-declared north-west land-interception shelter proxy;
- separates exact demo reproducibility from independent-dataset replicability documentation.

## 0.4.0 — 2026-08-27

- Added on-demand two-point great-circle depth transects decoded from DNT1 numeric arrays.
- Added paired sampling of the `depth_below_lat_m` and `seafloor_class` multidimensional variables.
- Added per-sample spatial coordinates, cumulative distance, tile/pixel evidence, depth, class code, and class label.
- Added deterministic SVG profiles whose seabed fill color follows the sampled classification.
- Added JSON and CSV profile representations with a canonical profile SHA-256.
- Added the interactive `/demo/profile` browser application and `/collections/{id}/profile` API.
- Added the offline `datatiles-profile` command.

## 0.3.0 — 2026-08-27

- Renamed the complete project and format namespace from the early Diles-derived working name to DataTiles.
- Changed the package, commands, SQLite tables, metadata keys, media type, application ID, and file extension consistently.
- Added the reproducible Bay of Naples EMODnet reference workflow.
- Added DTM 2024 bathymetry, Geology substrate, and EUSeaMap 2025 habitat acquisition.
- Added deterministic substrate/habitat classification and versioned fusion.
- Added raw source locks, runtime locks, manifests, checksum verification, and deterministic evidence bundles.
- Added byte-identical two-build verification with controlled geospatial fixtures.

## 0.2.0 — 2026-08-27

- Added point, interval, and point-or-interval dimensions with typed indexed bounds.
- Added structured horizontal, vertical, temporal, compound, and engineering CRS records.
- Added PROV-inspired agents, activities, entities, relations, checksums, and tile provenance links.
- Added the dependency-free DNT1 numeric-array encoding.
- Added a read-only OGC API – Tiles façade and generated OpenAPI description.
- Added dimensions, CRS, and provenance HTTP resources.

## 0.1.0 — 2026-08-26

- Initial multidimensional MBTiles-compatible reference implementation.
