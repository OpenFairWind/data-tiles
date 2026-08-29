# DataTiles 1.0-draft — schema revision 7 addendum

## Commercial product metadata

Revision 7 adds `datatiles_commercial_products` and `datatiles_drm_policies`. These tables are part of the canonical scientific object and therefore are covered by `DataTiles-Integrity-Manifest-1` when the object is signed.

`datatiles_commercial_products` identifies a commercial edition, publisher/issuer, human-readable terms URI, optional licence-service URI, and protection profile. `datatiles_drm_policies` stores machine-readable policy documents; the default policy profile is W3C ODRL 2.2.

These tables MUST NOT contain plaintext content-encryption keys, customer private keys, passwords, payment credentials, access tokens, or other secrets.

## Protected distribution

`DataTiles-Protected-Distribution-1` is an optional outer distribution format and does not replace the SQLite DataTiles format. A `.dtpkg` contains a public canonical JSON header plus AES-256-GCM ciphertext of one complete finalized DataTiles file and the GCM authentication tag. The public header is authenticated additional data and binds ciphertext to the product identity and plaintext SHA-256.

Authorized decryption MUST reproduce the exact original DataTiles bytes and MUST verify the stored SHA-256 before releasing the result as valid.

## Licence grants

`DataTiles-Commercial-License-1` is an issuer-signed JSON envelope. The native portable profile uses Ed25519 signatures and X25519 recipient keys. The content key is wrapped with a product-bound HKDF-SHA-256 derived key and AES-256-GCM.

Implementations MUST distinguish:

1. cryptographic validity of the issuer signature;
2. external trust in the issuer public key;
3. recipient-key binding;
4. validity-period enforcement;
5. product/hash binding;
6. legal rights expressed by the dataset licence and ODRL/human-readable terms.

A valid DRM licence MUST NOT be interpreted as evidence that upstream data may lawfully be sold or redistributed.

## Services

The standard read-only DataTiles HTTP service MAY expose non-secret commercial product metadata and ODRL policies from an authorized plaintext DataTiles object. It MUST NOT expose publisher content keys, recipient private keys, licence signing keys, or a standard endpoint that bypasses protected-distribution authorization.

Online purchase, payment, account management, revocation, floating licences, device activation, and remote attestation are deployment-specific services outside the normative portable profile.
