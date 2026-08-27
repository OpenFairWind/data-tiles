import hashlib
import importlib.util
from pathlib import Path

from datatiles import DataTiles

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"docs/tutorial/examples/build_tutorial.py"


def load_builder():
    spec=importlib.util.spec_from_file_location("datatiles_tutorial_builder",SCRIPT)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_tutorial_builder_is_valid_fair_mixed_and_deterministic(tmp_path):
    builder=load_builder(); first=tmp_path/"first.datatiles"; second=tmp_path/"second.datatiles"
    builder.build(first); builder.verify(first)
    builder.build(second); builder.verify(second)
    assert hashlib.sha256(first.read_bytes()).digest()==hashlib.sha256(second.read_bytes()).digest()
    with DataTiles(first,read_only=True) as store:
        assert store.validate()==[]
        assert store.fair_report()["passes"]
        assert {p["data_type"] for p in store.content_profiles()}=={"raster","vector"}
