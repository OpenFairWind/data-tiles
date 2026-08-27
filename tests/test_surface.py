import json
from datatiles.analysis import surface_grid
from datatiles.store import DataTiles, DataTilesError
from test_profile import _profile_store


def test_surface_is_numeric_checksummed_and_bounded(tmp_path):
    with _profile_store(tmp_path) as store:
        bbox=(-20,-60,20,60)
        a=surface_grid(store,bbox,width=12,height=10)
        b=surface_grid(store,bbox,width=12,height=10)
        assert a==b
        assert a["data_source"]=="on-demand DNT1 numeric tile decoding"
        assert len(a["depth_m"])==10 and len(a["depth_m"][0])==12
        assert len(a["seafloor_class"])==10
        assert len(a["surface_sha256"])==64
        json.dumps(a,allow_nan=False)
        try: surface_grid(store,bbox,width=129,height=10)
        except DataTilesError: pass
        else: raise AssertionError("unbounded surface accepted")
