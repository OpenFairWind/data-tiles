from __future__ import annotations
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from datatiles_store.catalog import extract_metadata, scan_catalog, tile_bytes
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
