from __future__ import annotations

import asyncio
import hashlib
import io
import json
import math
import os
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from PIL import Image
from datatiles.store import DataTiles, DataTilesError
from .netcdf import (OUTPUT_CRS, RESAMPLING, SOURCE_CRS, NetCDFTileError, archive_frames,
                     archive_path, load_products, netcdf_tile)

DATA_DIR = Path(os.environ.get("DATATILES_DATA_DIR", "/data"))
LAYERS_FILE = Path(os.environ.get("DATATILES_LAYERS", "/config/layers.json"))
CACHE_DIR = Path(os.environ.get("DATATILES_CACHE_DIR", "/cache"))
NETCDF_ROOT = Path(os.environ.get("DATATILES_NETCDF_ROOT", "/netcdf"))
NETCDF_PRODUCTS_FILE = Path(os.environ.get("DATATILES_NETCDF_PRODUCTS", "/config/netcdf-products.json"))
NETCDF_TILE_SIZE = int(os.environ.get("DATATILES_NETCDF_TILE_SIZE", "256"))
PUBLIC_BASE = os.environ.get("DATATILES_PUBLIC_BASE", "").rstrip("/")
RENDER_THREADS = max(1, int(os.environ.get("DATATILES_RENDER_THREADS", str(min(8, (os.cpu_count() or 2) * 2)))))
MAX_INFLIGHT_RENDERS = max(RENDER_THREADS, int(os.environ.get("DATATILES_MAX_INFLIGHT_RENDERS", str(RENDER_THREADS * 2))))
MAX_ELEMENTS = 16_777_216
MAX_HEADER_BYTES = 1_048_576

render_executor = ThreadPoolExecutor(max_workers=RENDER_THREADS, thread_name_prefix="datatiles-render")
render_slots = asyncio.Semaphore(MAX_INFLIGHT_RENDERS)
_lock_guard = threading.Lock()
_cache_locks: dict[str, threading.Lock] = {}
_metrics_lock = threading.Lock()
_metrics = {"requests": 0, "renders": 0, "cache_hits": 0, "cache_misses": 0, "rejections": 0,
            "render_seconds": 0.0, "inflight": 0}

