"""Dependency-free read-only OGC API façade for a DataTiles file."""
from __future__ import annotations

import argparse
import importlib.resources
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from .store import DataTiles, DataTilesError
from .profile import parse_point, profile_csv, profile_svg, sample_profile
from .analysis import contours, point_values, query_areas, stored_vector_features, surface_grid

CONFORMANCE = [
    "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/json",
    "http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/core",
]


def _json(handler: BaseHTTPRequestHandler, status: int, value: object, content_type: str = "application/json") -> None:
    body = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
    handler.send_response(status); handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body))); handler.end_headers(); handler.wfile.write(body)


def _body(handler: BaseHTTPRequestHandler, status: int, value: str | bytes, content_type: str) -> None:
    body=value.encode() if isinstance(value,str) else value
    handler.send_response(status); handler.send_header("Content-Type",content_type); handler.send_header("Content-Length",str(len(body)))
    handler.end_headers(); handler.wfile.write(body)


def _coordinates(query: dict[str, list[str]], dimensions: set[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name in dimensions:
        if name not in query: continue
        value = query[name][0]
        if "/" in value:
            lower, upper = value.split("/", 1)
            result[name] = (lower, upper)
        else:
            result[name] = value
    return result


def handler_for(path: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "DataTiles/0.15"

        def do_GET(self) -> None:
            parsed = urlparse(self.path); parts = [unquote(p) for p in parsed.path.split("/") if p]
            with DataTiles(path,read_only=True) as store:
                metadata = dict(store.db.execute("SELECT name,value FROM metadata"))
                collection = path.stem
                collection_url=quote(collection,safe="")
                dims = [dict(r) for r in store.db.execute(
                    "SELECT name,value_type,axis,unit,description,required,extent_kind FROM datatiles_dimensions ORDER BY ordering,name")]
                crs = [dict(r) for r in store.db.execute("SELECT role,authority,code,uri,wkt2,projjson,coordinate_epoch FROM datatiles_crs")]
                if not parts:
                    return _json(self, 200, {"title": metadata.get("name", collection),
                        "description": metadata.get("description", "DataTiles multidimensional tileset"),
                        "links": [{"rel":"self","href":"/","type":"application/json"},
                                  {"rel":"conformance","href":"/conformance","type":"application/json"},
                                  {"rel":"data","href":"/collections","type":"application/json"},
                                  {"rel":"service-desc","href":"/api","type":"application/vnd.oai.openapi+json;version=3.0"}]})
                if parts in (["demo","profile"],["playground"]):
                    html=importlib.resources.files("datatiles").joinpath("profile-demo.html").read_text()
                    center=metadata.get("center","0,0,0").split(",")
                    html=(html.replace("__COLLECTION__",collection).replace("__TITLE__",metadata.get("name",collection))
                          .replace("__CENTER_LON__",center[0]).replace("__CENTER_LAT__",center[1]))
                    return _body(self,200,html,"text/html; charset=utf-8")
                if parts == ["conformance"]: return _json(self, 200, {"conformsTo": CONFORMANCE})
                if parts == ["api"]: return _json(self, 200, self.openapi(collection, dims))
                summary = {"id": collection, "title": metadata.get("name", collection),
                           "description": metadata.get("description", ""),
                           "extent": {"spatial": {"bbox": [[float(x) for x in metadata.get("bounds", "-180,-85.05112878,180,85.05112878").split(",")]],
                                                   "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}},
                           "crs": [c["uri"] for c in crs if c["uri"]],
                           "datatiles:dimensions": dims,
                           "datatiles:contents": store.content_profiles(),
                           "datatiles:variables": store.variables(),
                           "links": [{"rel":"tilesets-map","href":f"/collections/{collection_url}/tiles","type":"application/json"},
                                     {"rel":"profile","href":f"/collections/{collection_url}/profile","type":"application/json"},
                                     {"rel":"point","href":f"/collections/{collection_url}/point","type":"application/json"},
                                     {"rel":"query","href":f"/collections/{collection_url}/query","type":"application/geo+json"},
                                     {"rel":"contours","href":f"/collections/{collection_url}/contours","type":"application/geo+json"},
                                     {"rel":"nautical-items","href":f"/collections/{collection_url}/nautical-items","type":"application/geo+json"},
                                     {"rel":"contents","href":f"/collections/{collection_url}/contents","type":"application/json"},
                                     {"rel":"surface","href":f"/collections/{collection_url}/surface","type":"application/json"},
                                     {"rel":"demo","href":"/playground","type":"text/html"}]}
                if parts == ["collections"]: return _json(self, 200, {"collections":[summary], "links":[]})
                if parts == ["collections", collection]: return _json(self, 200, summary)
                if parts == ["collections", collection, "dimensions"]: return _json(self, 200, {"dimensions":dims})
                if parts == ["collections", collection, "contents"]: return _json(self,200,{"contents":store.content_profiles()})
                if parts == ["collections", collection, "variables"]: return _json(self,200,{"variables":store.variables()})
                if parts == ["collections", collection, "commercial"]: return _json(self,200,store.drm_status())
                if parts == ["collections", collection, "release"]: return _json(self,200,{"release":store.release()})
                if parts == ["collections", collection, "commercial", "policies"]: return _json(self,200,{"policies":store.drm_policies()})
                if parts == ["collections", collection, "integrity"]: return _json(self,200,store.integrity_status(recompute=False))
                if parts == ["collections", collection, "integrity", "manifest"]: return _json(self,200,store.integrity_manifest())
                if parts == ["collections", collection, "fair"]: return _json(self,200,store.fair_report(strict_publication=False))
                if parts == ["collections", collection, "rights"]: return _json(self,200,{"rights":store.rights()})
                if parts == ["collections", collection, "provenance"]: return _json(self,200,store.prov_json())
                if parts == ["collections", collection, "datacite"]: return _json(self,200,store.datacite_metadata())
                if parts == ["collections", collection, "crs"]: return _json(self, 200, {"crs":crs})
                if parts == ["collections", collection, "fair"]: return _json(self,200,store.fair_report())
                if parts == ["collections", collection, "provenance"]:
                    return _json(self, 200, {
                        "agents":[dict(r) for r in store.db.execute("SELECT * FROM datatiles_provenance_agents")],
                        "activities":[dict(r) for r in store.db.execute("SELECT * FROM datatiles_provenance_activities")],
                        "entities":[dict(r) for r in store.db.execute("SELECT * FROM datatiles_provenance_entities")],
                        "relations":[dict(r) for r in store.db.execute("SELECT * FROM datatiles_provenance_relations")]})
                if parts == ["collections", collection, "point"]:
                    query=parse_qs(parsed.query)
                    try:
                        lon,lat=parse_point(query.get("coords",[""])[0]); zoom=int(query["zoom"][0]) if "zoom" in query else None
                        return _json(self,200,point_values(store,lon,lat,zoom=zoom))
                    except (DataTilesError,ValueError) as exc: return _json(self,400,{"code":"InvalidParameterValue","description":str(exc)})
                if parts in (["collections",collection,"query"],["collections",collection,"contours"]):
                    query=parse_qs(parsed.query)
                    try:
                        bounds=tuple(float(v) for v in query.get("bbox",[metadata.get("bounds","")])[0].split(","))
                        if len(bounds)!=4: raise ValueError("bbox requires west,south,east,north")
                        cells=int(query.get("cells",["64"])[0]); zoom=int(query["zoom"][0]) if "zoom" in query else None
                        if parts[-1]=="contours": result=contours(store,bounds,interval=float(query.get("interval",["5"])[0]),cells=cells,zoom=zoom,
                                                                 adaptive=query.get("adaptive",["false"])[0].lower() in ("1","true","yes"))
                        else: result=query_areas(store,bounds,min_depth=float(query["min_depth"][0]) if "min_depth" in query else None,
                            max_depth=float(query["max_depth"][0]) if "max_depth" in query else None,
                            classes=set(query.get("classes",[""])[0].split(",")),sheltered_by=query.get("sheltered_by",[None])[0],cells=cells,zoom=zoom)
                        return _json(self,200,result,"application/geo+json")
                    except (DataTilesError,ValueError) as exc: return _json(self,400,{"code":"InvalidParameterValue","description":str(exc)})
                if parts == ["collections",collection,"nautical-items"]:
                    query=parse_qs(parsed.query)
                    try:
                        bounds=tuple(float(v) for v in query.get("bbox",[metadata.get("bounds","")])[0].split(","))
                        if len(bounds)!=4: raise ValueError("bbox requires west,south,east,north")
                        result=stored_vector_features(store,bounds,zoom=int(query["zoom"][0]) if "zoom" in query else None)
                        return _json(self,200,result,"application/geo+json")
                    except (DataTilesError,ValueError) as exc:return _json(self,400,{"code":"InvalidParameterValue","description":str(exc)})
                if parts == ["collections",collection,"surface"]:
                    query=parse_qs(parsed.query)
                    try:
                        bounds=tuple(float(v) for v in query.get("bbox",[metadata.get("bounds","")])[0].split(","))
                        if len(bounds)!=4: raise ValueError("bbox requires west,south,east,north")
                        result=surface_grid(store,bounds,width=int(query.get("width",["64"])[0]),
                                            height=int(query.get("height",["64"])[0]),
                                            zoom=int(query["zoom"][0]) if "zoom" in query else None)
                        return _json(self,200,result)
                    except (DataTilesError,ValueError) as exc: return _json(self,400,{"code":"InvalidParameterValue","description":str(exc)})
                if parts == ["collections", collection, "profile"]:
                    query=parse_qs(parsed.query,keep_blank_values=True)
                    try:
                        start=parse_point(query.get("start",[""])[0]); end=parse_point(query.get("end",[""])[0])
                        samples=int(query.get("samples",["256"])[0]); zoom=int(query["zoom"][0]) if "zoom" in query else None
                        profile=sample_profile(store,start,end,samples=samples,zoom=zoom)
                    except (DataTilesError,ValueError) as exc:
                        return _json(self,400,{"code":"InvalidParameterValue","description":str(exc)})
                    output=query.get("f",["json"])[0]
                    if output=="svg": return _body(self,200,profile_svg(profile),"image/svg+xml; charset=utf-8")
                    if output=="csv": return _body(self,200,profile_csv(profile),"text/csv; charset=utf-8")
                    if output!="json": return _json(self,400,{"code":"InvalidParameterValue","description":"f must be json, csv, or svg"})
                    return _json(self,200,profile)
                if parts == ["collections", collection, "tiles"]:
                    tilesets=[]
                    for profile in store.content_profiles():
                        data_type=("coverage" if profile["data_type"]=="raster" and profile["encoding"].lower()=="dnt1"
                                   else "map" if profile["data_type"]=="raster" else "vector")
                        tilesets.append({"title":metadata.get("name",collection),"dataType":data_type,
                            "crs":"http://www.opengis.net/def/crs/EPSG/0/3857",
                            "tileMatrixSetURI":"http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad",
                            "datatiles:coordinates":profile["coordinates"],"datatiles:mediaType":profile["media_type"],
                            "datatiles:encoding":profile["encoding"],
                            "links":[{"rel":"item","href":f"/collections/{collection_url}/tiles/WebMercatorQuad/{{tileMatrix}}/{{tileCol}}/{{tileRow}}"}]})
                    return _json(self,200,{"tilesets":tilesets})
                # Canonical OGC path has seven segments after removing empty items.
                if len(parts) == 7 and parts[:4] == ["collections", collection, "tiles", "WebMercatorQuad"]:
                    try: z, x, y = map(int, parts[4:7])
                    except ValueError: return _json(self, 400, {"code":"InvalidParameterValue","description":"invalid tile coordinate"})
                    query = parse_qs(parsed.query, keep_blank_values=True)
                    coordinates = _coordinates(query, {d["name"] for d in dims})
                    try: blob = store.get(z, x, y, coordinates, xyz=True)
                    except DataTilesError as exc: return _json(self, 400, {"code":"InvalidParameterValue","description":str(exc)})
                    if blob is None: return _json(self, 404, {"code":"NotFound","description":"tile not found"})
                    set_id=store._coordinate_set(coordinates,create=False)
                    media = store.content_profile(set_id)["media_type"] if set_id is not None else "application/octet-stream"
                    if "/" not in media: media = mimetypes.types_map.get("." + media, "application/octet-stream")
                    self.send_response(200); self.send_header("Content-Type", media); self.send_header("Content-Length", str(len(blob)))
                    self.end_headers(); self.wfile.write(blob); return
                return _json(self, 404, {"code":"NotFound","description":"resource not found"})

        @staticmethod
        def openapi(collection: str, dims: list[dict]) -> dict:
            collection=quote(collection,safe="")
            params = [{"name":"tileMatrix", "in":"path", "required":True, "schema":{"type":"integer","minimum":0}},
                      {"name":"tileCol", "in":"path", "required":True, "schema":{"type":"integer","minimum":0}},
                      {"name":"tileRow", "in":"path", "required":True, "schema":{"type":"integer","minimum":0}}]
            params += [{"name":d["name"], "in":"query", "required":bool(d["required"]),
                       "schema":{"type":"string"}, "description":d["description"] or d["extent_kind"]} for d in dims]
            return {"openapi":"3.0.3", "info":{"title":"DataTiles OGC API","version":"0.15.0"},
                    "paths":{f"/collections/{collection}/tiles/WebMercatorQuad/{{tileMatrix}}/{{tileCol}}/{{tileRow}}":{
                        "get":{"parameters":params, "responses":{"200":{"description":"tile"},"404":{"description":"not found"}}}},
                        f"/collections/{collection}/profile":{"get":{"parameters":[
                            {"name":"start","in":"query","required":True,"schema":{"type":"string"}},
                            {"name":"end","in":"query","required":True,"schema":{"type":"string"}},
                            {"name":"samples","in":"query","schema":{"type":"integer","minimum":2,"maximum":4096,"default":256}},
                            {"name":"f","in":"query","schema":{"type":"string","enum":["json","csv","svg"]}}],
                            "responses":{"200":{"description":"on-demand numeric depth profile"}}}},
                        f"/collections/{collection}/point":{"get":{"parameters":[{"name":"coords","in":"query","required":True,"schema":{"type":"string"}}],"responses":{"200":{"description":"decoded coincident values"}}}},
                        f"/collections/{collection}/contents":{"get":{"responses":{"200":{"description":"raster and vector content profiles"}}}},
                        f"/collections/{collection}/surface":{"get":{"parameters":[{"name":"bbox","in":"query","required":True,"schema":{"type":"string"}},{"name":"width","in":"query","schema":{"type":"integer","minimum":8,"maximum":128}},{"name":"height","in":"query","schema":{"type":"integer","minimum":8,"maximum":128}}],"responses":{"200":{"description":"coincident numeric depth and seabed grid"}}}},
                        f"/collections/{collection}/contours":{"get":{"parameters":[{"name":"bbox","in":"query","required":True,"schema":{"type":"string"}},{"name":"interval","in":"query","schema":{"type":"number","default":5}},{"name":"adaptive","in":"query","schema":{"type":"boolean","default":False}}],"responses":{"200":{"description":"live derived GeoJSON contours"}}}},
                        f"/collections/{collection}/nautical-items":{"get":{"parameters":[{"name":"bbox","in":"query","required":True,"schema":{"type":"string"}}],"responses":{"200":{"description":"stored OpenStreetMap seamark vector features"}}}},
                        f"/collections/{collection}/query":{"get":{"parameters":[{"name":"bbox","in":"query","required":True,"schema":{"type":"string"}},{"name":"min_depth","in":"query","schema":{"type":"number"}},{"name":"max_depth","in":"query","schema":{"type":"number"}},{"name":"classes","in":"query","schema":{"type":"string"}},{"name":"sheltered_by","in":"query","schema":{"type":"string","enum":["nw"]}}],"responses":{"200":{"description":"predicate-selected GeoJSON areas"}}}},
                        f"/collections/{collection}/fair":{"get":{"responses":{"200":{"description":"FAIR-by-design assessment report"}}}}}}

        def log_message(self, fmt: str, *args: object) -> None: pass
    return Handler


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="datatiles-serve")
    p.add_argument("file", type=Path); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8080)
    args = p.parse_args(argv)
    try:
        with DataTiles(args.file,read_only=True) as check:
            errors=check.validate()
        if errors: p.error("invalid DataTiles container: "+"; ".join(errors))
    except (DataTilesError,OSError) as exc:
        p.error(str(exc))
    server = ThreadingHTTPServer((args.host, args.port), handler_for(args.file))
    print(f"Serving {args.file} at http://{args.host}:{args.port}")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
    return 0


if __name__ == "__main__": raise SystemExit(main())
