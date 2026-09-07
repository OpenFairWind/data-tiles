from pathlib import Path


def test_store_preview_assets_exist():
    root = Path(__file__).resolve().parents[1] / "datatiles_store" / "static"
    assert (root / "served-map.js").is_file()
    assert (root / "catalog-preview.js").is_file()
    assert (root / "explorer-online.js").is_file()


def test_served_map_uses_online_discovery():
    text = (Path(__file__).resolve().parents[1] / "datatiles_store" / "static" / "served-map.js").read_text()
    assert '}/maps`' in text
    assert "tilejson.json" in text
    assert "layer.dataset === dataset" in text
