import sqlite3
import gzip
import json

import pytest

from datatiles import DataTiles, DataTilesError
from datatiles import decode_numeric_tile, encode_numeric_tile


def make_store(tmp_path):
    path = tmp_path / "test.datatiles"
    store = DataTiles(path, create=True, name="test", tile_format="png")
    store.add_dimension("time", "datetime", axis="T")
    store.add_dimension("depth", "float", axis="Z", unit="m")
    return path, store


def test_roundtrip_and_order_independence(tmp_path):
    _, store = make_store(tmp_path)
    first = {"time": "2026-08-26T12:00:00+00:00", "depth": 10}
    store.put(2, 1, 3, b"tile", first)
    assert store.get(2, 1, 3, {"depth": "10.0", "time": "2026-08-26T12:00:00Z"}) == b"tile"
    store.close()


def test_mbtiles_view_selected_slice(tmp_path):
    _, store = make_store(tmp_path)
    a = {"time": "2026-08-26T12:00:00Z", "depth": 10}
    b = {"time": "2026-08-26T18:00:00Z", "depth": 10}
    store.put(1, 0, 0, b"a", a)
    store.put(1, 0, 0, b"b", b)
    store.select(b)
    assert store.db.execute("SELECT tile_data FROM tiles").fetchone()[0] == b"b"
    assert store.db.execute("PRAGMA table_info(tiles)").fetchall()[0][1] == "zoom_level"
    store.close()


def test_xyz_conversion(tmp_path):
    _, store = make_store(tmp_path)
    c = {"time": "2026-08-26T12:00:00Z", "depth": 0}
    store.put(3, 2, 1, b"xyz", c, xyz=True)
    assert store.get(3, 2, 6, c) == b"xyz"
    store.close()


def test_required_and_unknown_dimensions(tmp_path):
    _, store = make_store(tmp_path)
    with pytest.raises(DataTilesError, match="missing required"):
        store.put(0, 0, 0, b"x", {"depth": 1})
    with pytest.raises(DataTilesError, match="unknown"):
        store.put(0, 0, 0, b"x", {"depth": 1, "time": "2026-08-26T12:00:00Z", "member": 2})
    store.close()


def test_validation(tmp_path):
    _, store = make_store(tmp_path)
    assert store.validate() == []
    store.close()


def test_interval_and_numeric_tile(tmp_path):
    path = tmp_path / "numeric.datatiles"
    store = DataTiles(path, create=True, tile_format="application/vnd.datatiles.numeric")
    store.add_dimension("time", "datetime", axis="T", extent_kind="interval")
    coordinate = {"time": ("2026-08-27T00:00:00Z", "2026-08-27T06:00:00Z", True, False)}
    blob = encode_numeric_tile([1, 2, 3, 4], (2, 2), dtype="float32", unit="K")
    store.put(0, 0, 0, blob, coordinate)
    decoded = decode_numeric_tile(store.get(0, 0, 0, coordinate))
    assert decoded.shape == (2, 2)
    assert decoded.values == (1.0, 2.0, 3.0, 4.0)
    value = store.db.execute("SELECT lower_inclusive,upper_inclusive,is_interval FROM datatiles_values").fetchone()
    assert tuple(value) == (1, 0, 1)
    store.close()


def test_mixed_raster_and_vector_content_profiles(tmp_path):
    path=tmp_path/"mixed.datatiles"
    with DataTiles(path,create=True,tile_format="application/vnd.datatiles.numeric") as store:
        store.add_dimension("variable","text")
        raster=encode_numeric_tile([1,2,3,4],(2,2),dtype="float32",unit="m")
        store.put(0,0,0,raster,{"variable":"depth"},data_type="raster",
                  media_type="application/vnd.datatiles.numeric",encoding="DNT1")
        vector=gzip.compress(b"valid-mvt-fixture")
        vector_schema={"vector_layers":[{"id":"observations","fields":{"value":"Number"}}]}
        store.put(0,0,0,vector,{"variable":"observations"},data_type="vector",
                  media_type="application/vnd.mapbox-vector-tile",encoding="MVT+gzip",schema=vector_schema)
        geojson=json.dumps({"type":"FeatureCollection","features":[]},separators=(",",":")).encode()
        store.put(0,0,0,geojson,{"variable":"coastline"},data_type="vector",
                  media_type="application/geo+json",encoding="GeoJSON",schema={"geometryTypes":["LineString"]})
        profiles=store.content_profiles()
        assert {p["data_type"] for p in profiles}=={"raster","vector"}
        store.select({"variable":"observations"})
        metadata=dict(store.db.execute("SELECT name,value FROM metadata"))
        assert metadata["format"]=="pbf" and json.loads(metadata["json"])==vector_schema
        assert store.db.execute("SELECT tile_data FROM tiles").fetchone()[0]==vector
        store.select({"variable":"depth"})
        metadata=dict(store.db.execute("SELECT name,value FROM metadata"))
        assert metadata["format"]=="application/vnd.datatiles.numeric" and "json" not in metadata
        store.select({"variable":"coastline"})
        metadata=dict(store.db.execute("SELECT name,value FROM metadata"))
        assert metadata["format"]=="application/geo+json" and "json" not in metadata
        assert store.validate()==[]


def test_opening_missing_or_unrelated_sqlite_is_rejected(tmp_path):
    with pytest.raises(DataTilesError,match="does not exist"): DataTiles(tmp_path/"missing.datatiles")
    unrelated=tmp_path/"other.sqlite"
    sqlite3.connect(unrelated).close()
    with pytest.raises(DataTilesError,match="not a DataTiles"): DataTiles(unrelated)


