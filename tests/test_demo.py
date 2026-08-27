from datatiles.demo import CLASS_NAMES, classify_habitat, classify_substrate, request_url


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
