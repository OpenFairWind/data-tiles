"""Dependency-free helpers shared by the vector-to-DataTiles utilities."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable

from datatiles import DataTiles, DataTilesError

MAX_MERCATOR_LATITUDE = 85.05112878


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--min-zoom", type=int, default=0)
    parser.add_argument("--max-zoom", type=int, default=6)
    parser.add_argument("--name", help="dataset title; defaults to the input stem")
    parser.add_argument("--variable", help="DataTiles variable coordinate; defaults to the input stem")
    parser.add_argument("--force", action="store_true", help="replace an existing output file")


def _position_bounds(value: Any, bounds: list[float]) -> None:
    if isinstance(value, list) and len(value) >= 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value[:2]):
        lon, lat = float(value[0]), float(value[1])
        if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError(f"invalid longitude/latitude position: {value[:2]!r}")
        bounds[0] = min(bounds[0], lon); bounds[1] = min(bounds[1], lat)
        bounds[2] = max(bounds[2], lon); bounds[3] = max(bounds[3], lat)
        return
    if isinstance(value, list):
        for child in value: _position_bounds(child, bounds)


def geometry_bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    if not isinstance(geometry, dict) or not isinstance(geometry.get("type"), str):
        raise ValueError("feature geometry must be a GeoJSON geometry object")
    bounds = [math.inf, math.inf, -math.inf, -math.inf]
    if geometry["type"] == "GeometryCollection":
        for child in geometry.get("geometries", []):
            child_bounds = geometry_bounds(child)
            bounds = [min(bounds[0], child_bounds[0]), min(bounds[1], child_bounds[1]),
                      max(bounds[2], child_bounds[2]), max(bounds[3], child_bounds[3])]
    else:
        _position_bounds(geometry.get("coordinates"), bounds)
    if not math.isfinite(bounds[0]): raise ValueError("geometry contains no positions")
    return tuple(bounds)  # type: ignore[return-value]


def normalize_features(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and value.get("type") == "FeatureCollection": features = value.get("features")
    elif isinstance(value, dict) and value.get("type") == "Feature": features = [value]
    elif isinstance(value, dict) and isinstance(value.get("type"), str):
        features = [{"type":"Feature", "geometry":value, "properties":{}}]
    else: raise ValueError("input must be a GeoJSON FeatureCollection, Feature, or geometry")
    if not isinstance(features, list): raise ValueError("FeatureCollection.features must be an array")
    result = []
    for index, feature in enumerate(features):
        if not isinstance(feature, dict) or feature.get("type") != "Feature": raise ValueError(f"feature {index} is invalid")
        if feature.get("geometry") is None: continue
        geometry_bounds(feature["geometry"])
        clean = dict(feature); clean["properties"] = clean.get("properties") or {}
        if not isinstance(clean["properties"], dict): raise ValueError(f"feature {index} properties must be an object or null")
        result.append(clean)
    return result


def _xyz(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    size = 1 << zoom
    x = min(size - 1, max(0, int((lon + 180.0) / 360.0 * size)))
    lat = min(MAX_MERCATOR_LATITUDE, max(-MAX_MERCATOR_LATITUDE, lat))
    y = min(size - 1, max(0, int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * size)))
    return x, y


def tile_features(features: Iterable[dict[str, Any]], min_zoom: int, max_zoom: int) -> dict[tuple[int,int,int], list[dict[str,Any]]]:
    if not (0 <= min_zoom <= max_zoom <= 22): raise ValueError("zoom range must satisfy 0 <= min-zoom <= max-zoom <= 22")
    tiles: dict[tuple[int,int,int], list[dict[str,Any]]] = {}
    for feature in features:
        west, south, east, north = geometry_bounds(feature["geometry"])
        for z in range(min_zoom, max_zoom + 1):
            min_x, min_y = _xyz(west, north, z); max_x, max_y = _xyz(east, south, z)
            count = (max_x-min_x+1)*(max_y-min_y+1)
            if count > 100_000: raise ValueError(f"one feature intersects {count} tiles at zoom {z}; reduce --max-zoom")
            for x in range(min_x, max_x+1):
                for xyz_y in range(min_y, max_y+1):
                    tiles.setdefault((z,x,(1 << z)-1-xyz_y), []).append(feature)
    return tiles


def write_datatiles(features: list[dict[str, Any]], args: argparse.Namespace, *, source_format: str) -> None:
    output: Path = args.output
    if output.exists() and not args.force: raise FileExistsError(f"output already exists: {output} (use --force to replace it)")
    if output.exists(): output.unlink()
    normalized = normalize_features({"type":"FeatureCollection","features":features})
    if not normalized: raise ValueError("input contains no non-null GeoJSON features")
    tiles = tile_features(normalized, args.min_zoom, args.max_zoom)
    variable = args.variable or args.input.stem
    geometry_types = sorted({f["geometry"]["type"] for f in normalized})
    source_digest = hashlib.sha256(args.input.read_bytes()).hexdigest()
    try:
        with DataTiles(output, create=True, name=args.name or args.input.stem, tile_format="application/geo+json") as store:
            store.add_dimension("variable", "text", axis="C", description="Imported feature collection")
            store.add_crs("horizontal", authority="EPSG", code="4326", uri="http://www.opengis.net/def/crs/EPSG/0/4326")
            schema = {"geometryTypes":geometry_types, "sourceFormat":source_format}
            for (z,x,y), members in sorted(tiles.items()):
                payload = json.dumps({"type":"FeatureCollection","features":members}, sort_keys=True,
                                     separators=(",",":"), ensure_ascii=False, allow_nan=False).encode()
                store.put(z,x,y,payload,{"variable":variable},data_type="vector",
                          media_type="application/geo+json",encoding="GeoJSON",schema=schema)
            store.set_metadata("description", f"{source_format} features imported as tiled GeoJSON")
            store.set_metadata("minzoom", str(args.min_zoom)); store.set_metadata("maxzoom", str(args.max_zoom))
            store.set_metadata("datatiles:source_sha256", source_digest)
            store.set_metadata("datatiles:source_format", source_format)
            source_id=f"urn:sha256:{source_digest}"
            activity_id=f"urn:datatiles:import:{source_digest}"
            output_id=f"urn:datatiles:dataset:{source_digest}"
            store.add_provenance_agent("https://github.com/OpenFairWind/data-tiles", "DataTiles import utilities", agent_type="software")
            store.add_provenance_activity(activity_id, "feature-import", f"Import {source_format} features",
                                          software="datatiles", parameters={"minZoom":args.min_zoom,"maxZoom":args.max_zoom,"variable":variable})
            store.add_provenance_entity(source_id, "source", args.input.name,
                                        checksum_algorithm="SHA-256", checksum=source_digest)
            store.add_provenance_entity(output_id, "dataset", args.name or args.input.stem)
            store.add_provenance_relation(activity_id, "used", source_id)
            store.add_provenance_relation(output_id, "wasGeneratedBy", activity_id)
            store.add_provenance_relation(activity_id, "wasAssociatedWith", "https://github.com/OpenFairWind/data-tiles")
            for z,x,y in sorted(tiles): store.link_tile_provenance(z,x,y,{"variable":variable},output_id)
            store.select({"variable":variable})
            errors = store.validate()
            if errors: raise DataTilesError("generated container is invalid: " + "; ".join(errors))
    except Exception:
        if output.exists(): output.unlink()
        raise
    print(json.dumps({"output":os.fspath(output),"features":len(normalized),"tiles":len(tiles),"variable":variable}, sort_keys=True))


def run(parser: argparse.ArgumentParser, loader: Any) -> int:
    args = parser.parse_args()
    try:
        write_datatiles(loader(args), args, source_format=parser.prog.replace("2datatiles", ""))
        return 0
    except (DataTilesError, FileExistsError, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
        return 2
