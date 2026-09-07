import json

from fastapi.testclient import TestClient

from datatiles import DataTiles, encode_numeric_tile
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
