import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "demo" / "netcdf-archive" / "acquire.py"


def load_acquisition_module():
    spec = importlib.util.spec_from_file_location("netcdf_archive_acquire", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_acquisition_reuses_only_checksum_matched_source(tmp_path, monkeypatch):
    module = load_acquisition_module()
    payload = b"locked NetCDF fixture bytes"
    checksum = hashlib.sha256(payload).hexdigest()
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "product_d01_20260907Z1200.nc").write_bytes(payload)
    lock = tmp_path / "sources.lock.json"
    lock.write_text(json.dumps({"sources": [{
        "archive_path": "product/d01/archive/2026/09/07/product_d01_20260907Z1200.nc",
        "sha256": checksum,
        "url": "https://invalid.example/product_d01_20260907Z1200.nc",
    }]}), encoding="utf-8")
    monkeypatch.setattr(module, "LOCK", lock)
    output = module.acquire(tmp_path / "archive", cache, 1)
    assert len(output) == 1
    assert output[0].read_bytes() == payload
    assert module.sha256(output[0]) == checksum


def test_real_source_lock_and_demo_configuration_are_coherent():
    lock = json.loads((SCRIPT.parent / "sources.lock.json").read_text(encoding="utf-8"))
    products = json.loads((SCRIPT.parent / "netcdf-products.json").read_text(encoding="utf-8"))
    source = lock["sources"][0]
    assert source["archive_path"].startswith("wrf5/d01/archive/2026/09/07/")
    assert source["url"].startswith("https://data.meteo.uniparthenope.it/files/wrf5/d01/archive/")
    assert len(source["sha256"]) == 64
    assert len(lock["verification"]["tile_sha256"]) == 64
    assert {"T2C", "RH2", "U10M", "V10M"} <= set(products["wrf5"]["variables"])
