# DataTiles Store

The DataTiles Store is the optional Flask/SQLAlchemy PWA for institutional publication, discovery, preview, licensing, controlled download, optional commerce, and release-update workflows.

See [`docs/index.md`](docs/index.md) for the complete manual, also rendered in the PWA Help section.

## Quick start

```bash
cd store
python -m pip install -e .
python run.py
```

Change the administrator password and `SECRET_KEY` before deployment. Payment is disabled by default. PayPal Orders v2 is the reference provider and starts in sandbox mode when enabled.

## Licence

Store software is Apache License 2.0. Distributed data retains independent source/product licences. See [`LICENSE.md`](LICENSE.md).
