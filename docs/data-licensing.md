# Data licensing and rights

DataTiles never infers legal permission from technical accessibility. A URL that returns bytes establishes transport, not a licence.

Each imported source MUST have a `source` rights record bound to its provenance entity. Each publishable object MUST separately declare `dataset` and `metadata` rights. Records contain an SPDX expression, authoritative terms URI, attribution, access classification, optional rights holder and the scope to which the terms apply.

The converter utilities therefore require `--source-license`, `--source-license-uri`, `--source-attribution`, `--dataset-license`, and `--dataset-license-uri`. This forces the operator to make the legal basis explicit before ingestion. Use `LicenseRef-*` for proprietary, bespoke, or otherwise non-SPDX terms; do not guess a standard licence.

Licensing compatibility is a legal/policy determination and is deliberately not automated by DataTiles. The software can validate that records exist and are syntactically machine actionable; it cannot decide whether combining two sources is legally permissible. Publication workflows SHOULD include a human rights review and retain its decision outside credentials/secrets.

Attribution displayed in a playground is a convenience, not the sole legal record. The complete source-rights manifest travels with the DataTiles object and publication evidence.

## Signatures do not alter rights

Digital signatures attest integrity/authenticity; they do not grant copyright permission, sublicense upstream datasets, or resolve licence compatibility. Rights evaluation must be complete before a release is signed, and any later rights correction produces a new manifest and therefore requires a new signature.

## Commercial licensing and DRM

Commercial DRM may enforce an access grant only after the publisher has established the legal right to commercialize every contributing source. W3C ODRL policy and a DataTiles commercial licence are additional machine-readable/access-control layers; they do not replace SPDX/source rights records and cannot narrow attribution or other mandatory upstream notices invisibly.
