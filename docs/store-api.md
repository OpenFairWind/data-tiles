# DataTiles Store API v1

The Store is API-first. Human HTML/PWA pages are convenience clients; third-party applications should integrate through `/api/v1`. API authorization resolves to the same SQLAlchemy `User -> Group -> Role -> Permission` graph used by browser sessions.

## Authentication

Obtain an opaque Bearer token:

```http
POST /api/v1/auth/token
Content-Type: application/json

{"username":"alice","password":"...","name":"desktop client","expires_in":2592000}
```

Use the returned token as:

```http
Authorization: Bearer dts_...
```

The Store persists only a SHA-256 hash and short non-secret prefix, never the bearer secret itself. Tokens can be listed, created, and revoked through `/api/v1/auth/tokens`. Revocation or user deactivation stops future authorization. TLS is mandatory for production API use.

## Agreement workflow

Catalog metadata can be discovered without accepting a product licence when the user's role permits catalog view. Payload access is different: portrayal tiles and file download require a current acceptance for the exact release.

```http
GET /api/v1/catalog/42/agreement
```

returns the file SHA-256, structured rights records, canonical licence fingerprint, safety agreement version/text and current acceptance status.

Acceptance requires an explicit JSON body:

```http
POST /api/v1/catalog/42/agreement/accept
Authorization: Bearer ...
Content-Type: application/json

{"accept_license":true,"accept_safety":true}
```

The acceptance is invalid for access purposes if the DataTiles SHA-256, extracted rights fingerprint, or configured safety-agreement version changes. A gated endpoint returns HTTP `428 Precondition Required` with an `agreement_url` when a current acceptance is missing.

## Catalog and search

```text
GET /api/v1/catalog?q=sea_floor_depth_below_geoid
GET /api/v1/catalog/{id}
```

Search uses metadata automatically extracted from the indexed DataTiles objects: title/description, MBTiles metadata, CF standard names, rights/licences, provenance identifiers and labels, bounds and other catalog facts. It does not full-text-index raw scientific cell values.

## Preview and download

```text
GET /api/v1/catalog/{id}/tiles/{z}/{x}/{y}
GET /api/v1/catalog/{id}/download
```

Both require appropriate role permission and current agreement acceptance. The portrayal endpoint returns only recognized portrayal image payloads from the selected compatibility slice; numeric DNT1 arrays are not converted heuristically. Responses are marked private/no-store where appropriate.

## DataTiles CRUD

Users in the bootstrapped `managers` group inherit the `catalog_manager` role and can perform Store-level file CRUD:

```text
POST   /api/v1/catalog                 multipart `file`; optional `filename`
GET    /api/v1/catalog/{id}            read indexed metadata
PUT    /api/v1/catalog/{id}/file       multipart replacement; optional `filename`
PATCH  /api/v1/catalog/{id}            JSON rename: {"filename":"new.datatiles"}
DELETE /api/v1/catalog/{id}
POST   /api/v1/catalog/scan
```

Create/update first validates the candidate as a readable DataTiles/MBTiles-compatible SQLite file. Replacement is atomic and re-indexes metadata and SHA-256. A new checksum necessarily invalidates prior access acceptance. These endpoints never edit released scientific metadata in place.

## User/group administration

Administrative clients have API counterparts for identity management:

```text
GET/POST          /api/v1/users
PATCH/DELETE      /api/v1/users/{id}
GET/POST          /api/v1/groups
PATCH/DELETE      /api/v1/groups/{id}
```

The `administrators` and `managers` bootstrap groups are protected from API deletion. Applications should assign permissions through groups/roles rather than username-specific policy.

## Audit

```text
GET /api/v1/audit?limit=100
```

returns operational events such as agreement acceptance, download, catalog create/update/rename/delete, scans, token issuance/revocation and administrative changes. Audit retention and client metadata collection must follow the operator's privacy and records policy. The Store audit is not a substitute for W3C PROV evidence inside DataTiles.

## Discovery and errors

```text
GET /api/v1
GET /api/v1/openapi.json
GET /healthz
```

Common API status semantics are `401` authentication required, `403` insufficient role permission, `404` absent asset, `409` state conflict, `415` selected slice is not portrayal imagery, and `428` current agreement acceptance required.

The reference OpenAPI document is machine-readable discovery metadata. Production deployments may generate a more detailed contract from the same endpoint set and should version incompatible API changes under a new API prefix.

## Authentication/configuration additions

API v1 also exposes authentication-provider discovery, managed-account registration/email verification, administrator configuration, and help documentation. Interactive Google/Microsoft/generic OIDC authorization uses browser redirects but resolves to the same Store identity and authorization model. See `store/docs/api.md` and `store/docs/authentication.md`.
