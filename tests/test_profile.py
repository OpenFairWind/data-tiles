import json
from pathlib import Path

from datatiles import DataTiles, encode_numeric_tile
from datatiles.profile import profile_csv, profile_svg, sample_profile


ROOT=Path(__file__).resolve().parents[1]


def _profile_store(tmp_path):
    path = tmp_path / "profile.datatiles"
    store = DataTiles(path, create=True, tile_format="application/vnd.datatiles.numeric")
    store.add_dimension("variable", "text")
    store.add_dimension("release", "text")
    depth = encode_numeric_tile([10, 20, 30, 40], (2, 2), dtype="float32", nodata=-9999, unit="m")
    classes = encode_numeric_tile([4, 4, 3, 3], (2, 2), dtype="uint8", nodata=0, unit="1")
    shelter = encode_numeric_tile([1, 0, 1, 0], (2, 2), dtype="uint8", nodata=255, unit="1")
    store.put(0, 0, 0, depth, {"variable":"depth_below_lat_m", "release":"fixture"}, xyz=True)
    store.put(0, 0, 0, classes, {"variable":"seafloor_class", "release":"fixture"}, xyz=True)
    store.put(0, 0, 0, shelter, {"variable":"northwest_wind_shelter", "release":"fixture"}, xyz=True)
    store.db.execute("INSERT INTO metadata(name,value) VALUES (?,?)", (
        "datatiles:classes", json.dumps({"3":"rock", "4":"sand"}, separators=(",", ":"))))
    store.db.commit()
    return store


def test_profile_decodes_numeric_dimensions_on_demand(tmp_path):
    with _profile_store(tmp_path) as store:
        result = sample_profile(store, (-10, 40), (10, -40), samples=9)

    assert result["type"] == "DataTilesDepthProfile"
    assert "no pre-rendered map tiles" in result["data_source"]
    assert len(result["observations"]) == 9
    assert {o["class_name"] for o in result["observations"]} == {"rock", "sand"}
    assert all(o["depth_tile"]["pixel"] is not None for o in result["observations"])
    assert profile_csv(result).startswith("index,distance_m,longitude,latitude,depth_m,class_code,class_name\n")
    svg = profile_svg(result)
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert result["profile_sha256"] in svg


def test_playground_profile_projection_callback_is_unary():
    page=(ROOT/"src/datatiles/profile-demo.html").read_text()
    assert ".map(coordinate=>ol.proj.toLonLat(coordinate))" in page
    assert ".map(ol.proj.toLonLat)" not in page
    assert "location.protocol==='file:'" in page
    assert "This HTML file is a server-side template" in page
    assert "http://127.0.0.1:8080/playground" in page
