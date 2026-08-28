import json

import numpy as np
from PIL import Image

from datatiles.demo import build, runtime_versions, sha256, verify, write_json


def _feature(fid, properties, ring):
    return {"type":"Feature", "id":fid, "properties":properties,
            "geometry":{"type":"Polygon", "coordinates":[ring]}}


def test_two_builds_are_byte_identical(tmp_path):
    work=tmp_path/"work"; raw=work/"raw"; raw.mkdir(parents=True)
    config={
        "demo_id":"fixture", "title":"fixture", "bbox_wgs84":[14.0,40.6,14.2,40.8],
        "grid":{"width":16,"height":16}, "tiles":{"tile_size":16,"minzoom":8,"maxzoom":8},
        "sources":{
            "bathymetry":{"dataset":"bathy","catalogue_uuid":"b","release":"1","license":"test"},
            "substrate":{"dataset":"substrate","catalogue_uuid":"s","release":"1","license":"test"},
            "habitat":{"dataset":"habitat","catalogue_uuid":"h","release":"1","license":"test"}},
        "classification":{"version":"test-v1"}}
    config_path=tmp_path/"config.json"; write_json(config_path,config)
    write_json(tmp_path/"runtime-lock.json",runtime_versions())
    Image.fromarray(np.linspace(-100,-1,256,dtype=np.float32).reshape(16,16)).save(raw/"bathymetry.tif")
    left=[[14.0,40.6],[14.1,40.6],[14.1,40.8],[14.0,40.8],[14.0,40.6]]
    right=[[14.1,40.6],[14.2,40.6],[14.2,40.8],[14.1,40.8],[14.1,40.6]]
    (raw/"substrate.geojson").write_text(json.dumps({"type":"FeatureCollection","features":[
        _feature("a",{"folk":"sand"},left),_feature("b",{"folk":"rock"},right)]}))
    (raw/"habitat.geojson").write_text(json.dumps({"type":"FeatureCollection","features":[
        _feature("c",{"eunis":"Posidonia"},left),_feature("d",{"eunis":"coralligenous"},right)]}))
    for name in ("bathymetry-catalogue.json","substrate-catalogue.json","habitat-catalogue.json"):
        (raw/name).write_text("{}")
    (raw/"bathymetry-capabilities.xml").write_text("<Capabilities/>")
    files={"bathymetry_catalogue":"bathymetry-catalogue.json","substrate_catalogue":"substrate-catalogue.json",
           "habitat_catalogue":"habitat-catalogue.json","bathymetry_capabilities":"bathymetry-capabilities.xml",
           "bathymetry":"bathymetry.tif","substrate":"substrate.geojson","habitat":"habitat.geojson"}
    lock={"lock_version":1,"demo_id":"fixture","config_sha256":sha256(config_path),"sources":{
        key:{"file":name,"sha256":sha256(raw/name),"request_url":"fixture:"+name,"bytes":(raw/name).stat().st_size}
        for key,name in files.items()}}
    write_json(work/"source-lock.json",lock)
    build(config_path,work)
    first=(sha256(work/"gaeta-to-maratea.datatiles"),sha256(work/"gaeta-to-maratea-evidence.zip"))
    verify(config_path,work)
    build(config_path,work)
    second=(sha256(work/"gaeta-to-maratea.datatiles"),sha256(work/"gaeta-to-maratea-evidence.zip"))
    verify(config_path,work)
    assert first==second
