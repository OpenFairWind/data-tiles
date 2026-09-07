#!/usr/bin/env python3
"""Import Meteo@UniParthenope NetCDF products into time-partitioned DataTiles."""
from __future__ import annotations

import argparse
import hashlib
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
    return root / f"{instant:%Y}" / f"{instant:%m}" / f"{instant:%d}" / f"{identity.stamp}.mbtiles"


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
    _ensure_dimension(store, "domain", "text", description="Meteo@UniParthenope grid domain (d01 coarse to d03 fine)")
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


def import_dataset(store: Any, dataset: Any, resolved: ResolvedSource, identity: SourceIdentity, *,
                   variables: list[str] | None, zoom: int, tile_size: int,
                   bbox: tuple[float, float, float, float] | None, max_tiles: int,
                   source_license: str, source_license_uri: str, source_attribution: str,
                   dataset_license: str, dataset_license_uri: str,
                   dataset_attribution: str | None, access_rights: str,
                   opendap: bool) -> dict[str, int]:
    np, _ = require_scientific_stack()
    from datatiles.numeric import encode_numeric_tile

    validate_dataset_time(dataset, identity)
    names = variables or sorted(name for name, da in dataset.data_vars.items()
                                if {"latitude", "longitude"}.issubset(da.dims))
    if not names:
        raise ConversionError("no latitude/longitude data variables selected")
    missing = [name for name in names if name not in dataset.data_vars]
    if missing:
        raise ConversionError("variable not found: " + ", ".join(missing))
    arrays = [dataset[name] for name in names]
    for da in arrays:
        if not {"latitude", "longitude"}.issubset(da.dims):
            raise ConversionError(f"{da.name}: latitude and longitude must be array dimensions")

    lat = np.asarray(dataset.coords["latitude"].values, dtype="float64")
    lon = np.asarray(dataset.coords["longitude"].values, dtype="float64")
    if lat.ndim != 1 or lon.ndim != 1 or not np.all(np.isfinite(lat)) or not np.all(np.isfinite(lon)):
        raise ConversionError("latitude and longitude must be finite one-dimensional coordinates")
    lon = ((lon + 180.0) % 360.0) - 180.0
    lat_order, lon_order = np.argsort(lat), np.argsort(lon)
    lat, lon = lat[lat_order], lon[lon_order]
    native_bbox = (float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max()))
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

    entity_id = f"source:meteouniparthenope:{identity.product}:{identity.domain}:sha256:{resolved.checksum}"
    if store.db.execute("SELECT 1 FROM datatiles_provenance_entities WHERE entity_id=?", (entity_id,)).fetchone():
        raise ConversionError(f"source was already imported: {resolved.identifier}")
    store.add_provenance_entity(
        entity_id, "dataset", f"Meteo@UniParthenope {identity.product}/{identity.domain} source",
        uri=resolved.uri, checksum_algorithm=resolved.checksum_algorithm, checksum=resolved.checksum,
        attributes={"source_kind": "NetCDF", "product": identity.product, "domain": identity.domain,
                    "valid_time": _instant_text(identity.instant),
                    "acquisition": "OPeNDAP materialized snapshot" if opendap else "file bytes"},
    )
    store.add_rights("source", source_license, license_uri=source_license_uri,
                     attribution_text=source_attribution, access_rights=access_rights,
                     source_entity_id=entity_id, applies_to=resolved.identifier)
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
    activity_id = f"activity:import:{identity.product}:{identity.domain}:{resolved.checksum}"
    store.add_provenance_activity(
        activity_id, "conversion", f"Import {identity.product}/{identity.domain} NetCDF",
        software="DataTiles meteouniparthenope2datatiles",
        parameters={"algorithm": "nearest-neighbour", "zoom": zoom, "tile_size": tile_size,
                    "bbox": bbox, "source_crs": "EPSG:4326", "output_crs": "EPSG:3857",
                    "product": identity.product, "domain": identity.domain, "opendap": opendap},
    )
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
            values = np.asarray(slice_da.transpose("latitude", "longitude").values, dtype="float64")
            values = values[lat_order, :][:, lon_order]
            coordinates = {"variable": token, "product": identity.product, "domain": identity.domain,
                           "valid_time": valid_time, **extra}
            first_coordinates = first_coordinates or dict(coordinates)
            stats["slices"] += 1
            for x in xs:
                for y in ys:
                    pixel_lon, pixel_lat = tile_pixel_lon_lat(zoom, x, y, tile_size)
                    iy, ix = nearest_indices(lat, pixel_lat), nearest_indices(lon, pixel_lon)
                    tile = values[np.ix_(iy, ix)]
                    west, south, east, north = actual_bbox
                    inside = ((pixel_lat[:, None] >= south) & (pixel_lat[:, None] <= north) &
                              (pixel_lon[None, :] >= west) & (pixel_lon[None, :] <= east))
                    tile = np.where(inside & np.isfinite(tile) & (tile != fill), tile, nodata).astype("float32")
                    blob = encode_numeric_tile(tile.ravel().tolist(), tile.shape, dtype="float32",
                                               compression="zlib", nodata=nodata, unit=unit)
                    store.put(zoom, x, y, blob, coordinates, xyz=True, data_type="raster",
                              media_type="application/vnd.datatiles.numeric", encoding="DNT1",
                              schema={"resampling": "nearest", "grid": "WebMercatorQuad", "tile_size": tile_size,
                                      "source_grid": "rectilinear latitude/longitude", "source_crs": "EPSG:4326",
                                      "source_kind": "Meteo@UniParthenope NetCDF"})
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
    p.add_argument("--variable", action="append", dest="variables", help="variable to import; repeatable")
    p.add_argument("--zoom", type=int, default=6)
    p.add_argument("--tile-size", type=int, default=256)
    p.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    p.add_argument("--max-tiles", type=int, default=10000, help="per-source safety bound")
    p.add_argument("--engine", help="xarray NetCDF engine")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--source-license", required=True)
    p.add_argument("--source-license-uri", required=True)
    p.add_argument("--source-attribution", required=True)
    p.add_argument("--dataset-license", required=True)
    p.add_argument("--dataset-license-uri", required=True)
    p.add_argument("--dataset-attribution")
    p.add_argument("--access-rights", choices=("open", "embargoed", "restricted", "closed"), default="open")
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        if not 0 <= args.zoom <= 22:
            raise ConversionError("--zoom must be between 0 and 22")
        if not 8 <= args.tile_size <= 1024:
            raise ConversionError("--tile-size must be between 8 and 1024")
        identities = [parse_source_identity(source) for source in args.source]
        if len({identity.instant for identity in identities}) != 1:
            raise ConversionError("all sources in one invocation must have the same filename date/time")
        target = output_path(args.root.expanduser().resolve(), identities[0])
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, staging_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
        os.close(fd)
        staging = Path(staging_name)
        staging.unlink()
        if target.exists():
            shutil.copy2(target, staging)
        totals = {"variables": 0, "slices": 0, "tiles": 0}
        try:
            from datatiles.store import DataTiles
            with DataTiles(staging, create=not staging.exists(), name=target.stem,
                           tile_format="application/vnd.datatiles.numeric") as store:
                _ensure_container(store)
                for source, identity in zip(args.source, identities):
                    with open_source_dataset(source, opendap=args.opendap, engine=args.engine,
                                             timeout=args.timeout) as (dataset, resolved):
                        stats = import_dataset(
                            store, dataset, resolved, identity, variables=args.variables, zoom=args.zoom,
                            tile_size=args.tile_size, bbox=tuple(args.bbox) if args.bbox else None,
                            max_tiles=args.max_tiles, source_license=args.source_license,
                            source_license_uri=args.source_license_uri, source_attribution=args.source_attribution,
                            dataset_license=args.dataset_license, dataset_license_uri=args.dataset_license_uri,
                            dataset_attribution=args.dataset_attribution, access_rights=args.access_rights,
                            opendap=args.opendap,
                        )
                        for key in totals:
                            totals[key] += stats[key]
                metadata = store.metadata()
                store.set_metadata("minzoom", str(min(args.zoom, int(metadata.get("minzoom", args.zoom)))))
                store.set_metadata("maxzoom", str(max(args.zoom, int(metadata.get("maxzoom", args.zoom)))))
                store.set_metadata("datatiles:meteouniparthenope_valid_time", _instant_text(identities[0].instant))
                errors = store.validate(require_variable_semantics=True)
                if errors:
                    raise ConversionError("generated DataTiles failed validation: " + "; ".join(errors))
            os.replace(staging, target)
        finally:
            staging.unlink(missing_ok=True)
        print(f"updated {target}: {totals['variables']} variables, {totals['slices']} slices, {totals['tiles']} tiles")
        return 0
    except (ConversionError, OSError, ValueError) as exc:
        parser().error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
