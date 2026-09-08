# Direct NetCDF archive delivery demo

This demo exercises the Online Delivery server without first converting its source into a DataTiles or MBTiles file. It creates a deterministic, explicitly synthetic CF-style NetCDF frame in the required product/domain archive tree and requests numeric DNT1 tiles directly from that immutable frame. It stores no image tiles and applies no portrayal.

The analytic temperature and wind fields are software fixtures, not observations or forecasts. Their horizontal source CRS is EPSG:4326; the server samples them at EPSG:3857 WebMercatorQuad pixel centres using `nearest-neighbour-at-Web-Mercator-pixel-centres-v1`. The output is converted to `float32`, preserves the declared unit, and uses the DNT1 nodata value outside the source extent. The demo is uncertified and MUST NOT be used for navigation.

From the repository root, install the server dependencies and generate the fixture:

```bash
python -m pip install -e '.[server]'
python demo/netcdf-archive/prepare.py --root data/netcdf-archive-demo
```

Start the application, then open `http://127.0.0.1:8080/` for the interactive numeric preview:

```bash
DATATILES_NETCDF_ROOT="$PWD/data/netcdf-archive-demo" \
DATATILES_NETCDF_PRODUCTS="$PWD/demo/netcdf-archive/netcdf-products.json" \
DATATILES_LAYERS="$PWD/server/layers.example.json" \
DATATILES_DATA_DIR="$PWD/data" \
DATATILES_CACHE_DIR="$PWD/data/netcdf-archive-cache" \
python -m uvicorn server.app:app --host 127.0.0.1 --port 8080
```

In another terminal, discover the configured variables and frame, then retrieve one tile:

```bash
curl http://127.0.0.1:8080/api/netcdf
curl -D data/netcdf-archive-demo/tile.headers \
  -o data/netcdf-archive-demo/air-temperature.dnt1 \
  'http://127.0.0.1:8080/api/netcdf/demo_weather/d01/20260907Z1200/tiles/5/16/11?variable=air_temperature'
```

The response media type is `application/vnd.datatiles.dnt1`. Its headers declare the source CRS, output CRS, derivation algorithm, cache policy, and content ETag. `/docs` exposes the generated FastAPI contract.

To exercise representative Meteo@UniParthenope inputs already present in a local development workspace, copy—not move—the files into the configured archive tree while retaining their original checksums. For example:

```text
data/netcdf-archive/wrf5/d02/archive/2026/09/07/wrf5_d02_20260907Z1200.nc
data/netcdf-archive/ww33/d01/archive/2026/09/07/ww33_d01_20260907Z1200.nc
```

Declare only approved variables for `wrf5` and `ww33` in a separate product configuration derived from `server/netcdf-products.example.json`. Upstream licence, attribution, access conditions, source checksum, datum, native resolution, and scientific limitations remain publication requirements; the direct-delivery endpoint does not invent that evidence.
