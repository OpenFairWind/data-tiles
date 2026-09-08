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

from demo.weather.config import WeatherConfigurationError, weather_config  # noqa: E402
from server.app import app  # noqa: E402

LOGGER = logging.getLogger(__name__)


def dataset_path() -> Path:
    path = DATA_DIR / f"{DATASET}.mbtiles"
    if not path.is_file():
        raise HTTPException(503, f"weather dataset is missing: {path}")
    return path


@app.get("/weather", include_in_schema=False)
def weather_page():
    return FileResponse(DEMO_DIR / "index.html")


@app.get("/weather/config.json", include_in_schema=False)
def weather_configuration():
    try:
        return weather_config(dataset_path())
    except WeatherConfigurationError as exc:
        raise HTTPException(503, str(exc)) from exc


app.mount("/weather/assets", StaticFiles(directory=DEMO_DIR / "static"), name="weather-assets")
app.mount("/plugins", StaticFiles(directory=ROOT / "plugins"), name="plugins")


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    LOGGER.info("serving weather demo at http://127.0.0.1:8090/weather")
    uvicorn.run(app, host="127.0.0.1", port=8090)
