"""Reproducible Bay of Naples EMODnet reference workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .numeric import encode_numeric_tile
from .store import DataTiles


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(value))


def runtime_versions() -> dict[str, str]:
    import sqlite3
    import zlib
    import numpy
    from PIL import __version__ as pillow_version
    return {"python":platform.python_version(),"sqlite":sqlite3.sqlite_version,"zlib":zlib.ZLIB_VERSION,
            "numpy":numpy.__version__,"pillow":pillow_version,"datatiles":__version__}


def enforce_runtime(config_path: Path) -> tuple[Path, dict[str, str]]:
    lock_path=config_path.parent/"runtime-lock.json"
    if not lock_path.exists(): raise RuntimeError(f"missing runtime lock: {lock_path}")
    expected=json.loads(lock_path.read_text()); actual=runtime_versions()
    differences=[f"{key}: expected {value}, got {actual.get(key)}" for key,value in expected.items() if actual.get(key)!=value]
    if differences: raise RuntimeError("runtime differs from lock: "+"; ".join(differences))
    return lock_path,actual


def request_url(base: str, params: dict[str, object]) -> str:
    return base + "?" + urllib.parse.urlencode(params, doseq=True, safe=":,/")


def download(url: str, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": f"DataTiles/{__version__} reproducibility-demo"})
    with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output)
        headers = {key.lower(): value for key, value in response.headers.items()}
        final_url = response.geturl()
    temporary.replace(target)
    return {"request_url": url, "final_url": final_url, "sha256": sha256(target),
            "bytes": target.stat().st_size, "content_type": headers.get("content-type"),
            "etag": headers.get("etag"), "last_modified": headers.get("last-modified")}


def _raw_requests(config: dict[str, Any]) -> list[tuple[str, str, str]]:
    west, south, east, north = config["bbox_wgs84"]
    width, height = config["grid"]["width"], config["grid"]["height"]
    sources = config["sources"]
    bathy = sources["bathymetry"]
    substrate = sources["substrate"]
    habitat = sources["habitat"]
    requests = []
    for name, source in sources.items():
        suffix="xml" if name=="nautical" else "json"
        url=source["catalogue_url"] if name=="nautical" else source["catalogue_url"] + "?format=json"
        requests.append((f"{name}_catalogue", f"{name}-catalogue.{suffix}", url))
    requests.extend([
        ("bathymetry_capabilities", "bathymetry-capabilities.xml", request_url(bathy["service"], {
            "service":"WCS", "version":"1.0.0", "request":"GetCapabilities"})),
        ("bathymetry", "bathymetry.tif", request_url(bathy["service"], {
            "service":"WCS", "version":"1.0.0", "request":"GetCoverage", "coverage":bathy["coverage"],
            "crs":"EPSG:4326", "bbox":f"{west},{south},{east},{north}", "width":width,
            "height":height, "format":"GeoTIFF"})),
        ("substrate", "substrate.geojson", request_url(substrate["service"], {
            "service":"WFS", "version":"2.0.0", "request":"GetFeature", "typeNames":substrate["type_name"],
            "outputFormat":"application/json", "srsName":"EPSG:4326",
            "bbox":f"{west},{south},{east},{north},EPSG:4326"})),
        ("habitat", "habitat.geojson", request_url(habitat["service"], {
            "service":"WFS", "version":"2.0.0", "request":"GetFeature", "typeNames":habitat["type_name"],
            "outputFormat":"application/json", "srsName":"EPSG:4326",
            "bbox":f"{west},{south},{east},{north},EPSG:4326"})),
    ])
    if "nautical" in sources:
        nautical=sources["nautical"]
        query=(f'[out:json][timeout:180];(node["seamark:type"]({south},{west},{north},{east});'
               f'way["seamark:type"]({south},{west},{north},{east}););out tags geom;')
        requests.append(("nautical", "nautical-overpass.json", request_url(nautical["service"], {"data":query})))
    return requests


def resolve_coverage(capabilities: Path, preferred: str) -> str:
    root = ET.fromstring(capabilities.read_bytes())
    names = sorted({(element.text or "").strip() for element in root.iter()
                    if element.tag.rsplit("}", 1)[-1].lower() in ("name", "identifier") and (element.text or "").strip()})
    if preferred in names: return preferred
    candidates = [name for name in names if name.rsplit(":", 1)[-1].lower() == "mean"]
    if not candidates: candidates = [name for name in names if "mean" in name.lower() and "land" not in name.lower()]
    if not candidates: raise RuntimeError(f"WCS coverage {preferred!r} not found and no unambiguous mean-depth coverage exists")
    return candidates[0]


def validate_raw(key: str, path: Path) -> None:
    head = path.read_bytes()[:64]
    if key == "bathymetry" and not (head.startswith(b"II*\x00") or head.startswith(b"MM\x00*")):
        raise RuntimeError("bathymetry response is not a TIFF; inspect the WCS service response")
    if key in ("substrate", "habitat"):
        value = json.loads(path.read_text())
        if value.get("type") != "FeatureCollection": raise RuntimeError(f"{key} response is not a GeoJSON FeatureCollection")
    if key == "nautical":
        value=json.loads(path.read_text())
        if not isinstance(value.get("elements"),list): raise RuntimeError("nautical response is not Overpass JSON")


def acquire(config_path: Path, work: Path, expected_lock: Path | None = None) -> None:
    config = json.loads(config_path.read_text())
    work.mkdir(parents=True, exist_ok=True)
    (work / ".datatiles-demo-work").write_text(config["demo_id"] + "\n")
    expected = json.loads(expected_lock.read_text()) if expected_lock else None
    destination = work / ("incoming" if expected else "raw")
    entries = {}; reports = {}
    for key, filename, url in _raw_requests(config):
        if key == "bathymetry":
            coverage = resolve_coverage(destination / "bathymetry-capabilities.xml", config["sources"]["bathymetry"]["coverage"])
            west, south, east, north = config["bbox_wgs84"]
            url = request_url(config["sources"]["bathymetry"]["service"], {
                "service":"WCS", "version":"1.0.0", "request":"GetCoverage", "coverage":coverage,
                "crs":"EPSG:4326", "bbox":f"{west},{south},{east},{north}", "width":config["grid"]["width"],
                "height":config["grid"]["height"], "format":"GeoTIFF"})
        print(f"acquire {key}: {url}")
        info = download(url, destination / filename)
        validate_raw(key, destination / filename)
        entries[key] = {"file":filename, "request_url":url, "sha256":info["sha256"], "bytes":info["bytes"]}
        reports[key] = info
    lock = {"lock_version":1, "demo_id":config["demo_id"], "config_sha256":sha256(config_path), "sources":entries}
    if expected:
        mismatches = [key for key, info in entries.items()
                      if expected.get("sources", {}).get(key, {}).get("sha256") != info["sha256"]]
        write_json(work / "incoming-source-lock.json", lock)
        if mismatches:
            raise RuntimeError("upstream bytes differ from expected lock: " + ", ".join(mismatches))
        raw = work / "raw"; raw.mkdir(exist_ok=True)
        for _, filename, _ in _raw_requests(config): (destination / filename).replace(raw / filename)
        write_json(work / "source-lock.json", expected)
    else:
        write_json(work / "source-lock.json", lock)
    write_json(work / "acquisition-report.json", {"demo_id":config["demo_id"],"responses":reports})


CLASS_NAMES = {0:"unknown", 1:"other", 2:"mixed sediment", 3:"mud", 4:"sand",
               5:"gravel/coarse sediment", 6:"rock/hard substrate", 7:"algae/maerl/kelp",
               8:"seagrass/Posidonia", 9:"coral/coralligenous/reef"}


def overpass_to_geojson(path: Path) -> dict[str, Any]:
    """Convert locked OpenStreetMap seamark elements into deterministic CRS84 GeoJSON."""
    elements=json.loads(path.read_text()).get("elements",[]); features=[]
    for element in sorted(elements,key=lambda item:(item.get("type",""),int(item.get("id",0)))):
        tags={key:value for key,value in sorted((element.get("tags") or {}).items()) if key.startswith("seamark:") or key in ("name","ref")}
        if element.get("type")=="node" and "lon" in element and "lat" in element:
            geometry={"type":"Point","coordinates":[element["lon"],element["lat"]]}
        else:
            points=[[point["lon"],point["lat"]] for point in element.get("geometry",[]) if "lon" in point and "lat" in point]
            if len(points)<2: continue
            geometry={"type":"LineString","coordinates":points}
        features.append({"type":"Feature","id":f'{element.get("type")}/{element.get("id")}',"properties":tags,"geometry":geometry})
    return {"type":"FeatureCollection","features":features,
            "datatiles:source":"OpenStreetMap seamark-tagged elements used by the OpenSeaMap rendering ecosystem"}


def _geometry_bounds(geometry: dict[str, Any]) -> tuple[float,float,float,float] | None:
    coordinates=geometry.get("coordinates",[])
    points=[coordinates] if geometry.get("type")=="Point" else coordinates if geometry.get("type")=="LineString" else []
    if not points:return None
    return min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)


def _tile_bounds(z: int, x: int, y: int) -> tuple[float,float,float,float]:
    n=2**z
    west=x/n*360-180; east=(x+1)/n*360-180
    north=math.degrees(math.atan(math.sinh(math.pi*(1-2*y/n))))
    south=math.degrees(math.atan(math.sinh(math.pi*(1-2*(y+1)/n))))
    return west,south,east,north


def _property_text(properties: dict[str, Any]) -> str:
    return " | ".join(str(properties[k]).lower() for k in sorted(properties) if properties[k] is not None)


def classify_substrate(properties: dict[str, Any]) -> int:
    text = _property_text(properties)
    if any(word in text for word in ("rock", "bedrock", "hard substrate", "boulder")): return 6
    if any(word in text for word in ("gravel", "coarse", "pebble", "cobble")): return 5
    if "sandy mud" in text: return 3
    if "muddy sand" in text: return 4
    if ("sand" in text and any(word in text for word in ("mud", "silt", "clay"))) or any(word in text for word in ("mixed", "heterogeneous")): return 2
    if "sand" in text: return 4
    if any(word in text for word in ("mud", "silt", "clay")): return 3
    return 1 if text else 0


def classify_habitat(properties: dict[str, Any]) -> int:
    text = _property_text(properties)
    if any(word in text for word in ("coral", "coralligenous")): return 9
    if any(word in text for word in ("posidonia", "seagrass", "sea grass", "zostera", "cymodocea")): return 8
    if any(word in text for word in ("algae", "algal", "maerl", "kelp", "macroalga")): return 7
    return 0


def _inside_ring(xs, ys, ring):
    import numpy as np
    inside = np.zeros(xs.shape, dtype=bool)
    xj, yj = ring[-1][:2]
    for point in ring:
        xi, yi = point[:2]
        crossing = ((yi > ys) != (yj > ys)) & (xs < (xj - xi) * (ys - yi) / ((yj - yi) or 1e-300) + xi)
        inside ^= crossing
        xj, yj = xi, yi
    return inside


def rasterize_geojson(path: Path, bbox: list[float], width: int, height: int,
                       classifier: Callable[[dict[str, Any]], int]):
    import numpy as np
    data = json.loads(path.read_text())
    if data.get("type") != "FeatureCollection": raise ValueError(f"not GeoJSON FeatureCollection: {path}")
    west, south, east, north = bbox
    result = np.zeros((height, width), dtype=np.uint8)
    features = sorted(data.get("features", []), key=lambda f: str(f.get("id", "")) + json.dumps(f.get("properties", {}), sort_keys=True))
    for feature in features:
        value = classifier(feature.get("properties") or {})
        if not value: continue
        geometry = feature.get("geometry") or {}; coordinates = geometry.get("coordinates") or []
        polygons = [coordinates] if geometry.get("type") == "Polygon" else coordinates if geometry.get("type") == "MultiPolygon" else []
        for polygon in polygons:
            if not polygon or not polygon[0]: continue
            all_points = [point for ring in polygon for point in ring]
            pwest=max(west,min(p[0] for p in all_points)); peast=min(east,max(p[0] for p in all_points))
            psouth=max(south,min(p[1] for p in all_points)); pnorth=min(north,max(p[1] for p in all_points))
            if pwest >= peast or psouth >= pnorth: continue
            x0=max(0,int(math.floor((pwest-west)/(east-west)*width))); x1=min(width,int(math.ceil((peast-west)/(east-west)*width)))
            y0=max(0,int(math.floor((north-pnorth)/(north-south)*height))); y1=min(height,int(math.ceil((north-psouth)/(north-south)*height)))
            xcoords=west+(np.arange(x0,x1)+0.5)/width*(east-west)
            ycoords=north-(np.arange(y0,y1)+0.5)/height*(north-south)
            xs,ys=np.meshgrid(xcoords,ycoords)
            mask=_inside_ring(xs,ys,polygon[0])
            for hole in polygon[1:]: mask &= ~_inside_ring(xs,ys,hole)
            window=result[y0:y1,x0:x1]
            window[mask & (value >= window)] = value
    return result


def read_bathymetry(path: Path, width: int, height: int):
    import numpy as np
    from PIL import Image
    with Image.open(path) as image: values = np.asarray(image)
    if values.ndim != 2: raise ValueError("bathymetry WCS response is not a single-band numeric GeoTIFF")
    values = values.astype(np.float64)
    finite = np.isfinite(values) & (np.abs(values) < 1e20)
    median = float(np.median(values[finite])) if finite.any() else 0.0
    depth = -values if median < 0 else values
    depth[~finite | (depth < 0)] = -9999.0
    if depth.shape != (height, width):
        yi=np.rint(np.linspace(0,depth.shape[0]-1,height)).astype(int)
        xi=np.rint(np.linspace(0,depth.shape[1]-1,width)).astype(int)
        depth=depth[np.ix_(yi,xi)]
    return depth.astype(np.float32), ("negated_elevation" if median < 0 else "positive_water_depth")


def northwest_wind_shelter(depth, reach_cells: int):
    """Derive a reproducible NW land-interception exposure proxy."""
    import numpy as np
    wet=depth>=0; sheltered=np.zeros(depth.shape,dtype=np.uint8)
    height,width=depth.shape
    for y in range(height):
        for x in range(width):
            if not wet[y,x]: continue
            for step in range(1,reach_cells+1):
                yy=y-step; xx=x-step
                if yy<0 or xx<0: break
                if not wet[yy,xx]: sheltered[y,x]=1; break
    return sheltered


def _tile_range(bbox: list[float], zoom: int):
    west,south,east,north=bbox; n=2**zoom
    lonx=lambda lon:max(0,min(n-1,int(math.floor((lon+180)/360*n))))
    laty=lambda lat:max(0,min(n-1,int(math.floor((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n))))
    return range(lonx(west),lonx(east)+1), range(laty(north),laty(south)+1)


def _sample_tile(grid, bbox: list[float], z: int, x: int, y: int, tile_size: int, nodata, dtype):
    import numpy as np
    n=2**z
    px=(x+(np.arange(tile_size)+0.5)/tile_size)/n
    py=(y+(np.arange(tile_size)+0.5)/tile_size)/n
    lons=px*360-180
    lats=np.degrees(np.arctan(np.sinh(math.pi*(1-2*py))))
    lon2,lat2=np.meshgrid(lons,lats)
    west,south,east,north=bbox
    valid=(lon2>=west)&(lon2<=east)&(lat2>=south)&(lat2<=north)
    gx=np.clip(np.rint((lon2-west)/(east-west)*(grid.shape[1]-1)).astype(int),0,grid.shape[1]-1)
    gy=np.clip(np.rint((north-lat2)/(north-south)*(grid.shape[0]-1)).astype(int),0,grid.shape[0]-1)
    out=np.full((tile_size,tile_size),nodata,dtype=dtype); out[valid]=grid[gy[valid],gx[valid]]
    return out


def build(config_path: Path, work: Path) -> None:
    import numpy as np
    runtime_lock,runtime=enforce_runtime(config_path)
    config=json.loads(config_path.read_text()); lock=json.loads((work/"source-lock.json").read_text())
    if lock["config_sha256"] != sha256(config_path): raise RuntimeError("configuration differs from source lock")
    for info in lock["sources"].values():
        path=work/"raw"/info["file"]
        if not path.exists() or sha256(path)!=info["sha256"]: raise RuntimeError(f"raw checksum mismatch: {path}")
    bbox=config["bbox_wgs84"]; width=config["grid"]["width"]; height=config["grid"]["height"]
    bathy,depth_transform=read_bathymetry(work/"raw/bathymetry.tif",width,height)
    substrate=rasterize_geojson(work/"raw/substrate.geojson",bbox,width,height,classify_substrate)
    habitat=rasterize_geojson(work/"raw/habitat.geojson",bbox,width,height,classify_habitat)
    fused=np.maximum(substrate,habitat).astype(np.uint8)
    shelter_reach=int(config.get("derived",{}).get("northwest_shelter_reach_cells",32))
    northwest_shelter=northwest_wind_shelter(bathy,shelter_reach)
    nautical=(overpass_to_geojson(work/"raw/nautical-overpass.json")
              if "nautical" in config["sources"] else {"type":"FeatureCollection","features":[]})
    from PIL import Image
    palette=np.array([[210,210,210],[170,170,170],[175,145,110],[105,85,70],[224,204,145],
                      [160,145,120],[115,105,100],[90,150,70],[35,135,75],[205,85,100]],dtype=np.uint8)
    seafloor_preview=work/"seafloor-class-preview.png"; Image.fromarray(palette[fused],"RGB").save(seafloor_preview,optimize=False,compress_level=9)
    valid_depth=bathy>=0; normalized=np.clip(bathy,0,2000)/2000
    bathy_rgb=np.empty((height,width,3),dtype=np.uint8); bathy_rgb[:]=[220,218,200]
    bathy_rgb[valid_depth,0]=(25+35*(1-normalized[valid_depth])).astype(np.uint8)
    bathy_rgb[valid_depth,1]=(70+120*(1-normalized[valid_depth])).astype(np.uint8)
    bathy_rgb[valid_depth,2]=(115+130*(1-normalized[valid_depth])).astype(np.uint8)
    bathymetry_preview=work/"bathymetry-preview.png"; Image.fromarray(bathy_rgb,"RGB").save(bathymetry_preview,optimize=False,compress_level=9)
    output=work/"bay-of-naples.datatiles"
    if output.exists(): output.unlink()
    tile_size=config["tiles"]["tile_size"]; minzoom=config["tiles"]["minzoom"]; maxzoom=config["tiles"]["maxzoom"]
    source_entities={key:f"urn:datatiles:source:{key}:{info['sha256']}" for key,info in lock["sources"].items() if key in ("bathymetry","substrate","habitat","nautical")}
    coordinates={
      "depth_below_lat_m":{"variable":"depth_below_lat_m","dataset_release":"EMODnet DTM 2024"},
      "seabed_substrate":{"variable":"seabed_substrate","dataset_release":"EMODnet Geology 2022","classification_scheme":"datatiles-substrate-v1"},
      "seabed_habitat":{"variable":"seabed_habitat","dataset_release":"EUSeaMap 2025","classification_scheme":"EUNIS-2007 generalized"},
      "seafloor_class":{"variable":"seafloor_class","dataset_release":config["demo_id"],"classification_scheme":config["classification"]["version"]},
      "northwest_wind_shelter":{"variable":"northwest_wind_shelter","dataset_release":config["demo_id"],"classification_scheme":"land-interception-nw-v1"}}
    nautical_coordinates={"variable":"openseamap_items","dataset_release":config["sources"].get("nautical",{}).get("release",config["demo_id"]),
                          "classification_scheme":"OpenSeaMap seamark tagging"}
    grids={"depth_below_lat_m":(bathy,"float32",-9999.0,"m"), "seabed_substrate":(substrate,"uint8",0,"1"),
           "seabed_habitat":(habitat,"uint8",0,"1"), "seafloor_class":(fused,"uint8",0,"1"),
           "northwest_wind_shelter":(northwest_shelter,"uint8",255,"1")}
    with DataTiles(output,create=True,name=config["title"],tile_format="application/vnd.datatiles.numeric") as store:
        store.add_dimension("variable","text",axis="C")
        store.add_dimension("dataset_release","text",axis="O")
        store.add_dimension("classification_scheme","text",axis="O",required=False)
        store.add_crs("horizontal",authority="EPSG",code="3857",uri="http://www.opengis.net/def/crs/EPSG/0/3857")
        store.add_crs("vertical",wkt2='VERTCRS["Lowest Astronomical Tide (LAT)",VDATUM["Lowest Astronomical Tide"],CS[vertical,1],AXIS["depth",down],LENGTHUNIT["metre",1]]')
        store.add_provenance_agent("https://emodnet.ec.europa.eu/","EMODnet",agent_type="organization",uri="https://emodnet.ec.europa.eu/")
        if "nautical" in config["sources"]:
            store.add_provenance_agent("https://www.openstreetmap.org/copyright","OpenStreetMap contributors",agent_type="organization",uri="https://www.openstreetmap.org/copyright")
        store.add_provenance_agent("urn:software:datatiles",f"DataTiles {__version__}",agent_type="software")
        for key,entity in source_entities.items():
            info=lock["sources"][key]; source=config["sources"][key]
            store.add_provenance_entity(entity,"dataset-snapshot",source["dataset"],uri=info["request_url"],checksum_algorithm="sha256",checksum=info["sha256"],attributes={"catalogue_uuid":source["catalogue_uuid"],"release":source["release"],"license":source["license"]})
            store.add_provenance_relation(entity,"wasAttributedTo","https://www.openstreetmap.org/copyright" if key=="nautical" else "https://emodnet.ec.europa.eu/")
        activity="urn:datatiles:activity:bay-of-naples-v1"
        store.add_provenance_activity(activity,"deterministic-tiling","Bay of Naples DataTiles build",software=f"DataTiles {__version__}",parameters={"config_sha256":sha256(config_path),"depth_transform":depth_transform,"northwest_shelter":{"method":"northwest land-interception ray","reach_cells":shelter_reach,"status":"derived exposure proxy"}})
        store.add_provenance_relation(activity,"wasAssociatedWith","urn:software:datatiles")
        for entity in source_entities.values(): store.add_provenance_relation(activity,"used",entity)
        count=0
        for z in range(minzoom,maxzoom+1):
            xs,ys=_tile_range(bbox,z)
            for x in xs:
                for y in ys:
                    for variable,(grid,dtype,nodata,unit) in grids.items():
                        tile=_sample_tile(grid,bbox,z,x,y,tile_size,nodata,np.float32 if dtype=="float32" else np.uint8)
                        blob=encode_numeric_tile(tile.ravel(),tile.shape,dtype=dtype,nodata=nodata,unit=unit)
                        store.put(z,x,y,blob,coordinates[variable],xyz=True)
                        entity_keys=("bathymetry",) if variable in ("depth_below_lat_m","northwest_wind_shelter") else ("substrate",) if variable=="seabed_substrate" else ("habitat",) if variable=="seabed_habitat" else ("bathymetry","substrate","habitat")
                        for key in entity_keys: store.link_tile_provenance(z,x,y,coordinates[variable],source_entities[key],xyz=True)
                        count+=1
                    if "nautical" in source_entities:
                        tile_bbox=_tile_bounds(z,x,y); features=[]
                        for feature in nautical["features"]:
                            fb=_geometry_bounds(feature["geometry"])
                            if fb and not (fb[2]<tile_bbox[0] or fb[0]>tile_bbox[2] or fb[3]<tile_bbox[1] or fb[1]>tile_bbox[3]):
                                features.append(feature)
                        payload=canonical_json({"type":"FeatureCollection","features":features})
                        store.put(z,x,y,payload,nautical_coordinates,xyz=True,data_type="vector",media_type="application/geo+json",
                                  encoding="GeoJSON",schema={"geometry_types":["Point","LineString"],"property_prefix":"seamark:","crs":"OGC:CRS84"})
                        store.link_tile_provenance(z,x,y,nautical_coordinates,source_entities["nautical"],xyz=True)
                        count+=1
        for name,value in {
            "bounds":",".join(map(str,bbox)), "center":f"14.125,40.775,{minzoom}", "minzoom":str(minzoom), "maxzoom":str(maxzoom),
            "description":"Reproducible EMODnet bathymetry, substrate, habitat, fused seafloor classification, and stored OpenStreetMap seamark vectors for the Bay of Naples.",
            "attribution":"EMODnet products and OpenStreetMap contributors (ODbL); not for navigation.",
            "version":"1", "datatiles:demo_config_sha256":sha256(config_path), "datatiles:warning":"DO NOT USE FOR NAVIGATION",
            "datatiles:fair_profile":"1", "datatiles:identifier":"urn:datatiles:demo:bay-of-naples:1",
            "datatiles:license":"https://creativecommons.org/licenses/by/4.0/", "datatiles:access_rights":"public",
            "datatiles:creators":json.dumps([{"name":"Raffaele Montella"}],separators=(",",":")),
            "datatiles:keywords":json.dumps(["bathymetry","seabed substrate","marine habitat","seamark","OpenSeaMap","Bay of Naples","EMODnet"],separators=(",",":")),
            "datatiles:issued":"2026-08-27", "datatiles:modified":"2026-08-27",
            "datatiles:landing_page":"https://github.com/OpenFairWind/DataTiles",
            "datatiles:classes":json.dumps(CLASS_NAMES,separators=(",",":"),sort_keys=True)}.items():
            store.db.execute("INSERT OR REPLACE INTO metadata(name,value) VALUES (?,?)",(name,value))
        store.select(coordinates["seafloor_class"])
        store.db.commit()
        if store.validate(): raise RuntimeError("generated DataTiles failed validation: "+"; ".join(store.validate()))
        store.db.execute("VACUUM")
    summary={"demo_id":config["demo_id"],"config_sha256":sha256(config_path),"source_lock_sha256":sha256(work/"source-lock.json"),
             "output":"bay-of-naples.datatiles","output_sha256":sha256(output),"output_bytes":output.stat().st_size,"tile_records":count,
             "previews":{"bathymetry":{"file":bathymetry_preview.name,"sha256":sha256(bathymetry_preview)},
                         "seafloor_class":{"file":seafloor_preview.name,"sha256":sha256(seafloor_preview)}},
             "grid_shape":[height,width],"depth_transform":depth_transform,
             "class_cell_counts":{str(code):int((fused==code).sum()) for code in sorted(CLASS_NAMES)},
             "runtime_lock_sha256":sha256(runtime_lock),"environment":runtime}
    write_json(work/"artifact-manifest.json",summary)
    bundle=work/"bay-of-naples-evidence.zip"
    members=[(config_path,"config.json"),(runtime_lock,"runtime-lock.json"),(work/"source-lock.json","source-lock.json"),
             (work/"artifact-manifest.json","artifact-manifest.json"),(output,"bay-of-naples.datatiles"),
             (bathymetry_preview,bathymetry_preview.name),(seafloor_preview,seafloor_preview.name)]
    members += [(work/"raw"/info["file"],"raw/"+info["file"]) for info in lock["sources"].values()]
    with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for source,name in sorted(members,key=lambda item:item[1]):
            entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0)); entry.compress_type=zipfile.ZIP_DEFLATED
            entry.external_attr=0o100644<<16; archive.writestr(entry,source.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    write_json(work/"bay-of-naples-evidence.zip.sha256",{"file":bundle.name,"sha256":sha256(bundle),"bytes":bundle.stat().st_size})


def verify(config_path: Path, work: Path) -> None:
    enforce_runtime(config_path)
    lock=json.loads((work/"source-lock.json").read_text()); manifest=json.loads((work/"artifact-manifest.json").read_text())
    errors=[]
    if lock["config_sha256"] != sha256(config_path): errors.append("config checksum")
    for key,info in lock["sources"].items():
        if sha256(work/"raw"/info["file"]) != info["sha256"]: errors.append(f"raw:{key}")
    output=work/manifest["output"]
    if sha256(output) != manifest["output_sha256"]: errors.append("output checksum")
    for name,info in manifest.get("previews",{}).items():
        if sha256(work/info["file"]) != info["sha256"]: errors.append(f"preview:{name}")
    with DataTiles(output) as store: errors.extend("database:"+error for error in store.validate())
    bundle_info=json.loads((work/"bay-of-naples-evidence.zip.sha256").read_text())
    if sha256(work/bundle_info["file"]) != bundle_info["sha256"]: errors.append("evidence bundle checksum")
    if errors: raise RuntimeError("verification failed: "+", ".join(errors))
    print(f"verified {output} sha256={manifest['output_sha256']}")


def clean(config_path: Path, work: Path) -> None:
    config=json.loads(config_path.read_text()); marker=work/".datatiles-demo-work"
    if not marker.exists() or marker.read_text().strip()!=config["demo_id"]: raise RuntimeError("refusing to clean an unmarked work directory")
    resolved=work.resolve()
    if resolved in (Path("/").resolve(),Path.home().resolve()) or len(resolved.parts)<3: raise RuntimeError("unsafe work directory")
    shutil.rmtree(resolved)


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(prog="datatiles-demo")
    sub=parser.add_subparsers(dest="command",required=True)
    for command in ("acquire","build","verify","all","clean"):
        p=sub.add_parser(command); p.add_argument("--config",type=Path,required=True); p.add_argument("--work",type=Path,required=True)
        if command in ("acquire","all"): p.add_argument("--expect-lock",type=Path)
    args=parser.parse_args(argv)
    try:
        if args.command in ("acquire","all"): acquire(args.config,args.work,args.expect_lock)
        if args.command in ("build","all"): build(args.config,args.work)
        if args.command in ("verify","all"): verify(args.config,args.work)
        if args.command=="clean": clean(args.config,args.work)
        return 0
    except (OSError,ValueError,RuntimeError) as exc:
        print(f"error: {exc}",file=sys.stderr); return 1


if __name__=="__main__": raise SystemExit(main())
