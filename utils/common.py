"""Shared implementation for the DataTiles NetCDF, GRIB and Zarr import utilities.

The repository core remains dependency-free.  These utilities intentionally use
optional scientific-I/O dependencies and write only standard DataTiles DNT1
numeric raster matrices.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import tempfile
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

WEBMERCATOR_LAT_LIMIT = 85.0511287798066
DEFAULT_NODATA = -3.4028234663852886e38


class ConversionError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedSource:
    identifier: str
    local_path: Path | None
    uri: str
    checksum_algorithm: str
    checksum: str
    temporary: bool

    @property
    def sha256(self) -> str:
        """Backward-compatible accessor for single-file sources only."""
        if self.checksum_algorithm != "sha256":
            raise ConversionError(f"source checksum is {self.checksum_algorithm}, not sha256")
        return self.checksum


@contextmanager
def resolve_source(source: str, *, timeout: float = 60.0) -> Iterator[ResolvedSource]:
    """Resolve a local path or HTTP(S) URL to a seekable local source.

    URLs are downloaded to a temporary file while hashing the exact bytes.  A
    local source is hashed in place.  The original identifier remains the
    provenance URI so the resulting DataTiles file does not lose source identity.
    """
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in {"http", "https"}:
        suffix = Path(parsed.path).suffix
        fd, name = tempfile.mkstemp(prefix="datatiles-source-", suffix=suffix)
        os.close(fd)
        path = Path(name)
        digest = hashlib.sha256()
        try:
            request = urllib.request.Request(source, headers={"User-Agent": "DataTiles-utils/1"})
            with urllib.request.urlopen(request, timeout=timeout) as response, path.open("wb") as output:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    digest.update(block)
                    output.write(block)
            yield ResolvedSource(source, path, source, "sha256", digest.hexdigest(), True)
        finally:
            path.unlink(missing_ok=True)
        return

    if parsed.scheme not in {"", "file"}:
        raise ConversionError("source must be a local path, file: URI, or HTTP(S) URL")
    path = Path(urllib.request.url2pathname(parsed.path) if parsed.scheme == "file" else source).expanduser().resolve()
    if not path.is_file():
        raise ConversionError(f"source file does not exist: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    yield ResolvedSource(source, path, path.as_uri(), "sha256", digest.hexdigest(), False)



def _zarr_tree_digest(path: Path) -> str:
    """Hash a local Zarr directory using a canonical key+length+bytes stream.

    The algorithm is named ``zarr-tree-sha256-v1``.  It is deliberately not
    described as a SHA-256 of a file: a Zarr store is a set of named objects.
    Symlinks are rejected so the digest cannot depend on filesystem traversal
    semantics outside the declared store root.
    """
    digest = hashlib.sha256(b"DataTiles-Zarr-Tree-SHA256-v1\0")
    files = []
    for item in path.rglob("*"):
        if item.is_symlink():
            raise ConversionError(f"Zarr provenance hashing refuses symlink: {item}")
        if item.is_file():
            files.append(item)
    for item in sorted(files, key=lambda x: x.relative_to(path).as_posix()):
        rel = item.relative_to(path).as_posix().encode("utf-8")
        size = item.stat().st_size
        digest.update(rel); digest.update(b"\0")
        digest.update(str(size).encode("ascii")); digest.update(b"\0")
        with item.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        digest.update(b"\0")
    return digest.hexdigest()


@contextmanager
def resolve_zarr_source(source: str, *, source_sha256: str | None = None, provenance_uri: str | None = None) -> Iterator[ResolvedSource]:
    """Resolve a Zarr store without falsely reducing it to a single file.

    Local directory stores receive a deterministic ``zarr-tree-sha256-v1``
    digest over every key/object.  Remote stores remain remote and require an
    operator-supplied authoritative SHA-256 for the immutable store/snapshot.
    This avoids an implicit, potentially unbounded second traversal of a cloud
    store merely to manufacture a checksum.
    """
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in {"", "file"}:
        path = Path(urllib.request.url2pathname(parsed.path) if parsed.scheme == "file" else source).expanduser().resolve()
        if not path.is_dir():
            raise ConversionError(f"local Zarr source must be a directory store: {path}")
        checksum = _zarr_tree_digest(path)
        yield ResolvedSource(source, path, path.as_uri(), "zarr-tree-sha256-v1", checksum, False)
        return
    if not re.fullmatch(r"[0-9a-fA-F]{64}", source_sha256 or ""):
        raise ConversionError("remote Zarr stores require --source-sha256 with the authoritative 64-hex SHA-256 of the immutable store/snapshot")
    if (parsed.username or parsed.password or parsed.query) and not provenance_uri:
        raise ConversionError("remote Zarr source contains user-info or query parameters; provide --provenance-uri with a stable credential-free identifier so secrets are not persisted")
    identity = provenance_uri or source
    identity_parsed = urllib.parse.urlparse(identity)
    if identity_parsed.username or identity_parsed.password or identity_parsed.query:
        raise ConversionError("--provenance-uri must not contain credentials or query parameters")
    yield ResolvedSource(identity, None, identity, "sha256", str(source_sha256).lower(), False)

def require_scientific_stack():
    try:
        import numpy as np
        import xarray as xr
    except ImportError as exc:
        raise ConversionError(
            "the import utilities require the optional 'utils' dependencies; "
            "install with: python -m pip install -e '.[utils]'"
        ) from exc
    return np, xr


def require_zarr_stack():
    np, xr = require_scientific_stack()
    try:
        import zarr  # noqa: F401
        import fsspec  # noqa: F401
    except ImportError as exc:
        raise ConversionError(
            "Zarr import requires zarr and fsspec from the optional 'utils' dependencies; "
            "install with: python -m pip install -e '.[utils]'"
        ) from exc
    return np, xr


def safe_token(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_").lower()
    if not token:
        raise ConversionError(f"cannot derive a variable token from {value!r}")
    if token[0].isdigit():
        token = "v_" + token
    return token


def cf_or_source_semantics(name: str, attrs: dict[str, Any]) -> tuple[str, str, str | None, str | None]:
    standard = str(attrs.get("standard_name") or "").strip()
    unit = str(attrs.get("units") or "").strip() or None
    long_name = str(attrs.get("long_name") or "").strip() or None
    if standard:
        return standard, "CF", unit, long_name
    # Never claim a producer-local name is a CF Standard Name.
    return safe_token(name), "source", unit, long_name


def find_lat_lon(da: Any, *, lat_name: str | None = None, lon_name: str | None = None) -> tuple[str, str]:
    candidates = set(da.coords) | set(da.dims)
    if lat_name is None:
        lat_name = next((n for n in candidates if n.lower() in {"lat", "latitude", "nav_lat"}), None)
    if lon_name is None:
        lon_name = next((n for n in candidates if n.lower() in {"lon", "longitude", "nav_lon"}), None)
    if not lat_name or not lon_name or lat_name not in da.coords or lon_name not in da.coords:
        raise ConversionError(f"{da.name}: unable to identify latitude/longitude coordinates; use --lat/--lon")
    if da.coords[lat_name].ndim != 1 or da.coords[lon_name].ndim != 1:
        raise ConversionError(f"{da.name}: only rectilinear 1-D latitude/longitude grids are supported")
    if lat_name not in da.dims or lon_name not in da.dims:
        raise ConversionError(f"{da.name}: latitude and longitude must be array dimensions")
    return lat_name, lon_name


def normalized_axes(da: Any, lat_name: str, lon_name: str):
    np, _ = require_scientific_stack()
    lat = np.asarray(da.coords[lat_name].values, dtype="float64")
    lon = np.asarray(da.coords[lon_name].values, dtype="float64")
    if lat.ndim != 1 or lon.ndim != 1 or lat.size < 1 or lon.size < 1:
        raise ConversionError("latitude/longitude axes must be non-empty 1-D arrays")
    if not np.all(np.isfinite(lat)) or not np.all(np.isfinite(lon)):
        raise ConversionError("latitude/longitude coordinates must be finite")
    lon = ((lon + 180.0) % 360.0) - 180.0
    lat_order = np.argsort(lat)
    lon_order = np.argsort(lon)
    return lat[lat_order], lon[lon_order], lat_order, lon_order


def lon_to_tile_x(lon: float, z: int) -> int:
    n = 1 << z
    return min(n - 1, max(0, int(math.floor((lon + 180.0) / 360.0 * n))))


def lat_to_tile_y(lat: float, z: int) -> int:
    lat = min(WEBMERCATOR_LAT_LIMIT, max(-WEBMERCATOR_LAT_LIMIT, lat))
    rad = math.radians(lat)
    n = 1 << z
    y = (1.0 - math.asinh(math.tan(rad)) / math.pi) / 2.0 * n
    return min(n - 1, max(0, int(math.floor(y))))


def tile_ranges(bbox: tuple[float, float, float, float], z: int) -> tuple[range, range]:
    west, south, east, north = bbox
    if west > east:
        raise ConversionError("antimeridian-crossing bboxes are not yet supported; split the import into two bboxes")
    x0, x1 = lon_to_tile_x(west, z), lon_to_tile_x(east, z)
    y0, y1 = lat_to_tile_y(north, z), lat_to_tile_y(south, z)
    return range(min(x0, x1), max(x0, x1) + 1), range(min(y0, y1), max(y0, y1) + 1)


def tile_pixel_lon_lat(z: int, x: int, y: int, size: int):
    np, _ = require_scientific_stack()
    n = float(1 << z)
    px = x + (np.arange(size, dtype="float64") + 0.5) / size
    py = y + (np.arange(size, dtype="float64") + 0.5) / size
    lon = px / n * 360.0 - 180.0
    merc = math.pi * (1.0 - 2.0 * py / n)
    lat = np.degrees(np.arctan(np.sinh(merc)))
    return lon, lat


def nearest_indices(axis, values):
    np, _ = require_scientific_stack()
    if len(axis) == 1:
        return np.zeros(values.shape, dtype="int64")
    idx = np.searchsorted(axis, values, side="left")
    idx = np.clip(idx, 1, len(axis) - 1)
    left = axis[idx - 1]
    right = axis[idx]
    return idx - (values - left <= right - values)


def infer_dimension_type(value: Any) -> str:
    np, _ = require_scientific_stack()
    if np.issubdtype(np.asarray(value).dtype, np.datetime64):
        return "datetime"
    if isinstance(value, (bool, np.bool_)):
        return "boolean"
    if isinstance(value, (int, np.integer)):
        return "integer"
    if isinstance(value, (float, np.floating)):
        return "float"
    return "text"


def coordinate_value(value: Any) -> Any:
    np, _ = require_scientific_stack()
    arr = np.asarray(value)
    if np.issubdtype(arr.dtype, np.datetime64):
        # xarray/numpy time values are normalized to UTC-looking ISO strings.
        text = np.datetime_as_string(arr.astype("datetime64[us]"), unit="us")
        return str(text) + "Z" if not str(text).endswith("Z") else str(text)
    if isinstance(value, np.generic):
        value = value.item()
    return value if isinstance(value, (str, int, float, bool)) else str(value)


def ensure_dimensions(store: Any, dataset: Any, variables: list[Any], *, lat_names: set[str], lon_names: set[str]) -> None:
    existing = {row[0] for row in store.db.execute("SELECT name FROM datatiles_dimensions")}
    if "variable" not in existing:
        store.add_dimension("variable", "text", description="Semantic variable token")
        existing.add("variable")
    for da in variables:
        for dim in da.dims:
            if dim in lat_names or dim in lon_names or dim in existing:
                continue
            coord = dataset.coords.get(dim)
            sample = coord.values[0] if coord is not None and coord.size else "0"
            axis = str((coord.attrs.get("axis") if coord is not None else "") or "").strip().upper() or None
            unit = str((coord.attrs.get("units") if coord is not None else "") or "").strip() or None
            store.add_dimension(dim, infer_dimension_type(sample), axis=axis, unit=unit,
                                description=f"Imported source dimension {dim}", required=False)
            existing.add(dim)


def iter_non_spatial_slices(da: Any, lat_name: str, lon_name: str) -> Iterable[tuple[dict[str, Any], Any]]:
    np, _ = require_scientific_stack()
    dims = [d for d in da.dims if d not in {lat_name, lon_name}]
    if not dims:
        yield {}, da
        return
    shape = [da.sizes[d] for d in dims]
    for index in np.ndindex(*shape):
        selectors = dict(zip(dims, index))
        coords = {d: coordinate_value(da.coords[d].values[i]) if d in da.coords else int(i)
                  for d, i in selectors.items()}
        yield coords, da.isel(selectors)


def register_variable(store: Any, da: Any, *, source_kind: str) -> str:
    token = safe_token(str(da.name))
    standard, vocabulary, unit, long_name = cf_or_source_semantics(str(da.name), dict(da.attrs))
    if not store.db.execute("SELECT 1 FROM datatiles_variables WHERE name=?", (token,)).fetchone():
        store.add_variable(token, standard, vocabulary=vocabulary,
                           vocabulary_version=str(da.attrs.get("standard_name_vocabulary_version") or "") or None,
                           canonical_unit=unit, long_name=long_name,
                           description=f"Imported from {source_kind} variable {da.name}")
    # Keep the native variable identifier as a crosswalk.
    try:
        store.add_variable_identifier(token, f"{source_kind}-variable", str(da.name))
    except Exception:
        pass
    if source_kind == "GRIB2":
        attrs = da.attrs
        discipline = attrs.get("GRIB_discipline")
        category = attrs.get("GRIB_parameterCategory")
        number = attrs.get("GRIB_parameterNumber")
        if discipline is not None and category is not None and number is not None:
            identifier = f"{discipline}.{category}.{number}"
            try:
                store.add_variable_identifier(token, "WMO-GRIB2", identifier)
            except Exception:
                pass
        short_name = attrs.get("GRIB_shortName")
        if short_name:
            try:
                store.add_variable_identifier(token, "GRIB-shortName", str(short_name))
            except Exception:
                pass
    return token


def source_bbox(lat_axis, lon_axis, override: tuple[float, float, float, float] | None):
    native = (float(lon_axis.min()), float(lat_axis.min()), float(lon_axis.max()), float(lat_axis.max()))
    if override is None:
        return native
    west, south, east, north = override
    if west > east or south > north:
        raise ConversionError("invalid --bbox ordering")
    clipped = (max(west, native[0]), max(south, native[1]), min(east, native[2]), min(north, native[3]))
    if clipped[0] > clipped[2] or clipped[1] > clipped[3]:
        raise ConversionError("--bbox does not intersect the source grid")
    return clipped


def convert_dataset(dataset: Any, target: str | Path, *, source: ResolvedSource, source_kind: str,
                    variables: list[str] | None, zoom: int, tile_size: int,
                    bbox: tuple[float, float, float, float] | None, max_tiles: int,
                    source_license: str, source_license_uri: str, source_attribution: str,
                    dataset_license: str, dataset_license_uri: str, dataset_attribution: str | None,
                    access_rights: str = "open", provenance_parameters: dict[str, Any] | None = None) -> dict[str, int]:
    np, _ = require_scientific_stack()
    try:
        from datatiles.numeric import encode_numeric_tile
        from datatiles.store import DataTiles
    except ImportError as exc:
        raise ConversionError("install DataTiles before running this utility") from exc

    if not 0 <= zoom <= 22:
        raise ConversionError("--zoom must be between 0 and 22 for these import utilities")
    if tile_size < 8 or tile_size > 1024:
        raise ConversionError("--tile-size must be between 8 and 1024")

    names = variables or [name for name, da in dataset.data_vars.items() if da.ndim >= 2]
    if not names:
        raise ConversionError("no data variables selected")
    arrays = []
    lat_names: set[str] = set()
    lon_names: set[str] = set()
    spatial: dict[str, tuple[str, str]] = {}
    for name in names:
        if name not in dataset.data_vars:
            raise ConversionError(f"variable not found: {name}")
        da = dataset[name]
        lat_name, lon_name = find_lat_lon(da)
        arrays.append(da)
        spatial[name] = (lat_name, lon_name)
        lat_names.add(lat_name); lon_names.add(lon_name)

    target = Path(target)
    if target.exists():
        raise ConversionError(f"target already exists: {target}")

    stats = {"variables": 0, "slices": 0, "tiles": 0}
    with DataTiles(target, create=True, name=target.stem, tile_format="application/vnd.datatiles.numeric") as store:
        ensure_dimensions(store, dataset, arrays, lat_names=lat_names, lon_names=lon_names)
        store.add_crs("horizontal", authority="EPSG", code="3857", uri="http://www.opengis.net/def/crs/EPSG/0/3857")
        store.set_metadata("datatiles:source_identifier", source.identifier)
        store.set_metadata("datatiles:source_checksum_algorithm", source.checksum_algorithm)
        store.set_metadata("datatiles:source_checksum", source.checksum)
        if source.checksum_algorithm == "sha256":
            store.set_metadata("datatiles:source_sha256", source.checksum)
        entity_id = "source:" + source.checksum_algorithm + ":" + source.checksum
        store.add_provenance_entity(entity_id, "dataset", f"{source_kind} source", uri=source.uri,
                                    checksum_algorithm=source.checksum_algorithm, checksum=source.checksum,
                                    attributes={"source_kind": source_kind, "source_identifier": source.identifier})
        # Rights are never inferred from transport accessibility or file metadata.
        # The operator must provide an explicit source licence/terms record and a
        # separately concluded licence for the generated DataTiles object.
        store.add_rights("source", source_license, license_uri=source_license_uri,
                         attribution_text=source_attribution, access_rights=access_rights,
                         source_entity_id=entity_id, applies_to=source.identifier)
        store.add_rights("dataset", dataset_license, license_uri=dataset_license_uri,
                         attribution_text=dataset_attribution, access_rights=access_rights)
        store.add_rights("metadata", "CC0-1.0", license_uri="https://creativecommons.org/publicdomain/zero/1.0/",
                         attribution_text="DataTiles machine-readable metadata; source attribution remains binding where applicable")
        activity_id = "activity:import"
        store.add_provenance_activity(activity_id, "conversion", f"{source_kind} to DataTiles",
                                      software="DataTiles utils",
                                      parameters={"zoom": zoom, "tile_size": tile_size, "bbox": bbox, **(provenance_parameters or {})})
        store.add_provenance_relation(activity_id, "used", entity_id)

        for da in arrays:
            token = register_variable(store, da, source_kind=source_kind)
            lat_name, lon_name = spatial[str(da.name)]
            lat_axis, lon_axis, lat_order, lon_order = normalized_axes(da, lat_name, lon_name)
            actual_bbox = source_bbox(lat_axis, lon_axis, bbox)
            xs, ys = tile_ranges(actual_bbox, zoom)
            planned = len(xs) * len(ys)
            if stats["tiles"] + planned > max_tiles:
                raise ConversionError(f"conversion would exceed --max-tiles={max_tiles}; select variables/bbox or change zoom")
            unit = str(da.attrs.get("units") or "").strip() or None
            fill = da.attrs.get("_FillValue", da.attrs.get("missing_value", DEFAULT_NODATA))
            try:
                nodata = float(fill)
                if not math.isfinite(nodata):
                    nodata = DEFAULT_NODATA
            except (TypeError, ValueError):
                nodata = DEFAULT_NODATA

            for extra_coords, slice_da in iter_non_spatial_slices(da, lat_name, lon_name):
                values = np.asarray(slice_da.transpose(lat_name, lon_name).values, dtype="float64")
                values = values[np.asarray(lat_order), :][:, np.asarray(lon_order)]
                coordinates = {"variable": token, **extra_coords}
                stats["slices"] += 1
                for x in xs:
                    for y in ys:
                        pixel_lon, pixel_lat = tile_pixel_lon_lat(zoom, x, y, tile_size)
                        iy = nearest_indices(lat_axis, pixel_lat)
                        ix = nearest_indices(lon_axis, pixel_lon)
                        tile = values[np.ix_(iy, ix)]
                        west, south, east, north = actual_bbox
                        inside = ((pixel_lat[:, None] >= south) & (pixel_lat[:, None] <= north) &
                                  (pixel_lon[None, :] >= west) & (pixel_lon[None, :] <= east))
                        tile = np.where(inside & np.isfinite(tile), tile, nodata).astype("float32", copy=False)
                        blob = encode_numeric_tile(tile.ravel().tolist(), tile.shape, dtype="float32",
                                                   compression="zlib", nodata=nodata, unit=unit)
                        store.put(zoom, x, y, blob, coordinates, xyz=True, data_type="raster",
                                  media_type="application/vnd.datatiles.numeric", encoding="DNT1",
                                  schema={"resampling": "nearest", "grid": "WebMercatorQuad",
                                          "tile_size": tile_size, "source_kind": source_kind})
                        store.link_tile_provenance(zoom, x, y, coordinates, entity_id, xyz=True)
                        stats["tiles"] += 1
            stats["variables"] += 1
    return stats
