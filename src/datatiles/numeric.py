"""Compact, self-describing numeric-array tile encoding (DNT1)."""
from __future__ import annotations

import json
import math
import struct
import zlib
from dataclasses import dataclass
from typing import Any, Sequence

MAGIC = b"DNT1"
MAX_HEADER_BYTES = 1_048_576
MAX_ELEMENTS = 16_777_216
DTYPES = {"int8": "b", "uint8": "B", "int16": "h", "uint16": "H", "int32": "i",
          "uint32": "I", "int64": "q", "uint64": "Q", "float32": "f", "float64": "d"}
HEADER_KEYS = {"dtype","shape","byteorder","compression","nodata","scale","offset","unit"}


@dataclass(frozen=True)
class NumericTile:
    values: tuple[int | float, ...]
    shape: tuple[int, ...]
    dtype: str
    byteorder: str = "little"
    nodata: int | float | None = None
    scale: float = 1.0
    offset: float = 0.0
    unit: str | None = None


def encode_numeric_tile(values: Sequence[int | float], shape: Sequence[int], *, dtype: str = "float32",
                        byteorder: str = "little", compression: str = "zlib", nodata: int | float | None = None,
                        scale: float = 1.0, offset: float = 0.0, unit: str | None = None) -> bytes:
    if dtype not in DTYPES or byteorder not in ("little", "big") or compression not in ("none", "zlib"):
        raise ValueError("unsupported numeric tile option")
    count = 1
    for size in shape:
        if not isinstance(size,int) or isinstance(size,bool) or size <= 0: raise ValueError("shape values must be positive integers")
        count *= size
        if count>MAX_ELEMENTS: raise ValueError("DNT1 element limit exceeded")
    if count != len(values): raise ValueError("shape does not match value count")
    if not isinstance(scale,(int,float)) or isinstance(scale,bool) or not math.isfinite(scale): raise ValueError("scale must be finite")
    if not isinstance(offset,(int,float)) or isinstance(offset,bool) or not math.isfinite(offset): raise ValueError("offset must be finite")
    if nodata is not None and (not isinstance(nodata,(int,float)) or isinstance(nodata,bool) or not math.isfinite(nodata)): raise ValueError("nodata must be finite or null")
    if unit is not None and (not isinstance(unit,str) or len(unit)>1024): raise ValueError("unit must be a string of at most 1024 characters")
    prefix = "<" if byteorder == "little" else ">"
    try: payload = struct.pack(prefix + str(count) + DTYPES[dtype], *values)
    except (struct.error,OverflowError) as exc: raise ValueError(f"values are invalid for {dtype}") from exc
    if compression == "zlib": payload = zlib.compress(payload)
    header = json.dumps({"dtype": dtype, "shape": list(shape), "byteorder": byteorder,
                         "compression": compression, "nodata": nodata, "scale": scale,
                         "offset": offset, "unit": unit}, separators=(",", ":")).encode()
    return MAGIC + struct.pack(">I", len(header)) + header + payload


def decode_numeric_tile(blob: bytes) -> NumericTile:
    if len(blob) < 8 or blob[:4] != MAGIC: raise ValueError("not a DNT1 numeric tile")
    length = struct.unpack(">I", blob[4:8])[0]
    if length > MAX_HEADER_BYTES or 8+length > len(blob): raise ValueError("invalid DNT1 header length")
    header = json.loads(blob[8:8 + length])
    required={"dtype","shape","byteorder","compression"}
    if not isinstance(header,dict) or not required<=set(header): raise ValueError("incomplete DNT1 header")
    if set(header)-HEADER_KEYS: raise ValueError("unknown DNT1 header field")
    if header["dtype"] not in DTYPES or header["byteorder"] not in ("little","big") or header["compression"] not in ("none","zlib"): raise ValueError("unsupported DNT1 header option")
    if not isinstance(header["shape"],list) or not 1<=len(header["shape"])<=8: raise ValueError("invalid DNT1 shape")
    payload = blob[8 + length:]
    count = 1
    for size in header["shape"]:
        if not isinstance(size,int) or isinstance(size,bool) or size<=0: raise ValueError("invalid DNT1 shape")
        count *= size
        if count>MAX_ELEMENTS: raise ValueError("DNT1 element limit exceeded")
    item_size=struct.calcsize(DTYPES[header["dtype"]]); expected=count*item_size
    if header["compression"] == "zlib":
        inflater=zlib.decompressobj()
        try: payload=inflater.decompress(payload,expected+1)
        except zlib.error as exc: raise ValueError("invalid DNT1 zlib payload") from exc
        if len(payload)!=expected or not inflater.eof or inflater.unused_data: raise ValueError("DNT1 decompressed size mismatch")
    elif len(payload)!=expected: raise ValueError("DNT1 payload size mismatch")
    scale=header.get("scale",1.0); offset=header.get("offset",0.0)
    if (not isinstance(scale,(int,float)) or isinstance(scale,bool) or not isinstance(offset,(int,float)) or
            isinstance(offset,bool) or not math.isfinite(scale) or not math.isfinite(offset)): raise ValueError("invalid DNT1 scale or offset")
    nodata=header.get("nodata")
    if nodata is not None and (not isinstance(nodata,(int,float)) or isinstance(nodata,bool) or not math.isfinite(nodata)): raise ValueError("invalid DNT1 nodata")
    unit=header.get("unit")
    if unit is not None and (not isinstance(unit,str) or len(unit)>1024): raise ValueError("invalid DNT1 unit")
    prefix = "<" if header["byteorder"] == "little" else ">"
    values = struct.unpack(prefix + str(count) + DTYPES[header["dtype"]], payload)
    return NumericTile(values, tuple(header["shape"]), header["dtype"], header["byteorder"],
                       nodata, scale, offset, unit)
