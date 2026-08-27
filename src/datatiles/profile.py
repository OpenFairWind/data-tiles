"""On-demand depth transects decoded from multidimensional numeric DataTiles."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from html import escape
from pathlib import Path
from typing import Any

from .numeric import NumericTile, decode_numeric_tile
from .store import DataTiles, DataTilesError

CLASS_COLORS = {0:"#d2d2d2",1:"#aaaaaa",2:"#af916e",3:"#695546",4:"#e0cc91",
                5:"#a09178",6:"#736964",7:"#5a9646",8:"#23874b",9:"#cd5564"}


def haversine(a: tuple[float,float], b: tuple[float,float]) -> float:
    lon1,lat1=map(math.radians,a); lon2,lat2=map(math.radians,b)
    dlon=lon2-lon1; dlat=lat2-lat1
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371008.8*2*math.asin(min(1.0,math.sqrt(h)))


def great_circle_points(start: tuple[float,float], end: tuple[float,float], samples: int):
    def vector(point):
        lon,lat=map(math.radians,point); return (math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat))
    a=vector(start); b=vector(end); dot=max(-1.0,min(1.0,sum(x*y for x,y in zip(a,b)))); omega=math.acos(dot)
    for index in range(samples):
        fraction=index/(samples-1)
        if omega < 1e-12: vector_i=a
        else:
            denominator=math.sin(omega); wa=math.sin((1-fraction)*omega)/denominator; wb=math.sin(fraction*omega)/denominator
            vector_i=tuple(wa*x+wb*y for x,y in zip(a,b))
        x,y,z=vector_i; yield (math.degrees(math.atan2(y,x)),math.degrees(math.atan2(z,math.hypot(x,y))))


def _resolve_variable(store: DataTiles, variable: str) -> tuple[int,dict[str,str]]:
    matches=[set_id for set_id in store.find_coordinate_sets({"variable":variable})
             if store.content_profile(set_id)["data_type"]=="raster" and store.content_profile(set_id)["encoding"].lower()=="dnt1"]
    if not matches: raise DataTilesError(f"variable not found: {variable}")
    if len(matches)>1: raise DataTilesError(f"variable {variable!r} has multiple coordinate sets; specify a release profile")
    return matches[0],store.coordinate_set_values(matches[0])


def _xyz(lon: float, lat: float, zoom: int) -> tuple[int,int,float,float]:
    n=2**zoom; lat=max(-85.05112878,min(85.05112878,lat))
    gx=(lon+180)/360*n; gy=(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n
    x=max(0,min(n-1,int(math.floor(gx)))); y=max(0,min(n-1,int(math.floor(gy))))
    return x,y,gx-x,gy-y


def _sample_numeric(store: DataTiles, set_id: int, lon: float, lat: float, zoom: int,
                    cache: dict[tuple[int,int,int,int],NumericTile]) -> tuple[float|int|None,dict[str,Any]]:
    x,y,fx,fy=_xyz(lon,lat,zoom); key=(set_id,zoom,x,y)
    tile=cache.get(key)
    if tile is None:
        blob=store.get_by_coordinate_set(zoom,x,y,set_id,xyz=True)
        if blob is None: return None,{"z":zoom,"x":x,"y":y,"pixel":None}
        tile=decode_numeric_tile(blob); cache[key]=tile
    if len(tile.shape)!=2: raise DataTilesError("profile variables must contain two-dimensional numeric tiles")
    height,width=tile.shape; px=min(width-1,int(fx*width)); py=min(height-1,int(fy*height)); raw=tile.values[py*width+px]
    value=None if tile.nodata is not None and raw==tile.nodata else raw*tile.scale+tile.offset
    return value,{"z":zoom,"x":x,"y":y,"pixel":[px,py]}


def sample_profile(store: DataTiles, start: tuple[float,float], end: tuple[float,float], *, samples: int=256,
                   zoom: int|None=None, depth_variable: str="depth_below_lat_m", class_variable: str="seafloor_class") -> dict[str,Any]:
    if not 2<=samples<=4096: raise DataTilesError("samples must be between 2 and 4096")
    if not all(math.isfinite(value) for value in (*start,*end)): raise DataTilesError("coordinates must be finite")
    depth_set,depth_coords=_resolve_variable(store,depth_variable); class_set,class_coords=_resolve_variable(store,class_variable)
    if zoom is None:
        row=store.db.execute(
            "SELECT zoom_level FROM datatiles_tiles WHERE coordinate_set_id IN (?,?) "
            "GROUP BY zoom_level HAVING count(DISTINCT coordinate_set_id)=2 ORDER BY zoom_level DESC LIMIT 1",
            (depth_set,class_set),
        ).fetchone()
        if row is None: raise DataTilesError("depth and class variables do not share a tile zoom level")
        zoom=int(row[0])
    legend=json.loads(dict(store.db.execute("SELECT name,value FROM metadata")).get("datatiles:classes","{}"))
    cache={}; total=haversine(start,end); observations=[]
    for index,(lon,lat) in enumerate(great_circle_points(start,end,samples)):
        depth,depth_tile=_sample_numeric(store,depth_set,lon,lat,zoom,cache)
        class_value,class_tile=_sample_numeric(store,class_set,lon,lat,zoom,cache)
        code=int(class_value) if class_value is not None else 0
        observations.append({"index":index,"distance_m":total*index/(samples-1),"longitude":lon,"latitude":lat,
                             "depth_m":depth,"class_code":code,"class_name":legend.get(str(code),"unknown"),
                             "depth_tile":depth_tile,"class_tile":class_tile})
    identity={"start":list(start),"end":list(end),"samples":samples,"zoom":zoom,
              "depth_coordinates":depth_coords,"class_coordinates":class_coords}
    profile_hash=hashlib.sha256(json.dumps(observations,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {"type":"DataTilesDepthProfile","data_source":"on-demand decoding of DNT1 numeric DataTiles; no pre-rendered map tiles",
            "profile":identity,"total_distance_m":total,"class_colors":{str(k):v for k,v in CLASS_COLORS.items()},
            "profile_sha256":profile_hash,"observations":observations}


def profile_csv(profile: dict[str,Any]) -> str:
    output=io.StringIO(newline=""); fields=("index","distance_m","longitude","latitude","depth_m","class_code","class_name")
    writer=csv.DictWriter(output,fieldnames=fields,extrasaction="ignore",lineterminator="\n"); writer.writeheader(); writer.writerows(profile["observations"])
    return output.getvalue()


def profile_svg(profile: dict[str,Any], width: int=1100, height: int=620) -> str:
    observations=profile["observations"]; valid=[o["depth_m"] for o in observations if o["depth_m"] is not None]
    max_depth=max(valid) if valid else 1.0; left,top,right,bottom=85,70,width-35,height-85; chart_w=right-left; chart_h=bottom-top
    x=lambda o:left+(o["distance_m"]/profile["total_distance_m"] if profile["total_distance_m"] else 0)*chart_w
    y=lambda o:top+(o["depth_m"]/max_depth if o["depth_m"] is not None else 0)*chart_h
    pieces=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#f7fafc"/>',
            '<text x="32" y="36" font-family="sans-serif" font-size="25" fill="#152536">DataTiles on-demand depth profile</text>',
            '<text x="32" y="58" font-family="sans-serif" font-size="13" fill="#526273">Decoded from numeric depth and classification dimensions - no rendered map tiles</text>']
    for tick in range(6):
        depth=max_depth*tick/5; yy=top+chart_h*tick/5
        pieces.append(f'<line x1="{left}" y1="{yy:.2f}" x2="{right}" y2="{yy:.2f}" stroke="#d8e0e7"/><text x="{left-9}" y="{yy+5:.2f}" text-anchor="end" font-family="sans-serif" font-size="12">{depth:.0f} m</text>')
    for first,second in zip(observations,observations[1:]):
        if first["depth_m"] is None or second["depth_m"] is None: continue
        color=CLASS_COLORS.get(first["class_code"],CLASS_COLORS[0])
        pieces.append(f'<path d="M{x(first):.2f},{bottom} L{x(first):.2f},{y(first):.2f} L{x(second):.2f},{y(second):.2f} L{x(second):.2f},{bottom} Z" fill="{color}"/>')
    points=" ".join(f'{x(o):.2f},{y(o):.2f}' for o in observations if o["depth_m"] is not None)
    pieces += [f'<polyline points="{points}" fill="none" stroke="#132331" stroke-width="1.5"/>',
               f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#263746"/><line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#263746"/>',
               f'<text x="{(left+right)/2}" y="{height-25}" text-anchor="middle" font-family="sans-serif" font-size="14">Distance: {profile["total_distance_m"]/1000:.2f} km</text>']
    used=[]
    for o in observations:
        if o["class_code"] not in used: used.append(o["class_code"])
    lx=left
    for code in used:
        name=next((o["class_name"] for o in observations if o["class_code"]==code),"unknown")
        pieces.append(f'<rect x="{lx}" y="{height-65}" width="16" height="16" fill="{CLASS_COLORS.get(code,CLASS_COLORS[0])}"/><text x="{lx+22}" y="{height-52}" font-family="sans-serif" font-size="12">{escape(name)}</text>')
        lx+=max(115,22+len(name)*7)
    pieces.append(f'<metadata>profile-sha256:{profile["profile_sha256"]}</metadata></svg>')
    return "".join(pieces)


def parse_point(text: str) -> tuple[float,float]:
    try: lon,lat=map(float,text.split(",",1))
    except (ValueError,TypeError) as exc: raise DataTilesError("point must be longitude,latitude") from exc
    if not -180<=lon<=180 or not -90<=lat<=90: raise DataTilesError("point outside longitude/latitude range")
    return lon,lat


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(prog="datatiles-profile")
    parser.add_argument("file",type=Path); parser.add_argument("start"); parser.add_argument("end")
    parser.add_argument("--samples",type=int,default=256); parser.add_argument("--zoom",type=int)
    parser.add_argument("--format",choices=("json","csv","svg"),default="svg"); parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    try:
        with DataTiles(args.file) as store: profile=sample_profile(store,parse_point(args.start),parse_point(args.end),samples=args.samples,zoom=args.zoom)
        content=json.dumps(profile,indent=2,ensure_ascii=False)+"\n" if args.format=="json" else profile_csv(profile) if args.format=="csv" else profile_svg(profile)
        if args.output: args.output.write_text(content)
        else: print(content)
        return 0
    except (OSError,DataTilesError,ValueError) as exc:
        parser.error(str(exc)); return 2


if __name__=="__main__": raise SystemExit(main())
