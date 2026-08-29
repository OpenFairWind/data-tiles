# AGENTS.md — DataTiles Store

## Scope
These instructions apply to `/store`.

## Architecture rules
- Flask is the HTTP/PWA framework and SQLAlchemy 2.x is the only database interface.
- Every material browser interaction should have `/api/v1` parity.
- Authorization is always User → Group → Role → Permission for sessions and Bearer tokens.
- Never bypass licence/safety acceptance or paid entitlement gates.
- Payment providers implement `PaymentProvider`; PayPal is a reference adapter, not a schema dependency.
- Never store payment card credentials, OAuth/SMTP/provider secrets, DRM keys, or access tokens in DataTiles metadata/provenance.
- Published DataTiles releases are immutable; a new version is a new file/release.
- Update notifications do not imply entitlement to the newer release.
- Service-worker caches exclude authenticated APIs, data tiles, downloads, checkout/payment responses, and private library data.
- Preserve FAIR/provenance/citation/licensing/signature/DRM boundaries and the Not-for-navigation notice.

## Security and QA
Use HTTPS and secure cookies in production; keep secrets in deployment/secret storage; verify/capture provider payments server-side; never log provider secrets. Update Store docs, API/OpenAPI descriptions, tests, and PWA Help with behavior changes.
