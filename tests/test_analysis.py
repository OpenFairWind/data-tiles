import pytest

from datatiles.analysis import contours, point_values, query_areas
from datatiles.store import DataTilesError
from test_profile import _profile_store


def test_point_contour_and_compound_query(tmp_path):
    with _profile_store(tmp_path) as store:
        point=point_values(store,-10,40)
        assert point["depth_m"]==10
        assert point["class_name"]=="sand"
        assert point["northwest_wind_sheltered"] is True
        assert point["evidence"]["depth_below_lat_m"]["pixel"]==[0,0]
        selected=query_areas(store,(-20,10,-1,60),min_depth=5,max_depth=25,classes={"sand"},sheltered_by="nw",cells=4)
        assert selected["features"]
        assert all(f["properties"]["class_name"]=="sand" and 5<f["properties"]["depth_m"]<25 for f in selected["features"])
        isolines=contours(store,(-20,-60,20,60),interval=10,cells=8)
        assert isolines["type"]=="FeatureCollection"
        assert isolines["datatiles:dataSource"].startswith("live marching-squares")


def test_analysis_rejects_nonfinite_or_out_of_range_bbox(tmp_path):
    with _profile_store(tmp_path) as store:
        with pytest.raises(DataTilesError,match="finite"): query_areas(store,(0,0,float("nan"),1))
        with pytest.raises(DataTilesError,match="CRS84"): contours(store,(-181,-10,10,10))


def test_adaptive_contours_preserve_shallow_detail_and_thin_deep_levels(tmp_path):
    from test_profile import _profile_store
    with _profile_store(tmp_path) as store:
        result=contours(store,(-20,-60,20,60),interval=5,cells=8,adaptive=True)
    assert result["datatiles:spacing"].startswith("adaptive")
    assert all(feature["properties"]["contour_class"] in {"minor","index","major"}
               for feature in result["features"])
