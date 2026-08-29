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

For production install `.[prod]` and run behind an HTTPS reverse proxy, for example Gunicorn. Set a strong `DATATILES_STORE_SECRET_KEY`, protect the application database and catalog filesystem, and set secure session cookies.

## Initial administrator

`store/config.py` defines bootstrap `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_GROUP`, and the managers group. Environment variables should supply the initial secret in production. On first initialization the password is hashed into the SQLAlchemy database. Rotate the bootstrap credential immediately after provisioning.

## Persistence

Back up the SQLAlchemy database and catalog directory together. DataTiles files are independently checksum-indexed; acceptance evidence and audit events live in the application database. Do not restore one without considering consistency with the other.
