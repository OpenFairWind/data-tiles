# API integration

All operational Store capabilities have `/api/v1` counterparts for third-party applications. Bearer tokens resolve to the same users, groups, roles, permissions, licence acceptance, and audit rules as browser sessions.

Use `/api/v1/openapi.json` for machine-readable discovery. Configuration is available to administrators through `GET/PATCH /api/v1/configuration`; help content is available through `/api/v1/help` and `/api/v1/help/{slug}`.

Data preview/download can return HTTP `428 Precondition Required` until the current licence and safety/no-liability agreement is accepted for the exact file hash and rights fingerprint.

OAuth browser redirects remain interactive identity-provider flows; API clients should complete an approved interactive OIDC login or use Store-issued Bearer tokens according to institutional policy. Never embed administrator credentials in third-party applications.


## Commerce and library API
The API exposes provider discovery, checkout/capture, user library, and update notifications.
