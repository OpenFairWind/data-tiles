# SMTP and email verification

SMTP is configured from the administrator Configuration page. Use a dedicated service account where possible. Prefer STARTTLS on port 587 or implicit TLS where required by the provider. Do not use a personal mailbox password when an application credential is available.

The verification message contains a signed, expiring URL. Verification proves control of the mailbox at that time; it is not proof of legal identity or organizational role. Group/role elevation remains an administrator action.

Operational monitoring should alert on delivery failures. If SMTP is disabled, local self-registration requiring email verification cannot complete and should be disabled.
