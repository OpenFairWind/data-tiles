# Meteo@UniParthenope direct NetCDF archive demo

This demo exercises the Online Delivery server directly against a real Meteo@UniParthenope WRF NetCDF frame. It does not first convert that source into DataTiles or MBTiles, stores no image tiles, and applies only a client-side diagnostic portrayal to the numeric DNT1 response.

The immutable `sources.lock.json` records the exact provider archive URL, byte count, SHA-256 checksum, attribution, and terms URL for `wrf5_d01_20260907Z1200.nc`. `acquire.py` first checks the already-downloaded `data/meteouniparthenope/files` copy. It reuses that file only when its SHA-256 matches; otherwise it downloads the locked URL into a temporary file, verifies the checksum, and atomically installs it under the server's required archive hierarchy. This makes repeated executions independent of a mutable “latest” listing while retaining exact source identity.

The source exposes a rectilinear EPSG:4326 grid. The server samples EPSG:3857 WebMercatorQuad pixel centres using `nearest-neighbour-at-Web-Mercator-pixel-centres-v1`, returns `float32` DNT1 numeric arrays, preserves each variable's unit, and marks cells outside the source extent as nodata. The upstream product and this visualization are uncertified and MUST NOT be used for navigation.

## Reproduce and run

From the repository root:

```bash
python -m pip install -e '.[server]'
python demo/netcdf-archive/acquire.py
```

Start the application:

```bash
DATATILES_NETCDF_ROOT="$PWD/data/netcdf-archive-demo" \
DATATILES_NETCDF_PRODUCTS="$PWD/demo/netcdf-archive/netcdf-products.json" \
DATATILES_LAYERS="$PWD/server/layers.example.json" \
DATATILES_DATA_DIR="$PWD/data" \
DATATILES_CACHE_DIR="$PWD/data/netcdf-archive-cache" \
python -m uvicorn server.app:app --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080/`—not the HTML file directly—to discover the real `wrf5/d01/20260907Z1200` frame and render `T2C`, `RH2`, `U10M`, `V10M`, `SLP`, or `CLDFRA_TOTAL`. If `server/netcdf-preview.html` is opened through `file://`, it attempts the same loopback API and displays an explicit server-start instruction when the application is unavailable.

Machine-readable verification:

```bash
curl http://127.0.0.1:8080/api/netcdf
curl -D data/netcdf-archive-demo/tile.headers \
  -o data/netcdf-archive-demo/T2C.dnt1 \
  'http://127.0.0.1:8080/api/netcdf/wrf5/d01/20260907Z1200/tiles/5/16/11?variable=T2C'
```

The response media type is `application/vnd.datatiles.dnt1`. Its headers declare the source CRS, output CRS, derivation algorithm, cache policy, and content ETag. `/docs` exposes the generated FastAPI contract.

The lock also records SHA-256 `5a31d53ac66141f9ef34d6c773ec47cb8294f0f0b6f069fe4e15b0372ced791e` for the uncompressed 256 × 256 `T2C/5/16/11` DNT1 derivation. Reproducibility here establishes byte identity of the retained input and deterministic derivation for the declared software/runtime. It does not establish observational validity, forecast skill, official-chart status, or permission beyond the provider terms. Publication workflows MUST retain the source checksum, terms, attribution, datum, native resolution, processing parameters, and limitations.
