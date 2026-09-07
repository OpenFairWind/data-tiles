# Served DataTiles catalogue browsing and map preview

The Store can use a DataTiles Online Delivery server as its visual discovery backend. The Store remains responsible for catalogue metadata, agreements, entitlements, downloads and audit records; the online server handles high-throughput scientific and portrayal tile delivery.

## Configuration

Set the Store environment variable:

```bash
DATATILES_STORE_TILE_SERVER_URL=https://tiles.example.org
```

The browser accesses the configured server directly. The tile server therefore needs CORS permission for the Store origin. For same-origin reverse-proxy deployments, set the value to the public proxied path/base URL.

The Store matches a catalogue file to a served dataset by filename stem. `weather.datatiles` maps to the online server dataset id `weather`.

## Catalogue visual browsing

Every catalogue card contains a small slippy-map viewport. The browser calls the online server's `/maps` endpoint, selects the highest-priority layer whose `dataset` matches the catalogue item, obtains its TileJSON document, fits the advertised dataset bounds and draws server-rendered XYZ tiles. This avoids downloading or decoding the scientific container merely to browse the catalogue.

If no served layer is available, the card retains the Store's decorative fallback and the rest of the catalogue remains functional.

## Detail-page map preview

The detail page offers two complementary preview modes:

* **Online map** uses the server-rendered portrayal and supports pan/zoom. It is the fast default for visual inspection.
* **Scientific tile** preserves the existing Store behavior: one exact selected-slice tile is fetched from the Store and DNT1 is decoded and portrayed client-side in the browser.

The two modes are representations of the same DataTiles publication rather than different datasets.

## Server layer metadata

A server layer may include an optional `catalog` member:

```json
{
  "temperature": {
    "dataset": "weather",
    "title": "2 m air temperature",
    "bounds": [5.0, 35.0, 20.0, 48.0],
    "catalog": {
      "enabled": true,
      "priority": 100,
      "query": {"valid_time": "2026-09-07T12:00:00Z"}
    }
  }
}
```

`enabled=false` prevents Store discovery. `priority` chooses the preferred browse layer when several portrayals belong to one dataset. `query` supplies stable default dimensions for catalogue portrayal; it MUST NOT be used to conceal a dimension that changes the scientific identity of the product.

## Access control

Catalogue portrayals are publication previews. Operators must not expose a layer through public tile-server URLs if its licence or access policy forbids public visual preview. For protected products, deploy the online server behind the same authorization gateway or disable the layer for catalogue discovery.

The Store's existing agreement and purchase gates still govern its scientific preview and downloads. A separate public portrayal endpoint does not automatically inherit those gates.

## Docker Compose

When Store and online server run together, expose the online server through a reverse proxy or publish its port and set `DATATILES_STORE_TILE_SERVER_URL` to the browser-visible URL, not an internal Docker DNS name. Example:

```yaml
services:
  tiles:
    build: ./server
    environment:
      DATATILES_CORS_ORIGINS: https://store.example.org
    volumes:
      - ./catalog:/data:ro
      - ./layers.json:/config/layers.json:ro
      - ./tile-cache:/cache

  store:
    build: ./store
    environment:
      DATATILES_STORE_TILE_SERVER_URL: https://tiles.example.org
    volumes:
      - ./catalog:/app/catalog:ro
```

For production, place both behind TLS and use long-lived cache headers/CDN caching for immutable server portrayals.
