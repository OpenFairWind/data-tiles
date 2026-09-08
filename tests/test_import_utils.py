from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
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


def load_meteo_utility():
    utils = Path(__file__).parents[1] / "utils"
    sys.path.insert(0, str(utils))
    try:
        path = utils / "meteouniparthenope2datatiles.py"
        spec = importlib.util.spec_from_file_location("meteouniparthenope2datatiles", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(utils))


def test_safe_token_and_tile_ranges():
    common = load_common()
    assert common.safe_token("Sea Floor Depth") == "sea_floor_depth"
    xs, ys = common.tile_ranges((12.8, 39.9, 15.8, 41.3), 7)
    assert len(xs) > 0 and len(ys) > 0


def test_meteouniparthenope_source_identity_and_output_path(tmp_path):
    utility = load_meteo_utility()
    identity = utility.parse_source_identity(
        "https://data.meteo.uniparthenope.it/files/wrf5/d01/archive/2026/09/07/wrf5_d01_20260907Z1200.nc"
    )
    assert (identity.product, identity.domain, identity.stamp) == ("wrf5", "d01", "20260907Z1200")
    assert utility.output_path(tmp_path, identity) == tmp_path / "2026/09/07/wrf5_20260907Z1200.mbtiles"


def test_meteouniparthenope_import_writes_frames_separately_by_default(tmp_path):
    import pytest
    np = pytest.importorskip("numpy")
    xr = pytest.importorskip("xarray")
    from datatiles import DataTiles

    coordinates = {
        "time": xr.DataArray([1110492], dims="time", attrs={"units": "hours since 1900-01-01 00:00:0.0"}),
        "latitude": [40.0, 41.0],
        "longitude": [13.0, 14.0],
    }
    sources = []
    for product, domain, offset in (("wrf5", "d01", 0.0), ("ww33", "d02", 10.0)):
        path = tmp_path / f"{product}_{domain}_20260907Z1200.nc"
        xr.Dataset(
            {"VALUE": (("time", "latitude", "longitude"),
                       np.array([[[1.0, 2.0], [3.0, 4.0]]], dtype="float32") + offset,
                       {"description": "Producer-local value", "units": "m s-1"})},
            coords=coordinates,
        ).to_netcdf(path)
        sources.append(path)

    root = Path(__file__).parents[1]
    output_root = tmp_path / "tiles"
    command = [
        sys.executable, str(root / "utils/meteouniparthenope2datatiles.py"),
        *(str(path) for path in sources), "--root", str(output_root), "--zoom", "0", "--tile-size", "8",
        "--source-license", "LicenseRef-Fixture", "--source-license-uri", "https://example.test/source-terms",
        "--source-attribution", "Fixture provider", "--dataset-license", "LicenseRef-Fixture-Derived",
        "--dataset-license-uri", "https://example.test/output-terms",
    ]
    result = subprocess.run(command, text=True, capture_output=True,
                            env={**os.environ, "PYTHONPATH": str(root / "src")})
    assert result.returncode == 0, result.stderr
    wrf_output = output_root / "2026/09/07/wrf5_20260907Z1200.mbtiles"
    wave_output = output_root / "2026/09/07/ww33_20260907Z1200.mbtiles"
    with DataTiles(wrf_output, read_only=True) as store:
        assert store.validate(require_variable_semantics=True) == []
        profiles = store.content_profiles()
        assert len(profiles) == 1
        assert profiles[0]["coordinates"]["product"] == "wrf5"
        assert {p["coordinates"]["valid_time"] for p in profiles} == {"2026-09-07T12:00:00.000000Z"}
    with DataTiles(wave_output, read_only=True) as store:
        assert store.content_profiles()[0]["coordinates"]["product"] == "ww33"

    single_root = tmp_path / "single"
    single_command = command + ["--frame-storage", "single"]
    single_command[single_command.index(str(output_root))] = str(single_root)
    result = subprocess.run(single_command, text=True, capture_output=True,
                            env={**os.environ, "PYTHONPATH": str(root / "src")})
    assert result.returncode == 0, result.stderr
    with DataTiles(single_root / "meteouniparthenope.mbtiles", read_only=True) as store:
        assert {(profile["coordinates"]["product"], profile["coordinates"]["domain"])
                for profile in store.content_profiles()} == {("wrf5", "d01"), ("ww33", "d02")}

    appended = tmp_path / "rms3_d03_20260907Z1200.nc"
    xr.Dataset(
        {"VALUE": (("time", "latitude", "longitude"),
                   np.array([[[21.0, 22.0], [23.0, 24.0]]], dtype="float32"),
                   {"description": "Producer-local value", "units": "m s-1"})},
        coords=coordinates,
    ).to_netcdf(appended)
    append_command = command[:2] + [str(appended)] + command[4:]
    result = subprocess.run(append_command, text=True, capture_output=True,
                            env={**os.environ, "PYTHONPATH": str(root / "src")})
    assert result.returncode == 0, result.stderr
    with DataTiles(output_root / "2026/09/07/rms3_20260907Z1200.mbtiles", read_only=True) as store:
        assert len(store.content_profiles()) == 1
        assert store.validate(require_variable_semantics=True) == []


