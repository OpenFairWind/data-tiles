import json, struct, zlib
import pytest
from fastapi import HTTPException
from server.app import decode_dnt1, render_scalar

def tile(values=(0.0,10.0,20.0,30.0)):
    header={"dtype":"float32","shape":[2,2],"byteorder":"little","compression":"zlib","scale":1.0,"offset":0.0,"nodata":None}
    hb=json.dumps(header,separators=(",",":")).encode(); payload=struct.pack("<4f",*values)
    return b"DNT1"+struct.pack(">I",len(hb))+hb+zlib.compress(payload)

def test_decode_and_render():
    d=decode_dnt1(tile()); assert d["header"]["shape"]==[2,2]
    body=render_scalar(d,{"palette":[[0,"#000000"],[30,"#ffffff"]]},"png")
    assert body.startswith(b"\x89PNG\r\n\x1a\n")


def test_decode_rejects_oversized_and_unknown_headers():
    header={"dtype":"float32","shape":[16777217],"byteorder":"little","compression":"none"}
    hb=json.dumps(header,separators=(",",":")).encode()
    with pytest.raises(HTTPException) as exc:
        decode_dnt1(b"DNT1"+struct.pack(">I",len(hb))+hb)
    assert exc.value.status_code == 413

    header={"dtype":"float32","shape":[1],"byteorder":"little","compression":"none","surprise":1}
    hb=json.dumps(header,separators=(",",":")).encode()
    with pytest.raises(HTTPException) as exc:
        decode_dnt1(b"DNT1"+struct.pack(">I",len(hb))+hb+b"\0\0\0\0")
    assert exc.value.status_code == 422
