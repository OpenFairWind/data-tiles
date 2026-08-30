# Security and operations

Use HTTPS, a strong secret key, secure cookies, least-privilege groups, protected database/catalog storage, and a production WSGI server. Put the service behind a maintained reverse proxy and apply infrastructure rate limiting and monitoring.

Treat OAuth client secrets and SMTP credentials as secrets. Configuration APIs are administrator-only and secret values are not returned. Rotate provider credentials after suspected exposure.

Branding values are validated before persistence. Theme colours accept only six-digit hexadecimal values; non-colour style controls use fixed allowlists. Logo uploads accept only verified PNG/JPEG/WebP inputs, enforce byte and pixel limits, discard metadata during normalization, and never serve user-provided SVG. Protect `BRANDING_DIR` from direct writes by untrusted processes.

CSRF-exempt `/api/v1` writes require an explicit Bearer header and do not authorize from the ambient session cookie. HTML form writes use Flask-WTF CSRF tokens. Reverse proxies should still reject cross-origin requests by policy and rate-limit credential and token endpoints.

The PWA service worker caches the vendored Bootstrap files and public application-shell assets, not authenticated API responses, selected-slice preview payloads, portrayal tiles, or downloadable DataTiles files. The public logo uses conditional HTTP caching and is not accepted as scientific evidence.

![Protected access gates](figures/access-gates.svg)

Back up audit/acceptance records. Review logs for authentication failures, token issuance/revocation, catalog CRUD, agreement acceptance, and administrative changes. Test restore procedures periodically.
