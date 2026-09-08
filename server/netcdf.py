"""Read-only, on-demand DNT1 tiling of configured NetCDF archives."""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from datatiles.numeric import encode_numeric_tile

SOURCE_CRS = "EPSG:4326"
OUTPUT_CRS = "EPSG:3857"
RESAMPLING = "nearest-neighbour-at-Web-Mercator-pixel-centres-v1"
DEFAULT_NODATA = -3.4028234663852886e38
TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
STAMP_RE = re.compile(r"^\d{8}Z\d{4}$")


class NetCDFTileError(ValueError):
    """A safe, client-visible NetCDF archive or tiling error."""


@dataclass(frozen=True)
class NetCDFTile:
    body: bytes
    source: Path
    variable: str
    unit: str | None
    source_shape: tuple[int, int]


def load_products(path: Path) -> dict[str, tuple[str, ...]]:
    """Load ``{product: [variables...]}`` or object-valued product entries."""
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NetCDFTileError(f"invalid NetCDF product configuration: {exc}") from exc
    if not isinstance(raw, dict):
        raise NetCDFTileError("NetCDF product configuration must be a JSON object")
    products: dict[str, tuple[str, ...]] = {}
    for product, definition in sorted(raw.items()):
        _token(product, "product")
        variables = definition.get("variables") if isinstance(definition, dict) else definition
        if not isinstance(variables, list) or not variables:
            raise NetCDFTileError(f"product {product!r} must declare a non-empty variables list")
        if any(not isinstance(value, str) for value in variables):
            raise NetCDFTileError(f"product {product!r} variables must be strings")
        checked = tuple(_token(value, "variable") for value in variables)
        if len(set(checked)) != len(checked):
            raise NetCDFTileError(f"product {product!r} contains duplicate variables")
        products[product] = checked
    return products


def _token(value: str, label: str) -> str:
    if not isinstance(value, str) or not TOKEN_RE.fullmatch(value):
        raise NetCDFTileError(f"invalid {label}")
    return value


def archive_path(root: Path, product: str, domain: str, stamp: str) -> Path:
    """Resolve the normative archive layout without accepting path traversal."""
    product = _token(product, "product")
    domain = _token(domain, "domain")
    if not STAMP_RE.fullmatch(stamp):
        raise NetCDFTileError("time must use YYYYMMDDZhhmm")
    try:
        instant = datetime.strptime(stamp, "%Y%m%dZ%H%M")
    except ValueError as exc:
        raise NetCDFTileError("invalid calendar date or time") from exc
    return (root / product / domain / "archive" / f"{instant:%Y}" / f"{instant:%m}" /
            f"{instant:%d}" / f"{product}_{domain}_{stamp}.nc")


def archive_frames(root: Path, product: str) -> list[dict[str, str]]:
    """Discover correctly named frames for a configured product."""
    product = _token(product, "product")
    base = root / product
    if not base.is_dir():
        return []
    pattern = re.compile(rf"^{re.escape(product)}_(?P<domain>[A-Za-z0-9_.-]+)_(?P<stamp>\d{{8}}Z\d{{4}})\.nc$")
    found: list[dict[str, str]] = []
    for path in sorted(base.glob("*/archive/[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/*.nc")):
        match = pattern.fullmatch(path.name)
        if match and path == archive_path(root, product, match.group("domain"), match.group("stamp")):
            found.append({"domain": match.group("domain"), "time": match.group("stamp")})
    return found


def _pixel_lon_lat(z: int, x: int, y: int, size: int) -> tuple[np.ndarray, np.ndarray]:
    if not 0 <= z <= 22 or not 0 <= x < 2**z or not 0 <= y < 2**z:
        raise NetCDFTileError("invalid WebMercatorQuad XYZ tile coordinate")
    pixels = np.arange(size, dtype=np.float64) + 0.5
    lon = ((x + pixels / size) / (2**z)) * 360.0 - 180.0
    mercator = math.pi * (1.0 - 2.0 * (y + pixels / size) / (2**z))
    lat = np.degrees(np.arctan(np.sinh(mercator)))
    return lon, lat


