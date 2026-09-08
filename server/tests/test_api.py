import json

from fastapi.testclient import TestClient

from datatiles import DataTiles, decode_numeric_tile, encode_numeric_tile
from server import app as service


def configured_service(tmp_path, monkeypatch):
    data = tmp_path / "data"
    cache = tmp_path / "cache"
    data.mkdir()
    path = data / "weather.datatiles"
    with DataTiles(path, create=True, tile_format="application/vnd.datatiles.dnt1") as store:
        store.add_dimension("variable", "text")
        blob = encode_numeric_tile([0, 100, 200, 255], (2, 2), dtype="uint8", nodata=255, scale=0.1, offset=-20, unit="degC")
        store.put(0, 0, 0, blob, {"variable": "air_temperature"}, xyz=True)
    layers = tmp_path / "layers.json"
    layers.write_text(json.dumps({"temperature": {
        "dataset": "weather", "dataset_release": "fixture-1", "title": "Temperature",
        "dimensions": {"variable": "air_temperature"}, "formats": ["png", "webp"],
        "bounds": [-180, -85, 180, 85], "portrayal": {"unit": "degC", "palette": [[-20, "#000000"], [0, "#ffffff"]]},
        "catalog": {"enabled": True, "priority": 10}
    }}))
    monkeypatch.setattr(service, "DATA_DIR", data)
    monkeypatch.setattr(service, "CACHE_DIR", cache)
    monkeypatch.setattr(service, "LAYERS_FILE", layers)
    return TestClient(service.app), cache


def test_discovery_render_cache_and_conditionals(tmp_path, monkeypatch):
    client, cache = configured_service(tmp_path, monkeypatch)
    assert "DataTiles · direct NetCDF delivery" in client.get("/", headers={"Accept": "text/html"}).text
    assert client.get("/", headers={"Accept": "application/json"}).json()["version"] == "1.2.0"
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200
    listing = client.get("/maps").json()["layers"]
    assert listing[0]["dataset"] == "weather"
    assert client.get("/maps/temperature").json()["portrayalDigest"]
    tilejson = client.get("/maps/temperature/tilejson.json").json()
    assert tilejson["tilejson"] == "3.0.0"
    assert tilejson["datatiles:representations"]["client"]["mediaTypes"] == ["application/vnd.datatiles.dnt1"]
    assert client.get("/maps/temperature/legend.json").json()["unit"] == "degC"
    assert client.get("/maps/temperature/legend.png").content.startswith(b"\x89PNG")

    scientific = client.get("/api/datasets/weather/tiles/0/0/0", params={"variable": "air_temperature"})
    assert scientific.status_code == 200
    assert scientific.content.startswith(b"DNT1")
    assert client.get("/api/datasets/weather/tiles/0/0/0", params={"variable": "air_temperature"},
                      headers={"If-None-Match": scientific.headers["etag"]}).status_code == 304

    rendered = client.get("/maps/temperature/0/0/0.png")
    assert rendered.status_code == 200
    assert rendered.content.startswith(b"\x89PNG")
    assert "immutable" in rendered.headers["cache-control"]
    assert any(cache.rglob("*.png"))
    assert client.get("/maps/temperature/0/0/0.png", headers={"If-None-Match": rendered.headers["etag"]}).status_code == 304
    assert "datatiles_cache_hits" in client.get("/metrics").text


def test_api_rejects_unknown_layers_formats_and_dimensions(tmp_path, monkeypatch):
    client, _ = configured_service(tmp_path, monkeypatch)
    assert client.get("/maps/missing").status_code == 404
    assert client.get("/maps/temperature/0/0/0.jpg").status_code == 406
    # Compact fixed-dimension layer definitions do not expose arbitrary query axes.
    assert client.get("/maps/temperature/0/0/0.png?valid_time=latest").status_code == 400


def test_configured_netcdf_archive_serves_numeric_tiles(tmp_path, monkeypatch):
    xr = __import__("xarray")
    np = __import__("numpy")
    root = tmp_path / "netcdf"
    frame = root / "wrf5" / "d01" / "archive" / "2026" / "09" / "07" / "wrf5_d01_20260907Z1200.nc"
    frame.parent.mkdir(parents=True)
    dataset = xr.Dataset(
        {"T2C": (("time", "latitude", "longitude"), np.array([[[1, 2], [3, 4]]], dtype="float32"),
                  {"units": "degC"}),
         "SECRET": (("time", "latitude", "longitude"), np.zeros((1, 2, 2), dtype="float32"))},
        coords={"time": [0], "latitude": [-85.0, 85.0], "longitude": [-170.0, 170.0]},
    )
    dataset.to_netcdf(frame)
    products = tmp_path / "netcdf-products.json"
    products.write_text(json.dumps({"wrf5": {"variables": ["T2C"]}}), encoding="utf-8")
    monkeypatch.setattr(service, "NETCDF_ROOT", root)
    monkeypatch.setattr(service, "NETCDF_PRODUCTS_FILE", products)
    monkeypatch.setattr(service, "NETCDF_TILE_SIZE", 8)
    client = TestClient(service.app)

    listing = client.get("/api/netcdf")
    assert listing.status_code == 200
    assert listing.json()["products"] == [{"id": "wrf5", "variables": ["T2C"],
                                            "frames": [{"domain": "d01", "time": "20260907Z1200"}]}]
    response = client.get("/api/netcdf/wrf5/d01/20260907Z1200/tiles/0/0/0", params={"variable": "T2C"})
    assert response.status_code == 200
    decoded = decode_numeric_tile(response.content)
    assert decoded.shape == (8, 8) and decoded.unit == "degC"
    assert set(decoded.values) == {1.0, 2.0, 3.0, 4.0}
    assert response.headers["datatiles-source-crs"] == "EPSG:4326"
    assert "nearest-neighbour" in response.headers["datatiles-algorithm"]
    assert client.get(response.request.url, headers={"If-None-Match": response.headers["etag"]}).status_code == 304
    assert client.get("/api/netcdf/wrf5/d01/20260907Z1200/tiles/0/0/0", params={"variable": "SECRET"}).status_code == 404
    assert client.get("/api/netcdf/wrf5/d01/not-a-time/tiles/0/0/0", params={"variable": "T2C"}).status_code == 422
    plain = client.get("/api/netcdf/wrf5/d01/20260907Z1200/tiles/0/0/0",
                       params={"variable": "T2C", "compression": "none"})
    assert plain.status_code == 200 and decode_numeric_tile(plain.content).shape == (8, 8)
