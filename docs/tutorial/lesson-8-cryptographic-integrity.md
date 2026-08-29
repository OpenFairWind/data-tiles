# Lesson 8 — Cryptographic integrity and signed releases

This lesson turns a reproducible DataTiles build into an optionally signed research object. Complete the scientific build, citations, licences, provenance, and FAIR release checks **before** signing; every later scientific mutation intentionally invalidates the signature.

## 1. Why a signature is different from a checksum

A SHA-256 checksum identifies bytes or logical content. A digital signature binds a digest to possession of a private key. DataTiles signs a canonical logical manifest so harmless SQLite storage rewrites do not break authenticity while changes to scientific tables do.

Trust remains external: an embedded public key proves only self-consistency. Obtain a trusted public key through an institutional repository, project website, certificate infrastructure, signed Git release, or another independently authenticated channel.

## 2. Install optional signing support

```bash
python -m pip install -e '.[integrity]'
```

The base DataTiles package remains dependency-free; signing support is intentionally optional.

## 3. Inspect the unsigned manifest

```bash
datatiles-integrity manifest gaeta-maratea.datatiles \
  --output gaeta-maratea.integrity.json
```

Inspect `root_sha256`, table row counts, per-table digests, and schema revision. This file is deterministic for the same logical signed domain.

## 4. Generate a release key

For this exercise only:

```bash
datatiles-integrity generate-key \
  --private-key tutorial-release-key.pem \
  --public-key tutorial-release-key.pub.pem
```

Production institutions should use their established key-management policy. Never publish the private key.

## 5. Sign the final object

```bash
datatiles-integrity sign gaeta-maratea.datatiles \
  --private-key tutorial-release-key.pem \
  --signer 'Tutorial publisher' \
  --detached gaeta-maratea.datatiles.sig.json
```

The command stores a signature in the container and creates a detached envelope suitable for a repository release.

## 6. Verify with an independently obtained key

```bash
datatiles-integrity verify gaeta-maratea.datatiles \
  --detached gaeta-maratea.datatiles.sig.json \
  --public-key tutorial-release-key.pub.pem
```

The report must show `cryptographically_valid: true`, `trusted_key_supplied: true`, `content_matches_signed_manifest: true`, and `valid: true`.

Now copy the DataTiles file, modify one metadata value in the copy, and verify again. The signature remains mathematically valid over its historical manifest, but `content_matches_signed_manifest` becomes false. This separation is essential for forensic clarity.

## 7. Connect signer and provenance

Create or reuse a PROV agent representing the responsible person or organization and record its persistent identifier. When signing inside a publication workflow, pass its identifier as `--signer-agent-id`. The agent identity and cryptographic key identity remain distinct.

## 8. Release checklist

A signed scholarly release should archive the DataTiles object, detached signature, trusted public key/certificate reference, source manifest, provenance graph, source-specific citations, rights records, DataCite metadata, strict FAIR report, and any optional Sigstore/timestamp evidence.

A signature is not a navigation approval. The Gaeta-to-Maratea product remains **Not for navigation** regardless of signature status.