def test_meteouniparthenope_cli_parses_ranges_csv_aliases_and_quoted_glob(tmp_path):
    utility = load_meteo_utility()
    assert utility.parse_zoom_range("6,8") == (6, 7, 8)
    assert utility.parse_variables(["U10,V10,T2C"], None) == ["U10", "V10", "T2C"]
    (tmp_path / "b.nc").touch(); (tmp_path / "a.nc").touch()
    assert utility.expand_sources([str(tmp_path / "*.nc")]) == [str(tmp_path / "a.nc"), str(tmp_path / "b.nc")]
    parsed = utility.parser().parse_args([
        "wrf5_d01_20260907Z1200.nc", "--root", str(tmp_path),
        "--source-license", "LicenseRef-Source", "--source-license-uri", "https://example.test/terms",
        "--source-attribution", "Provider", "--dataset-license", "LicenseRef-Derived",
    ])
    assert parsed.dataset_license_uri is None


def test_meteouniparthenope_domain_selection_uses_measured_resolution():
    import pytest
    xr = pytest.importorskip("xarray")
    utility = load_meteo_utility()
    identity = utility.parse_source_identity("wrf5_d01_20260907Z1200.nc")
    records = []
    for domain, step in (("d01", 0.12), ("d02", 0.03), ("d03", 0.006)):
        ds = xr.Dataset(coords={"latitude": [40.0, 40.0 + step], "longitude": [14.0, 14.0 + step]})
        records.append((domain, utility.SourceIdentity(identity.product, domain, identity.instant), ds, None))
    chosen = utility.domains_by_zoom(records, tuple(range(6, 11)))
    assert chosen[6][1].domain == "d01"
    assert chosen[8][1].domain == "d02"
    assert chosen[10][1].domain == "d03"
    assert utility.optimal_zoom_range(records) == tuple(range(3, 9))
    automatic = utility.domains_by_zoom(records, utility.optimal_zoom_range(records), native_anchors=True)
    assert automatic[3][1].domain == "d01"
    assert automatic[8][1].domain == "d03"
    assert utility.parser().parse_args([
        "wrf5_d01_20260907Z1200.nc", "--root", ".", "--source-license", "LicenseRef-X",
        "--source-license-uri", "https://example.test", "--source-attribution", "X",
        "--dataset-license", "LicenseRef-Y",
    ]).zoom is None