app = FastAPI(title="DataTiles Online Reference Server", version="1.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x for x in os.environ.get("DATATILES_CORS_ORIGINS", "*").split(",")],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def count_requests(request: Request, call_next):
    metric("requests")
    return await call_next(request)


def load_layers() -> dict[str, Any]:
    if not LAYERS_FILE.exists():
        return {}
    value = json.loads(LAYERS_FILE.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("layers configuration must be a JSON object")
    return value


def load_netcdf_products() -> dict[str, tuple[str, ...]]:
    return load_products(NETCDF_PRODUCTS_FILE)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def portrayal_digest(portrayal: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(portrayal).encode("utf-8")).hexdigest()


def metric(name: str, amount: float = 1) -> None:
    with _metrics_lock:
        _metrics[name] += amount


def dataset_path(dataset: str) -> Path:
    safe = Path(dataset).name
    for suffix in (".datatiles", ".mbtiles", ".sqlite"):
        p = DATA_DIR / (safe if safe.endswith(suffix) else safe + suffix)
        if p.is_file():
            return p
    raise HTTPException(404, f"dataset {dataset!r} not found")


def request_dimensions(request: Request, fixed: dict[str, Any] | None = None) -> dict[str, Any]:
    reserved = {"format", "representation", "style"}
    result = dict(fixed or {})
    for k, v in request.query_params.multi_items():
        if k not in reserved:
            result[k] = v
    return result


def layer_coordinates(cfg: dict[str, Any], request: Request) -> dict[str, Any]:
    source = cfg.get("source", {})
    fixed = dict(cfg.get("fixed_dimensions", {}))
    if isinstance(source, dict):
        fixed.update({k: v for k, v in source.items() if k not in {"dataset", "variables"}})
    # Backward-compatible compact configurations used `dimensions` for fixed values.
    for key, value in cfg.get("dimensions", {}).items():
        if not isinstance(value, dict):
            fixed[key] = value
    supplied = request_dimensions(request)
    exposed = {k for k, v in cfg.get("dimensions", {}).items() if isinstance(v, dict) and v.get("exposed", True)}
    unknown = set(supplied) - exposed if exposed else set()
    if unknown:
        raise HTTPException(400, "dimension is not exposed: " + ", ".join(sorted(unknown)))
    fixed.update(supplied)
    return fixed


def content_media(store: DataTiles, coordinates: dict[str, Any]) -> str:
    sid = store._coordinate_set(coordinates, create=False)
    if sid is None:
        return "application/octet-stream"
    return store.content_profile(sid)["media_type"]


def _cache_lock(key: str) -> threading.Lock:
    # Per-process request coalescing prevents a burst of identical cache misses
    # from rendering the same tile concurrently. Cross-process duplication is
    # harmless because cache writes are atomic.
    with _lock_guard:
        return _cache_locks.setdefault(key, threading.Lock())


def _atomic_write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_bytes(body)
    os.replace(tmp, path)


@app.on_event("shutdown")
def shutdown_executor() -> None:
    render_executor.shutdown(wait=True, cancel_futures=True)


@app.get("/")
def landing(request: Request):
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse((Path(__file__).with_name("netcdf-preview.html")).read_text(encoding="utf-8"))
    return {
        "title": "DataTiles Online Reference Server",
        "version": "1.2.0",
        "render_threads_per_worker": RENDER_THREADS,
        "max_inflight_renders_per_worker": MAX_INFLIGHT_RENDERS,
        "links": [{"rel": "layers", "href": "/maps"}, {"rel": "datasets", "href": "/api/datasets"},
                  {"rel": "netcdf", "href": "/api/netcdf"}, {"rel": "preview", "href": "/", "type": "text/html"}],
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    try:
        load_layers()
        load_netcdf_products()
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(503, f"layer configuration unavailable: {exc}") from exc
    return {"status": "ready"}


@app.get("/metrics")
def metrics():
    with _metrics_lock:
        values = dict(_metrics)
    lines = [f"datatiles_{key} {value}" for key, value in sorted(values.items())]
    lines.append(f"datatiles_worker_info{{pid=\"{os.getpid()}\"}} 1")
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@app.get("/api/datasets")
def datasets():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ids = sorted({p.stem for p in DATA_DIR.iterdir() if p.suffix in {".datatiles", ".mbtiles", ".sqlite"}})
    return {"datasets": ids}


@app.get("/api/netcdf")
def netcdf_products():
    products = load_netcdf_products()
    return {"products": [{"id": name, "variables": list(variables),
                           "frames": archive_frames(NETCDF_ROOT, name)}
                          for name, variables in products.items()]}


@app.get("/api/netcdf/{product}/{domain}/{stamp}/tiles/{z}/{x}/{y}")
def netcdf_scientific_tile(product: str, domain: str, stamp: str, z: int, x: int, y: int,
                           request: Request, variable: str, compression: str = "zlib"):
    try:
        products = load_netcdf_products()
        if product not in products:
            raise HTTPException(404, f"NetCDF product {product!r} is not configured")
        if variable not in products[product]:
            raise HTTPException(404, f"variable {variable!r} is not configured for product {product!r}")
        source = archive_path(NETCDF_ROOT, product, domain, stamp)
        if not source.is_file():
            raise HTTPException(404, "NetCDF frame not found")
        tile = netcdf_tile(source, variable, z, x, y, tile_size=NETCDF_TILE_SIZE, compression=compression)
    except NetCDFTileError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    etag = '"' + hashlib.sha256(tile.body).hexdigest() + '"'
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=60",
        "Access-Control-Expose-Headers": "ETag, DataTiles-Source-CRS, DataTiles-Output-CRS, DataTiles-Algorithm",
        "DataTiles-Source-CRS": SOURCE_CRS,
        "DataTiles-Output-CRS": OUTPUT_CRS,
        "DataTiles-Algorithm": RESAMPLING,
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(tile.body, media_type="application/vnd.datatiles.dnt1", headers=headers)


@app.get("/api/datasets/{dataset}/tiles/{z}/{x}/{y}")
def scientific_tile(dataset: str, z: int, x: int, y: int, request: Request):
    coords = request_dimensions(request)
    try:
        with DataTiles(dataset_path(dataset), read_only=True) as store:
            blob = store.get(z, x, y, coords, xyz=True)
            if blob is None:
                raise HTTPException(404, "tile not found")
            media = content_media(store, coords)
    except DataTilesError as exc:
        raise HTTPException(400, str(exc)) from exc
    headers = {"Cache-Control": "public, max-age=300", "Access-Control-Expose-Headers": "ETag"}
    headers["ETag"] = '"' + hashlib.sha256(blob).hexdigest() + '"'
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    return Response(blob, media_type=media if "/" in media else "application/octet-stream", headers=headers)


@app.get("/maps")
def maps():
    return {"layers": [{"id": k, **{q: v for q, v in cfg.items() if q != "portrayal"}} for k, cfg in load_layers().items()]}


@app.get("/maps/{layer}")
def map_detail(layer: str):
    cfg = load_layers().get(layer)
    if not cfg:
        raise HTTPException(404, "layer not found")
    return {"id": layer, **cfg, "portrayalDigest": portrayal_digest(cfg.get("portrayal", {}))}


@app.get("/maps/{layer}/dimensions")
def dimensions(layer: str):
    cfg = load_layers().get(layer)
    if not cfg:
        raise HTTPException(404, "layer not found")
    return {"dimensions": cfg.get("dimensions", {}), "fixed": cfg.get("fixed_dimensions", {})}


@app.get("/maps/{layer}/times")
def times(layer: str):
    cfg = load_layers().get(layer)
    if not cfg:
        raise HTTPException(404, "layer not found")
    definition = cfg.get("dimensions", {}).get("valid_time", {})
    return {"times": definition.get("values", []) if isinstance(definition, dict) else []}


@app.get("/maps/{layer}/legend.json")
def legend(layer: str):
    cfg = load_layers().get(layer)
    if not cfg:
        raise HTTPException(404, "layer not found")
    portrayal = cfg.get("portrayal", {})
    return {"layer": layer, "unit": portrayal.get("unit"), "palette": portrayal.get("palette", []),
            "portrayalDigest": portrayal_digest(portrayal)}


@app.get("/maps/{layer}/legend.png")
def legend_png(layer: str):
    cfg = load_layers().get(layer)
    if not cfg:
        raise HTTPException(404, "layer not found")
    stops = cfg.get("portrayal", {}).get("palette", [])
    if not stops:
        raise HTTPException(422, "portrayal palette is required")
    width, height = 256, 24
    positions = np.linspace(float(stops[0][0]), float(stops[-1][0]), width)
    colors = np.vstack([_rgba(color) for _, color in stops])
    stop_values = np.asarray([float(value) for value, _ in stops])
    pixels = np.stack([np.interp(positions, stop_values, colors[:, channel]) for channel in range(4)], axis=1)
    pixels = np.repeat(np.rint(pixels)[None, :, :], height, axis=0).astype(np.uint8)
    out = io.BytesIO()
    Image.fromarray(pixels, mode="RGBA").save(out, "PNG", compress_level=6)
    return Response(out.getvalue(), media_type="image/png")


@app.get("/maps/{layer}/tilejson.json")
def tilejson(layer: str, request: Request):
    cfg = load_layers().get(layer)
    if not cfg:
        raise HTTPException(404, "layer not found")
    base = PUBLIC_BASE or str(request.base_url).rstrip("/")
    fmt = cfg.get("formats", ["webp"])[0]
    result = {
        "tilejson": "3.0.0",
        "name": cfg.get("title", layer),
        "scheme": "xyz",
        "minzoom": cfg.get("minzoom", 0),
        "maxzoom": cfg.get("maxzoom", 18),
        "tiles": [f"{base}/maps/{layer}/{{z}}/{{x}}/{{y}}.{fmt}"],
        "datatiles:representations": {
            "server": {"mediaTypes": [f"image/{x}" for x in cfg.get("formats", [fmt])]},
            "client": {
                "mediaTypes": ["application/vnd.datatiles.dnt1"],
                "url": f"{base}/api/datasets/{cfg['dataset']}/tiles/{{z}}/{{x}}/{{y}}",
            },
        },
        "datatiles:dimensions": cfg.get("dimensions", {}),
        "datatiles:portrayal": cfg.get("portrayal", {}),
        "datatiles:catalog": cfg.get("catalog", {}),
    }
    if cfg.get("bounds"):
        result["bounds"] = cfg["bounds"]
    return result


@app.get("/maps/{layer}/portrayal.json")
def portrayal(layer: str):
    cfg = load_layers().get(layer)
    if not cfg:
        raise HTTPException(404, "layer not found")
    return cfg.get("portrayal", {})


@app.get("/maps/{layer}/{z}/{x}/{y}.{fmt}")
async def rendered_tile(layer: str, z: int, x: int, y: int, fmt: str, request: Request):
    cfg = load_layers().get(layer)
    if not cfg:
        raise HTTPException(404, "layer not found")
    fmt = fmt.lower()
    if fmt not in cfg.get("formats", ["png", "webp"]):
        raise HTTPException(406, "format not supported")

    coords = layer_coordinates(cfg, request)
    portrayal_cfg = cfg.get("portrayal", {})
    key_obj = {
        "layer": layer,
        "dataset": cfg["dataset"],
        "coords": coords,
        "z": z,
        "x": x,
        "y": y,
        "fmt": fmt,
        "portrayal_digest": portrayal_digest(portrayal_cfg),
        "renderer": "datatiles-reference-1",
        "dataset_release": cfg.get("dataset_release", cfg.get("release", "mutable")),
        "tile_size": cfg.get("tileSize", 256),
        "resampling": cfg.get("resampling", "nearest"),
    }
    key = hashlib.sha256(canonical_json(key_obj).encode()).hexdigest()
    cache = CACHE_DIR / key[:2] / f"{key}.{fmt}"
    immutable = key_obj["dataset_release"] not in {"mutable", "latest", None}
    headers = {"ETag": f'"{key}"', "Cache-Control": ("public, max-age=31536000, immutable" if immutable else "public, max-age=60")}
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)

    if cache.exists():
        metric("cache_hits")
        return Response(cache.read_bytes(), media_type=f"image/{fmt}", headers=headers)

    metric("cache_misses")
    try:
        await asyncio.wait_for(render_slots.acquire(), timeout=0.05)
    except TimeoutError as exc:
        metric("rejections")
        raise HTTPException(503, "render capacity exhausted", headers={"Retry-After": "1"}) from exc
    metric("inflight", 1)
    started = time.monotonic()
    try:
        loop = asyncio.get_running_loop()
        body = await loop.run_in_executor(
            render_executor,
            _load_render_and_cache,
            cfg,
            coords,
            z,
            x,
            y,
            fmt,
            key,
            cache,
        )
    finally:
        metric("render_seconds", time.monotonic() - started)
        metric("inflight", -1)
        render_slots.release()
    return Response(body, media_type=f"image/{fmt}", headers=headers)


def _load_render_and_cache(
    cfg: dict[str, Any],
    coords: dict[str, Any],
    z: int,
    x: int,
    y: int,
    fmt: str,
    key: str,
    cache: Path,
) -> bytes:
    lock = _cache_lock(key)
    with lock:
        if cache.exists():
            return cache.read_bytes()
        try:
            with DataTiles(dataset_path(cfg["dataset"]), read_only=True) as store:
                blob = store.get(z, x, y, coords, xyz=True)
                if blob is None:
                    raise HTTPException(404, "tile not found")
        except DataTilesError as exc:
            raise HTTPException(400, str(exc)) from exc
        decoded = decode_dnt1(blob)
        body = render_scalar(decoded, cfg.get("portrayal", {}), fmt)
        _atomic_write(cache, body)
        metric("renders")
        return body


def decode_dnt1(blob: bytes) -> dict[str, Any]:
    if len(blob) < 8 or blob[:4] != b"DNT1":
        raise HTTPException(415, "server portrayal currently requires DNT1")
    hlen = int.from_bytes(blob[4:8], "big")
    if hlen > MAX_HEADER_BYTES or 8 + hlen > len(blob):
        raise HTTPException(422, "invalid DNT1 header")
    try:
        header = json.loads(blob[8 : 8 + hlen])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, "invalid DNT1 header JSON") from exc
    required = {"dtype", "shape", "byteorder", "compression"}
    allowed = required | {"nodata", "scale", "offset", "unit"}
    if not isinstance(header, dict) or not required <= set(header) or set(header) - allowed:
        raise HTTPException(422, "invalid DNT1 header fields")
    shape = header.get("shape")
    if not isinstance(shape, list) or not 1 <= len(shape) <= 8 or any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in shape):
        raise HTTPException(422, "invalid DNT1 shape")
    if header.get("byteorder") not in {"little", "big"}:
        raise HTTPException(422, "invalid DNT1 byte order")
    payload = blob[8 + hlen :]
    if header.get("compression") == "zlib":
        inflater = zlib.decompressobj()
        expected_count = math.prod(shape)
        if expected_count > MAX_ELEMENTS:
            raise HTTPException(413, "DNT1 element limit exceeded")
        # The precise byte bound is checked after dtype resolution below; this
        # cap prevents a malformed compressed stream from expanding without bound.
        try:
            payload = inflater.decompress(payload, expected_count * 8 + 1)
        except zlib.error as exc:
            raise HTTPException(422, "invalid DNT1 compressed payload") from exc
        if not inflater.eof or inflater.unused_data:
            raise HTTPException(422, "invalid DNT1 compressed payload")
    elif header.get("compression") != "none":
        raise HTTPException(415, "unsupported DNT1 compression")

    dtype_names = {
        "int8": "i1",
        "uint8": "u1",
        "int16": "i2",
        "uint16": "u2",
        "int32": "i4",
        "uint32": "u4",
        "int64": "i8",
        "uint64": "u8",
        "float32": "f4",
        "float64": "f8",
    }
    dtype_name = dtype_names.get(header.get("dtype"))
    if not dtype_name:
        raise HTTPException(415, "unsupported DNT1 dtype")
    endian = "<" if header.get("byteorder") == "little" else ">"
    dtype = np.dtype(endian + dtype_name)
    count = math.prod(shape)
    if count > MAX_ELEMENTS:
        raise HTTPException(413, "DNT1 element limit exceeded")
    if len(payload) != count * dtype.itemsize:
        raise HTTPException(422, "DNT1 payload size mismatch")
    values = np.frombuffer(payload, dtype=dtype, count=count)
    return {"header": header, "values": values}


