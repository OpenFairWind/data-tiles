from pathlib import Path

from datatiles import DataTiles, encode_numeric_tile
from demo.weather.app import weather_config


def test_weather_demo_discovers_numeric_frame_and_zoom_domains(tmp_path):
    path = tmp_path / "wrf5_20260907Z1200.mbtiles"
    coordinates = {"variable": "wrf5_t2c", "product": "wrf5", "domain": "d02",
                   "valid_time": "2026-09-07T12:00:00Z"}
    with DataTiles(path, create=True, tile_format="application/vnd.datatiles.numeric") as store:
        for name, value_type in (("variable", "text"), ("product", "text"), ("domain", "text"),
                                 ("valid_time", "datetime")):
            store.add_dimension(name, value_type)
        store.put(5, 16, 12, encode_numeric_tile([20.0] * 64, (8, 8), dtype="float32", unit="degC"),
                  coordinates, xyz=True, data_type="raster",
                  media_type="application/vnd.datatiles.numeric", encoding="DNT1")
        store.set_metadata("bounds", "13,39,16,42")
        store.set_metadata("minzoom", "3")
        store.set_metadata("maxzoom", "10")
        store.set_metadata("datatiles:meteouniparthenope_domain_selection", "z4:wrf5/d01,z5:wrf5/d02,z6:wrf5/d03")
    config = weather_config(path)
    assert config["dataset"] == path.stem
    assert config["minzoom"] == 4 and config["maxzoom"] == 6
    assert config["domainByZoom"] == {"4": "d01", "5": "d02", "6": "d03"}
    assert config["variables"] == ["wrf5_t2c"]
    assert config["validTimes"] == ["2026-09-07T12:00:00.000000Z"]


def test_weather_demo_uses_leaflet_datatiles_plugin():
    root = Path(__file__).parents[1]
    html = (root / "demo/weather/index.html").read_text()
    script = (root / "demo/weather/static/weather.js").read_text()
    plugin = (root / "plugins/leaflet/datatiles-leaflet.js").read_text()
    assert "leaflet@1.9.4" in html and "clientLayer" in script
    assert 'from "/plugins/leaflet/datatiles-leaflet.js"' in script
    assert 'typeof dimensions === "function"' in plugin
    assert "fetchDNT1" in script and "not for navigation" in html.lower()
