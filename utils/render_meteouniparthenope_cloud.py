#!/usr/bin/env python3
"""Render CLDFRA_TOTAL from stored Meteo@UniParthenope DNT1 values."""
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
    coordinates = {"variable": f"{args.product}_cldfra_total", "product": args.product,
                   "domain": args.domain, "valid_time": args.valid_time}
    rows = []
    declared_unit = None
    with DataTiles(args.input, read_only=True) as store:
        for y in range(ty - 1, ty + 2):
            row = []
            for x in range(tx - 1, tx + 2):
                blob = store.get(args.zoom, x, y, coordinates, xyz=True)
                if blob is None:
                    raise SystemExit(f"missing z{args.zoom}/{x}/{y} CLDFRA_TOTAL tile")
                tile = decode_numeric_tile(blob)
                if tile.shape != (256, 256):
                    raise SystemExit(f"unsupported tile shape {tile.shape}")
                if declared_unit not in (None, tile.unit):
                    raise SystemExit("CLDFRA_TOTAL tile units differ")
                declared_unit = tile.unit
                values = np.asarray(tile.values, dtype="float64").reshape(tile.shape)
                valid = np.isfinite(values)
                if tile.nodata is not None:
                    valid &= values != tile.nodata
                row.append(np.where(valid, values * tile.scale + tile.offset, np.nan))
            rows.append(np.concatenate(row, axis=1))
    mosaic = np.concatenate(rows, axis=0)
    left, top = int(px), int(py)
    cloud = mosaic[top:top + 512, left:left + 512]
    finite = cloud[np.isfinite(cloud)]
    lo, hi = float(np.min(finite)), float(np.max(finite))

    # Fixed 0..1 portrayal preserves source values and does not reinterpret the
    # producer's percent unit declaration as an instruction to multiply by 100.
    level = np.clip(cloud, 0.0, 1.0)
    rgb = np.stack((25 + 225 * level, 65 + 190 * level, 105 + 150 * level), axis=-1)
    rgb[~np.isfinite(cloud)] = (235, 235, 235)
    image = Image.fromarray(rgb.astype("uint8")).resize((768, 768), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (768, 860), "white")
    canvas.paste(image, (0, 56))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    draw.text((16, 14), f"CLDFRA_TOTAL · {args.valid_time} · z{args.zoom} {args.domain}", fill="black", font=font)
    draw.text((16, 34), f"center {args.lat:.4f} N, {args.lon:.4f} E · declared unit {declared_unit or 'none'}", fill="black", font=font)
    draw.ellipse((380, 432, 388, 440), outline="black", fill="white", width=1)
    draw.text((16, 828), f"stored-value range {lo:.4f}–{hi:.4f}; fixed 0–1 blue/white ramp; bilinear display interpolation", fill="black", font=font)
    draw.text((16, 844), "Source declares % but values are not rescaled · uncertified · not for navigation", fill="#8b0000", font=font)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, optimize=True)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(json.dumps({"center": [args.lat, args.lon], "declared_unit": declared_unit,
                      "output": str(args.output), "sha256": digest,
                      "stored_value_min": lo, "stored_value_max": hi}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
