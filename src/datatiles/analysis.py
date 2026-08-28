"""Derived scientific products computed directly from numeric DataTiles."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .profile import CLASS_COLORS, _resolve_variable, _sample_numeric
from .store import DataTiles, DataTilesError


def _valid_bbox(bbox: tuple[float,float,float,float]) -> tuple[float,float,float,float]:
    if len(bbox)!=4 or not all(math.isfinite(v) for v in bbox): raise DataTilesError("bbox values must be finite")
    west,south,east,north=bbox
    if not (-180<=west<east<=180 and -90<=south<north<=90): raise DataTilesError("bbox is outside CRS84 or has invalid ordering")
    return west,south,east,north


def _common_zoom(store: DataTiles, set_ids: list[int], requested: int | None) -> int:
    if requested is not None:
        return requested
    placeholders=",".join("?" for _ in set_ids)
    row=store.db.execute(
        f"SELECT zoom_level FROM datatiles_tiles WHERE coordinate_set_id IN ({placeholders}) "
        "GROUP BY zoom_level HAVING count(DISTINCT coordinate_set_id)=? ORDER BY zoom_level DESC LIMIT 1",
        (*set_ids,len(set_ids))).fetchone()
    if row is None: raise DataTilesError("requested variables do not share a tile zoom level")
    return int(row[0])


class _PointSampler:
    def __init__(self, store: DataTiles, zoom: int|None=None):
        self.store=store; self.resolved=[]; self.cache={}
        for name in ("depth_below_lat_m","seafloor_class","northwest_wind_shelter"):
            try:self.resolved.append((name,*_resolve_variable(store,name)))
            except DataTilesError:
                if name!="northwest_wind_shelter":raise
        self.zoom=_common_zoom(store,[item[1] for item in self.resolved],zoom)
        self.legend=json.loads(dict(store.db.execute("SELECT name,value FROM metadata")).get("datatiles:classes","{}"))

    def __call__(self,lon:float,lat:float)->dict[str,Any]:
        values={}; evidence={}
        for name,set_id,_ in self.resolved:
            value,tile=_sample_numeric(self.store,set_id,lon,lat,self.zoom,self.cache); values[name]=value; evidence[name]=tile
        code=int(values.get("seafloor_class") or 0)
        return {"type":"DataTilesPointObservation","longitude":lon,"latitude":lat,"zoom":self.zoom,
                "depth_m":values.get("depth_below_lat_m"),"class_code":code,
                "class_name":self.legend.get(str(code),"unknown"),
                "northwest_wind_sheltered":bool(values.get("northwest_wind_shelter")),
                "evidence":evidence,"data_source":"on-demand DNT1 numeric tile decoding"}


def point_values(store: DataTiles, lon: float, lat: float, *, zoom: int | None=None) -> dict[str,Any]:
    return _PointSampler(store,zoom)(lon,lat)


def surface_grid(store: DataTiles, bbox: tuple[float,float,float,float], *, width: int=64,
                 height: int=64, zoom: int|None=None) -> dict[str,Any]:
    """Sample coincident depth and seabed arrays for client-side scientific rendering."""
    if not 8 <= width <= 128 or not 8 <= height <= 128:
        raise DataTilesError("surface width and height must be between 8 and 128")
    west,south,east,north=_valid_bbox(bbox)
    sample=_PointSampler(store,zoom); depth=[]; classes=[]
    for row in range(height):
        lat=north-(row+.5)*(north-south)/height; depth_row=[]; class_row=[]
        for col in range(width):
            lon=west+(col+.5)*(east-west)/width; value=sample(lon,lat)
            d=value["depth_m"]
            depth_row.append(None if d is None or not math.isfinite(float(d)) else round(float(d),6))
            class_row.append(int(value["class_code"]))
        depth.append(depth_row); classes.append(class_row)
    payload={"bbox":[west,south,east,north],"width":width,"height":height,"zoom":sample.zoom,
             "row_order":"north-to-south","depth_m":depth,"seafloor_class":classes,
             "class_legend":sample.legend,"data_source":"on-demand DNT1 numeric tile decoding"}
    payload["surface_sha256"]=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return payload


def query_areas(store: DataTiles, bbox: tuple[float,float,float,float], *, min_depth: float|None=None,
                max_depth: float|None=None, classes: set[str]|None=None, sheltered_by: str|None=None,
                cells: int=64, zoom: int|None=None) -> dict[str,Any]:
    if not 4<=cells<=128: raise DataTilesError("cells must be between 4 and 128")
    west,south,east,north=_valid_bbox(bbox)
    accepted={item.strip().lower() for item in (classes or set()) if item.strip()}
    features=[]; sample=_PointSampler(store,zoom)
    for row in range(cells):
        lat1=north-row*(north-south)/cells; lat0=north-(row+1)*(north-south)/cells
        for col in range(cells):
            lon0=west+col*(east-west)/cells; lon1=west+(col+1)*(east-west)/cells
            value=sample((lon0+lon1)/2,(lat0+lat1)/2)
            depth=value["depth_m"]; name=value["class_name"].lower()
            if depth is None or min_depth is not None and depth<=min_depth or max_depth is not None and depth>=max_depth: continue
            if accepted and name not in accepted: continue
            if sheltered_by and sheltered_by.lower() in ("nw","northwest","north-west") and not value["northwest_wind_sheltered"]: continue
            features.append({"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[lon0,lat0],[lon1,lat0],[lon1,lat1],[lon0,lat1],[lon0,lat0]]]},
                             "properties":{"depth_m":depth,"class_code":value["class_code"],"class_name":value["class_name"],
                                           "northwest_wind_sheltered":value["northwest_wind_sheltered"],"fill":CLASS_COLORS.get(value["class_code"],CLASS_COLORS[0])}})
    criteria={"min_depth_exclusive":min_depth,"max_depth_exclusive":max_depth,"classes":sorted(accepted),"sheltered_by":sheltered_by,"cells":cells}
    digest=hashlib.sha256(json.dumps(features,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {"type":"FeatureCollection","features":features,"datatiles:criteria":criteria,"datatiles:sha256":digest,
            "datatiles:dataSource":"on-demand predicate evaluation over decoded numeric tiles"}


def contours(store: DataTiles, bbox: tuple[float,float,float,float], *, interval: float=10,
             cells: int=64, zoom: int|None=None) -> dict[str,Any]:
    if interval<=0: raise DataTilesError("interval must be positive")
    if not 8<=cells<=128: raise DataTilesError("cells must be between 8 and 128")
    west,south,east,north=_valid_bbox(bbox); grid=[]; sample=_PointSampler(store,zoom)
    for r in range(cells+1):
        lat=north-r*(north-south)/cells
        grid.append([sample(west+c*(east-west)/cells,lat)["depth_m"] for c in range(cells+1)])
    valid=[v for row in grid for v in row if v is not None]
    if not valid: return {"type":"FeatureCollection","features":[]}
    levels=range(int(math.ceil(min(valid)/interval)),int(math.floor(max(valid)/interval))+1); features=[]
    edges=((0,1),(1,2),(2,3),(3,0))
    for multiple in levels:
        level=multiple*interval; segments=[]
        for r in range(cells):
            for c in range(cells):
                vals=(grid[r][c],grid[r][c+1],grid[r+1][c+1],grid[r+1][c])
                if any(v is None for v in vals): continue
                pts=((c,r),(c+1,r),(c+1,r+1),(c,r+1)); crossings=[]
                for a,b in edges:
                    va,vb=vals[a],vals[b]
                    if (va<level<=vb) or (vb<level<=va):
                        t=(level-va)/(vb-va); x=pts[a][0]+t*(pts[b][0]-pts[a][0]); y=pts[a][1]+t*(pts[b][1]-pts[a][1])
                        crossings.append([west+x/cells*(east-west),north-y/cells*(north-south)])
                if len(crossings)==2: segments.append(crossings)
                elif len(crossings)==4: segments.extend((crossings[:2],crossings[2:]))
        if segments: features.append({"type":"Feature","geometry":{"type":"MultiLineString","coordinates":segments},"properties":{"depth_m":level}})
    return {"type":"FeatureCollection","features":features,"datatiles:interval_m":interval,
            "datatiles:dataSource":"live marching-squares derivation from decoded depth tiles"}


def stored_vector_features(store: DataTiles, bbox: tuple[float,float,float,float], *,
                           variable: str="openseamap_items", zoom: int|None=None) -> dict[str,Any]:
    """Return deduplicated features from stored tiled GeoJSON vector content."""
    west,south,east,north=_valid_bbox(bbox)
    matches=store.find_coordinate_sets({"variable":variable})
    matches=[item for item in matches if store.content_profile(item)["data_type"]=="vector"]
    if not matches:raise DataTilesError(f"vector variable not found: {variable}")
    if len(matches)>1:raise DataTilesError(f"vector variable {variable!r} has multiple coordinate sets")
    set_id=matches[0]; coordinates=store.coordinate_set_values(set_id)
    profile=store.content_profile(set_id)
    if profile["data_type"]!="vector" or profile["media_type"]!="application/geo+json":
        raise DataTilesError(f"{variable} is not tiled GeoJSON vector content")
    z=_common_zoom(store,[set_id],zoom); n=2**z
    lonx=lambda lon:max(0,min(n-1,int(math.floor((lon+180)/360*n))))
    laty=lambda lat:max(0,min(n-1,int(math.floor((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n))))
    features={}
    for x in range(lonx(west),lonx(east)+1):
        for y in range(laty(north),laty(south)+1):
            blob=store.get_by_coordinate_set(z,x,y,set_id,xyz=True)
            if blob is None:continue
            try:value=json.loads(blob)
            except (UnicodeDecodeError,json.JSONDecodeError) as exc:raise DataTilesError("stored GeoJSON vector tile is invalid") from exc
            for feature in value.get("features",[]):
                geometry=feature.get("geometry") or {}; raw=geometry.get("coordinates",[])
                points=[raw] if geometry.get("type")=="Point" else raw if geometry.get("type")=="LineString" else []
                if not points:continue
                fw,fs,fe,fn=min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)
                if fe<west or fw>east or fn<south or fs>north:continue
                features[str(feature.get("id",json.dumps(feature,sort_keys=True,separators=(',',':'))))]=feature
    ordered=[features[key] for key in sorted(features)]
    digest=hashlib.sha256(json.dumps(ordered,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {"type":"FeatureCollection","features":ordered,"datatiles:variable":variable,"datatiles:coordinates":coordinates,
            "datatiles:zoom":z,"datatiles:sha256":digest,
            "datatiles:dataSource":"stored tiled GeoJSON vector content; not a remote portrayal"}
