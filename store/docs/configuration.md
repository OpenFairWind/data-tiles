# Configuration

Administrators open **Configuration** in the PWA. Runtime identity, registration, SMTP, and public-URL settings are stored through SQLAlchemy and can also be managed through the authenticated `/api/v1/configuration` API.

Secret fields are write-only in the web/API representation: an existing client secret or SMTP password is not returned to browsers or API clients. Blank secret fields in the web form retain the existing value.

## Authentication controls

- `auth.local.enabled`: managed email/username and password authentication.
- `auth.registration.enabled`: permits new self-service accounts.
- `auth.registration.default_group`: group assigned to self-registered identities.
- Google, Microsoft, and generic OIDC settings enable infrastructure SSO.

At least one usable authentication method must remain enabled before an administrator signs out.

## Public base URL

Set `store.public_base_url` to the canonical HTTPS origin when the Store is behind a proxy. Verification emails and OIDC redirect URIs use this value. Register the resulting callback URIs with each identity provider.

## SMTP

Configure host, port, STARTTLS or implicit TLS, username/password, sender address/name, and timeout. Email verification requires SMTP to be enabled and operational. Use the SMTP test operation after changes.


## Commerce and PayPal
Payment is disabled by default. Administrators configure the provider and PayPal sandbox/live credentials in Configuration.