def test_empty_interval_and_non_boolean_are_rejected(tmp_path):
    _,store=make_store(tmp_path)
    store.add_dimension("flag","boolean",required=False)
    store.add_dimension("window","float",required=False,extent_kind="interval")
    with pytest.raises(DataTilesError,match="empty"):
        store.put(0,0,0,b"x",{"time":"2026-08-26T12:00:00Z","depth":1,"window":(1,1,False,False)})
    with pytest.raises(DataTilesError,match="boolean"):
        store.put(0,0,0,b"x",{"time":"2026-08-26T12:00:00Z","depth":1,"flag":2})
    store.close()


def test_revision_two_is_migrated_with_content_profiles(tmp_path):
    path=tmp_path/"legacy.datatiles"
    with DataTiles(path,create=True,tile_format="png") as store:
        store.put(0,0,0,b"png",{})
        store.db.execute("DROP TABLE datatiles_contents")
        for table in ("datatiles_release", "datatiles_drm_policies", "datatiles_commercial_products",
                      "datatiles_signatures", "datatiles_integrity_manifests", "datatiles_publication_evidence",
                      "datatiles_fair_agents", "datatiles_rights", "datatiles_related_identifiers",
                      "datatiles_identifiers", "datatiles_variable_identifiers", "datatiles_variables"):
            store.db.execute(f"DROP TABLE {table}")
        store.db.execute("DELETE FROM metadata WHERE name='datatiles:default_media_type'")
        store.db.execute("PRAGMA user_version=2"); store.db.commit()
    with DataTiles(path) as migrated:
        assert migrated.db.execute("PRAGMA user_version").fetchone()[0]==8
        assert migrated.content_profiles()[0]["media_type"]=="image/png"
        assert migrated.get(0,0,0,{})==b"png"


def test_tile_matrix_and_payload_types_are_bounded(tmp_path):
    path=tmp_path/"bounded.datatiles"
    with DataTiles(path,create=True) as store:
        with pytest.raises(DataTilesError,match="outside zoom matrix"): store.put(31,0,0,b"x",{})
        with pytest.raises(DataTilesError,match="bytes-like"): store.put(0,0,0,"not bytes",{})


def test_numeric_coordinate_canonicalization_is_strict(tmp_path):
    path=tmp_path/"strict.datatiles"
    with DataTiles(path,create=True) as store:
        store.add_dimension("integer","integer")
        store.add_dimension("float","float")
        with pytest.raises(DataTilesError,match="integer"): store.put(0,0,0,b"x",{"integer":1.5,"float":2})
        with pytest.raises(DataTilesError,match="not boolean"): store.put(0,0,0,b"x",{"integer":1,"float":True})


def test_public_metadata_api_protects_managed_keys(tmp_path):
    path=tmp_path/"metadata.datatiles"
    with DataTiles(path,create=True) as store:
        store.set_metadata("description","A test object")
        assert store.metadata()["description"]=="A test object"
        with pytest.raises(DataTilesError,match="managed"): store.set_metadata("format","pbf")
        with pytest.raises(DataTilesError,match="must be text"): store.set_metadata("version",1)


def test_standalone_mbtiles_export_uses_physical_standard_tables(tmp_path):
    source=tmp_path/"source.datatiles"; target=tmp_path/"fallback.mbtiles"
    with DataTiles(source,create=True,name="Fallback",tile_format="png") as store:
        store.add_dimension("time","datetime",axis="T")
        coordinates={"time":"2026-08-27T00:00:00Z"}
        store.put(2,1,2,b"png-bytes",coordinates,media_type="image/png")
        store.select(coordinates)
        assert store.export_mbtiles(target)==target
    db=sqlite3.connect(target)
    objects=dict(db.execute("SELECT name,type FROM sqlite_master WHERE name IN ('metadata','tiles')"))
    assert objects=={"metadata":"table","tiles":"table"}
    assert [r[1] for r in db.execute("PRAGMA table_info(metadata)")]==["name","value"]
    assert [r[1] for r in db.execute("PRAGMA table_info(tiles)")]==["zoom_level","tile_column","tile_row","tile_data"]
    assert not db.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'datatiles_%'").fetchone()
    metadata=dict(db.execute("SELECT name,value FROM metadata"))
    assert metadata["format"]=="png" and metadata["minzoom"]==metadata["maxzoom"]=="2"
    assert db.execute("SELECT * FROM tiles").fetchone()==(2,1,2,b"png-bytes")
    db.close()


def test_mbtiles_export_vector_metadata_and_rejections(tmp_path):
    source=tmp_path/"source.datatiles"; vector_target=tmp_path/"vector.mbtiles"
    with DataTiles(source,create=True,tile_format="application/vnd.datatiles.numeric") as store:
        store.add_dimension("variable","text")
        numeric=encode_numeric_tile([1],(1,1),dtype="float32",unit="m")
        store.put(0,0,0,numeric,{"variable":"depth"})
        schema={"vector_layers":[{"id":"observations","fields":{"value":"Number"}}]}
        store.put(0,0,0,gzip.compress(b"mvt"),{"variable":"features"},data_type="vector",
                  media_type="application/vnd.mapbox-vector-tile",encoding="MVT+gzip",schema=schema)
        store.export_mbtiles(vector_target,{"variable":"features"})
        assert json.loads(dict(sqlite3.connect(vector_target).execute("SELECT name,value FROM metadata"))["json"])==schema
        with pytest.raises(DataTilesError,match="not directly representable"):
            store.export_mbtiles(tmp_path/"numeric.mbtiles",{"variable":"depth"})
        with pytest.raises(DataTilesError,match="already exists"):
            store.export_mbtiles(vector_target,{"variable":"features"})