def _rgba(color: str) -> np.ndarray:
    h = color.lstrip("#")
    if len(h) == 6:
        return np.array([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255], dtype=np.float64)
    if len(h) == 8:
        return np.array([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)], dtype=np.float64)
    raise HTTPException(422, f"invalid palette color {color}")


def render_scalar(decoded: dict[str, Any], portrayal: dict[str, Any], fmt: str) -> bytes:
    h = decoded["header"]
    shape = h["shape"]
    if len(shape) < 2:
        raise HTTPException(422, "scalar portrayal needs a 2-D tile")
    height, width = shape[-2], shape[-1]
    stops = portrayal.get("palette")
    if not stops:
        raise HTTPException(422, "portrayal palette is required")

    ordered = sorted(stops, key=lambda x: float(x[0]))
    stop_values = np.asarray([float(s[0]) for s in ordered], dtype=np.float64)
    stop_colors = np.vstack([_rgba(s[1]) for s in ordered])

    raw = decoded["values"].astype(np.float64, copy=False)
    scale = float(h.get("scale", 1))
    offset = float(h.get("offset", 0))
    values = raw * scale + offset
    nodata = h.get("nodata")
    invalid = ~np.isfinite(values)
    if nodata is not None:
        invalid |= raw == float(nodata)

    channels = [np.interp(values, stop_values, stop_colors[:, i]) for i in range(4)]
    rgba = np.stack(channels, axis=1)
    rgba[invalid] = (0, 0, 0, 0)
    pixels = np.clip(np.rint(rgba), 0, 255).astype(np.uint8).reshape(height, width, 4)

    image = Image.fromarray(pixels, mode="RGBA")
    out = io.BytesIO()
    if fmt == "webp":
        image.save(out, "WEBP", lossless=True, method=4)
    elif fmt == "png":
        image.save(out, "PNG", compress_level=6)
    else:
        raise HTTPException(406, "unsupported image format")
    return out.getvalue()
