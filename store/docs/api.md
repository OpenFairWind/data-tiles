# API integration

All operational Store capabilities have `/api/v1` counterparts for third-party applications. Bearer tokens resolve to the same users, groups, roles, permissions, licence acceptance, and audit rules as browser sessions. API writes require an explicit `Authorization: Bearer …` header; an ambient browser session cookie is deliberately insufficient on CSRF-exempt API routes. Browser forms use separate CSRF-protected routes.

Use `/api/v1/openapi.json` for machine-readable discovery. Configuration is available to administrators through `GET/PATCH /api/v1/configuration`; help content is available through `/api/v1/help` and `/api/v1/help/{slug}`.

Data preview/download can return HTTP `428 Precondition Required` until the current licence and safety/no-liability agreement is accepted for the exact file hash and rights fingerprint.

`GET /api/v1/catalog/{id}/preview` returns one exact tile from the selected DataTiles slice with `X-DataTiles-Encoding`, data type, zoom, column, and stored TMS-row headers. A DNT1 response uses `application/vnd.datatiles.numeric`; the client is responsible for bounded decoding and portrayal. The existing `/tiles/{z}/{x}/{y}` resource remains restricted to declared image portrayal slices and converts XYZ rows only at the interface.

OAuth browser redirects remain interactive identity-provider flows; API clients should complete an approved interactive OIDC login or use Store-issued Bearer tokens according to institutional policy. Never embed administrator credentials in third-party applications.


## Commerce and library API
The API exposes provider discovery, checkout/capture, user library, and update notifications.
