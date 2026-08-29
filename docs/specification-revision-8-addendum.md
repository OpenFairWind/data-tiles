# DataTiles schema revision 8 addendum: release versioning

## Status

This addendum defines the normative `DataTiles-Release-Versioning-1` profile. A DataTiles file represents one immutable scientific release. Versioning identifies successive releases of the same logical product; it does not mutate an old signed release in place.

## Stable product identity and release identity

A revision-8 container MAY contain exactly one row in `datatiles_release`. When present, `product_id`, `version`, `sequence`, and `released_at` are REQUIRED. `product_id` MUST remain stable across releases of the same logical product and SHOULD be a persistent URI/URN/DOI concept identifier under publisher control. `version` is the human-facing release label and MAY use Semantic Versioning, calendar versioning, an institutional scheme, or another documented scheme.

`sequence` is the normative ordering field. It MUST be a positive integer, MUST increase for each published successor of the same `product_id`, and MUST NOT be reused for a different release. Consumers MUST NOT infer ordering from lexical comparison of `version`. `released_at` MUST be an RFC 3339 timestamp.

Optional `previous_version` and `previous_identifier` fields link the release to its predecessor. `release_notes_uri` SHOULD identify a human-readable changelog. `update_uri` MAY identify a catalogue/API endpoint where successors can be discovered.

## Immutability

A new scientific release MUST be represented by a new DataTiles object with a new checksum and, where signing is used, a new integrity manifest/signature. Replacing bytes underneath an already published version is non-conforming. Corrected products MUST increment `sequence` and use a new release label.

## Provenance, citation, and Store update discovery

Version metadata complements, but never replaces, provenance, persistent identifiers, rights, source citation, and integrity evidence. A citation SHOULD identify the exact release used. A Store MAY notify users who accessed an older sequence when a larger sequence for the same `product_id` is published. Such notification does not by itself grant entitlement to the new release.
