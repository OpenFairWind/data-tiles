# HTTP and OGC API exposure

Run `datatiles-serve FILE --host 127.0.0.1 --port 8080`. The server is read-only.

| Resource | Purpose |
|---|---|
| `/` | landing page |
| `/conformance` | implemented OGC conformance declarations |
| `/api` | OpenAPI 3.0 description |
| `/collections` | collection list |
| `/collections/{id}` | collection, dimensions, CRS, and extent |
| `/collections/{id}/dimensions` | typed point/interval dimensions |
| `/collections/{id}/crs` | scientific CRS records |
| `/collections/{id}/contents` | raster/vector types, media types, encodings, schemas, and coordinate selectors |
| `/collections/{id}/provenance` | provenance graph |
| `/collections/{id}/profile` | numeric two-point depth transect as JSON, CSV, or SVG |
| `/playground` | OpenLayers multidimensional scientific playground |
| `/collections/{id}/point` | cursor values with source tile and pixel evidence |
| `/collections/{id}/contours` | live GeoJSON bathymetric isolines |
| `/collections/{id}/query` | compound numeric, categorical, and mask predicates |
| `/collections/{id}/tiles` | tileset list |
| `/collections/{id}/tiles/WebMercatorQuad/{z}/{x}/{y}` | tile retrieval |

Point dimensions are supplied as query parameters. Interval dimensions use ISO 8601 interval syntax `lower/upper`; numeric intervals use the same separator. The reference server resolves complete coordinate sets exactly. Partial queries, nearest-neighbor selection, and interpolation are intentionally rejected by the storage layer.

Tile responses use the media type declared by the resolved multidimensional content profile, so a single DataTiles collection may expose numeric raster matrices, raster portrayals, MVT, and GeoJSON at different coordinates. The implementation uses OGC API – Tiles patterns and `WebMercatorQuad`. It is an interoperability profile and has not undergone OGC compliance certification.