def test_meteouniparthenope_cloud_renderer_is_deterministic(tmp_path):
    import pytest
    np = pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    from datatiles import DataTiles, encode_numeric_tile

    source = tmp_path / "cloud.mbtiles"
    coordinates = {"variable": "wrf5_cldfra_total", "product": "wrf5", "domain": "d03",
                   "valid_time": "2026-09-07T12:00:00Z"}
    values = np.linspace(0.0, 1.0, 256 * 256, dtype="float32")
    blob = encode_numeric_tile(values.tolist(), (256, 256), dtype="float32", unit="%")
    with DataTiles(source, create=True, tile_format="application/vnd.datatiles.numeric") as store:
        for name, value_type in (("variable", "text"), ("product", "text"), ("domain", "text"),
                                 ("valid_time", "datetime")):
            store.add_dimension(name, value_type)
        for x in range(1, 4):
            for y in range(1, 4):
                store.put(2, x, y, blob, coordinates, xyz=True)
    root = Path(__file__).parents[1]
    output = tmp_path / "cloud.png"
    command = [sys.executable, str(root / "utils/render_meteouniparthenope_cloud.py"),
               str(source), str(output), "--zoom", "2", "--lat", "0", "--lon", "0",
               "--valid-time", "2026-09-07T12:00:00Z"]
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    first = subprocess.run(command, text=True, capture_output=True, env=env)
    assert first.returncode == 0, first.stderr
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    second = subprocess.run(command, text=True, capture_output=True, env=env)
    assert second.returncode == 0, second.stderr
    assert hashlib.sha256(output.read_bytes()).hexdigest() == digest


def test_meteouniparthenope_nested_domain_tiles_use_coarser_fallback(tmp_path):
    import math
    import pytest
    np = pytest.importorskip("numpy")
    xr = pytest.importorskip("xarray")
    from datatiles import DataTiles, decode_numeric_tile

    coordinates = {
        "time": xr.DataArray([1110492], dims="time", attrs={"units": "hours since 1900-01-01 00:00:0.0"}),
    }
    sources = []
    for domain, axis, value in (("d01", [0.0, 1.0], 10.0),
                                ("d02", [0.25, 0.5, 0.75], 20.0)):
        path = tmp_path / f"wrf5_{domain}_20260907Z1200.nc"
        xr.Dataset(
            {"T2C": (("time", "latitude", "longitude"),
                     np.full((1, len(axis), len(axis)), value, dtype="float32"), {"units": "C"})},
            coords={**coordinates, "latitude": axis, "longitude": axis},
        ).to_netcdf(path)
        sources.append(path)
    root = Path(__file__).parents[1]
    command = [sys.executable, str(root / "utils/meteouniparthenope2datatiles.py"),
               *(str(path) for path in sources), "--root", str(tmp_path / "tiles"),
               "--zoom", "8", "--tile-size", "8", "--variables", "T2C",
               "--source-license", "LicenseRef-Fixture", "--source-license-uri", "https://example.test/source",
               "--source-attribution", "Fixture", "--dataset-license", "LicenseRef-Derived"]
    result = subprocess.run(command, text=True, capture_output=True,
                            env={**os.environ, "PYTHONPATH": str(root / "src")})
    assert result.returncode == 0, result.stderr
    output = tmp_path / "tiles/2026/09/07/wrf5_20260907Z1200.mbtiles"
    selection = {"variable": "wrf5_t2c", "product": "wrf5", "domain": "d01+d02",
                 "valid_time": "2026-09-07T12:00:00Z"}

    def value_at(store, lon, lat):
        scale = 2 ** 8
        gx = (lon + 180.0) / 360.0 * scale
        gy = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * scale
        tile = decode_numeric_tile(store.get(8, int(gx), int(gy), selection, xyz=True))
        px, py = int((gx % 1) * 8), int((gy % 1) * 8)
        return tile.values[py * 8 + px]

    with DataTiles(output, read_only=True) as store:
        assert value_at(store, 0.05, 0.05) == pytest.approx(10.0)
        assert value_at(store, 0.5, 0.5) == pytest.approx(20.0)
        profile = next(p for p in store.content_profiles() if p["coordinates"]["domain"] == "d01+d02")
        assert profile["schema"]["domain_composition"] == ["d01", "d02"]


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
