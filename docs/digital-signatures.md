# Cryptographic integrity and digital signatures

DataTiles supports **optional** digital signatures as an integrity and authenticity layer. Signatures complement, but do not replace, checksums, provenance, persistent identifiers, licences, repository preservation, or scientific validation.

## Threat model and claims

A cryptographic hash answers: *are these logical DataTiles contents identical to the contents that produced this digest?* A digital signature additionally answers: *was that digest signed by the holder of a particular private key?* Neither statement, by itself, establishes who the human or institution behind the key is. Trust requires an independently authenticated public key, certificate, institutional key registry, Sigstore identity, or another trust policy.

The native DataTiles profile signs a canonical **logical SQLite manifest**, not raw database bytes. This deliberately survives SQLite page layout, VACUUM, journaling, and other byte-level storage changes that do not alter the represented DataTiles content. It detects changes to signed tables, values, schema definitions, views, and triggers. The two integrity/signature tables are excluded to avoid circular self-signing.

## Native profile

- manifest profile: `DataTiles-Integrity-Manifest-1`
- canonicalization: `datatiles-sqlite-logical-v1`
- digest: SHA-256
- native signature: Ed25519
- signature envelope: `DataTiles-Ed25519-Signature-1`
- payload media type: `application/vnd.openfairwind.datatiles.integrity-manifest.v1+json`

Ed25519 is specified by RFC 8032 and is included by NIST FIPS 186-5. The native signer is an optional dependency so the dependency-free DataTiles core remains usable without cryptography packages.

## What is signed

The manifest records schema revision and, for every non-integrity user table, a normalized schema digest, row count, and deterministic digest of the complete row multiset. Views and triggers are also schema-hashed. Each SQLite value is type-tagged before hashing; REAL values are represented by their IEEE-754 binary64 bit pattern and BLOB values by their exact bytes.

Rows are independently SHA-256 hashed and externally sorted in bounded chunks before the table digest is produced. Consequently database row order is irrelevant, duplicate multiplicity is retained, and large tile tables do not require all row hashes in memory.

`datatiles_integrity_manifests` and `datatiles_signatures` are excluded from the signed domain. Adding or removing signatures therefore does not invalidate the scientific object they attest.

## Key generation and signing

Install the optional cryptographic support:

```bash
python -m pip install -e '.[integrity]'
```

Generate an Ed25519 key pair:

```bash
datatiles-integrity generate-key \
  --private-key release-signing-key.pem \
  --public-key release-signing-key.pub.pem
```

The private key is PKCS#8 PEM and should be protected as a secret. The tool attempts to create it with owner-only permissions. Do not commit private keys to Git, release archives, containers, notebooks, or DataTiles files.

Sign a final container and also emit a detached envelope:

```bash
datatiles-integrity sign product.datatiles \
  --private-key release-signing-key.pem \
  --signer 'Ocean Data Laboratory' \
  --detached product.datatiles.sig.json
```

The signature may be stored inside the DataTiles object, emitted as a detached JSON envelope, or both. Detached signatures are useful for read-only repositories and archival systems.

## Verification and trust

Cryptographic verification with only the public key embedded in a signature proves self-consistency, **not signer trust**. A scholarly verification should supply a public key obtained independently:

```bash
datatiles-integrity verify product.datatiles \
  --detached product.datatiles.sig.json \
  --public-key trusted-release-key.pub.pem
```

For automated release gates, pin the expected key identifier too:

```bash
datatiles-integrity verify product.datatiles \
  --signature-id urn:uuid:... \
  --public-key trusted-release-key.pub.pem \
  --require-key-id sha256:...
```

Verification reports separately:

- cryptographic validity of the signature;
- whether a trusted external key was supplied;
- whether the current DataTiles logical contents match the signed manifest;
- signer/key metadata and the signed root digest.

Software MUST NOT convert “signature valid using its embedded key” into “trusted publisher”.

## Provenance integration

A signature can reference a `datatiles_provenance_agents` record through `signer_agent_id`. The agent identity should use an institutional URI, ORCID, ROR, or another persistent identifier when appropriate. The cryptographic key identifier and the scholarly agent identifier are separate facts and MUST NOT be conflated.

Signing is a provenance activity performed **after** the final scientific build, rights evaluation, citation resolution, and release metadata freeze. NetCDF, GRIB2, and Zarr import utilities therefore do not auto-sign intermediate outputs. Release automation should sign only after all intended mutations have completed.

## Sigstore and in-toto interoperability

The native profile is offline-first. Publication pipelines MAY additionally publish a Sigstore bundle or an in-toto/DSSE attestation referencing the DataTiles manifest root. Such external evidence can provide certificate identity, transparency-log inclusion, and/or trusted timestamps. It must be recorded as verification material or publication evidence; it does not change the native DataTiles manifest digest.

A Sigstore bundle should be archived with the release rather than requiring future network access for basic DataTiles verification. Keyless signatures require identity-policy verification (issuer and subject), not merely mathematical signature checking.

## FAIR and preservation

Digital signatures strengthen integrity and provenance evidence, particularly reproducibility and chain-of-custody assertions, but they are not a FAIR principle by themselves and remain optional. `fair_report()` must never fail solely because a DataTiles object is unsigned. A release profile may establish a stricter institutional policy requiring a trusted signature.

For long-term preservation, archive together:

1. the DataTiles object;
2. detached signature envelope(s), if used;
3. trusted public key/certificate or durable reference to it;
4. any Sigstore bundle, RFC 3161 timestamp, or transparency evidence;
5. PID/DataCite metadata, source manifests, citations, rights, and provenance.

Key rotation is expected. Historical signatures must remain verifiable with archived historical public keys. Revocation affects trust policy, not the immutable mathematical fact that a given key produced a signature.

## Non-goals

A valid signature does not certify hydrographic authority, navigation safety, correctness of a model, correctness of source data, licence compatibility, or fitness for purpose. It proves integrity/authenticity only within the verifier's explicit trust policy.

## Sign before protecting

When both integrity signatures and DRM are used, finalize and sign the plaintext DataTiles object first, then create the protected `.dtpkg`. The DRM header binds to the plaintext SHA-256. This makes the signed scientific object stable and allows authorized recipients to verify the recovered DataTiles independently of the transport/access-control wrapper.
