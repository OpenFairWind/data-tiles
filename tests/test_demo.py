import json

import numpy as np
from PIL import Image

from datatiles.demo import (CLASS_NAMES, _raw_requests, bbox_contains, classify_habitat, classify_substrate,
                            apply_land_mask, compose_bathymetry, overpass_to_geojson, read_bathymetry, request_url)


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


def test_frozen_source_must_contain_widened_publication_bbox():
    required=[12.85,39.99852,15.71851,41.21408]
    assert not bbox_contains([13.37082,39.79852,15.91851,41.41408],required)
    assert bbox_contains([12.65,39.79852,15.91851,41.41408],required)


def test_class_legend_is_complete():
    assert sorted(CLASS_NAMES) == list(range(10))


def test_overpass_seamarks_become_deterministic_geojson(tmp_path):
    source=tmp_path/"overpass.json"
    source.write_text(json.dumps({"elements":[
        {"type":"way","id":2,"tags":{"seamark:type":"fairway","source":"omitted"},
         "geometry":[{"lon":14.0,"lat":40.0},{"lon":14.1,"lat":40.1}]},
        {"type":"node","id":3,"lon":14.2,"lat":40.2,"tags":{"place":"town","name":"Not a seamark"}},
        {"type":"node","id":1,"lon":14.05,"lat":40.05,"tags":{"seamark:type":"buoy_lateral","name":"A"}}]}))
    result=overpass_to_geojson(source)
    assert [feature["id"] for feature in result["features"]]==["node/1","way/2"]
    assert "source" not in result["features"][1]["properties"]


def test_gaeta_to_maratea_configuration_extent():
    from pathlib import Path
    config=json.loads((Path(__file__).parents[1]/"demo/from-gaeta-to-maratea/config.json").read_text())
    assert config["title"]=="From Gaeta to Maratea"
    assert config["bbox_wgs84"]==[12.85,39.99852,15.71851,41.21408]
    assert config["grid"]=={"width":2754,"height":1167}
    west,south,east,north=config["bbox_wgs84"]
    islands={"Palmarola":(12.96,40.94),"Ponza":(12.96,40.90),"Zannone":(13.06,40.97),
             "Ventotene":(13.43,40.79),"Santo Stefano":(13.46,40.79)}
    assert all(west<=lon<=east and south<=lat<=north for lon,lat in islands.values())
    assert config["tiles"]["maxzoom"]==12
    nautical=[item for item in _raw_requests(config) if item[0].startswith("nautical_") and item[0]!="nautical_catalogue"]
    assert [item[0] for item in nautical]==["nautical_0","nautical_1","nautical_2","nautical_3"]


def test_bathymetry_halo_is_cropped_before_resampling(tmp_path):
    source=-np.arange(1,101,dtype=np.float32).reshape(10,10)
    path=tmp_path/"halo.tif"; Image.fromarray(source).save(path)
    result,transform=read_bathymetry(path,6,6,source_bbox=[0,0,10,10],target_bbox=[2,2,8,8])
    assert transform.startswith("negative_elevation_to_positive_depth")
    assert result.shape==(6,6)
    np.testing.assert_array_equal(result,-source[2:8,2:8])


def test_land_mask_and_finest_finite_jamme_fallback():
    emodnet=np.array([[-10,5],[-30,-40]],dtype=np.float32)
    coarse=np.array([[20,np.nan],[np.nan,42]],dtype=np.float32)
    fine=np.array([[11,np.nan],[33,np.nan]],dtype=np.float32)
    depth,source,classes=compose_bathymetry(
        np.where(emodnet<0,-emodnet,-9999),[(40,coarse),(2,fine)])
    np.testing.assert_array_equal(depth,np.array([[11,-9999],[33,42]],dtype=np.float32))
    assert classes[int(source[0,0])]=="JammeGaia22 2 m"
    assert classes[int(source[0,1])]=="land/nodata"
    assert classes[int(source[1,1])]=="JammeGaia22 40 m"


def test_gshhg_mask_overrides_all_bathymetry_sources():
    depth=np.array([[4,5],[6,7]],dtype=np.float32)
    source=np.array([[2,1],[3,4]],dtype=np.uint8)
    masked_depth,masked_source=apply_land_mask(depth,source,np.array([[0,1],[1,0]],dtype=np.uint8))
    np.testing.assert_array_equal(masked_depth,np.array([[4,-9999],[-9999,7]],dtype=np.float32))
    np.testing.assert_array_equal(masked_source,np.array([[2,0],[0,4]],dtype=np.uint8))
