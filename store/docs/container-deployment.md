# Docker and Docker Compose deployment

The reference container packages only the operational Store. Scientific DataTiles objects, the SQLAlchemy application database, and branding assets remain on three distinct persistent volumes. Containerization does not change DataTiles checksums, provenance, licences, release identity, or the not-for-navigation limitation.

## Build and run with Docker Compose

Run from `store/`:

```bash
export DATATILES_STORE_SECRET_KEY="$(openssl rand -hex 32)"
export DATATILES_STORE_ADMIN_PASSWORD="replace-with-a-unique-long-password"
docker compose build --pull
docker compose up -d
docker compose ps
curl -fsS http://127.0.0.1:8080/healthz
```

The supplied Compose file binds the service only to loopback. Put a maintained HTTPS reverse proxy in front of it for network access. Set `DATATILES_STORE_SESSION_COOKIE_SECURE=1` after HTTPS termination is configured. Never publish the development HTTP port directly to an untrusted network.

The image runs Gunicorn as unprivileged UID/GID `10001`, uses a read-only root filesystem, disables privilege escalation, and permits writes only through the three `/data` volumes and the bounded `/tmp` tmpfs. A single Gunicorn worker with four threads is deliberate for the reference SQLite application database; operators moving to another SQLAlchemy database may evaluate a different worker topology under load testing.

## Persistent volumes

| Volume | Mount | Purpose |
|---|---|---|
| `datatiles-store-state` | `/data/state` | SQLAlchemy users, permissions, settings, acceptances, commerce, and audit records |
| `datatiles-store-catalog` | `/data/catalog` | complete DataTiles/MBTiles-compatible SQLite publication files |
| `datatiles-store-branding` | `/data/branding` | validated, normalized public Store logo |

The Store name, tagline, and Bootstrap theme tokens are rows in the application database; the logo is a separate PNG in the branding volume. Back up and restore all three volumes as one operational recovery set. The catalog files remain independently verifiable scientific objects.

## Import existing DataTiles files

Copy a finalized file into the catalog volume, then use **Rescan catalog**:

```bash
docker compose cp /absolute/path/product.datatiles store:/data/catalog/product.datatiles
```

`docker compose cp` writes through the running container. Confirm ownership and rescan status after import. For a host bind mount instead, replace the catalog named volume with an explicit absolute path whose owner grants UID `10001` the intended read/write access. A read-only bind mount is appropriate only when manager upload/replace/delete operations are intentionally disabled by filesystem policy.

## Direct Docker invocation

```bash
docker build -t datatiles-store:0.6.0 store
docker volume create datatiles-store-state
docker volume create datatiles-store-catalog
docker volume create datatiles-store-branding
docker run -d --name datatiles-store \
  -p 127.0.0.1:8080:8080 \
  --read-only --tmpfs /tmp:size=64m,mode=1777 \
  --security-opt no-new-privileges:true \
  -e DATATILES_STORE_SECRET_KEY="replace-with-a-random-secret" \
  -e DATATILES_STORE_ADMIN_PASSWORD="replace-with-a-unique-long-password" \
  -e DATATILES_STORE_DATABASE_URL="sqlite:////data/state/store.db" \
  -e DATATILES_STORE_CATALOG_DIR="/data/catalog" \
  -e DATATILES_STORE_BRANDING_DIR="/data/branding" \
  -v datatiles-store-state:/data/state \
  -v datatiles-store-catalog:/data/catalog \
  -v datatiles-store-branding:/data/branding \
  datatiles-store:0.6.0
```

## Updates and rollback

Before an image update, stop mutation traffic and back up every volume. Build the new immutable image tag, run its tests, then recreate the service without deleting volumes:

```bash
docker compose build --pull
docker compose up -d --force-recreate
docker compose logs --tail=100 store
```

Rollback means restoring the previous image and, if an application-database migration occurred, its matching state-volume backup. Never roll back only the catalog volume when acceptance, purchase, or audit state refers to newer files.

## Operational verification

After deployment, verify:

1. `/healthz` returns `{"status":"ok"}`.
2. the bootstrap administrator can sign in and rotates the initial credential;
3. Configuration saves branding/theme values and the logo survives container recreation;
4. catalog scan indexes a known checksum-verified revision-8 fixture;
5. agreement gating, exact DNT1 preview, and authorized download behave as documented;
6. the reverse proxy supplies HTTPS, request-size limits, rate limiting, and retained access/error logs;
7. backup restoration is tested rather than assumed.
