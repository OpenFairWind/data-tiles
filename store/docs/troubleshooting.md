# Troubleshooting

## OIDC redirect mismatch

Set the Store public base URL to the exact externally visible HTTPS origin and register `/auth/google/callback`, `/auth/microsoft/callback`, or `/auth/oauth2/callback` with the provider.

## Registration email does not arrive

Confirm SMTP is enabled, sender policy permits the configured From address, TLS mode/port match the provider, and credentials are valid. Check spam/quarantine and application logs.

## User can sign in but cannot download

Check group/role permissions and whether the current DataTiles licence/safety agreement has been accepted. A recently replaced file requires a new acceptance.

## External user is rejected

When registration is disabled, provision the user first. For Google, check allowed domains. For Microsoft, check tenant configuration. For generic OIDC, confirm the provider returns `sub` and `email` claims.
