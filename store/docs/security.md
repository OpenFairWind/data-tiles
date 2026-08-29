# Security and operations

Use HTTPS, a strong secret key, secure cookies, least-privilege groups, protected database/catalog storage, and a production WSGI server. Put the service behind a maintained reverse proxy and apply infrastructure rate limiting and monitoring.

Treat OAuth client secrets and SMTP credentials as secrets. Configuration APIs are administrator-only and secret values are not returned. Rotate provider credentials after suspected exposure.

The PWA service worker caches only public application-shell assets, not authenticated API responses, map payloads, or downloadable DataTiles files.

Back up audit/acceptance records. Review logs for authentication failures, token issuance/revocation, catalog CRUD, agreement acceptance, and administrative changes. Test restore procedures periodically.
