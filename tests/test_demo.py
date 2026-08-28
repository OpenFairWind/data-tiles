import json

from datatiles.demo import CLASS_NAMES, classify_habitat, classify_substrate, overpass_to_geojson, request_url


def test_substrate_generalization():
    assert classify_substrate({"folk_5": "Rock and other hard substrate"}) == 6
    assert classify_substrate({"folk_5": "Coarse sediment and gravel"}) == 5
    assert classify_substrate({"folk_5": "Sand"}) == 4
    assert classify_substrate({"folk_5": "Mud and sandy mud"}) == 3
    assert classify_substrate({"folk_5": "Sand and mud"}) == 2


def test_biogenic_habitat_generalization():
    assert classify_habitat({"label": "Mediterranean coralligenous reef"}) == 9
    assert classify_habitat({"label": "Posidonia oceanica seagrass beds"}) == 8
    assert classify_habitat({"label": "Maerl and macroalgal communities"}) == 7
    assert classify_habitat({"label": "Sublittoral mud"}) == 0


def test_request_url_is_stable():
    assert request_url("https://example.test/wfs", {"service":"WFS","bbox":"13.7,40.45,14.55,41.1"}) == \
        "https://example.test/wfs?service=WFS&bbox=13.7,40.45,14.55,41.1"


def test_class_legend_is_complete():
    assert sorted(CLASS_NAMES) == list(range(10))


def test_overpass_seamarks_become_deterministic_geojson(tmp_path):
    source=tmp_path/"overpass.json"
    source.write_text(json.dumps({"elements":[
        {"type":"way","id":2,"tags":{"seamark:type":"fairway","source":"omitted"},
         "geometry":[{"lon":14.0,"lat":40.0},{"lon":14.1,"lat":40.1}]},
        {"type":"node","id":1,"lon":14.05,"lat":40.05,"tags":{"seamark:type":"buoy_lateral","name":"A"}}]}))
    result=overpass_to_geojson(source)
    assert [feature["id"] for feature in result["features"]]==["node/1","way/2"]
    assert "source" not in result["features"][1]["properties"]
