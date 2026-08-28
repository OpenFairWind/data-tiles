import json
import threading
import urllib.error
import urllib.request
import urllib.parse
from http.server import ThreadingHTTPServer

import pytest

from datatiles.server import handler_for
from datatiles import DataTiles
from test_profile import _profile_store


@pytest.fixture
def service(tmp_path):
    with _profile_store(tmp_path) as store:
        server=ThreadingHTTPServer(("127.0.0.1",0),handler_for(store.path))
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        yield f"http://127.0.0.1:{server.server_port}",store.path.stem
        server.shutdown(); thread.join(timeout=5); server.server_close()


def get_json(url):
    with urllib.request.urlopen(url,timeout=5) as response:
        return response.status,response.headers["Content-Type"],json.load(response)


def test_discovery_openapi_and_fair_resources(service):
    base,collection=service
    assert get_json(base+"/")[2]["links"]
    assert get_json(base+"/conformance")[2]["conformsTo"]
    assert f"/collections/{collection}/surface" in get_json(base+"/api")[2]["paths"]
    assert get_json(base+f"/collections/{collection}")[2]["id"]==collection
    assert "checks" in get_json(base+f"/collections/{collection}/fair")[2]


def test_analysis_endpoints_and_content_types(service):
    base,collection=service; root=base+f"/collections/{collection}"
    assert get_json(root+"/point?coords=-10,40")[2]["depth_m"]==10
    surface=get_json(root+"/surface?bbox=-20,-60,20,60&width=12&height=10")[2]
    assert surface["width"]==12 and len(surface["surface_sha256"])==64
    assert get_json(root+"/contours?bbox=-20,-60,20,60&cells=8&interval=10")[1].startswith("application/geo+json")
    nautical=get_json(root+"/nautical-items?bbox=-20,-60,20,60")[2]
    assert nautical["features"][0]["properties"]["seamark:type"]=="buoy_lateral"
    assert nautical["datatiles:dataSource"].startswith("stored tiled GeoJSON")
    assert get_json(root+"/query?bbox=-20,-60,20,60&cells=4&min_depth=5&classes=sand")[2]["type"]=="FeatureCollection"
    with urllib.request.urlopen(root+"/profile?start=-10,40&end=10,-40&samples=9&f=svg") as response:
        assert response.headers["Content-Type"].startswith("image/svg+xml") and response.read().startswith(b"<svg")


def test_playground_and_error_contract(service):
    base,collection=service
    with urllib.request.urlopen(base+"/playground") as response:
        html=response.read().decode()
    assert collection in html and "Live 3D visualization" in html and "/surface?bbox=" in html
    for path,status in [(f"/collections/{collection}/point?coords=bad",400),("/missing",404),
                        (f"/collections/{collection}/surface?bbox=-20,-60,20,60&width=129",400)]:
        with pytest.raises(urllib.error.HTTPError) as caught: urllib.request.urlopen(base+path)
        assert caught.value.code==status


def test_collection_identifiers_are_url_encoded(tmp_path):
    path=tmp_path/"collection with spaces.datatiles"
    with DataTiles(path,create=True) as store:
        server=ThreadingHTTPServer(("127.0.0.1",0),handler_for(path))
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            encoded=urllib.parse.quote(path.stem,safe="")
            status,_,value=get_json(f"http://127.0.0.1:{server.server_port}/collections/{encoded}")
            assert status==200 and value["id"]==path.stem
            assert all(" " not in link["href"] for link in value["links"])
        finally: server.shutdown(); thread.join(timeout=5); server.server_close()
