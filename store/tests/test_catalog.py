from __future__ import annotations
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from datatiles import DataTiles, encode_numeric_tile
from datatiles_store.catalog import extract_metadata, preview_tile, scan_catalog, tile_bytes
from datatiles_store.models import Base, CatalogItem


def make_tile(path: Path):
    con=sqlite3.connect(path)
    con.executescript('''
    PRAGMA user_version=7;
    CREATE TABLE metadata(name TEXT PRIMARY KEY,value TEXT);
    INSERT INTO metadata VALUES('name','Test Sea Depth');
    INSERT INTO metadata VALUES('description','Bathymetry test product');
    INSERT INTO metadata VALUES('bounds','12,39,16,42');
    INSERT INTO metadata VALUES('minzoom','4');
    INSERT INTO metadata VALUES('maxzoom','8');
    CREATE TABLE datatiles_variables(variable_id INTEGER PRIMARY KEY,name TEXT,standard_name TEXT,standard_name_vocabulary TEXT,standard_name_vocabulary_version TEXT,canonical_unit TEXT,long_name TEXT,description TEXT);
    INSERT INTO datatiles_variables VALUES(1,'bathymetry','sea_floor_depth_below_geoid','CF','94','m','Depth',NULL);
    CREATE TABLE datatiles_rights(rights_id INTEGER PRIMARY KEY,scope TEXT,license_expression TEXT,license_uri TEXT,rights_holder TEXT,attribution_text TEXT,access_rights TEXT,applies_to TEXT);
    INSERT INTO datatiles_rights VALUES(1,'dataset','CC-BY-4.0','https://creativecommons.org/licenses/by/4.0/','Example','Credit Example','open',NULL);
    CREATE TABLE tiles(zoom_level INTEGER,tile_column INTEGER,tile_row INTEGER,tile_data BLOB);
    ''')
    con.commit(); con.close()


def test_metadata_extraction(tmp_path):
    p=tmp_path/'a.datatiles'; make_tile(p)
    d=extract_metadata(p)
    assert d['revision']==7
    assert d['variables'][0]['standard_name']=='sea_floor_depth_below_geoid'
    assert d['rights'][0]['license_expression']=='CC-BY-4.0'
    assert d['bounds']==[12.0,39.0,16.0,42.0]


def test_scan_indexes_searchable_metadata(tmp_path):
    p=tmp_path/'a.datatiles'; make_tile(p)
    engine=create_engine('sqlite:///:memory:'); Base.metadata.create_all(engine)
    with Session(engine) as db:
        result=scan_catalog(db,tmp_path,('.datatiles',))
        assert result=={'indexed':1,'failed':0}
        item=db.query(CatalogItem).one()
        assert 'sea_floor_depth_below_geoid' in item.search_text
        assert item.sha256 and len(item.sha256)==64


def test_tile_xyz_to_tms_and_png_detection(tmp_path):
    p=tmp_path/'a.datatiles'; make_tile(p)
    png=b'\x89PNG\r\n\x1a\nrest'
    con=sqlite3.connect(p); con.execute('INSERT INTO tiles VALUES(2,1,2,?)',(png,)); con.commit(); con.close()
    data,mime=tile_bytes(p,2,1,1) # XYZ y=1 -> TMS y=2
    assert data==png and mime=='image/png'


def test_revision_8_metadata_and_numeric_preview_use_current_schema(tmp_path):
    path = tmp_path / "revision-8.datatiles"
    with DataTiles(path, create=True, name="Revision 8 depth", tile_format="application/vnd.datatiles.numeric") as store:
        store.add_dimension("variable", "text", axis="C")
        store.add_variable("depth", "sea_floor_depth_below_sea_surface", canonical_unit="m")
        store.add_rights("dataset", "CC-BY-4.0", license_uri="https://creativecommons.org/licenses/by/4.0/")
        store.add_commercial_product("urn:example:depth", issuer="Example Institute", terms_uri="https://example.invalid/terms")
        store.set_release("urn:example:depth", "2026.1", 1, released_at="2026-08-29T00:00:00Z")
        payload = encode_numeric_tile([1.0, 2.0, 3.0, 4.0], (2, 2), dtype="float32", compression="none", unit="m")
        store.put(0, 0, 0, payload, {"variable": "depth"}, xyz=True)
        store.select({"variable": "depth"})

    detail = extract_metadata(path)
    assert detail["revision"] == 8
    assert detail["dimensions"][0]["value_type"] == "text"
    assert detail["contents"][0]["encoding"] == "DNT1"
    assert detail["commercial"][0]["issuer"] == "Example Institute"
    assert detail["release"]["sequence"] == 1
    preview = preview_tile(path)
    assert preview["encoding"] == "DNT1"
    assert preview["media_type"] == "application/vnd.datatiles.numeric"
    assert preview["tile_data"] == payload
