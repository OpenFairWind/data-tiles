# Payments and commerce

Payment is optional and provider-independent. `PaymentProvider` defines checkout creation and capture. Store records provider name, external order reference, amount/currency, state, and entitlement; it never stores card or bank credentials.

## PayPal reference provider
The included implementation uses PayPal REST Orders v2 with server-side OAuth 2.0 client credentials. Configure Commerce and PayPal settings in the administrator Configuration page. Use sandbox first. The flow creates an order with `CAPTURE`, redirects to the PayPal approval URL, then captures server-side after approval.

PayPal code is isolated in `payments.py`; other providers can implement the same interface without changing purchase/download tables.

## API
- `GET /api/v1/payments/providers`
- `POST /api/v1/catalog/{id}/checkout`
- `POST /api/v1/payments/{transaction_id}/capture`
- `GET /api/v1/library`
- `GET /api/v1/notifications`

Payment entitlement and data-licence/safety acceptance are independent gates.

## PayPal implementation references

The reference adapter follows the current PayPal REST guidance:

- https://developer.paypal.com/api/rest/integration/orders-api
- https://developer.paypal.com/api/make-api-requests

Use `https://api-m.sandbox.paypal.com` for sandbox testing and `https://api-m.paypal.com` only after production credentials and merchant readiness are established.
