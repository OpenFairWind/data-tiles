"""Dependency-free configuration discovery for the weather demonstration."""
from __future__ import annotations

from pathlib import Path

from datatiles.store import DataTiles, DataTilesError


class WeatherConfigurationError(RuntimeError):
    """Raised when the configured weather frame cannot serve the demo."""


def weather_config(path: Path) -> dict[str, object]:
    try:
        with DataTiles(path, read_only=True) as store:
            metadata = store.metadata()
            profiles = store.content_profiles()
    except (OSError, DataTilesError) as exc:
        raise WeatherConfigurationError(f"cannot read weather dataset: {exc}") from exc
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
        raise WeatherConfigurationError("weather dataset does not declare a zoom/domain mapping")
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
