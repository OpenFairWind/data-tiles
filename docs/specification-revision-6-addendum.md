# DataTiles 1.0-draft — schema revision 6 addendum: cryptographic integrity

This addendum extends schema revision 5 with optional integrity manifests and digital signatures. All revision-5 scientific, semantic, FAIR, provenance, licensing, and MBTiles-compatibility requirements remain unchanged.

## New tables

`datatiles_integrity_manifests` stores canonical logical manifests. Each manifest declares its profile, canonicalization, hash algorithm, SHA-256 root, canonical JSON representation, and creation time.

`datatiles_signatures` stores one or more signatures over a recorded manifest. Native signatures use Ed25519 and may embed the raw public key required for self-contained mathematical verification. `signer_agent_id` MAY link the signature to a PROV agent. `verification_material_json` MAY retain additional certificate, transparency-log, timestamp, or external trust material.

The signature tables are intentionally outside the canonical signed domain. Signature insertion/removal MUST NOT change the manifest root of otherwise identical scientific content.

## Canonical integrity manifest

Conforming implementations of `DataTiles-Integrity-Manifest-1` MUST:

1. hash the logical SQLite object rather than raw database bytes;
2. include the DataTiles schema revision;
3. include every user table except `datatiles_integrity_manifests` and `datatiles_signatures`;
4. include normalized schema definitions for those tables and definitions for user views/triggers;
5. preserve SQLite value types and exact BLOB bytes in row canonicalization;
6. preserve the IEEE-754 binary64 representation of REAL values;
7. make table row order irrelevant while preserving duplicate multiplicity;
8. use SHA-256 for row, table, schema, and root digests;
9. serialize manifest JSON with UTF-8, lexicographically sorted object keys, no insignificant whitespace, and no NaN/Infinity JSON numbers.

The normative implementation profile is documented in `digital-signatures.md`.

## Signature profile

`DataTiles-Ed25519-Signature-1` signs the complete canonical manifest JSON, including its verified `root_sha256`. The signature record MUST identify its algorithm and key identifier. The key identifier is `sha256:` followed by the lowercase SHA-256 digest of the 32-byte raw Ed25519 public key.

Verification MUST distinguish mathematical validity from trust. An embedded public key is sufficient for cryptographic verification but is not, by itself, evidence that the key belongs to a claimed person or institution.

## Migration

Revision 5 containers migrate to revision 6 by adding the two tables and profile metadata. Existing content remains unsigned. Migration MUST NOT invent signatures, signer identities, timestamps, or trust assertions.

## HTTP and playground

Servers MAY expose read-only integrity/signature metadata. They MUST NOT expose private keys and SHOULD NOT provide remote signing endpoints. Because full manifest recomputation may require reading every tile, interactive services SHOULD avoid implicit full verification on every request; verification belongs in release/validation workflows or explicitly requested operations.

## FAIR relationship

Digital signatures are optional enhanced evidence. Unsigned DataTiles can still satisfy the FAIR publication profile. A FAIR report MAY disclose signature presence, but MUST NOT conflate a signature with FAIRness, scientific validity, legal compliance, or safety certification.
