import json

from datatiles.static_demo import build_static_demo
from test_profile import _profile_store


def test_static_demo_exports_numeric_and_vector_client_bundle(tmp_path):
    with _profile_store(tmp_path) as store:
        store.db.execute("INSERT OR REPLACE INTO metadata(name,value) VALUES ('bounds','-20,-60,20,60')")
        store.db.execute("INSERT OR REPLACE INTO metadata(name,value) VALUES ('name','Static fixture')")
        store.db.commit(); source=store.path
    output=tmp_path/"static"
    build_static_demo(source,output)
    surface=json.loads((output/"data/surface.json").read_text())
    nautical=json.loads((output/"data/nautical.geojson").read_text())
    assert surface["width"]==128 and len(surface["depth_m"])==128*72
    assert len(surface["northwest_wind_shelter"])==128*72
    assert nautical["features"][0]["properties"]["seamark:type"]=="buoy_lateral"
    assert (output/source.name).read_bytes()==source.read_bytes()
    html=(output/"index.html").read_text()
    assert "live client-side portrayal" in html and "JSON.parse(E(id).textContent)" in html
    assert "__SURFACE_JSON__" not in html and '"northwest_wind_shelter"' in html
    for feature in ("Shadow relief","Depth isolines","Smartly distributed depth samples",
                    "Live 3D visualization","Sheltered from north-west winds"):
        assert feature in html
    assert "toDataURL" in html and "northwest_wind_shelter" in html
