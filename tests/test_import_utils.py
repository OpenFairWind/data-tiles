from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path


def load_common():
    path = Path(__file__).parents[1] / "utils" / "common.py"
    spec = importlib.util.spec_from_file_location("datatiles_utils_common", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_safe_token_and_tile_ranges():
    common = load_common()
    assert common.safe_token("Sea Floor Depth") == "sea_floor_depth"
    xs, ys = common.tile_ranges((12.8, 39.9, 15.8, 41.3), 7)
    assert len(xs) > 0 and len(ys) > 0


def test_local_source_identity_and_checksum(tmp_path):
    common = load_common()
    source = tmp_path / "sample.nc"
    source.write_bytes(b"example scientific source")
    with common.resolve_source(str(source)) as resolved:
        assert resolved.local_path == source.resolve()
        assert resolved.uri == source.resolve().as_uri()
        assert resolved.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
        assert not resolved.temporary


def test_source_bbox_is_clipped_not_extrapolated():
    common = load_common()
    class Axis:
        def __init__(self, lo, hi): self.lo, self.hi = lo, hi
        def min(self): return self.lo
        def max(self): return self.hi
    assert common.source_bbox(Axis(40, 41), Axis(13, 15), (12, 39, 14.5, 42)) == (13.0, 40.0, 14.5, 41.0)


def test_local_zarr_tree_digest_is_content_and_key_sensitive(tmp_path):
    common = load_common()
    store = tmp_path / "sample.zarr"
    store.mkdir()
    (store / "zarr.json").write_text('{"zarr_format":3}')
    (store / "c").mkdir()
    (store / "c" / "0").write_bytes(b"chunk")
    with common.resolve_zarr_source(str(store)) as resolved:
        first = resolved.checksum
        assert resolved.checksum_algorithm == "zarr-tree-sha256-v1"
        assert resolved.local_path == store.resolve()
    (store / "c" / "0").write_bytes(b"changed")
    with common.resolve_zarr_source(str(store)) as resolved:
        assert resolved.checksum != first


def test_remote_zarr_requires_authoritative_sha256():
    common = load_common()
    import pytest
    with pytest.raises(common.ConversionError):
        with common.resolve_zarr_source("https://example.org/data.zarr"):
            pass
    checksum = "a" * 64
    with common.resolve_zarr_source("s3://bucket/snapshot.zarr", source_sha256=checksum) as resolved:
        assert resolved.local_path is None
        assert resolved.checksum_algorithm == "sha256"
        assert resolved.checksum == checksum


def test_remote_zarr_signed_url_requires_credential_free_provenance_uri():
    common = load_common()
    import pytest
    checksum = "b" * 64
    with pytest.raises(common.ConversionError):
        with common.resolve_zarr_source("https://example.org/data.zarr?token=secret", source_sha256=checksum):
            pass
    with common.resolve_zarr_source(
        "https://example.org/data.zarr?token=secret",
        source_sha256=checksum,
        provenance_uri="https://example.org/data.zarr",
    ) as resolved:
        assert resolved.identifier == "https://example.org/data.zarr"
        assert "secret" not in resolved.identifier


def test_conversion_selects_first_slice_and_enforces_revision_8_semantics(tmp_path):
    import pytest
    np=pytest.importorskip("numpy"); xr=pytest.importorskip("xarray")
    from datatiles import DataTiles
    common=load_common()
    dataset=xr.Dataset(
        {"depth":(("lat","lon"),np.array([[1.0,2.0],[3.0,4.0]],dtype="float32"),
                  {"standard_name":"sea_floor_depth_below_sea_surface","units":"m"})},
        coords={"lat":[40.0,41.0],"lon":[13.0,14.0]},
    )
    target=tmp_path/"converted.datatiles"
    source_file=tmp_path/"source.bin"; source_file.write_bytes(b"fixture")
    with common.resolve_source(str(source_file)) as source:
        stats=common.convert_dataset(
            dataset,target,source=source,source_kind="NetCDF",variables=["depth"],zoom=0,tile_size=8,
            bbox=None,max_tiles=1,source_license="CC-BY-4.0",
            source_license_uri="https://creativecommons.org/licenses/by/4.0/",source_attribution="Fixture source",
            dataset_license="CC-BY-4.0",dataset_license_uri="https://creativecommons.org/licenses/by/4.0/",
            dataset_attribution="Fixture output",
        )
    assert stats=={"variables":1,"slices":1,"tiles":1}
    with DataTiles(target,read_only=True) as store:
        assert store.db.execute("SELECT count(*) FROM tiles").fetchone()[0]==1
        assert store.metadata()["bounds"]=="13,40,14,41"
        assert store.validate(require_variable_semantics=True)==[]
