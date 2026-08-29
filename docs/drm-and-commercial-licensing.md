# Optional DRM and commercial licensing

DataTiles supports an optional protected-distribution profile for institutions and companies that are legally entitled to sell proprietary cartographic or scientific products. DRM is a distribution control, not a substitute for copyright ownership, source licensing, attribution, provenance, FAIR metadata, or scientific validation.

## Separation of concerns

A DataTiles object remains an ordinary revision-7 SQLite scientific object. Publishers finalize its semantics, provenance, rights, citations, QA, and optional digital signatures first. Commercial distribution then wraps that immutable file in `DataTiles-Protected-Distribution-1` (`.dtpkg`). Authorized recipients decrypt the package back to the exact original bytes.

The legal licence and technical entitlement are distinct. `datatiles_rights` and human-readable terms state the legal basis. W3C ODRL 2.2 can encode machine-readable permissions, prohibitions, constraints, and duties. The DRM licence token only conveys an issuer-signed access grant and a recipient-wrapped content-encryption key; it does not create rights the publisher does not already possess.

## Cryptographic profile

- content encryption: AES-256-GCM;
- package nonce: fresh random 96-bit nonce per protected package;
- recipient key agreement: X25519;
- key derivation: HKDF-SHA-256 with product-specific context;
- content-key wrapping: AES-256-GCM;
- licence issuer signature: Ed25519;
- product and key identifiers: SHA-256 based identifiers;
- public policy model: W3C ODRL 2.2.

Private content keys and recipient private keys MUST NOT be embedded in the DataTiles object, package header, provenance graph, demo, playground, source repository, or licence token. Publisher content-key files are generated with restrictive filesystem permissions and should normally be moved into a KMS/HSM or equivalent institutional secret-management system.

## Package and licence binding

Each protected package carries a public, authenticated header containing the product identifier, edition, issuer, terms URI, optional licence-service URI, encryption profile, creation time, original DataTiles SHA-256, and original size. The header is authenticated as AES-GCM associated data.

Each licence is bound to:

- the exact `product_id`;
- the exact plaintext DataTiles SHA-256;
- a recipient X25519 public-key identifier;
- an issuer Ed25519 key identifier;
- optional validity start/end times;
- an explicit list of technical permissions;
- an optional ODRL 2.2 policy document.

The content key is never sent in plaintext. It is wrapped to the recipient public key using an ephemeral X25519 key and HKDF-derived wrapping key. A copied licence therefore does not unlock the product for a different recipient key.

## Threat and trust model

This profile protects data at rest and in distribution and provides cryptographic evidence of issuer authorization. It cannot prevent an authorized user or compromised client from copying plaintext after decryption, photographing/rendering displayed information, or extracting data from a process with sufficient privileges. Stronger controls may use secure enclaves, platform key stores, HSM-backed device identities, remote attestation, or online authorization, but these are deployment profiles rather than requirements of the portable DataTiles format.

The issuer public key must be authenticated independently. A mathematically valid licence signed by an unknown key is not evidence that a particular company or institution authorized access.

## Commercial-law and upstream-rights rule

A publisher MUST NOT commercialize a derivative merely because DataTiles can encrypt it. Every contributing source must permit the intended commercial use and redistribution, all attribution/share-alike/database-right obligations must be satisfied, and incompatible upstream terms must block the commercial release. DRM MUST NOT be used to remove, conceal, contradict, or technically frustrate licence notices that must remain available to recipients.

## Workflow

1. Build the DataTiles object from lawful sources.
2. Preserve source citations, provenance, source licences, and commercial-use evidence.
3. Register the commercial product and ODRL policy in the inner DataTiles object.
4. Complete scientific QA and FAIR checks.
5. Optionally sign the canonical DataTiles integrity manifest.
6. Freeze the release.
7. Protect the exact frozen file into `.dtpkg` and securely retain the generated content key.
8. Generate or obtain each customer's X25519 public key.
9. Issue an issuer-signed licence for that recipient and product.
10. Deliver the package plus licence; distribute the issuer public key through an authenticated channel.

## CLI example

```bash
python -m pip install -e '.[drm,integrity]'

datatiles-drm protect product.datatiles product.dtpkg \
  --content-key-file product.cek.json \
  --product-id urn:example:charts:med-2026 \
  --issuer 'Example Hydrographic Publisher' \
  --terms-uri https://example.org/licence/med-2026

datatiles-drm generate-recipient-key \
  --private-key customer.key \
  --public-key customer.pub.pem

datatiles-drm issue-license product.dtpkg \
  --content-key-file product.cek.json \
  --recipient-public-key customer.pub.pem \
  --issuer-private-key publisher-ed25519.pem \
  --issuer 'Example Hydrographic Publisher' \
  --recipient-id customer-123 \
  --permission read \
  --output customer-123.license.json

datatiles-drm decrypt product.dtpkg product.datatiles \
  --license customer-123.license.json \
  --recipient-private-key customer.key \
  --issuer-public-key publisher-ed25519.pub.pem
```

## FAIR compatibility

FAIR does not mean free-of-charge or unrestricted. Restricted/proprietary DataTiles can remain FAIR when metadata, identifiers, access conditions, provenance, vocabulary semantics, and licence terms are sufficiently machine-readable and persistent. Public discovery metadata should remain available even when data access requires purchase or authorization. DRM status must never be reported as a FAIR score, quality score, hydrographic certification, or navigation-safety claim.
