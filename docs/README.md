# DataTiles documentation

The documentation is organized by authority and purpose. `specification.md` is normative; code and examples must conform to it. The remaining documents are explanatory profiles, implementation guidance, or scientific protocols and must not silently redefine normative behavior.

The [figure provenance register](figures/README.md) identifies the source documents, construction method, parameters, and interpretive scope of each explanatory SVG.

| Document | Purpose |
|---|---|
| [Specification](specification.md) | normative container, dimensions, CRS, provenance, numeric payload, FAIR metadata, validation, and HTTP profile |
| [MBTiles fallback](mbtiles-fallback.md) | selected-slice compatibility and physical-table export for conservative OpenLayers adapters |
| [Onboard intelligence white paper](white-paper.md) | manifesto, AI evidence contract, practical marine/automotive architecture, and safety boundaries |
| [Design evaluation](design-evaluation.md) | concise definition, audit findings, corrections, and compatibility conclusion |
| [Zero-to-hero tutorial](tutorial/README.md) | ten theory-led lessons with executable raster/vector, FAIR, integrity, DRM, and Store laboratories |
| [FAIR by design](fair-by-design.md) | operational mapping from each FAIR principle to DataTiles evidence and publication gates |
| [FAIR scientific publication profile](fair-publication-profile.md) | normative-supporting FAIR gates, DataCite 4.7 alignment, and release evidence |
| [Scientific provenance](provenance.md) | W3C PROV-aligned entities, activities, agents, lineage, and audit rules |
| [Data licensing and rights](data-licensing.md) | SPDX expressions, source/output/metadata rights separation, attribution, and access conditions |
| [Cryptographic integrity and digital signatures](digital-signatures.md) | optional SHA-256 logical manifests, Ed25519 signatures, trust policy, offline verification, and Sigstore/in-toto interoperability |
| [Data sources and citation](data_sources_and_citation.md) | authoritative source-by-source citations, acknowledgements, licences, frozen-manifest rules, and FAIR release checklist |
| [Architecture](architecture.md) | component boundaries and design rationale |
| [Numeric tiles](numeric-tiles.md) | DNT1 encoding and physical-value semantics |
| [Vector tiles](vector-tiles.md) | multidimensional MVT/GeoJSON profiles and MBTiles projection |
| [HTTP/OGC API](ogc-api.md) | resource model and interoperability scope |
| [Playground](playground.md) | OpenLayers scientific operations and limitations |
| [DataTiles Store PWA](store-pwa.md) | Flask/SQLAlchemy institutional catalog, metadata search, role-based access, interactive preview, licence/safety acceptance, API-first CRUD, and authorized downloads |
| [DataTiles Store API v1](store-api.md) | Bearer authentication, agreement workflow, catalog/search, preview/download, managers CRUD, identity administration, and audit endpoints |
| [Testing and release](testing-and-release.md) | local suite, CI gates, protected delivery, and release checklist |
| [Profile demo](profile-demo.md) | two-point transect algorithm and evidence |
| [Reproducibility](reproducibility.md) | exact reconstruction of the Naples reference object |
| [Replicability](replicability.md) | protocol for independent regions, sources, variables, and implementations |
| [Getting started](getting-started.md) | concise installation and API tutorial |
| [Interoperability conventions](conventions.md) | CF-first variable semantics, units, CRS/datum, source identity, dimensions, and portrayal boundaries |
| [Import utilities](import-utilities.md) | Dependency-free feature ingestion plus NetCDF/GRIB/Zarr scientific ingestion, deterministic tiling, semantic mapping, and provenance |
| [Zarr source profile](zarr-source-profile.md) | normative Zarr v2/v3 source identity, checksums, groups, remote stores, FAIR provenance and rights |
| [References](references.md) | research papers, standards, vocabularies, and source records |
| [Commercial DRM](drm-and-commercial-licensing.md) | optional protected distribution, ODRL policy, recipient licences |
