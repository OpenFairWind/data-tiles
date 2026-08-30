# Installation and deployment

## Purpose

DataTiles Store is a Flask PWA and API service. It keeps its SQLAlchemy application database separate from the scientific DataTiles files. Catalog indexing is read-only with respect to published DataTiles objects; manager CRUD replaces whole files rather than editing scientific releases in place.

## Requirements

Python 3.10 or newer is required. From the repository root:

```bash
cd store
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python run.py
```

For production install `.[prod]` and run behind an HTTPS reverse proxy, for example Gunicorn. Set a strong `DATATILES_STORE_SECRET_KEY`, protect the application database, catalog filesystem, and branding directory, and set secure session cookies. Bootstrap 5.3.8 is vendored with the Store, so runtime access to a public asset CDN is not required.

## Initial administrator

`store/config.py` defines bootstrap `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_GROUP`, and the managers group. Environment variables should supply the initial secret in production. On first initialization the password is hashed into the SQLAlchemy database. Rotate the bootstrap credential immediately after provisioning.

## Persistence

Back up the SQLAlchemy database, catalog directory, and `DATATILES_STORE_BRANDING_DIR` together. DataTiles files are independently checksum-indexed; acceptance evidence and theme settings live in the application database, while the normalized logo is a separate presentation asset. Do not restore one without considering consistency with the others.
