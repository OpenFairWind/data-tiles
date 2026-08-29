# DataTiles Store: institutional catalog and PWA

The optional `/store` application turns a directory of DataTiles releases into a searchable institutional catalog without changing the scientific objects themselves. It is implemented in Python/Flask and uses SQLAlchemy 2.x for all application-database persistence.

## Architectural separation

There are two databases with deliberately different purposes:

1. **DataTiles containers** are immutable or publication-controlled SQLite scientific objects. The store opens them read-only to extract metadata and to serve a selected compatibility portrayal.
2. **The Store database** is an application database managed through SQLAlchemy. It contains users, groups, roles and a denormalized searchable catalog index. It does not become part of the scholarly DataTiles provenance chain.

This separation avoids accidental modification of published checksums/signatures and permits the catalog index to be rebuilt at any time from authoritative DataTiles files.

## Catalog discovery and indexing

A scan walks `CATALOG_DIR`, opens candidate SQLite files through SQLAlchemy in read-only/query-only mode, and extracts ordinary MBTiles metadata plus DataTiles-specific metadata when present: schema revision, semantic variables/CF names, structured rights, provenance entities/activities, integrity signatures, commercial-product metadata, bounds and zoom ranges. Search operates over this extracted index, not over raw tile payloads.

The catalog records a SHA-256 of each stored file for operational identity. This is separate from revision-6 logical integrity manifests and signatures, whose semantics remain authoritative for signed scholarly releases.

## Explorer

The explorer presents product metadata, variables, provenance, rights, release identity, and authorized downloads beside a selected-slice preview. C-MAP Chart Explorer is a qualitative reference for information hierarchy only; its datasets, symbols, assets, interactions, and pixels are not copied.

The Store retrieves one exact tile from `datatiles_selected_slice`. For DNT1, the browser enforces the header and element limits, decompresses zlib when supported, applies declared byte order, excludes raw-domain nodata, computes physical values as `raw × scale + offset`, and creates an ephemeral deterministic colour ramp from the finite range of the first array plane. The Store does not save those pixels or represent them as a scientific variable. For a selected PNG/JPEG/WebP portrayal profile, the stored portrayal is displayed without reinterpreting it as measurements. Unsupported encodings remain discoverable and downloadable but are not silently converted.

![Client-side preview boundary](../store/docs/figures/client-side-preview.svg)

## Authentication and authorization

The authorization graph is:

```text
User -> Group -> Role -> Permission
```

The built-in roles are `viewer`, `downloader`, `catalog_manager`, and `admin`. The configuration file defines the bootstrap administrator username/password/group/role. On first application initialization, the `admin` user is created, its configured password is hashed, it is placed in the `administrators` group, and that group receives the `admin` role.

No application route should infer authorization directly from a username. Route protection uses permissions derived from group-role membership.

## PWA and confidentiality

The service worker caches only the static app shell. It explicitly bypasses `/api/*` and file-download responses. Consequently, enabling PWA installation does not automatically create uncontrolled offline copies of protected datasets.

A production deployment should use HTTPS, a strong random Flask secret, secure cookies, a reverse proxy, database backups, rate limiting at the proxy/gateway, and external secret management. The repository's `config.py` contains an explicit bootstrap password setting as requested, but deployments should override it from a secret manager and rotate it after initialization.

## FAIR, licences, signatures and DRM

Authentication and download authorization do not change dataset rights. The application surfaces source-specific acknowledgements, licensing and provenance extracted from each DataTiles release. A restricted catalog can still support FAIR discovery when public metadata/PIDs are published appropriately, but this specific PWA defaults to authenticated catalog access.

Digital signatures continue to attest the inner scientific object; the Store index is disposable and unsigned. DRM content keys and customer secrets do not belong in the Store catalog database. A commercial deployment can connect the Store to a separate entitlement/KMS service, but that is an integration profile rather than part of the portable Store reference implementation.

## Versioned licence acceptance and safety/no-liability agreement

Data availability is not consent. Before a user or API client may retrieve portrayal tiles or download the underlying DataTiles object, the Store requires a current acceptance record tied to four facts: the authenticated user, the catalog item, the exact DataTiles SHA-256, and the current agreement identity. The agreement identity includes the structured rights/licence records extracted from the DataTiles release plus the configured safety/no-liability agreement version.

