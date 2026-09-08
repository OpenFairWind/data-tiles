#!/usr/bin/env python3
"""Render a documented wind-vector view from stored U10M/V10M DNT1 arrays."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def xyz_at(lon: float, lat: float, zoom: int) -> tuple[int, int, float, float]:
    scale = 2 ** zoom
    gx = (lon + 180.0) / 360.0 * scale
    gy = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * scale
    return int(gx), int(gy), (gx % 1.0) * 256.0, (gy % 1.0) * 256.0


def physical(tile, np):
    values = np.asarray(tile.values, dtype="float64").reshape(tile.shape)
    valid = np.isfinite(values)
    if tile.nodata is not None:
        valid &= values != tile.nodata
    return np.where(valid, values * tile.scale + tile.offset, np.nan)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--zoom", type=int, required=True)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--product", default="wrf5")
    parser.add_argument("--domain", default="d03")
    parser.add_argument("--valid-time", required=True)
    args = parser.parse_args()

    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from datatiles import DataTiles, decode_numeric_tile

    tx, ty, px, py = xyz_at(args.lon, args.lat, args.zoom)
    coordinates = {
        name: {"variable": f"{args.product}_{name}", "product": args.product,
               "domain": args.domain, "valid_time": args.valid_time}
        for name in ("u10m", "v10m")
    }
    fields = {}
    units = set()
    with DataTiles(args.input, read_only=True) as store:
        for name in ("u10m", "v10m"):
            rows = []
            for y in range(ty - 1, ty + 2):
                row = []
                for x in range(tx - 1, tx + 2):
                    blob = store.get(args.zoom, x, y, coordinates[name], xyz=True)
                    if blob is None:
                        raise SystemExit(f"missing z{args.zoom}/{x}/{y} for {name}")
                    tile = decode_numeric_tile(blob)
                    if tile.shape != (256, 256):
                        raise SystemExit(f"unsupported tile shape {tile.shape}")
                    units.add(tile.unit)
                    row.append(physical(tile, np))
                rows.append(np.concatenate(row, axis=1))
            fields[name] = np.concatenate(rows, axis=0)
    if len(units) != 1:
        raise SystemExit("U10M and V10M units differ")

    left, top = int(256 + px - 256), int(256 + py - 256)
    u = fields["u10m"][top:top + 512, left:left + 512]
    v = fields["v10m"][top:top + 512, left:left + 512]
    speed = np.hypot(u, v)
    finite = speed[np.isfinite(speed)]
    lo, hi = (float(np.min(finite)), float(np.max(finite)))
    normalized = np.clip((speed - lo) / (hi - lo if hi > lo else 1.0), 0.0, 1.0)
    rgb = np.stack((35 + 220 * normalized, 68 + 150 * normalized,
                    130 - 80 * normalized), axis=-1)
    rgb[~np.isfinite(speed)] = (235, 235, 235)
    image = Image.fromarray(rgb.astype("uint8")).resize((768, 768), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (768, 860), "white")
    canvas.paste(image, (0, 56))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    draw.text((16, 14), f"10 m wind · {args.valid_time} · z{args.zoom} {args.domain}", fill="black", font=font)
    draw.text((16, 34), f"center {args.lat:.4f} N, {args.lon:.4f} E · speed {units.pop() or 'unit not declared'}", fill="black", font=font)
    for iy in range(40, 512, 48):
        for ix in range(40, 512, 48):
            uu, vv = u[iy, ix], v[iy, ix]
            if not (math.isfinite(uu) and math.isfinite(vv)):
                continue
            x, y = ix * 1.5, 56 + iy * 1.5
            length = 22.0
            magnitude = math.hypot(uu, vv) or 1.0
            ex, ey = x + length * uu / magnitude, y - length * vv / magnitude
            draw.line((x, y, ex, ey), fill="white", width=2)
            angle = math.atan2(-(ey - y), ex - x)
            for delta in (-2.55, 2.55):
                draw.line((ex, ey, ex + 7 * math.cos(angle + delta), ey - 7 * math.sin(angle + delta)),
                          fill="white", width=2)
    draw.ellipse((380, 432, 388, 440), outline="black", fill="white", width=1)
    draw.text((16, 828), f"range {lo:.2f}–{hi:.2f}; DNT1 scale/offset, nodata, bilinear display interpolation; arrows subsampled", fill="black", font=font)
    draw.text((16, 844), "Scientific model visualization · uncertified · not for navigation", fill="#8b0000", font=font)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, optimize=True)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(json.dumps({"output": str(args.output), "sha256": digest, "speed_min": lo,
                      "speed_max": hi, "center": [args.lat, args.lon]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
