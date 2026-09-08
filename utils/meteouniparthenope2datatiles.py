#!/usr/bin/env python3
"""Import Meteo@UniParthenope NetCDF products into time-partitioned DataTiles."""
from __future__ import annotations

import argparse
import glob
import hashlib
import logging
import math
import os
import re
import shutil
import tempfile
import urllib.parse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from common import (
    DEFAULT_NODATA,
    ConversionError,
    ResolvedSource,
    coordinate_value,
    nearest_indices,
    require_scientific_stack,
    resolve_source,
    safe_token,
    tile_pixel_lon_lat,
    tile_ranges,
)

PRODUCTS = ("wrf5", "ww33", "rms3", "wcm3", "aiq3")
DOMAINS = ("d01", "d02", "d03")
VARIABLE_ALIASES = {"U10": "U10M", "V10": "V10M"}
COARSE_DOMAIN_REFERENCE_ZOOM = 6
LOGGER = logging.getLogger(__name__)
SOURCE_RE = re.compile(
    r"(?P<product>wrf5|ww33|rms3|wcm3|aiq3)_(?P<domain>d01|d02|d03)_"
    r"(?P<stamp>\d{8}Z\d{4})\.nc(?:$|[?#])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceIdentity:
    product: str
    domain: str
    instant: datetime

    @property
    def stamp(self) -> str:
        return self.instant.strftime("%Y%m%dZ%H%M")


def parse_source_identity(source: str) -> SourceIdentity:
    """Extract the producer product, domain and valid instant from a source URI."""
    match = SOURCE_RE.search(source)
    if not match:
        raise ConversionError(
            "source name must end in <prod>_<domain>_<YYYYMMDD>Z<hh><mm>.nc "
            f"where prod is one of {', '.join(PRODUCTS)} and domain is one of {', '.join(DOMAINS)}"
        )
    try:
        instant = datetime.strptime(match.group("stamp"), "%Y%m%dZ%H%M").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ConversionError(f"invalid source date/time: {match.group('stamp')}") from exc
    return SourceIdentity(match.group("product").lower(), match.group("domain").lower(), instant)


def output_path(root: Path, identity: SourceIdentity) -> Path:
    instant = identity.instant
    return root / f"{instant:%Y}" / f"{instant:%m}" / f"{instant:%d}" / f"{identity.product}_{identity.stamp}.mbtiles"


def parse_zoom_range(value: str) -> tuple[int, ...]:
    """Parse one zoom or an inclusive MIN,MAX range."""
    try:
        fields = [int(field.strip()) for field in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("zoom must be Z or MIN,MAX") from exc
    if len(fields) == 1:
        start = end = fields[0]
    elif len(fields) == 2:
        start, end = fields
    else:
        raise argparse.ArgumentTypeError("zoom must be Z or MIN,MAX")
    if not 0 <= start <= end <= 22:
        raise argparse.ArgumentTypeError("zoom must satisfy 0 <= MIN <= MAX <= 22")
    return tuple(range(start, end + 1))


def expand_sources(patterns: list[str]) -> list[str]:
    """Expand local glob arguments even when a caller quoted them for portability."""
    expanded: list[str] = []
    for pattern in patterns:
        if urllib.parse.urlparse(pattern).scheme or not glob.has_magic(pattern):
            expanded.append(pattern)
            continue
        matches = sorted(glob.glob(os.path.expanduser(pattern)))
        if not matches:
            raise ConversionError(f"source pattern matched no files: {pattern}")
        expanded.extend(matches)
    return expanded


def parse_variables(csv_values: list[str] | None, repeated: list[str] | None) -> list[str] | None:
    names = list(repeated or [])
    for value in csv_values or []:
        names.extend(field.strip() for field in value.split(",") if field.strip())
    return names or None


def available_variables(dataset: Any, requested: list[str] | None) -> list[str]:
    if requested is None:
        return sorted(name for name, da in dataset.data_vars.items()
                      if {"latitude", "longitude"}.issubset(da.dims))
    resolved = [name if name in dataset.data_vars else VARIABLE_ALIASES.get(name, name)
                for name in requested]
    return [name for name in resolved if name in dataset.data_vars]


def grid_resolution(dataset: Any) -> float:
    """Return median rectilinear cell spacing in approximate metres."""
    np, _ = require_scientific_stack()
    lat = np.asarray(dataset.coords["latitude"].values, dtype="float64")
    lon = np.asarray(dataset.coords["longitude"].values, dtype="float64")
    if lat.ndim != 1 or lon.ndim != 1 or lat.size < 2 or lon.size < 2:
        raise ConversionError("domain selection requires non-degenerate 1-D latitude/longitude coordinates")
    latitude = float(np.median(lat))
    dy = float(np.median(np.abs(np.diff(np.sort(lat))))) * 111_320.0
    dx = float(np.median(np.abs(np.diff(np.sort(lon))))) * 111_320.0 * math.cos(math.radians(latitude))
    resolution = math.sqrt(dx * dy)
    if not math.isfinite(resolution) or resolution <= 0:
        raise ConversionError("domain has invalid spatial resolution")
    return resolution


def native_zoom(dataset: Any) -> float:
    """Estimate the Web Mercator zoom whose pixel spacing matches the source grid."""
    np, _ = require_scientific_stack()
    latitude = float(np.median(np.asarray(dataset.coords["latitude"].values, dtype="float64")))
    metres_per_pixel_z0 = 156543.03392804097 * max(math.cos(math.radians(latitude)), 1e-6)
    return math.log2(metres_per_pixel_z0 / grid_resolution(dataset))


def optimal_zoom_range(records: list[tuple[str, SourceIdentity, Any, ResolvedSource]]) -> tuple[int, ...]:
    """Choose the inclusive native-resolution range represented by available domains."""
    estimates = [native_zoom(record[2]) for record in records]
    start = max(0, min(22, int(math.floor(min(estimates)))))
    end = max(start, min(22, int(math.ceil(max(estimates)))))
    return tuple(range(start, end + 1))


def domains_by_zoom(records: list[tuple[str, SourceIdentity, Any, ResolvedSource]],
                    zooms: tuple[int, ...], *, native_anchors: bool = False
                    ) -> dict[int, tuple[str, SourceIdentity, Any, ResolvedSource]]:
    """Select coarse-to-fine domains from measured resolution across the zoom range."""
    ordered = sorted(records, key=lambda record: (-grid_resolution(record[2]), record[1].domain))
    coarsest = grid_resolution(ordered[0][2])
    anchors = ([native_zoom(record[2]) for record in ordered] if native_anchors else
               [COARSE_DOMAIN_REFERENCE_ZOOM + math.log2(coarsest / grid_resolution(record[2]))
                for record in ordered])
    return {
        zoom: min(zip(anchors, ordered), key=lambda item: (abs(zoom - item[0]), item[0]))[1]
        for zoom in zooms
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@contextmanager
def open_source_dataset(source: str, *, opendap: bool, engine: str | None,
                        timeout: float) -> Iterator[tuple[Any, ResolvedSource]]:
    """Open a file/URL or materialize an exact OPeNDAP response snapshot."""
    _, xr = require_scientific_stack()
    # Keep time numeric here and decode its simple CF unit explicitly.  This
    # avoids platform-dependent pandas date bounds and retains the source value.
    kwargs: dict[str, Any] = {"decode_cf": True, "decode_times": False}
    if engine:
        kwargs["engine"] = engine
    if not opendap:
        with resolve_source(source, timeout=timeout) as resolved:
            with xr.open_dataset(resolved.local_path, **kwargs) as dataset:
                yield dataset, resolved
        return

    parsed = urllib.parse.urlparse(source)
    if parsed.scheme not in {"http", "https"}:
        raise ConversionError("--opendap requires an HTTP(S) dataset URL")
    fd, name = tempfile.mkstemp(prefix="datatiles-opendap-snapshot-", suffix=".nc")
    os.close(fd)
    snapshot = Path(name)
    try:
        with xr.open_dataset(source, **kwargs) as remote:
            remote.load()
            remote.to_netcdf(snapshot)
        resolved = ResolvedSource(source, snapshot, source, "sha256", _sha256(snapshot), True)
        with xr.open_dataset(snapshot, decode_cf=True, decode_times=False) as dataset:
            yield dataset, resolved
    finally:
        snapshot.unlink(missing_ok=True)


def _instant_text(instant: datetime) -> str:
    return instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_dataset_time(dataset: Any, identity: SourceIdentity) -> None:
    np, _ = require_scientific_stack()
    if "time" not in dataset.coords or dataset.coords["time"].size != 1:
        raise ConversionError("Meteo@UniParthenope source must contain exactly one time coordinate")
    time_coord = dataset.coords["time"]
    value = np.asarray(time_coord.values).reshape(-1)[0]
    units = str(time_coord.attrs.get("units") or "").strip()
    match = re.fullmatch(
        r"(seconds?|minutes?|hours?|days?)\s+since\s+"
        r"(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}(?::\d+(?:\.\d+)?)?))?(?:\s*(?:Z|UTC))?",
        units, re.IGNORECASE,
    )
    if not match or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ConversionError("time must use numeric CF seconds/minutes/hours/days since a Gregorian epoch")
    clock = match.group(3) or "00:00:00"
    fields = clock.split(":")
    hour, minute = int(fields[0]), int(fields[1])
    seconds = float(fields[2]) if len(fields) == 3 else 0.0
    epoch = datetime.fromisoformat(match.group(2)).replace(tzinfo=timezone.utc)
    epoch += timedelta(hours=hour, minutes=minute, seconds=seconds)
    scale = {"second": 1.0, "minute": 60.0, "hour": 3600.0, "day": 86400.0}[match.group(1).lower().rstrip("s")]
    source_time = epoch + timedelta(seconds=float(value) * scale)
    if abs((source_time - identity.instant).total_seconds()) >= 30:
        raise ConversionError(
            f"NetCDF time {_instant_text(source_time)} does not match filename {identity.stamp}"
        )


def _ensure_dimension(store: Any, name: str, value_type: str, **kwargs: Any) -> None:
    if not store.db.execute("SELECT 1 FROM datatiles_dimensions WHERE name=?", (name,)).fetchone():
        store.add_dimension(name, value_type, **kwargs)


def _ensure_container(store: Any) -> None:
    _ensure_dimension(store, "variable", "text", description="Semantic variable token")
    _ensure_dimension(store, "product", "text", description="Meteo@UniParthenope model/product identifier")
    _ensure_dimension(store, "domain", "text", description="Meteo@UniParthenope source domain or coarse+fine nested composition")
    _ensure_dimension(store, "valid_time", "datetime", axis="T", description="Forecast valid time in UTC")
    if not store.db.execute("SELECT 1 FROM datatiles_crs WHERE role='horizontal' AND authority='EPSG' AND code='3857'").fetchone():
        store.add_crs("horizontal", authority="EPSG", code="3857", uri="http://www.opengis.net/def/crs/EPSG/0/3857")


def _register_variable(store: Any, da: Any, identity: SourceIdentity) -> str:
    token = safe_token(f"{identity.product}_{da.name}")
    unit = str(da.attrs.get("units") or "").strip() or None
    description = str(da.attrs.get("description") or da.attrs.get("long_name") or "").strip() or None
    if not store.db.execute("SELECT 1 FROM datatiles_variables WHERE name=?", (token,)).fetchone():
        # Producer-local standard_name values such as "u-component" are not
        # asserted as CF Standard Names without an authoritative crosswalk.
        store.add_variable(token, safe_token(str(da.name)), vocabulary="MeteoUniParthenope",
                           canonical_unit=unit, long_name=description,
                           description=f"Imported from {identity.product} NetCDF variable {da.name}")
        store.add_variable_identifier(token, "MeteoUniParthenope-variable",
                                      f"{identity.product}:{da.name}")
    else:
        row = store.db.execute(
            "SELECT canonical_unit FROM datatiles_variables WHERE name=?", (token,)
        ).fetchone()
        if row[0] != unit:
            raise ConversionError(f"variable {da.name} unit {unit!r} conflicts with the existing {token} definition")
    return token


def _non_spatial_slices(da: Any) -> Iterator[tuple[dict[str, Any], Any]]:
    np, _ = require_scientific_stack()
    extra = [dim for dim in da.dims if dim not in {"time", "latitude", "longitude"}]
    if not extra:
        yield {}, da.isel(time=0) if "time" in da.dims else da
        return
    for index in np.ndindex(*(da.sizes[dim] for dim in extra)):
        selectors = dict(zip(extra, index))
        coordinates = {
            dim: coordinate_value(da.coords[dim].values[i]) if dim in da.coords else int(i)
            for dim, i in selectors.items()
        }
        if "time" in da.dims:
            selectors["time"] = 0
        yield coordinates, da.isel(selectors)


def _ensure_extra_dimensions(store: Any, dataset: Any, arrays: list[Any]) -> None:
    np, _ = require_scientific_stack()
    for da in arrays:
        for dim in da.dims:
            if dim in {"time", "latitude", "longitude"}:
                continue
            coord = dataset.coords.get(dim)
            value = coord.values[0] if coord is not None and coord.size else 0
            dtype = "datetime" if np.issubdtype(np.asarray(value).dtype, np.datetime64) else (
                "integer" if isinstance(value, (int, np.integer)) else
                "float" if isinstance(value, (float, np.floating)) else "text"
            )
            _ensure_dimension(store, dim, dtype, required=False,
                              unit=str(coord.attrs.get("units") or "").strip() or None if coord is not None else None,
                              description=f"Imported source dimension {dim}")


def _prepared_grid(dataset: Any) -> tuple[Any, Any, Any, Any, tuple[float, float, float, float]]:
    np, _ = require_scientific_stack()
    lat = np.asarray(dataset.coords["latitude"].values, dtype="float64")
    lon = np.asarray(dataset.coords["longitude"].values, dtype="float64")
    if lat.ndim != 1 or lon.ndim != 1 or not np.all(np.isfinite(lat)) or not np.all(np.isfinite(lon)):
        raise ConversionError("latitude and longitude must be finite one-dimensional coordinates")
    lon = ((lon + 180.0) % 360.0) - 180.0
    lat_order, lon_order = np.argsort(lat), np.argsort(lon)
    lat, lon = lat[lat_order], lon[lon_order]
    return lat, lon, lat_order, lon_order, (float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max()))


def _source_entity(store: Any, dataset: Any, resolved: ResolvedSource, identity: SourceIdentity, *,
                   source_license: str, source_license_uri: str, source_attribution: str,
                   access_rights: str, opendap: bool) -> str:
    entity_id = f"source:meteouniparthenope:{identity.product}:{identity.domain}:sha256:{resolved.checksum}"
    if not store.db.execute("SELECT 1 FROM datatiles_provenance_entities WHERE entity_id=?", (entity_id,)).fetchone():
        store.add_provenance_entity(
            entity_id, "dataset", f"Meteo@UniParthenope {identity.product}/{identity.domain} source",
            uri=resolved.uri, checksum_algorithm=resolved.checksum_algorithm, checksum=resolved.checksum,
            attributes={"source_kind": "NetCDF", "product": identity.product, "domain": identity.domain,
                        "valid_time": _instant_text(identity.instant),
                        "native_resolution_metres": grid_resolution(dataset),
                        "acquisition": "OPeNDAP materialized snapshot" if opendap else "file bytes"},
        )
        store.add_rights("source", source_license, license_uri=source_license_uri,
                         attribution_text=source_attribution, access_rights=access_rights,
                         source_entity_id=entity_id, applies_to=resolved.identifier)
    return entity_id


def import_dataset(store: Any, dataset: Any, resolved: ResolvedSource, identity: SourceIdentity, *,
                   variables: list[str] | None, zoom: int, tile_size: int,
                   bbox: tuple[float, float, float, float] | None, max_tiles: int,
                   source_license: str, source_license_uri: str, source_attribution: str,
                   dataset_license: str, dataset_license_uri: str,
                   dataset_attribution: str | None, access_rights: str,
                   opendap: bool, zoom_selection: str = "explicit",
                   fallback_domains: list[tuple[Any, ResolvedSource, SourceIdentity]] | None = None) -> dict[str, int]:
    np, _ = require_scientific_stack()
    from datatiles.numeric import encode_numeric_tile

    sources = list(fallback_domains or []) + [(dataset, resolved, identity)]
    for source_dataset, _, source_identity in sources:
        validate_dataset_time(source_dataset, source_identity)
        if source_identity.product != identity.product or source_identity.instant != identity.instant:
            raise ConversionError("nested domains must have the same product and valid time")
    names = available_variables(dataset, variables)
    if not names:
        raise ConversionError("no latitude/longitude data variables selected")
    arrays = [dataset[name] for name in names]
    for da in arrays:
        if not {"latitude", "longitude"}.issubset(da.dims):
            raise ConversionError(f"{da.name}: latitude and longitude must be array dimensions")

    grids = [(source_dataset, source_resolved, source_identity, _prepared_grid(source_dataset))
             for source_dataset, source_resolved, source_identity in sources]
    native_bbox = grids[0][3][4]
    for _, _, _, grid in grids[1:]:
        extent = grid[4]
        native_bbox = (min(native_bbox[0], extent[0]), min(native_bbox[1], extent[1]),
                       max(native_bbox[2], extent[2]), max(native_bbox[3], extent[3]))
    actual_bbox = native_bbox
    if bbox is not None:
        west, south, east, north = bbox
        if west > east or south > north:
            raise ConversionError("invalid --bbox ordering")
        actual_bbox = (max(west, native_bbox[0]), max(south, native_bbox[1]),
                       min(east, native_bbox[2]), min(north, native_bbox[3]))
        if actual_bbox[0] > actual_bbox[2] or actual_bbox[1] > actual_bbox[3]:
            raise ConversionError("--bbox does not intersect the source grid")
    xs, ys = tile_ranges(actual_bbox, zoom)

    entity_ids = [
        _source_entity(store, source_dataset, source_resolved, source_identity,
                       source_license=source_license, source_license_uri=source_license_uri,
                       source_attribution=source_attribution, access_rights=access_rights, opendap=opendap)
        for source_dataset, source_resolved, source_identity, _ in grids
    ]
    if not store.db.execute("SELECT 1 FROM datatiles_rights WHERE scope='dataset'").fetchone():
        store.add_rights("dataset", dataset_license, license_uri=dataset_license_uri,
                         attribution_text=dataset_attribution, access_rights=access_rights)
        store.add_rights("metadata", "CC0-1.0",
                         license_uri="https://creativecommons.org/publicdomain/zero/1.0/",
                         attribution_text="DataTiles metadata; source attribution remains binding where applicable")
    else:
        existing_license = store.db.execute(
            "SELECT license_expression,license_uri FROM datatiles_rights WHERE scope='dataset' ORDER BY rights_id LIMIT 1"
        ).fetchone()
        if tuple(existing_license) != (dataset_license, dataset_license_uri):
            raise ConversionError("dataset licence does not match the existing same-time DataTiles file")
    domain_token = "+".join(source_identity.domain for _, _, source_identity, _ in grids)
    source_digest = hashlib.sha256("|".join(source_resolved.checksum for _, source_resolved, _, _ in grids).encode()).hexdigest()
    activity_id = f"activity:import-nested:{identity.product}:{domain_token}:z{zoom}:{source_digest}"
    if not store.db.execute(
        "SELECT 1 FROM datatiles_provenance_activities WHERE activity_id=?", (activity_id,)
    ).fetchone():
        store.add_provenance_activity(
            activity_id, "conversion", f"Import nested {identity.product}/{domain_token} NetCDF domains",
            software="DataTiles meteouniparthenope2datatiles",
            parameters={"algorithm": "nested-domain-finite-override-nearest-neighbour-v1",
                        "zoom": zoom, "tile_size": tile_size,
                        "bbox": bbox, "source_crs": "EPSG:4326", "output_crs": "EPSG:3857",
                        "product": identity.product, "domains_coarse_to_fine": domain_token.split("+"),
                        "opendap": opendap,
                        "zoom_selection": zoom_selection,
                        "native_resolution_metres": {
                            source_identity.domain: grid_resolution(source_dataset)
                            for source_dataset, _, source_identity, _ in grids
                        }},
        )
        for entity_id in entity_ids:
            store.add_provenance_relation(activity_id, "used", entity_id)
    _ensure_extra_dimensions(store, dataset, arrays)

    stats = {"variables": 0, "slices": 0, "tiles": 0}
    valid_time = _instant_text(identity.instant)
    first_coordinates = None
    for da in arrays:
        token = _register_variable(store, da, identity)
        fill = da.attrs.get("_FillValue", da.attrs.get("missing_value", DEFAULT_NODATA))
        try:
            nodata = float(fill)
            if not math.isfinite(nodata):
                nodata = DEFAULT_NODATA
        except (TypeError, ValueError):
            nodata = DEFAULT_NODATA
        unit = str(da.attrs.get("units") or "").strip() or None
        for extra, slice_da in _non_spatial_slices(da):
            planned = len(xs) * len(ys)
            if stats["tiles"] + planned > max_tiles:
                raise ConversionError(f"conversion would exceed --max-tiles={max_tiles}")
            domain_arrays = []
            for (source_dataset, _, source_identity, grid), entity_id in zip(grids, entity_ids):
                if da.name not in source_dataset.data_vars:
                    continue
                source_da = source_dataset[da.name]
                source_unit = str(source_da.attrs.get("units") or "").strip() or None
                if source_unit != unit:
                    raise ConversionError(f"{da.name}: nested domain units differ")
                selectors = {dim: value for dim, value in extra.items() if dim in source_da.coords}
                selected = source_da.sel(selectors) if selectors else source_da
                if "time" in selected.dims:
                    selected = selected.isel(time=0)
                lat, lon, lat_order, lon_order, extent = grid
                values = np.asarray(selected.transpose("latitude", "longitude").values, dtype="float64")
                values = values[lat_order, :][:, lon_order]
                source_fill = source_da.attrs.get("_FillValue", source_da.attrs.get("missing_value", DEFAULT_NODATA))
                domain_arrays.append((lat, lon, extent, values, source_fill, entity_id))
            coordinates = {"variable": token, "product": identity.product, "domain": domain_token,
                           "valid_time": valid_time, **extra}
            first_coordinates = first_coordinates or dict(coordinates)
            stats["slices"] += 1
            for x in xs:
                for y in ys:
                    pixel_lon, pixel_lat = tile_pixel_lon_lat(zoom, x, y, tile_size)
                    tile = np.full((tile_size, tile_size), nodata, dtype="float64")
                    contributors = []
                    west, south, east, north = actual_bbox
                    requested = ((pixel_lat[:, None] >= south) & (pixel_lat[:, None] <= north) &
                                 (pixel_lon[None, :] >= west) & (pixel_lon[None, :] <= east))
                    for lat, lon, extent, values, source_fill, entity_id in domain_arrays:
                        iy, ix = nearest_indices(lat, pixel_lat), nearest_indices(lon, pixel_lon)
                        sampled = values[np.ix_(iy, ix)]
                        west, south, east, north = extent
                        valid = (requested &
                                 (pixel_lat[:, None] >= south) & (pixel_lat[:, None] <= north) &
                                 (pixel_lon[None, :] >= west) & (pixel_lon[None, :] <= east) &
                                 np.isfinite(sampled) & (sampled != source_fill))
                        if np.any(valid):
                            tile = np.where(valid, sampled, tile)
                            contributors.append(entity_id)
                    tile = tile.astype("float32")
                    blob = encode_numeric_tile(tile.ravel().tolist(), tile.shape, dtype="float32",
                                               compression="zlib", nodata=nodata, unit=unit)
                    content_schema = {
                        "resampling": "nearest", "grid": "WebMercatorQuad", "tile_size": tile_size,
                        "source_grid": "rectilinear latitude/longitude", "source_crs": "EPSG:4326",
                        "source_kind": "Meteo@UniParthenope NetCDF",
                    }
                    if len(grids) > 1:
                        content_schema.update({
                            "domain_composition": domain_token.split("+"),
                            "composition_algorithm": "finite finer-domain override; no boundary blending",
                        })
                    store.put(zoom, x, y, blob, coordinates, xyz=True, data_type="raster",
                              media_type="application/vnd.datatiles.numeric", encoding="DNT1",
                              schema=content_schema)
                    for entity_id in contributors:
                        store.link_tile_provenance(zoom, x, y, coordinates, entity_id, xyz=True)
                    stats["tiles"] += 1
        stats["variables"] += 1
    if store.db.execute("SELECT coordinate_set_id FROM datatiles_selected_slice WHERE singleton=1").fetchone()[0] is None:
        store.select(first_coordinates)
    metadata = store.metadata()
    if "bounds" in metadata:
        previous = tuple(float(value) for value in metadata["bounds"].split(","))
        actual_bbox = (min(previous[0], actual_bbox[0]), min(previous[1], actual_bbox[1]),
                       max(previous[2], actual_bbox[2]), max(previous[3], actual_bbox[3]))
    store.set_metadata("bounds", ",".join(format(value, ".15g") for value in actual_bbox))
    return stats


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", nargs="+", help="NetCDF local path, file/HTTP(S) URL, or OPeNDAP URL")
    p.add_argument("--root", type=Path, required=True, help="output root directory")
    p.add_argument("--opendap", action="store_true", help="treat HTTP(S) sources as OPeNDAP datasets")
    p.add_argument("--variable", action="append", dest="variable", help="variable to import; repeatable")
    p.add_argument("--variables", action="append", help="comma-separated variables to import")
    p.add_argument("--zoom", type=parse_zoom_range, metavar="Z|MIN,MAX",
                   help="one zoom or an inclusive range; omit for metadata-derived native zooms")
    p.add_argument("--frame-storage", choices=("separate", "single"), default="separate",
                   help="write one product/time file per frame (default) or all frames to one file")
    p.add_argument("--tile-size", type=int, default=256)
    p.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    p.add_argument("--max-tiles", type=int, default=10000, help="per-source safety bound")
    p.add_argument("--engine", help="xarray NetCDF engine")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--source-license", required=True)
    p.add_argument("--source-license-uri", required=True)
    p.add_argument("--source-attribution", required=True)
    p.add_argument("--dataset-license", required=True)
    p.add_argument(
        "--dataset-license-uri",
        help="derived-dataset terms URI; defaults to --source-license-uri for this provider profile",
    )
    p.add_argument("--dataset-attribution")
    p.add_argument("--access-rights", choices=("open", "embargoed", "restricted", "closed"), default="open")
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        if not 8 <= args.tile_size <= 1024:
            raise ConversionError("--tile-size must be between 8 and 1024")
        if args.dataset_license_uri is None:
            args.dataset_license_uri = args.source_license_uri
        sources = expand_sources(args.source)
        identities = [parse_source_identity(source) for source in sources]
        variables = parse_variables(args.variables, args.variable)
        from contextlib import ExitStack
        from datatiles.store import DataTiles
        with ExitStack() as stack:
            records = []
            for source, identity in zip(sources, identities):
                dataset, resolved = stack.enter_context(open_source_dataset(
                    source, opendap=args.opendap, engine=args.engine, timeout=args.timeout
                ))
                records.append((source, identity, dataset, resolved))
            if args.frame_storage == "separate":
                keys = sorted({(record[1].product, record[1].instant) for record in records})
                groups = [([record for record in records if (record[1].product, record[1].instant) == key], None)
                          for key in keys]
            else:
                groups = [(records, args.root.expanduser().resolve() / "meteouniparthenope.mbtiles")]
            totals = {"variables": 0, "slices": 0, "tiles": 0}
            outputs = []
            for group, explicit_target in groups:
                if variables and not any(available_variables(record[2], variables) for record in group):
                    continue
                target = explicit_target or output_path(args.root.expanduser().resolve(), group[0][1])
                target.parent.mkdir(parents=True, exist_ok=True)
                fd, staging_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
                os.close(fd)
                staging = Path(staging_name)
                staging.unlink()
                if target.exists():
                    shutil.copy2(target, staging)
                try:
                    with DataTiles(staging, create=not staging.exists(), name=target.stem,
                                   tile_format="application/vnd.datatiles.numeric") as store:
                        _ensure_container(store)
                        frame_keys = sorted({(record[1].product, record[1].instant) for record in group})
                        used = []
                        used_zooms = []
                        for frame_key in frame_keys:
                            frame = [record for record in group if (record[1].product, record[1].instant) == frame_key]
                            if variables and not any(available_variables(record[2], variables) for record in frame):
                                continue
                            zooms = args.zoom or optimal_zoom_range(frame)
                            chosen = domains_by_zoom(frame, zooms, native_anchors=args.zoom is None)
                            ordered_domains = sorted(frame, key=lambda record: (-grid_resolution(record[2]), record[1].domain))
                            for zoom in zooms:
                                source, identity, dataset, resolved = chosen[zoom]
                                primary_index = next(index for index, record in enumerate(ordered_domains)
                                                     if record[1].domain == identity.domain)
                                fallback_records = ordered_domains[max(0, primary_index - 1):primary_index]
                                composite_domains = [record[1].domain for record in fallback_records] + [identity.domain]
                                used.append(f"z{zoom}:{identity.product}/{'+'.join(composite_domains)}")
                                used_zooms.append(zoom)
                                stats = import_dataset(
                                    store, dataset, resolved, identity, variables=variables, zoom=zoom,
                                    tile_size=args.tile_size, bbox=tuple(args.bbox) if args.bbox else None,
                                    max_tiles=args.max_tiles, source_license=args.source_license,
                                    source_license_uri=args.source_license_uri,
                                    source_attribution=args.source_attribution,
                                    dataset_license=args.dataset_license,
                                    dataset_license_uri=args.dataset_license_uri,
                                    dataset_attribution=args.dataset_attribution,
                                    access_rights=args.access_rights, opendap=args.opendap,
                                    zoom_selection=("explicit" if args.zoom is not None else
                                                    "automatic:native-web-mercator-pixel-resolution-v1"),
                                    fallback_domains=[(record[2], record[3], record[1])
                                                      for record in fallback_records],
                                )
                                for key in totals:
                                    totals[key] += stats[key]
                        metadata = store.metadata()
                        store.set_metadata("minzoom", str(min(min(used_zooms), int(metadata.get("minzoom", min(used_zooms))))))
                        store.set_metadata("maxzoom", str(max(max(used_zooms), int(metadata.get("maxzoom", max(used_zooms))))))
                        store.set_metadata("datatiles:meteouniparthenope_domain_selection", ",".join(used))
                        store.set_metadata(
                            "datatiles:meteouniparthenope_zoom_selection",
                            "explicit" if args.zoom is not None else "automatic:native-web-mercator-pixel-resolution-v1",
                        )
                        store.set_metadata(
                            "datatiles:meteouniparthenope_frames",
                            ",".join(f"{product}:{_instant_text(instant)}" for product, instant in frame_keys),
                        )
                        errors = store.validate(require_variable_semantics=True)
                        if errors:
                            raise ConversionError("generated DataTiles failed validation: " + "; ".join(errors))
                    os.replace(staging, target)
                    outputs.append(target)
                finally:
                    staging.unlink(missing_ok=True)
        for target in outputs:
            LOGGER.info("updated %s", target)
        LOGGER.info("total: %d variables, %d slices, %d tiles",
                    totals["variables"], totals["slices"], totals["tiles"])
        return 0
    except (ConversionError, OSError, ValueError) as exc:
        parser().error(str(exc))
        return 2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
