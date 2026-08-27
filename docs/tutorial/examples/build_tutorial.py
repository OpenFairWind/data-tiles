#!/usr/bin/env python3
"""Build and verify the self-contained DataTiles zero-to-hero dataset."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from datatiles import DataTiles, decode_numeric_tile, encode_numeric_tile

VALID_TIME=("2026-08-27T00:00:00Z","2026-08-27T06:00:00Z",True,True)


def coordinates(variable: str) -> dict[str,object]:
    return {"variable":variable,"valid_time":VALID_TIME,"release":"tutorial-v1"}


def build(path: Path) -> None:
    if path.exists(): raise SystemExit(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True,exist_ok=True)
    with DataTiles(path,create=True,name="DataTiles zero-to-hero dataset",
                   tile_format="application/vnd.datatiles.numeric") as store:
        store.add_dimension("variable","text",axis="C",description="Measured or derived phenomenon")
        store.add_dimension("valid_time","datetime",axis="T",description="Closed validity interval",extent_kind="interval")
        store.add_dimension("release","text",axis="O",description="Dataset release identifier")
        store.add_crs("horizontal",authority="EPSG",code="3857",uri="http://www.opengis.net/def/crs/EPSG/0/3857")
        store.add_crs("vertical",uri="https://vocab.example.org/datum/tutorial-lat",wkt2="VERTCRS[\"Tutorial depth relative to LAT, positive down\"]")

        depth=[5.0,8.0,12.0,20.0,6.0,9.0,14.0,24.0,7.0,10.0,16.0,28.0,8.0,11.0,18.0,32.0]
        seabed=[4,4,3,6,4,4,3,6,4,3,3,6,5,5,6,6]
        store.put(0,0,0,encode_numeric_tile(depth,(4,4),dtype="float32",nodata=-9999,unit="m"),
                  coordinates("depth_below_lat_m"),data_type="raster",
                  media_type="application/vnd.datatiles.numeric",encoding="DNT1",
                  schema={"shape":[4,4],"quantity":"depth","positive":"down"})
        store.put(0,0,0,encode_numeric_tile(seabed,(4,4),dtype="uint8",nodata=0,unit="1"),
                  coordinates("seafloor_class"),data_type="raster",
                  media_type="application/vnd.datatiles.numeric",encoding="DNT1",
                  schema={"shape":[4,4],"classification":"tutorial-seabed-v1"})
        portrayal=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        store.put(0,0,0,portrayal,coordinates("depth_portrayal"),data_type="raster",
                  media_type="image/png",encoding="PNG",
                  schema={"derivedFrom":"depth_below_lat_m","purpose":"MBTiles fallback exercise"})

        observations={"type":"FeatureCollection","features":[
            {"type":"Feature","id":"station-1","geometry":{"type":"Point","coordinates":[14.20,40.70]},
             "properties":{"name":"Station 1","depth_m":9.0}},
            {"type":"Feature","id":"station-2","geometry":{"type":"Point","coordinates":[14.28,40.62]},
             "properties":{"name":"Station 2","depth_m":18.0}}]}
        store.put(0,0,0,json.dumps(observations,sort_keys=True,separators=(",",":")).encode(),
                  coordinates("survey_stations"),data_type="vector",media_type="application/geo+json",
                  encoding="GeoJSON",schema={"geometryTypes":["Point"],"fields":{"name":"String","depth_m":"Number"}})

        store.add_provenance_agent("agent:tutorial-author","DataTiles tutorial",agent_type="software")
        store.add_provenance_activity("activity:tutorial-build","deterministic-build","Build tutorial raster and vector tiles",
                                      software="datatiles",parameters={"grid":[4,4],"zoom":0})
        source_bytes=json.dumps({"depth":depth,"seabed":seabed,"observations":observations},sort_keys=True,separators=(",",":")).encode()
        store.add_provenance_entity("entity:tutorial-source","source","Embedded tutorial observations",
                                    checksum_algorithm="SHA-256",checksum=hashlib.sha256(source_bytes).hexdigest())
        store.add_provenance_entity("entity:tutorial-container","dataset","Tutorial DataTiles container")
        store.add_provenance_relation("activity:tutorial-build","used","entity:tutorial-source")
        store.add_provenance_relation("entity:tutorial-container","wasGeneratedBy","activity:tutorial-build")
        store.add_provenance_relation("activity:tutorial-build","wasAssociatedWith","agent:tutorial-author")
        for variable in ("depth_below_lat_m","seafloor_class","depth_portrayal","survey_stations"):
            store.link_tile_provenance(0,0,0,coordinates(variable),"entity:tutorial-container")

        metadata={
            "description":"Self-contained raster and vector dataset for the DataTiles zero-to-hero course.",
            "bounds":"-180,-85.05112878,180,85.05112878","center":"14.2,40.7,0","minzoom":"0","maxzoom":"0",
            "version":"1","datatiles:fair_profile":"1","datatiles:identifier":"urn:uuid:4ea0e809-599d-5f2b-9669-75cd132b9997",
            "datatiles:license":"https://spdx.org/licenses/CC-BY-4.0.html","datatiles:access_rights":"public",
            "datatiles:creators":json.dumps([{"name":"DataTiles tutorial"}],separators=(",",":")),
            "datatiles:keywords":json.dumps(["bathymetry","seabed","vector observations"],separators=(",",":")),
            "datatiles:issued":"2026-08-27T00:00:00Z","datatiles:modified":"2026-08-27T00:00:00Z",
            "datatiles:landing_page":"https://example.org/datatiles/tutorial",
            "datatiles:provenance":"entity:tutorial-container",
            "datatiles:classes":json.dumps({"3":"mud","4":"sand","5":"gravel","6":"rock"},separators=(",",":"))}
        for name,value in metadata.items(): store.set_metadata(name,value)
        store.select(coordinates("depth_below_lat_m"))
        errors=store.validate()
        if errors: raise RuntimeError("invalid tutorial dataset: "+"; ".join(errors))


def verify(path: Path) -> None:
    with DataTiles(path,read_only=True) as store:
        errors=store.validate()
        if errors: raise SystemExit("validation failed: "+"; ".join(errors))
        profiles=store.content_profiles()
        if {p["data_type"] for p in profiles}!={"raster","vector"}: raise SystemExit("mixed content is missing")
        depth=decode_numeric_tile(store.get(0,0,0,coordinates("depth_below_lat_m")))
        if depth.shape!=(4,4) or depth.unit!="m": raise SystemExit("depth matrix mismatch")
        if not store.fair_report()["passes"]: raise SystemExit("FAIR object-boundary checks failed")
        columns=[row[1] for row in store.db.execute("PRAGMA table_info(tiles)")]
        if columns!=["zoom_level","tile_column","tile_row","tile_data"]: raise SystemExit("MBTiles interface mismatch")
    print(f"verified {path}")


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("command",choices=("build","verify")); parser.add_argument("file",type=Path)
    args=parser.parse_args()
    if args.command=="build": build(args.file)
    verify(args.file)
    return 0


if __name__=="__main__": raise SystemExit(main())
