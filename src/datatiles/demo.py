"""Reproducible Bay of Naples EMODnet reference workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
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


def bbox_contains(container: list[float], required: list[float]) -> bool:
    swest,ssouth,seast,snorth=container; west,south,east,north=required
    return swest<=west<east<=seast and ssouth<=south<north<=snorth


def download(url: str, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": f"DataTiles/{__version__} reproducibility-demo"})
    for attempt in range(1,5):
        try:
            with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
                headers = {key.lower(): value for key, value in response.headers.items()}
                final_url = response.geturl()
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in (429,500,502,503,504) or attempt==4:raise
            retry_after=exc.headers.get("Retry-After")
            delay=min(30,max(2,int(retry_after) if retry_after and retry_after.isdigit() else attempt*5))
            print(f"transient HTTP {exc.code}; retrying in {delay} seconds",file=sys.stderr)
            time.sleep(delay)
        except (urllib.error.URLError,TimeoutError) as exc:
            if attempt==4:raise
            delay=min(30,attempt*5)
            print(f"transient network error ({exc}); retrying in {delay} seconds",file=sys.stderr)
            time.sleep(delay)
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
        # JammeGaia22 and GSHHG require the permission/licence gate and are imported
        # from checksum-locked local acquisitions rather than fetched implicitly.
        if name in ("jamme","land"): continue
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
        middle_lon=round((west+east)/2,6); middle_lat=round((south+north)/2,6)
        quadrants=((west,south,middle_lon,middle_lat),(middle_lon,south,east,middle_lat),
                   (west,middle_lat,middle_lon,north),(middle_lon,middle_lat,east,north))
        for index,(qwest,qsouth,qeast,qnorth) in enumerate(quadrants):
            query=(f'[out:json][timeout:180];(node["seamark:type"]({qsouth},{qwest},{qnorth},{qeast});'
                   f'way["seamark:type"]({qsouth},{qwest},{qnorth},{qeast}););out tags geom;')
            requests.append((f"nautical_{index}",f"nautical-overpass-{index}.json",request_url(nautical["service"],{"data":query})))
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
    if key.startswith("nautical_") and key!="nautical_catalogue":
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
        if key.startswith("nautical_") and key!="nautical_0":
            time.sleep(10)
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


def import_medchart(config_path: Path, work: Path, source_root: Path) -> None:
    """Replace regional bathymetry/navigation inputs with frozen MedChart acquisitions."""
    config=json.loads(config_path.read_text()); raw=work/"raw"
    if not (work/"source-lock.json").exists():
        raise RuntimeError("run acquire first to obtain the thematic EMODnet inputs")
    selections={
        "bathymetry":("emodnet-bathymetry-2024-native-from-gaeta-to-maratea.json",
                      "emodnet-bathymetry-2024-native/emodnet-bathymetry-2024-native-from-gaeta-to-maratea.tif",
                      "bathymetry.tif"),
        "nautical":("osm-navigation-context-from-gaeta-to-maratea.json",
                    "osm-navigation-context/osm-navigation-context-from-gaeta-to-maratea.overpass.json",
                    "nautical-overpass.json"),
        "land":("noaa-gshhg-2.3.7-gulf-of-naples.json",
                "noaa-gshhg-2.3.7/gshhg-shp-2.3.7.zip",
                "gshhg-shp-2.3.7.zip")}
    lock=json.loads((work/"source-lock.json").read_text()); report={"source_root":str(source_root.resolve()),"imports":{}}
    for key,(manifest_name,relative,target_name) in selections.items():
        manifest_path=source_root/"manifests"/manifest_name; source=source_root/"raw"/relative
        manifest=json.loads(manifest_path.read_text()); asset=manifest["assets"][0]
        if asset["sha256"]!=sha256(source):raise RuntimeError(f"MedChart checksum mismatch: {source}")
        source_bbox=asset.get("metadata",{}).get("bbox")
        if key in ("bathymetry","nautical") and source_bbox:
            if not bbox_contains(source_bbox,config["bbox_wgs84"]):
                report["imports"][key]={"status":"retained-live-acquisition","reason":"frozen snapshot does not cover publication bounds",
                                         "source_bbox_wgs84":source_bbox,"required_bbox_wgs84":config["bbox_wgs84"],
                                         "upstream_manifest":manifest_name,"upstream_manifest_sha256":sha256(manifest_path)}
                continue
        shutil.copyfile(source,raw/target_name)
        info={"file":target_name,"request_url":asset["url"],"sha256":asset["sha256"],"bytes":asset["size"],
              "upstream_manifest":manifest_name,"upstream_manifest_sha256":sha256(manifest_path),
              "upstream_dataset":manifest["dataset"],"upstream_region":manifest["region"]}
        if key == "bathymetry": info["source_bbox_wgs84"] = asset["metadata"]["bbox"]
        report["imports"][key]=info
        if key=="bathymetry":lock["sources"]["bathymetry"]=info
        elif key=="nautical":
            for old in [name for name in lock["sources"] if name.startswith("nautical_") and name!="nautical_catalogue"]:
                lock["sources"].pop(old)
            lock["sources"]["nautical"]=info
        else:
            depth_grid=config.get("bathymetry_grid",config["grid"]); west,south,east,north=config["bbox_wgs84"]
            mask_name="gshhg-land-mask.tif"; mask_path=raw/mask_name
            shape=f"/vsizip/{source}/GSHHS_shp/f/GSHHS_f_L1.shp"
            command=["gdal_rasterize","-q","-burn","1","-init","0","-ot","Byte","-a_nodata","0",
                     "-te",str(west),str(south),str(east),str(north),"-ts",str(depth_grid["width"]),str(depth_grid["height"]),
                     "-co","COMPRESS=DEFLATE",shape,str(mask_path)]
            try: subprocess.run(command,check=True)
            except FileNotFoundError as exc: raise RuntimeError("gdal_rasterize is required to import GSHHG") from exc
            mask_info={"file":mask_name,"request_url":asset["url"],"sha256":sha256(mask_path),"bytes":mask_path.stat().st_size,
                       "source_sha256":asset["sha256"],"source_bytes":asset["size"],"upstream_manifest":manifest_name,
                       "upstream_manifest_sha256":sha256(manifest_path),"rasterize":{"source_layer":"GSHHS_f_L1",
                       "crs":"EPSG:4326","bbox":config["bbox_wgs84"],"shape":[depth_grid["height"],depth_grid["width"]],
                       "land_value":1,"water_value":0}}
            lock["sources"]["land"]=mask_info; report["imports"]["land_mask"]=mask_info
    jamme_lock_path=source_root/"snapshots/jamme-gaia22.lock.json"
    jamme_lock=json.loads(jamme_lock_path.read_text())
    if not jamme_lock.get("complete"): raise RuntimeError("JammeGaia22 source lock is incomplete")
    depth_grid=config.get("bathymetry_grid",config["grid"]); west,south,east,north=config["bbox_wgs84"]
    for asset in sorted(jamme_lock["assets"],key=lambda item:int(item["resolution_m"])):
        resolution=int(asset["resolution_m"]); source=Path(asset["local_path"])
        if not source.is_absolute(): source=source_root/source
        if source.stat().st_size!=asset["size_bytes"] or sha256(source)!=asset["sha256"]:
            raise RuntimeError(f"JammeGaia22 checksum mismatch: {source}")
        target_name=f"jamme-{resolution}m.tif"; target=raw/target_name
        command=["gdalwarp","-overwrite","-q","-t_srs","EPSG:4326","-te",str(west),str(south),str(east),str(north),
                 "-ts",str(depth_grid["width"]),str(depth_grid["height"]),"-r","near","-dstnodata","nan",
                 "-co","COMPRESS=DEFLATE","-co","PREDICTOR=3",str(source),str(target)]
        try: subprocess.run(command,check=True)
        except FileNotFoundError as exc: raise RuntimeError("gdalwarp is required to import JammeGaia22") from exc
        key=f"jamme_{resolution}m"
        info={"file":target_name,"request_url":asset["direct_url"],"sha256":sha256(target),"bytes":target.stat().st_size,
              "source_sha256":asset["sha256"],"source_bytes":asset["size_bytes"],"resolution_m":resolution,
              "data_uid":asset["data_uid"],"dataset_uid":asset["dataset_uid"],"warp":{
                  "algorithm":"nearest","crs":"EPSG:4326","bbox":config["bbox_wgs84"],
                  "shape":[depth_grid["height"],depth_grid["width"]],"nodata":"NaN"}}
        lock["sources"][key]=info; report["imports"][key]=info
    report["jamme_lock"]={"file":"jamme-gaia22.lock.json","sha256":sha256(jamme_lock_path),
                           "doi":jamme_lock["doi"],"license":jamme_lock["license"]}
    lock["config_sha256"]=sha256(config_path); lock["medchart_import"]={"schema":"medchart-acquisition-v1","report":"medchart-import.json"}
    write_json(work/"source-lock.json",lock); write_json(work/"medchart-import.json",report)


CLASS_NAMES = {0:"unknown", 1:"other", 2:"mixed sediment", 3:"mud", 4:"sand",
               5:"gravel/coarse sediment", 6:"rock/hard substrate", 7:"algae/maerl/kelp",
               8:"seagrass/Posidonia", 9:"coral/coralligenous/reef"}


def overpass_to_geojson(path: Path | list[Path]) -> dict[str, Any]:
    """Convert locked OpenStreetMap seamark elements into deterministic CRS84 GeoJSON."""
    paths=[path] if isinstance(path,Path) else path
    elements={}
    for source in paths:
        for element in json.loads(source.read_text()).get("elements",[]):
            elements[(element.get("type",""),int(element.get("id",0)))]=element
    features=[]
    for element in (elements[key] for key in sorted(elements)):
        source_tags=element.get("tags") or {}
        if not any(key.startswith("seamark:") for key in source_tags): continue
        tags={key:value for key,value in sorted(source_tags.items()) if key.startswith("seamark:") or key in ("name","ref")}
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


def read_bathymetry(path: Path, width: int, height: int, *, source_bbox: list[float] | None = None,
                    target_bbox: list[float] | None = None):
    import numpy as np
    from PIL import Image
    with Image.open(path) as image: values = np.asarray(image)
    if values.ndim != 2: raise ValueError("bathymetry WCS response is not a single-band numeric GeoTIFF")
    values = values.astype(np.float64)
    finite = np.isfinite(values) & (np.abs(values) < 1e20)
    depth = -values
    depth[~finite | (values >= 0)] = -9999.0
    if source_bbox is not None and target_bbox is not None:
        swest, ssouth, seast, snorth = source_bbox
        twest, tsouth, teast, tnorth = target_bbox
        if not (swest <= twest < teast <= seast and ssouth <= tsouth < tnorth <= snorth):
            raise ValueError("publication bounds are not contained by the source bathymetry bounds")
        source_height, source_width = depth.shape
        x0=max(0,int(math.floor((twest-swest)/(seast-swest)*source_width)))
        x1=min(source_width,int(math.ceil((teast-swest)/(seast-swest)*source_width)))
        y0=max(0,int(math.floor((snorth-tnorth)/(snorth-ssouth)*source_height)))
        y1=min(source_height,int(math.ceil((snorth-tsouth)/(snorth-ssouth)*source_height)))
        depth=depth[y0:y1,x0:x1]
    if depth.shape != (height, width):
        yi=np.rint(np.linspace(0,depth.shape[0]-1,height)).astype(int)
        xi=np.rint(np.linspace(0,depth.shape[1]-1,width)).astype(int)
        depth=depth[np.ix_(yi,xi)]
    return depth.astype(np.float32), "negative_elevation_to_positive_depth; elevation>=0 is land/nodata"


def compose_bathymetry(emodnet, jamme: list[tuple[int, object]]):
    """Apply the declared finest-finite JammeGaia22, then EMODnet fallback rule."""
    import numpy as np
    result=emodnet.astype(np.float32,copy=True)
    source=np.where(result>=0,1,0).astype(np.uint8)
    resolutions=sorted({resolution for resolution,_ in jamme},reverse=True)
    codes={resolution:index+2 for index,resolution in enumerate(sorted(resolutions))}
    for resolution,grid in sorted(jamme,key=lambda item:item[0],reverse=True):
        valid=np.isfinite(grid)&(grid>=0)
        result[valid]=grid[valid]; source[valid]=codes[resolution]
    return result,source,{0:"land/nodata",1:"EMODnet DTM 2024 fallback",**{
        codes[resolution]:f"JammeGaia22 {resolution} m" for resolution in sorted(resolutions)}}


def apply_land_mask(depth, source, land_mask):
    """Apply the separately sourced GSHHG topology after bathymetry composition."""
    import numpy as np
    if depth.shape != source.shape or depth.shape != land_mask.shape:
        raise ValueError("bathymetry, source, and land-mask shapes differ")
    masked_depth=depth.astype(np.float32,copy=True); masked_source=source.astype(np.uint8,copy=True)
    land=np.asarray(land_mask)>0
    masked_depth[land]=-9999.0; masked_source[land]=0
    return masked_depth,masked_source


def northwest_wind_shelter(depth, reach_cells: int):
    """Derive a reproducible NW land-interception exposure proxy."""
    import numpy as np
    wet=depth>=0; sheltered=np.zeros(depth.shape,dtype=bool)
    for step in range(1,reach_cells+1):
        sheltered[step:,step:] |= wet[step:,step:] & ~wet[:-step,:-step]
    sheltered=sheltered.astype(np.uint8)
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
    from PIL import Image
    runtime_lock,runtime=enforce_runtime(config_path)
    config=json.loads(config_path.read_text()); lock=json.loads((work/"source-lock.json").read_text())
    if lock["config_sha256"] != sha256(config_path): raise RuntimeError("configuration differs from source lock")
    for info in lock["sources"].values():
        path=work/"raw"/info["file"]
        if not path.exists() or sha256(path)!=info["sha256"]: raise RuntimeError(f"raw checksum mismatch: {path}")
    bbox=config["bbox_wgs84"]; width=config["grid"]["width"]; height=config["grid"]["height"]
    depth_width=config.get("bathymetry_grid",config["grid"])["width"]
    depth_height=config.get("bathymetry_grid",config["grid"])["height"]
    bathymetry_info=lock["sources"]["bathymetry"]
    emodnet,depth_transform=read_bathymetry(
        work/"raw/bathymetry.tif",depth_width,depth_height,
        source_bbox=bathymetry_info.get("source_bbox_wgs84"),target_bbox=bbox)
    jamme=[]
    for key in sorted((key for key in lock["sources"] if key.startswith("jamme_")),
                      key=lambda value:int(value.split("_")[1][:-1])):
        info=lock["sources"][key]
        grid,_=read_bathymetry(work/"raw"/info["file"],depth_width,depth_height)
        jamme.append((int(info["resolution_m"]),grid))
    bathy,bathymetry_source,bathymetry_source_classes=compose_bathymetry(emodnet,jamme)
    if "land" in config["sources"] and "land" not in lock["sources"]:
        raise RuntimeError("GSHHG land mask is required; import the frozen Mediterranean Chart Builder sources")
    if "land" in lock["sources"]:
        # This is a categorical topology mask, not an elevation grid.
        with Image.open(work/"raw"/lock["sources"]["land"]["file"]) as image:
            land_mask=np.asarray(image,dtype=np.uint8)
        bathy,bathymetry_source=apply_land_mask(bathy,bathymetry_source,land_mask)
    substrate=rasterize_geojson(work/"raw/substrate.geojson",bbox,width,height,classify_substrate)
    habitat=rasterize_geojson(work/"raw/habitat.geojson",bbox,width,height,classify_habitat)
    fused=np.maximum(substrate,habitat).astype(np.uint8)
    shelter_reach=int(config.get("derived",{}).get("northwest_shelter_reach_cells",32))
    northwest_shelter=northwest_wind_shelter(bathy,shelter_reach)
    nautical_keys=[key for key in sorted(lock["sources"])
                   if key=="nautical" or key.startswith("nautical_") and key!="nautical_catalogue"]
    nautical=(overpass_to_geojson([work/"raw"/lock["sources"][key]["file"] for key in nautical_keys])
              if "nautical" in config["sources"] else {"type":"FeatureCollection","features":[]})
    palette=np.array([[210,210,210],[170,170,170],[175,145,110],[105,85,70],[224,204,145],
                      [160,145,120],[115,105,100],[90,150,70],[35,135,75],[205,85,100]],dtype=np.uint8)
    seafloor_preview=work/"seafloor-class-preview.png"; Image.fromarray(palette[fused]).save(seafloor_preview,optimize=False,compress_level=9)
    valid_depth=bathy>=0; normalized=np.clip(bathy,0,2000)/2000
    bathy_rgb=np.empty((depth_height,depth_width,3),dtype=np.uint8); bathy_rgb[:]=[232,220,170]
    bathy_rgb[valid_depth,0]=(25+35*(1-normalized[valid_depth])).astype(np.uint8)
    bathy_rgb[valid_depth,1]=(70+120*(1-normalized[valid_depth])).astype(np.uint8)
    bathy_rgb[valid_depth,2]=(115+130*(1-normalized[valid_depth])).astype(np.uint8)
    bathymetry_preview=work/"bathymetry-preview.png"; Image.fromarray(bathy_rgb).save(bathymetry_preview,optimize=False,compress_level=9)
    output=work/config.get("output","gaeta-to-maratea.datatiles")
    if output.exists(): output.unlink()
    tile_size=config["tiles"]["tile_size"]; minzoom=config["tiles"]["minzoom"]; maxzoom=config["tiles"]["maxzoom"]
    source_entities={key:f"urn:datatiles:source:{key}:{info['sha256']}" for key,info in lock["sources"].items()
                     if key in ("bathymetry","land","substrate","habitat","nautical") or key.startswith("jamme_") or key.startswith("nautical_") and key!="nautical_catalogue"}
    coordinates={
      "depth_below_lat_m":{"variable":"depth_below_lat_m","dataset_release":"JammeGaia22 with EMODnet DTM 2024 fallback"},
      "bathymetry_source":{"variable":"bathymetry_source","dataset_release":config["demo_id"],"classification_scheme":"jamme-finite-cell-emodnet-fallback-v1"},
      "seabed_substrate":{"variable":"seabed_substrate","dataset_release":"EMODnet Geology 2022","classification_scheme":"datatiles-substrate-v1"},
      "seabed_habitat":{"variable":"seabed_habitat","dataset_release":"EUSeaMap 2025","classification_scheme":"EUNIS-2007 generalized"},
      "seafloor_class":{"variable":"seafloor_class","dataset_release":config["demo_id"],"classification_scheme":config["classification"]["version"]},
      "northwest_wind_shelter":{"variable":"northwest_wind_shelter","dataset_release":config["demo_id"],"classification_scheme":"land-interception-nw-v1"}}
    nautical_coordinates={"variable":"openseamap_items","dataset_release":config["sources"].get("nautical",{}).get("release",config["demo_id"]),
                          "classification_scheme":"OpenSeaMap seamark tagging"}
    grids={"depth_below_lat_m":(bathy,"float32",-9999.0,"m"),
           "bathymetry_source":(bathymetry_source,"uint8",0,"1"), "seabed_substrate":(substrate,"uint8",0,"1"),
           "seabed_habitat":(habitat,"uint8",0,"1"), "seafloor_class":(fused,"uint8",0,"1"),
           "northwest_wind_shelter":(northwest_shelter,"uint8",255,"1")}
    with DataTiles(output,create=True,name=config["title"],tile_format="application/vnd.datatiles.numeric") as store:
        store.add_dimension("variable","text",axis="C")
        store.add_dimension("dataset_release","text",axis="O")
        store.add_dimension("classification_scheme","text",axis="O",required=False)
        store.add_crs("horizontal",authority="EPSG",code="3857",uri="http://www.opengis.net/def/crs/EPSG/0/3857")
        store.add_crs("vertical",wkt2='VERTCRS["Lowest Astronomical Tide (LAT)",VDATUM["Lowest Astronomical Tide"],CS[vertical,1],AXIS["depth",down],LENGTHUNIT["metre",1]]')
        store.add_provenance_agent("https://emodnet.ec.europa.eu/","EMODnet",agent_type="organization",uri="https://emodnet.ec.europa.eu/")
        if jamme: store.add_provenance_agent("https://doi.org/10.60521/331667","JammeGaia22 / MGDS",agent_type="organization",uri="https://doi.org/10.60521/331667")
        store.add_provenance_agent("https://doi.org/10.1029/96JB00104","GSHHG / Wessel and Smith",agent_type="organization",uri="https://doi.org/10.1029/96JB00104")
        if "nautical" in config["sources"]:
            store.add_provenance_agent("https://www.openstreetmap.org/copyright","OpenStreetMap contributors",agent_type="organization",uri="https://www.openstreetmap.org/copyright")
        store.add_provenance_agent("urn:software:datatiles",f"DataTiles {__version__}",agent_type="software")
        for key,entity in source_entities.items():
            info=lock["sources"][key]; source=config["sources"]["nautical" if key=="nautical" or key.startswith("nautical_") else "jamme" if key.startswith("jamme_") else key]
            attributes={"catalogue_uuid":source["catalogue_uuid"],"release":source["release"],"license":source["license"]}
            if key.startswith("jamme_"): attributes.update({"source_sha256":info["source_sha256"],"resolution_m":info["resolution_m"],"warp":info["warp"]})
            if key=="land": attributes.update({"source_sha256":info["source_sha256"],"rasterize":info["rasterize"]})
            store.add_provenance_entity(entity,"dataset-snapshot",source["dataset"],uri=info["request_url"],checksum_algorithm="sha256",checksum=info["sha256"],attributes=attributes)
            attribution=("https://www.openstreetmap.org/copyright" if key=="nautical" or key.startswith("nautical_")
                         else "https://doi.org/10.60521/331667" if key.startswith("jamme_")
                         else "https://doi.org/10.1029/96JB00104" if key=="land" else "https://emodnet.ec.europa.eu/")
            store.add_provenance_relation(entity,"wasAttributedTo",attribution)
        activity=f"urn:datatiles:activity:{config['demo_id']}"
        store.add_provenance_activity(activity,"deterministic-tiling",config["title"]+" DataTiles build",software=f"DataTiles {__version__}",parameters={"config_sha256":sha256(config_path),"depth_transform":depth_transform,"northwest_shelter":{"method":"northwest land-interception ray","reach_cells":shelter_reach,"status":"derived exposure proxy"}})
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
                        depth_entities=tuple(key for key in ("bathymetry","land") if key in source_entities)+tuple(sorted(key for key in source_entities if key.startswith("jamme_")))
                        entity_keys=depth_entities if variable in ("depth_below_lat_m","bathymetry_source","northwest_wind_shelter") else ("substrate",) if variable=="seabed_substrate" else ("habitat",) if variable=="seabed_habitat" else ("substrate","habitat")
                        for key in entity_keys: store.link_tile_provenance(z,x,y,coordinates[variable],source_entities[key],xyz=True)
                        count+=1
                    nautical_entities=[source_entities[key] for key in sorted(source_entities)
                                       if key=="nautical" or key.startswith("nautical_")]
                    if nautical_entities:
                        tile_bbox=_tile_bounds(z,x,y); features=[]
                        for feature in nautical["features"]:
                            fb=_geometry_bounds(feature["geometry"])
                            if fb and not (fb[2]<tile_bbox[0] or fb[0]>tile_bbox[2] or fb[3]<tile_bbox[1] or fb[1]>tile_bbox[3]):
                                features.append(feature)
                        payload=canonical_json({"type":"FeatureCollection","features":features})
                        store.put(z,x,y,payload,nautical_coordinates,xyz=True,data_type="vector",media_type="application/geo+json",
                                  encoding="GeoJSON",schema={"geometry_types":["Point","LineString"],"property_prefix":"seamark:","crs":"OGC:CRS84"})
                        for entity in nautical_entities:store.link_tile_provenance(z,x,y,nautical_coordinates,entity,xyz=True)
                        count+=1
        for name,value in {
            "bounds":",".join(map(str,bbox)), "center":f"{(bbox[0]+bbox[2])/2},{(bbox[1]+bbox[3])/2},{minzoom}", "minzoom":str(minzoom), "maxzoom":str(maxzoom),
            "description":"Reproducible finest-finite JammeGaia22 bathymetry with EMODnet fallback, source coverage, substrate, habitat, fused seafloor classification, and stored OpenStreetMap seamark vectors for the Gaeta-to-Maratea corridor.",
            "attribution":"JammeGaia22/MGDS, EMODnet products, GSHHG/Wessel and Smith, and OpenStreetMap contributors (ODbL).",
            "version":"1", "datatiles:demo_config_sha256":sha256(config_path), "datatiles:warning":"NAUTICAL-CHART AID ONLY; NOT AN OFFICIAL OR SOLE SOURCE FOR NAVIGATION",
            "datatiles:fair_profile":"1", "datatiles:identifier":"urn:datatiles:demo:from-gaeta-to-maratea:1",
            "datatiles:license":"https://creativecommons.org/licenses/by/4.0/", "datatiles:access_rights":"public",
            "datatiles:creators":json.dumps([{"name":"Raffaele Montella"}],separators=(",",":")),
            "datatiles:keywords":json.dumps(["bathymetry","seabed substrate","marine habitat","seamark","OpenSeaMap","Bay of Naples","EMODnet"],separators=(",",":")),
            "datatiles:issued":"2026-08-27", "datatiles:modified":"2026-08-27",
            "datatiles:landing_page":"https://github.com/OpenFairWind/DataTiles",
            "datatiles:classes":json.dumps(CLASS_NAMES,separators=(",",":"),sort_keys=True),
            "datatiles:bathymetry_source_classes":json.dumps(bathymetry_source_classes,separators=(",",":"),sort_keys=True)}.items():
            store.db.execute("INSERT OR REPLACE INTO metadata(name,value) VALUES (?,?)",(name,value))
        store.select(coordinates["seafloor_class"])
        store.db.commit()
        if store.validate(): raise RuntimeError("generated DataTiles failed validation: "+"; ".join(store.validate()))
        store.db.execute("VACUUM")
    summary={"demo_id":config["demo_id"],"config_sha256":sha256(config_path),"source_lock_sha256":sha256(work/"source-lock.json"),
             "output":output.name,"output_sha256":sha256(output),"output_bytes":output.stat().st_size,"tile_records":count,
             "previews":{"bathymetry":{"file":bathymetry_preview.name,"sha256":sha256(bathymetry_preview)},
                         "seafloor_class":{"file":seafloor_preview.name,"sha256":sha256(seafloor_preview)}},
             "grid_shape":[height,width],"bathymetry_grid_shape":[depth_height,depth_width],"depth_transform":depth_transform,
             "bathymetry_source_cell_counts":{str(code):int((bathymetry_source==code).sum()) for code in sorted(bathymetry_source_classes)},
             "class_cell_counts":{str(code):int((fused==code).sum()) for code in sorted(CLASS_NAMES)},
             "runtime_lock_sha256":sha256(runtime_lock),"environment":runtime}
    write_json(work/"artifact-manifest.json",summary)
    bundle=work/(output.stem+"-evidence.zip")
    members=[(config_path,"config.json"),(runtime_lock,"runtime-lock.json"),(work/"source-lock.json","source-lock.json"),
             (work/"artifact-manifest.json","artifact-manifest.json"),(output,output.name),
             (bathymetry_preview,bathymetry_preview.name),(seafloor_preview,seafloor_preview.name)]
    if (work/"medchart-import.json").exists(): members.append((work/"medchart-import.json","medchart-import.json"))
    members += [(work/"raw"/info["file"],"raw/"+info["file"]) for info in lock["sources"].values()]
    with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for source,name in sorted(members,key=lambda item:item[1]):
            entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0)); entry.compress_type=zipfile.ZIP_DEFLATED
            entry.external_attr=0o100644<<16; archive.writestr(entry,source.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    write_json(work/(bundle.name+".sha256"),{"file":bundle.name,"sha256":sha256(bundle),"bytes":bundle.stat().st_size})


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
    bundle_name=Path(manifest["output"]).stem+"-evidence.zip"
    bundle_info=json.loads((work/(bundle_name+".sha256")).read_text())
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
    for command in ("acquire","import-medchart","build","verify","all","clean"):
        p=sub.add_parser(command); p.add_argument("--config",type=Path,required=True); p.add_argument("--work",type=Path,required=True)
        if command in ("acquire","all"): p.add_argument("--expect-lock",type=Path)
        if command=="import-medchart": p.add_argument("--source-root",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        if args.command in ("acquire","all"): acquire(args.config,args.work,args.expect_lock)
        if args.command=="import-medchart": import_medchart(args.config,args.work,args.source_root)
        if args.command in ("build","all"): build(args.config,args.work)
        if args.command in ("verify","all"): verify(args.config,args.work)
        if args.command=="clean": clean(args.config,args.work)
        return 0
    except (OSError,ValueError,RuntimeError) as exc:
        print(f"error: {exc}",file=sys.stderr); return 1


if __name__=="__main__": raise SystemExit(main())
