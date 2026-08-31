import json
import os
import subprocess
import sys
from pathlib import Path

from datatiles import DataTiles

ROOT=Path(__file__).resolve().parents[1]


def convert(tmp_path, utility, input_name, content, *options):
    source=tmp_path/input_name; output=tmp_path/f"{utility}.datatiles"
    source.write_text(content,encoding="utf-8")
    env={**os.environ,"PYTHONPATH":os.fspath(ROOT/"src")}
    result=subprocess.run([sys.executable,os.fspath(ROOT/"utils"/utility),os.fspath(source),os.fspath(output),
                           "--min-zoom","0","--max-zoom","1",*options],env=env,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
    with DataTiles(output,read_only=True) as store:
        assert store.validate()==[]
        assert store.content_profiles()[0]["media_type"]=="application/geo+json"
        assert store.metadata()["datatiles:source_sha256"]
        rows=store.db.execute("SELECT tile_data FROM datatiles_tiles ORDER BY zoom_level,tile_column,tile_row").fetchall()
        return [json.loads(row[0]) for row in rows]


def test_geojson_converter_tiles_features_deterministically(tmp_path):
    value={"type":"FeatureCollection","features":[{"type":"Feature","id":"a","geometry":{"type":"Point","coordinates":[14.2,40.7]},"properties":{"value":3}}]}
    tiles=convert(tmp_path,"geojson2datatiles","points.geojson",json.dumps(value))
    assert len(tiles)==2 and all(tile["features"][0]["id"]=="a" for tile in tiles)


def test_csv_converter_requires_and_supports_coordinate_columns(tmp_path):
    tiles=convert(tmp_path,"csv2datatiles","points.csv","Latitude,Longitude,name\n40.7,14.2,station\n")
    assert tiles[0]["features"][0]["properties"]=={"name":"station"}
    bad=tmp_path/"bad.csv"; bad.write_text("x,y\n1,2\n"); output=tmp_path/"bad.datatiles"
    result=subprocess.run([sys.executable,os.fspath(ROOT/"utils/csv2datatiles"),os.fspath(bad),os.fspath(output)],text=True,capture_output=True)
    assert result.returncode==2 and "latitude and longitude" in result.stderr and not output.exists()


def test_xml_gpx_and_ndjson_converters(tmp_path):
    xml=convert(tmp_path,"xml2datatiles","points.xml","<records><station><latitude>40.7</latitude><longitude>14.2</longitude><name>A</name></station></records>")
    assert xml[0]["features"][0]["properties"]["name"]=="A"
    gpx=convert(tmp_path,"gpx2datatiles","track.gpx",'<gpx version="1.1"><wpt lat="40.7" lon="14.2"><name>A</name></wpt><trk><name>T</name><trkseg><trkpt lat="40.7" lon="14.2"/><trkpt lat="40.8" lon="14.3"/></trkseg></trk></gpx>')
    assert {f["geometry"]["type"] for f in gpx[0]["features"]}=={"Point","LineString"}
    feature={"type":"Feature","geometry":{"type":"Point","coordinates":[14.2,40.7]},"properties":{}}
    ndjson=convert(tmp_path,"ndjson2datatiles","points.geojsonl",json.dumps(feature)+"\n")
    assert ndjson[0]["features"]


def test_bundled_ports_geojson_matches_tutorial_contract(tmp_path):
    source=ROOT/"resources/ports.json"; output=tmp_path/"ports.datatiles"
    value=json.loads(source.read_text(encoding="utf-8"))
    assert value["type"]=="FeatureCollection" and len(value["features"])==1140
    assert {feature["geometry"]["type"] for feature in value["features"]}=={"Point"}
    env={**os.environ,"PYTHONPATH":os.fspath(ROOT/"src")}
    result=subprocess.run([sys.executable,os.fspath(ROOT/"utils/geojson2datatiles"),os.fspath(source),os.fspath(output),
                           "--name","Ports collection","--variable","ports","--min-zoom","0","--max-zoom","0"],
                          env=env,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
    with DataTiles(output,read_only=True) as store:
        assert store.validate()==[]
        collection=json.loads(store.get(0,0,0,{"variable":"ports"}))
        assert len(collection["features"])==1140
        assert store.metadata()["datatiles:source_sha256"]=="519aacd40928770c72ce9b9d714776b4689c1352ec56f5a5b3ee52b60982fec9"
