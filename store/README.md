# DataTiles Store

The DataTiles Store is the optional Flask/SQLAlchemy and Bootstrap 5 PWA for institutional publication, discovery, preview, licensing, controlled download, optional commerce, and release-update workflows. Administrators can configure the Store name, tagline, validated logo, and bounded Bootstrap theme tokens without changing scientific DataTiles objects.

See [`docs/index.md`](docs/index.md) for the complete manual, also rendered in the PWA Help section.

Container deployment is provided through [`Dockerfile`](Dockerfile), [`docker-compose.yml`](docker-compose.yml), and the [Docker/Compose operations guide](docs/container-deployment.md).

## Quick start

```bash
cd store
python -m pip install -e .
python run.py
```

Change the administrator password and `SECRET_KEY` before deployment. Payment is disabled by default. PayPal Orders v2 is the reference provider and starts in sandbox mode when enabled.

## Licence

Store software is Apache License 2.0. Distributed data retains independent source/product licences. See [`LICENSE.md`](LICENSE.md).

Vendored Bootstrap 5.3.8 code is provided under its MIT licence; the exact notice is retained at `datatiles_store/static/BOOTSTRAP-LICENSE.txt`.
