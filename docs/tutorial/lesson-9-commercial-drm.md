# Lesson 9 — Commercial distribution and DRM

This lesson shows how a lawful proprietary DataTiles release can add technical access control without weakening FAIR metadata, provenance, licensing, citation, or cryptographic integrity.

## 1. Decide whether commercial distribution is legally permitted

Before encryption, inspect every source rights record and the frozen contribution manifest. The ability to encrypt a derivative does not grant commercial redistribution rights. Resolve attribution, share-alike, database rights, non-commercial restrictions, and contractual terms first.

## 2. Register the product and policy

Give the inner DataTiles object a stable product ID, publisher identity, edition, terms URI, optional licence-service URI, and machine-readable ODRL policy. Keep these facts inside the signed logical object so that policy metadata cannot be silently changed without invalidating the DataTiles integrity signature.

## 3. Freeze and optionally sign

Run FAIR/provenance/licensing checks, freeze the product, and optionally sign it with `datatiles-integrity`. The signature authenticates the exact scientific release; DRM comes afterward as a distribution wrapper.

## 4. Protect the product

Use `datatiles-drm protect`. The command generates a fresh AES-256 content key, encrypts the entire DataTiles file with authenticated encryption, records the plaintext SHA-256 in the authenticated package header, and writes the publisher content key to a restricted file. Move that secret to institutional key management as soon as practical.

## 5. Provision a recipient

Each recipient/device has an X25519 keypair. Only the public key is supplied to the publisher. The private key stays with the customer/device.

## 6. Issue a licence

The publisher wraps the content key to that recipient and signs the licence with its Ed25519 issuer key. The licence can include validity dates, a recipient identifier, technical permissions, and an ODRL policy. The same encrypted `.dtpkg` can therefore be distributed once while issuing different recipient-specific grants.

## 7. Verify and decrypt

The client verifies the issuer signature using an independently authenticated publisher public key, checks time/product/hash/recipient binding, unwraps the content key, authenticates/decrypts the package, and verifies the recovered DataTiles SHA-256.

## 8. Understand the limits

Portable DRM cannot guarantee that an authorized client will never copy plaintext. It protects distribution and access, not post-decryption behavior. Never market DRM as scientific certification, FAIR certification, copyright ownership, or navigation safety.

## Exercise

Create a small DataTiles release, sign it, protect it once, issue two licences for two recipient public keys, verify that each recipient can decrypt using only its own private key, and demonstrate that a licence copied to the other recipient fails. Then expire one licence and verify that decryption is denied.
