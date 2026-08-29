# FAIR by design

## Purpose

FAIR is an architectural property of DataTiles, not a label applied after publication. The container couples data, typed coordinates, semantics, provenance, integrity information, and standard access descriptions so that a computational agent can discover and evaluate a tile without relying on undocumented project knowledge. FAIR does not mean open: restricted data can be FAIR when access conditions are explicit and machine actionable.

## Conformance profile

| Principle | DataTiles design obligation | Evidence |
|---|---|---|
| F1 | Assign a globally unique persistent identifier to each published scientific object and revision. | `datatiles:identifier`; catalogue PID/DOI landing page |
| F2–F3 | Embed rich metadata and the identifier of the described object. | `metadata`, dimension records, CRS, provenance |
| F4 | Register the PID and searchable descriptive record in an appropriate catalogue. | catalogue record URL and indexing report |
| A1 | Resolve the identifier through an open protocol and advertise representations. | HTTPS landing page, OGC-style links, OpenAPI |
| A1.1–A1.2 | Use implementable protocols; state authentication when needed. | access-rights and security metadata |
| A2 | Preserve tombstone metadata after byte withdrawal. | repository retention policy |
| I1 | Use formal, machine-readable structures and media types. | SQLite schema, JSON, GeoJSON, OpenAPI, DNT1 |
| I2 | Identify units, CRSs, variables, classes, and licences with FAIR vocabularies/URIs. | dimension/CRS records and vocabulary mappings |
| I3 | Maintain qualified links among sources, agents, activities, tiles, and outputs. | PROV-inspired relations and tile provenance |
| R1 | State content, methods, uncertainty, resolution, and limitations. | abstract, variable metadata, manifests, documentation |
| R1.1 | Record an explicit licence URI for data and metadata. | `datatiles:license` and source licences |
| R1.2 | Preserve detailed provenance and immutable input identities. | entities, activities, agents, SHA-256 locks |
| R1.3 | Map to community standards and document departures. | MBTiles, OGC API patterns, CRS, PROV-O, domain terms |

## Publication gate

A release MUST fail its FAIR gate when it lacks an identifier, licence, access-rights statement, resolvable CRS, unit for a dimensional physical quantity, source attribution, source checksum, provenance activity, version, or machine-readable API link. The gate SHOULD also test vocabulary URI resolution, catalogue registration, metadata persistence policy, checksum retrieval, OpenAPI validity, and independent decoding of a sample DNT1 tile.

The From Gaeta to Maratea demonstration is a reference publication profile. Its evidence ZIP contains the raw responses needed for exact replay; the public DataTiles object contains the source graph and tile-level lineage needed for inspection. Derived `northwest_wind_shelter` values are explicitly identified as a deterministic land-interception exposure proxy and must not be confused with a validated wind-wave shelter model.

FAIR access does not imply frictionless or anonymous download. A provider may require authentication, explicit permission, or acceptance of licence terms. Acquisition tooling MUST preserve those access conditions in metadata without publishing credentials, and MUST stop when the responsible operator has not established authority to retrieve or redistribute the source. The private acceptance record and the public source/provenance record serve different purposes and MUST remain separate.

## FAIR maturity

FAIRness should be reported as individual test outcomes, not a single opaque score. Passing container checks demonstrates machine actionability but cannot establish that an external PID is registered, a repository will retain metadata, or a scientific vocabulary is governed. Those repository-level assertions require publication evidence and periodic audit.

## Academic publication profile

The publication gate is strengthened by `fair-publication-profile.md`. DataTiles separates persistent identifiers, DataCite 4.7 citation metadata, W3C PROV-aligned lineage, SPDX rights, and external repository evidence. Dataset, metadata, and every upstream source MUST have distinct machine-actionable rights records. A public URL is never interpreted as permission. A strict publication report MUST fail when PID, catalogue registration, landing-page evidence, metadata-retention evidence, source rights, source lineage, or community semantics are absent.

FAIR reports expose principle-level outcomes and repository-dependent assertions; they MUST NOT report an unexplained scalar FAIR score.
