# Authentication, SSO, and registration

The Store supports four optional authentication paths that all resolve to the same SQLAlchemy `User -> Group -> Role -> Permission` authorization model.

## Managed accounts

When local authentication is enabled, passwords are stored only as Werkzeug password hashes. Administrators can create managed users. For self-registration, the submitted email becomes both `username` and `email`; the account is inactive until verification succeeds.

## Email registration

When registration and local authentication are enabled, the user submits an email and a password of at least 12 characters. The Store sends a signed, time-limited verification link over the configured SMTP server. Successful verification activates the account and assigns the configured default group. Operators must use HTTPS and a correct public base URL.

## Google

Enable Google OIDC and configure client ID/client secret. The callback is `/auth/google/callback`. Optional allowed Workspace domains restrict new/existing Google sign-ins. Google must return a usable verified email identity.

## Microsoft Entra ID

Enable Microsoft authentication, configure the tenant (`common`, tenant UUID, or tenant domain), client ID, and client secret. The callback is `/auth/microsoft/callback`. For institutional deployment, use a specific tenant rather than `common` unless multi-tenant access is intended.

## Generic OAuth2/OIDC

The generic integration is OpenID Connect based: configure a discovery metadata URL, client ID, client secret, scopes, and display name. The callback is `/auth/oauth2/callback`. The provider must expose a stable subject identifier and email claim.

## Registration policy

If registration is disabled, an external identity may sign in only when it maps to an already provisioned Store user. If enabled, a first successful Google/Microsoft/OIDC login can create the account automatically and place it in the default group. Administrators remain responsible for assigning elevated groups.

Never map external claims directly to `admin` or `managers` without an explicit institutional authorization policy.