The mandatory safety text states that the product is **not suitable for navigation**, is provided **AS IS / AS AVAILABLE**, is not an official chart/ENC/ECDIS or certified navigation aid, requires independent verification against authoritative sources, and limits responsibility of distributors/licensors/contributors/institutions/software providers/service operators to the maximum extent permitted by applicable law. This reference language is a technical default, not jurisdiction-specific legal advice; commercial operators must have counsel review the actual contract and consumer/business-law requirements of their distribution jurisdictions.

An acceptance row preserves the licence snapshot, file checksum, safety text/version, timestamp, user identity, interaction source (`web` or `api`), and optionally bounded client IP/user-agent evidence. If the file is replaced, its rights change, or the configured safety version changes, the old acceptance remains in the audit history but no longer unlocks preview/download.

This separation is important academically and legally: accepting the Store agreement cannot create rights absent from upstream licences, waive non-waivable statutory rights, certify data quality, or make a scientific portrayal navigationally authoritative.

## API-first interaction contract

Every material Store interaction is exposed under `/api/v1`, including authentication/token lifecycle, catalog search/detail, agreement retrieval and acceptance, portrayal tiles, downloads, catalog rescans, DataTiles CRUD, user/group administration and audit retrieval. Browser routes are a human UI over the same authorization and data model; third-party applications use opaque Bearer tokens associated with an ordinary Store user and therefore receive the same group/role permissions.

The primary endpoints are:

```text
POST   /api/v1/auth/token
GET    /api/v1/auth/me
GET    /api/v1/auth/tokens
POST   /api/v1/auth/tokens
DELETE /api/v1/auth/tokens/{token_id}

GET    /api/v1/catalog?q=...
POST   /api/v1/catalog
GET    /api/v1/catalog/{id}
PUT    /api/v1/catalog/{id}/file
PATCH  /api/v1/catalog/{id}
DELETE /api/v1/catalog/{id}
POST   /api/v1/catalog/scan

GET    /api/v1/catalog/{id}/agreement
POST   /api/v1/catalog/{id}/agreement/accept
GET    /api/v1/catalog/{id}/tiles/{z}/{x}/{y}
GET    /api/v1/catalog/{id}/preview
GET    /api/v1/catalog/{id}/download

GET/POST/PATCH/DELETE /api/v1/users...
GET/POST/PATCH/DELETE /api/v1/groups...
GET    /api/v1/audit
GET    /api/v1/openapi.json
```

API write endpoints require Bearer authentication and are CSRF-exempt because they reject ambient browser-cookie authorization for writes. Browser form writes remain CSRF protected. API reads MAY use an authenticated browser session for the built-in UI and diagnostics, but third-party clients SHOULD consistently use Bearer tokens.

## Managers and Store-level CRUD

The bootstrap process creates a `managers` group (configurable with `MANAGERS_GROUP`) and assigns it the `catalog_manager` role. Members can create/upload, read, replace/update, rename and delete DataTiles files. These are Store-level file operations: update means atomic replacement by another valid DataTiles/MBTiles-compatible SQLite file, not mutation of the signed scientific object in place.

On replacement, the new file is opened read-only through SQLAlchemy and metadata extraction must succeed before it replaces the published file. A new SHA-256 and metadata index are generated. Because acceptance is checksum-bound, the new release immediately requires renewed licence/safety acceptance.

Destructive operations and agreement acceptance are recorded in the Store audit table. Audit records are operational evidence and do not replace the W3C PROV graph embedded in the scientific DataTiles object.

## Authentication and infrastructure integration

The Store supports managed password accounts, optional verified-email self-registration, Google OpenID Connect, Microsoft Entra ID tenants, and a generic OAuth2/OpenID Connect institutional provider. All identities resolve to the same SQLAlchemy user/group/role model. Runtime authentication and SMTP settings are administered from the PWA **Configuration** section by administrators and through the administrator API. Complete operator documentation is installed under `store/docs/` and rendered by the PWA **Help** section.
