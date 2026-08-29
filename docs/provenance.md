# Scientific provenance

DataTiles provenance follows the W3C PROV entity-activity-agent model and keeps tile-level lineage. Provenance must answer: **what bytes or observations were used, who/what acted, what transformation occurred, with which parameters/software, and what was generated?**

Source entities SHOULD have stable PID/URI, release/version, SHA-256 (or stronger approved digest), acquisition time, request identity and source-kind attributes. Activities SHOULD record start/end timestamps, software package/version or SWHID, configuration digest, resampling/interpolation, CRS operations, masks, quality filters and deterministic/random seeds. Agents SHOULD use ORCID for persons and ROR or another governed organizational identifier where available.

The provenance graph must distinguish evidence from assertion. A checksum verifies bytes. A citation identifies intellectual origin. A licence states terms. A quality report supports scientific validity. None substitutes for the others.

`prov_json()` exports the graph with explicit W3C PROV namespace mappings. For publication, validate the graph for dangling identifiers, source coverage, generated-entity links and activity-agent associations, then archive the export beside the artifact manifest.

## Signing as a provenance activity

Signing occurs only after the final reproducible build is frozen. The signer key identifier and scholarly PROV agent are separate identifiers. A valid signature may establish that a key attested a particular immutable manifest; attribution to a person or organization requires an external trust binding. Key rotation and revocation policy belong to the publishing institution and must not rewrite historical provenance.

## DRM provenance boundary

The commercial product ID, edition, issuer, terms URI, and public ODRL policy may be provenance-relevant and are part of the signed inner DataTiles object. Content keys, recipient private keys, licence-signing private keys, payment data, bearer tokens, and other secrets are operational security material and MUST NOT enter the scholarly provenance graph.
