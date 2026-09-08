"""Local Leaflet demonstration for Meteo@UniParthenope numeric DataTiles."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA_DIR = Path(os.environ.get(
    "DATATILES_WEATHER_DATA_DIR",
    ROOT / "data/meteouniparthenope/weather-tiles/2026/09/07",
)).resolve()
DATASET = os.environ.get("DATATILES_WEATHER_DATASET", "wrf5_20260907Z1200")

os.environ.setdefault("DATATILES_DATA_DIR", str(DATA_DIR))
os.environ.setdefault("DATATILES_LAYERS", str(DEMO_DIR / "layers.json"))
os.environ.setdefault("DATATILES_CACHE_DIR", str(ROOT / "data/meteouniparthenope/weather-cache"))

from datatiles.store import DataTiles, DataTilesError  # noqa: E402
from server.app import app  # noqa: E402

LOGGER = logging.getLogger(__name__)


def dataset_path() -> Path:
    path = DATA_DIR / f"{DATASET}.mbtiles"
    if not path.is_file():
        raise HTTPException(503, f"weather dataset is missing: {path}")
    return path


def weather_config(path: Path) -> dict[str, object]:
    try:
        with DataTiles(path, read_only=True) as store:
            metadata = store.metadata()
            profiles = store.content_profiles()
    except (OSError, DataTilesError) as exc:
        raise HTTPException(503, f"cannot read weather dataset: {exc}") from exc
    bounds = [float(value) for value in metadata["bounds"].split(",")]
    domain_by_zoom = {}
    for item in metadata.get("datatiles:meteouniparthenope_domain_selection", "").split(","):
        if not item:
            continue
        zoom, selection = item.split(":", 1)
        domain_by_zoom[zoom.removeprefix("z")] = selection.split("/", 1)[1]
    variables = sorted({str(profile["coordinates"]["variable"]) for profile in profiles})
    times = sorted({str(profile["coordinates"]["valid_time"]) for profile in profiles})
    generated_zooms = sorted(int(zoom) for zoom in domain_by_zoom)
    if not generated_zooms:
        raise HTTPException(503, "weather dataset does not declare a zoom/domain mapping")
    return {
        "dataset": path.stem,
        "bounds": bounds,
        "minzoom": generated_zooms[0],
        "maxzoom": generated_zooms[-1],
        "domainByZoom": domain_by_zoom,
        "variables": variables,
        "validTimes": times,
        "crs": "EPSG:3857 tile matrix; Leaflet interface uses EPSG:4326 positions and XYZ rows",
        "notice": "Uncertified numerical weather-model demonstration; not for navigation.",
    }


@app.get("/weather", include_in_schema=False)
def weather_page():
    return FileResponse(DEMO_DIR / "index.html")


@app.get("/weather/config.json", include_in_schema=False)
def weather_configuration():
    return weather_config(dataset_path())


app.mount("/weather/assets", StaticFiles(directory=DEMO_DIR / "static"), name="weather-assets")
app.mount("/plugins", StaticFiles(directory=ROOT / "plugins"), name="plugins")


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    LOGGER.info("serving weather demo at http://127.0.0.1:8090/weather")
    uvicorn.run(app, host="127.0.0.1", port=8090)