def _nearest(axis: np.ndarray, values: np.ndarray) -> np.ndarray:
    positions = np.searchsorted(axis, values)
    upper = np.clip(positions, 0, axis.size - 1)
    lower = np.clip(positions - 1, 0, axis.size - 1)
    return np.where(np.abs(values - axis[lower]) <= np.abs(axis[upper] - values), lower, upper)


def netcdf_tile(path: Path, variable: str, z: int, x: int, y: int, *, tile_size: int = 256,
                compression: str = "zlib") -> NetCDFTile:
    """Sample one configured CF-style rectilinear variable into a numeric DNT1 tile."""
    if not 8 <= tile_size <= 1024:
        raise NetCDFTileError("tile size must be between 8 and 1024")
    if compression not in {"none", "zlib"}:
        raise NetCDFTileError("compression must be none or zlib")
    try:
        import xarray as xr
    except ImportError as exc:  # pragma: no cover - exercised by deployment packaging
        raise RuntimeError("xarray and a NetCDF backend are required") from exc
    try:
        with xr.open_dataset(path, decode_cf=True) as dataset:
            if variable not in dataset.data_vars:
                raise NetCDFTileError(f"variable {variable!r} is not present in the source")
            da = dataset[variable]
            if "time" in da.dims:
                if da.sizes["time"] != 1:
                    raise NetCDFTileError("source variable must contain exactly one time value")
                da = da.isel(time=0)
            extra = [name for name in da.dims if name not in {"latitude", "longitude"}]
            if extra:
                raise NetCDFTileError("source variable has unsupported dimensions: " + ", ".join(extra))
            if not {"latitude", "longitude"}.issubset(da.dims):
                raise NetCDFTileError("source variable must use latitude and longitude dimensions")
            lat = np.asarray(dataset.coords["latitude"].values, dtype=np.float64)
            lon = np.asarray(dataset.coords["longitude"].values, dtype=np.float64)
            if lat.ndim != 1 or lon.ndim != 1 or not lat.size or not lon.size:
                raise NetCDFTileError("latitude and longitude must be non-empty one-dimensional coordinates")
            if not np.all(np.isfinite(lat)) or not np.all(np.isfinite(lon)):
                raise NetCDFTileError("latitude and longitude coordinates must be finite")
            lon = ((lon + 180.0) % 360.0) - 180.0
            lat_order, lon_order = np.argsort(lat), np.argsort(lon)
            lat, lon = lat[lat_order], lon[lon_order]
            values = np.asarray(da.transpose("latitude", "longitude").values, dtype=np.float64)
            values = values[lat_order, :][:, lon_order]
            source_shape = values.shape
            source_fill = da.attrs.get("_FillValue", da.attrs.get("missing_value"))
            unit = str(da.attrs.get("units") or "").strip() or None
    except NetCDFTileError:
        raise
    except (OSError, ValueError, KeyError) as exc:
        raise NetCDFTileError(f"cannot read NetCDF source: {exc}") from exc

    pixel_lon, pixel_lat = _pixel_lon_lat(z, x, y, tile_size)
    sampled = values[np.ix_(_nearest(lat, pixel_lat), _nearest(lon, pixel_lon))]
    inside = ((pixel_lat[:, None] >= lat[0]) & (pixel_lat[:, None] <= lat[-1]) &
              (pixel_lon[None, :] >= lon[0]) & (pixel_lon[None, :] <= lon[-1]))
    valid = inside & np.isfinite(sampled)
    if source_fill is not None:
        try:
            valid &= sampled != float(source_fill)
        except (TypeError, ValueError):
            pass
    output = np.where(valid, sampled, DEFAULT_NODATA).astype(np.float32)
    body = encode_numeric_tile(output.ravel().tolist(), output.shape, dtype="float32", compression=compression,
                               nodata=DEFAULT_NODATA, scale=1.0, offset=0.0, unit=unit)
    return NetCDFTile(body, path, variable, unit, source_shape)
