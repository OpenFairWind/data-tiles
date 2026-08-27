import json
import struct
import zlib

import pytest

from datatiles.numeric import MAGIC, MAX_ELEMENTS, decode_numeric_tile, encode_numeric_tile


@pytest.mark.parametrize("dtype",["int8","uint8","int16","uint16","int32","uint32","int64","uint64","float32","float64"])
@pytest.mark.parametrize("byteorder",["little","big"])
@pytest.mark.parametrize("compression",["none","zlib"])
def test_all_numeric_modes_roundtrip(dtype,byteorder,compression):
    values=[1,2,3,4]
    tile=decode_numeric_tile(encode_numeric_tile(values,(2,2),dtype=dtype,byteorder=byteorder,compression=compression,nodata=0,scale=.5,offset=2,unit="m"))
    assert tile.shape==(2,2) and tile.dtype==dtype and tuple(tile.values)==tuple(values)
    assert tile.scale==.5 and tile.offset==2 and tile.unit=="m"


@pytest.mark.parametrize("blob",[b"",b"DNT1",b"BAD!\0\0\0\0",MAGIC+struct.pack(">I",2_000_000)])
def test_rejects_truncated_or_invalid_envelopes(blob):
    with pytest.raises(ValueError): decode_numeric_tile(blob)


def _blob(header,payload=b""):
    value=json.dumps(header,separators=(",",":")).encode()
    return MAGIC+struct.pack(">I",len(value))+value+payload


def test_decoder_rejects_oversized_shape_and_compression_bomb():
    common={"dtype":"uint8","byteorder":"little","compression":"none"}
    with pytest.raises(ValueError,match="element limit"):
        decode_numeric_tile(_blob({**common,"shape":[MAX_ELEMENTS+1]}))
    header={**common,"shape":[4],"compression":"zlib"}
    with pytest.raises(ValueError,match="decompressed size"):
        decode_numeric_tile(_blob(header,zlib.compress(b"12345")))


@pytest.mark.parametrize("scale,offset",[(float("nan"),0),(1,float("inf"))])
def test_decoder_rejects_nonfinite_transform(scale,offset):
    header={"dtype":"uint8","shape":[1],"byteorder":"little","compression":"none","scale":scale,"offset":offset}
    with pytest.raises(ValueError,match="scale or offset"): decode_numeric_tile(_blob(header,b"\0"))


def test_rejects_unknown_header_fields_and_invalid_metadata():
    base={"dtype":"uint8","shape":[1],"byteorder":"little","compression":"none"}
    with pytest.raises(ValueError,match="unknown"): decode_numeric_tile(_blob({**base,"surprise":1},b"\0"))
    with pytest.raises(ValueError,match="nodata"): decode_numeric_tile(_blob({**base,"nodata":True},b"\0"))
    with pytest.raises(ValueError,match="unit"): decode_numeric_tile(_blob({**base,"unit":42},b"\0"))
    with pytest.raises(ValueError,match="element limit"): encode_numeric_tile([], (MAX_ELEMENTS+1,),dtype="uint8")
