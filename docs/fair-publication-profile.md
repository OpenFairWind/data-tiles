# DataTiles FAIR scientific publication profile

## Status and normative intent

This profile operationalizes the FAIR Guiding Principles for DataTiles scientific objects. It does **not** equate FAIR with open access, quality, truth, or fitness for a safety-critical purpose. The original FAIR principles require persistent identity and rich metadata (F1-F4), standardized access (A1-A2), formal shared semantics and qualified links (I1-I3), and explicit licence, provenance, and community standards (R1-R1.3). DataTiles therefore treats FAIRness as verifiable evidence, not a marketing score.

Normative references are Wilkinson et al. (2016), W3C PROV-O/PROV-DM, DataCite Metadata Schema 4.7 (2026), SPDX 3.0.1 license expressions, CF Standard Names for scientific quantities, EPSG/OGC CRS identifiers, and domain vocabularies such as NERC NVS where applicable.

## Publication invariants

A DataTiles object intended for scholarly publication MUST satisfy all locally testable requirements below and MUST carry external publication evidence for repository-level assertions.

1. **Identity.** The published object/revision has one explicit primary globally unique persistent identifier. DOI is RECOMMENDED for citable research datasets; Handle, ARK or another governed PID is acceptable. A mutable project URL is not a substitute for a versioned PID.
2. **Metadata.** Title, creators/contributors, publisher, publication year, spatial/temporal coverage, variables, units, CRS/datum, resolution, uncertainty/quality limitations, content profiles and version are machine readable. A DataCite 4.7-shaped export is available without claiming registration.
3. **Semantics.** Scientific variables use CF Standard Names when a suitable term exists, canonical units are declared, and external vocabulary mappings are retained. No local name is silently promoted to a CF term.
4. **Provenance.** Sources are immutable entities identified by URI/PID plus cryptographic digest where bytes are available. Transformations are activities with software identity/version, parameters and timestamps. Agents are explicit. Relations map to W3C PROV semantics. Tile lineage points to source/derived entities.
5. **Rights.** Dataset rights, metadata rights and every source dataset's rights are distinct records. SPDX expressions are used for machine-actionable licence identity; authoritative licence/terms URIs, attribution text, rights holder where known, and access-rights classification are retained. Public HTTP access MUST NOT be interpreted as permission to redistribute.
6. **Integrity and reproducibility.** Source locks, runtime locks, deterministic parameters, artifact manifests and checksums are retained. A checksum proves byte identity, not scientific validity.
7. **Accessibility.** The PID/landing page uses an open standardized protocol. Authentication/authorization may be required. Metadata persistence after data withdrawal is a repository obligation and requires evidence such as a preservation/retention policy.
8. **Indexing.** Catalogue/registry deposit is externally evidenced. The SQLite file cannot prove F4 by itself.
9. **Qualified links.** Source datasets, software, papers, previous/new versions, supplements and derived objects use typed related identifiers aligned with DataCite relation types.
10. **Limitations.** Known uncertainty, exclusions, transformations, resolution limits, licensing restrictions and safety boundaries remain visible in documentation and machine-readable metadata.

## FAIR report semantics

`fair_report(strict_publication=False)` evaluates facts the container can establish and labels repository-dependent checks as external. `strict_publication=True` makes missing catalogue registration, landing-page evidence and metadata-retention evidence publication blockers. A report MUST expose each principle-level result; implementations MUST NOT collapse FAIRness into an unexplained percentage.

## Licensing model

DataTiles distinguishes at least three legal layers:

- **software licence**: governs the DataTiles implementation, not automatically the data;
- **dataset licence**: governs the generated scientific object;
- **source licences**: govern each upstream source and may impose attribution, share-alike, database-right or redistribution obligations.

Metadata has its own rights record. CC0-1.0 is RECOMMENDED for newly authored machine-readable metadata where the publisher has authority to dedicate it, but DataTiles MUST NOT override third-party rights embedded in metadata or attribution requirements inherited from sources.

Composite rights use valid SPDX expressions such as `CC-BY-4.0`, `ODbL-1.0`, or `(LicenseRef-A AND LicenseRef-B)`. Custom/non-SPDX terms use a stable `LicenseRef-*` plus the authoritative terms URI. The dependency-free core validates expression syntax; CI/publication SHOULD validate identifiers against a pinned SPDX License List release.

## Provenance model

The internal graph is PROV-aligned:

- `datatiles_provenance_entities` -> `prov:Entity`;
- `datatiles_provenance_activities` -> `prov:Activity`;
- `datatiles_provenance_agents` -> `prov:Agent`;
- `wasGeneratedBy`, `used`, `wasDerivedFrom`, `wasAttributedTo`, `wasAssociatedWith`, `specializationOf` retain their W3C PROV meanings.

A conversion SHOULD create a source entity, conversion activity, generated dataset entity, software agent and responsible agent, then connect them with `used`, `wasGeneratedBy`, `wasAssociatedWith`, `wasAttributedTo`, and `wasDerivedFrom`. Parameters MUST include resampling, CRS transformation, masking, classification/fusion rules and all values capable of changing scientific output.

## DataCite alignment

DataTiles 0.12 targets DataCite Metadata Schema 4.7 for publication export. The export is a candidate deposit record, not proof of DOI registration. `datatiles_related_identifiers` retains typed scholarly links. DataCite 4.7 added RAiD and SWHID identifier types and a general `Other` relation type; use more specific relation types whenever possible.

## Minimum release evidence

A scholarly release SHOULD archive: the `.datatiles` object; SHA-256 manifest; source lock; source-rights manifest; runtime/software lock; configuration; PROV export; DataCite metadata export; validation/FAIR report; citation metadata; quality-control results; and, where redistribution permits, immutable raw inputs. If raw bytes cannot legally be redistributed, preserve checksums, PIDs/request identity, rights metadata and a lawful reacquisition procedure instead.

## Optional cryptographic release evidence

A DataTiles release MAY include a revision-6 integrity manifest and one or more trusted digital signatures. Signature absence MUST NOT make the FAIR report fail: FAIRness and cryptographic authenticity are distinct properties. When signatures are used, archive the detached envelope, independently authenticated public key/certificate, signer PROV-agent binding, and any timestamp/transparency evidence with the publication package.

## Restricted and commercial access

FAIR does not require that every dataset be free or anonymously downloadable. A restricted/proprietary DataTiles release may use the revision-7 DRM profile while retaining public persistent identifiers, rich metadata, source-specific citation, provenance, interoperable semantics, and explicit access conditions. DRM presence or absence is not a FAIR criterion by itself.
