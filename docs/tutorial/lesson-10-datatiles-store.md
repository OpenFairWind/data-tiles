# Lesson 10 — Publish a DataTiles catalog with the Store PWA

This lesson turns a directory of finalized DataTiles products into an authenticated searchable catalog and interactive browser.

## 1. Install the Store

From the repository root:

```bash
cd store
python -m pip install -e .
```

Edit `store/config.py`. At minimum replace `SECRET_KEY` and `ADMIN_PASSWORD`, and point `CATALOG_DIR` to the directory containing released DataTiles files.

## 2. Understand the trust boundary

The Store SQLAlchemy database is not a scientific database. It contains identity/authorization state and a rebuildable metadata search index. Published `.datatiles` files remain the authoritative research objects and are opened read-only.

This matters for revision-6 signatures: rescanning the Store must not mutate a signed file and must not change its canonical manifest.

## 3. Start the PWA

```bash
python run.py
```

Open `http://localhost:8080` and sign in with the configured bootstrap administrator. On the first initialization the account is assigned through:

```text
admin user -> administrators group -> admin role -> all permissions
```

## 4. Add products

Copy finalized DataTiles files under `CATALOG_DIR` and choose **Rescan catalog**, or upload a file while authenticated with `catalog.manage` permission.

The indexer extracts metadata, CF semantic variables, rights/licence records, provenance summaries, bounds, zoom levels, signature records and public commercial metadata. Search therefore works for queries such as a DOI, `sea_floor_depth_below_geoid`, a rights holder, an SPDX licence expression or a source label.

## 5. Explore a product

Select **Explore**. The browser provides pan/zoom, coverage fitting, a portrayal-layer toggle, variables, rights/citation, provenance and metadata panels.

DataTiles stores TMS rows while web clients use XYZ. The Store converts only at the HTTP interface. A PNG/JPEG/WebP selected compatibility slice is displayable. A DNT1 scientific matrix is not guessed into colors: prepare/select a declared portrayal profile when a preview is required.

The permanent **Not for navigation** notice remains visible for the reference workflow.

## 6. Add users and groups

The built-in roles provide progressively broader permissions. Create groups such as `researchers`, `customers`, or `publishers`, assign the appropriate roles, then create users in those groups. Do not create authorization checks based on hard-coded usernames.

## 7. Deploy as a PWA safely

The service worker makes the user interface installable but does not cache APIs, map payloads or file downloads. In production place Flask behind HTTPS, enable secure session cookies, keep the secret key and bootstrap password in a secret manager, and use a production WSGI server.

## 8. Commercial products

The Store is not the revision-7 DRM entitlement server. For proprietary products, keep content keys and customer private material in a dedicated KMS/licence service. Catalog metadata may advertise the product, issuer and terms, while actual authorization/decryption remains an independently secured subsystem.

## 9. Publication checklist

Before exposing any product, verify that its source-specific citation, rights, FAIR metadata, provenance and optional signature evidence are complete. Download authorization cannot cure a missing attribution or incompatible upstream licence, and an interactive preview does not certify the data for navigation.

## 10. Require explicit licence and safety acceptance

Open a product as a user with download permission. The Store shows the rights extracted from the DataTiles release together with the configured **not suitable for navigation / AS IS / limitation-of-responsibility** agreement. Preview and download remain unavailable until both checkboxes are explicitly accepted.

The acceptance is version-specific. Replace the file with a different release and observe that the old acceptance no longer authorizes access because the SHA-256 changed. The same happens when embedded rights change or the operator advances `SAFETY_AGREEMENT_VERSION`.

A third-party client performs the same workflow:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"customer","password":"a-long-customer-password"}' | jq -r .access_token)

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/catalog/1/agreement

curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"accept_license":true,"accept_safety":true}' \
  http://localhost:8080/api/v1/catalog/1/agreement/accept

curl -L -H "Authorization: Bearer $TOKEN" \
  -o product.datatiles \
  http://localhost:8080/api/v1/catalog/1/download
```

## 11. Use the managers group for DataTiles CRUD

The Store automatically creates the configured `managers` group with the `catalog_manager` role. Add a publishing user to this group. That user can upload a new DataTiles product, replace an existing release atomically, rename the stored file, or delete it.

Equivalent API calls use `POST /api/v1/catalog`, `PUT /api/v1/catalog/{id}/file`, `PATCH /api/v1/catalog/{id}`, and `DELETE /api/v1/catalog/{id}`. The API enforces the same permissions as the browser.

Do not use CRUD to rewrite the scientific SQLite object in place. Build/finalize/sign a new release first, then replace the catalog asset. This preserves the distinction between scholarly provenance and distribution operations.

## 12. Treat the API as the integration contract

Use `/api/v1/openapi.json` for machine discovery. Third-party portals, desktop GIS/MFD applications, institutional repositories and commercial entitlement frontends should integrate through the API rather than scraping HTML. Bearer tokens resolve to ordinary users and inherit exactly the roles granted through their groups.

The Store audit endpoint records operational actions such as agreement acceptance, downloads, uploads, replacements and deletes. Keep this audit database protected and retained according to institutional privacy/records policies; it is not a replacement for source provenance inside DataTiles.

## Identity integration and administrator configuration

The Store can use managed passwords, verified-email registration, Google OpenID Connect, Microsoft Entra ID tenants, or a generic OAuth2/OpenID Connect provider. Open the administrator **Configuration** section to enable providers, enter client credentials, configure the public callback URL and SMTP delivery, and choose whether new-user registration is allowed. All external identities still map into the same Store groups/roles; SSO is authentication, not automatic administrative authorization.

The complete operational manual is available inside the PWA **Help** section from the Markdown sources under `store/docs/`. Use `/api/v1/configuration`, `/api/v1/auth/providers`, `/api/v1/register`, and `/api/v1/help` when integrating infrastructure or third-party clients.

## 13. Publish versioned releases

Schema revision 8 adds `DataTiles-Release-Versioning-1`. Each release may declare a stable `product_id`, a human-facing `version`, a monotonically increasing integer `sequence`, `released_at`, and optional predecessor/release-notes/update links. Use `sequence` for ordering; do not sort arbitrary version strings lexically.

A published version is immutable. Corrections and updates are new DataTiles files with a larger sequence, a new checksum, and a new signature when cryptographic signing is used. The Store indexes release metadata and can identify successors without rewriting historical files.

## 14. Configure optional payments

Open **Configuration → Commerce / PayPal** as an administrator. Payment is disabled by default. Enable commerce, select the provider, and configure the PayPal reference adapter in sandbox mode first. The PayPal implementation uses server-side OAuth credentials and Orders v2; client secrets never enter DataTiles files or browser JavaScript.

Managers can mark a catalog release as purchase-required and assign price/currency. Licence/safety acceptance and payment entitlement are separate gates: payment never overrides an upstream licence or acknowledgement obligation.

Third-party clients can discover the provider and create/capture checkout transactions using:

```text
GET  /api/v1/payments/providers
POST /api/v1/catalog/{id}/checkout
POST /api/v1/payments/{transaction_id}/capture
```

## 15. Use My Library and update notifications

Every successful Store download is recorded with the exact release and SHA-256. Completed paid transactions create release-specific purchase records. Users can inspect both histories in **My Library** or with `GET /api/v1/library`.

When a higher `sequence` of the same stable `product_id` is indexed, users who previously purchased or downloaded an older release can receive an update notification. The notification is only discovery evidence: it does not automatically transfer a paid entitlement to the newer release.
