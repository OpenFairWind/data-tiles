# Changelog

## Unreleased — DataTiles Store 0.6.0

- adds dependency-free GeoJSON, CSV, XML, GPX, and newline-delimited GeoJSON feature importers with deterministic WGS 84 tiling, TMS storage, checksums, provenance, validation, and fail-clean output;
- adds the supplied 1,140-feature `resources/ports.json` collection and integrates the ports inside the Gaeta-to-Maratea demonstration bounds as an unofficial, provenance-linked tiled-GeoJSON slice with client-side nautical portrayal;
- vendors Bootstrap 5.3.8 CSS/JavaScript for a responsive, locally served PWA shell;
- adds administrator-managed Store name, tagline, validated/normalized logo upload, and bounded Bootstrap colour, card, background, text, border, radius, shadow, and font settings;
- adds Bearer-authenticated logo API parity, dynamic branding in the PWA manifest, security validation, regression tests, and updated Store documentation/visual evidence.
- adds a hardened Docker/Gunicorn image, persistent-volume Docker Compose deployment, container operations documentation, and the Montella–Foster 2010 environmental-data cloud-storage citation in the stated historical lineage toward Zarr.
- fixes the complete CI matrix by installing the declared `integrity` and `drm` extras required by the Ed25519 and encrypted-package tests.

## 0.20.0 — 2026-08-29

- consolidates revision-8 semantic, FAIR, integrity, commercial-policy, and immutable-release tables into the normative specification and synchronizes the HTTP/OpenAPI contract;
- corrects Store inspection of current revision-8 dimension, content, signature, and commercial-product columns and adds regression coverage using a real DataTiles container;
- replaces the Store's remote basemap preview with exact selected-slice retrieval and bounded client-side DNT1 portrayal while retaining explicit image-portrayal handling;
- adds Store architecture, access-gate, and preview-pipeline SVG figures plus verified catalog, scientific-preview, and agreement screenshots with provenance;
- aligns Store, demo, playground, utilities, tutorials, API documentation, release metadata, and visual registers with the revision-8 implementation.

## 0.19.0 — 2026-08-29

- advances the DataTiles schema to revision 8 with CF-first semantic variables, FAIR publication metadata, provenance, rights, optional integrity signatures, optional protected distribution, and immutable release identity;
- adds deterministic NetCDF, GRIB2, and Zarr scientific import utilities that preserve numeric DNT1 values and record source and conversion provenance;
- adds the optional Flask/SQLAlchemy DataTiles Store PWA, API, authentication, agreement enforcement, provider-neutral commerce, user libraries, and update discovery;
- expands the normative specification, migration addenda, source-citation register, white paper, tutorials, and regression coverage for revisions 4 through 8.

## 0.10.0 — 2026-08-27

- adds a command-line static-demo exporter, a Safari-compatible client-side numeric/vector portrayal, the full scientific playground toolset (relief, contours, smart labels, profile, compound query, and interactive 3D mesh), embedded checksum-identified data for direct `file://` use, an offline OpenLayers bundle, and an optional loopback-only launcher;
- renames the reference workflow directory to `demo/from-gaeta-to-maratea/` and aligns its default artifact identifier and filenames;
- expands the reference use case to the explicitly bounded Gaeta-to-Maratea corridor and retains approximately native 1/16 arc-minute EMODnet sampling through Web Mercator zoom 12;
- widens the western publication bound to `12.85° E` to include Palmarola, Ponza, Zannone, Ventotene, and Santo Stefano while preserving sampling density and rejecting insufficient frozen regional inputs;
- adds a checksum-validated Mediterranean Chart Builder import for its native EMODnet and OpenStreetMap acquisitions, crops the acquisition halo geospatially, and documents the remaining shallow-water resolution limit;
- imports and checksum-locks all seven JammeGaia22 grids, applies finest-finite selection with EMODnet fallback, and enforces a separately derived GSHHG 2.3.7 full-resolution land mask;
- documents the explicit permission/licence acceptance gate, private acquisition ledger, credential exclusion, FAIR access conditions, and Gaeta-to-Maratea island scope;
- improves shallow-water portrayal with bounded 96 × 72 surface sampling, adaptive contour spacing and hierarchy, a restrained scientific depth palette, lighter seabed patterns, reduced relief saturation, and shallow-prioritized depth labels;
- adds seven independent playground layer switches for depth color, seabed classification, shadow relief, isolines, smart depth samples, bathymetry source coverage, and stored OpenSeaMap-ecosystem vector items;
- recaptures every documented playground screenshot from the widened Gaeta-to-Maratea container and records current image, container, source-lock, runtime, profile, and query evidence;
- checksum-locks OpenStreetMap `seamark:*` acquisition, stores its deterministic CRS84 GeoJSON tiles under an explicit vector content profile, and exposes a bounded stored-feature endpoint without substituting a remote portrayal;
- restores Python 3.10 CI compatibility by using the test-only `tomli` backport when `tomllib` is unavailable;
- fixes two-point profile drawing by preventing the array index from being passed as an OpenLayers projection argument;
- documents an executed end-to-end Bay of Naples acquisition, double build, local service, API evidence capture, and scientific-playground protocol with provenance-registered screenshots;
- displays an actionable warning when the playground server template is opened directly through a `file://` URL and clarifies the required local HTTP launch procedure;
- adds accessible, reviewable SVG figures for the information model, DNT1 decoding, and reproducibility evidence chain, with an explicit figure-provenance register;
- restores the documented CI and protected release workflows and excludes local IDE, build, and generated DataTiles artifacts from version control;
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
