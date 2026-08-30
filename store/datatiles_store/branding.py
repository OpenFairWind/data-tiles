from __future__ import annotations

import io
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from PIL import Image, UnidentifiedImageError

MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_LOGO_PIXELS = 4_000_000
LOGO_FILENAME = "store-logo.png"
FONT_STACKS = {
    "system": "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
    "serif": "Georgia, 'Times New Roman', serif",
    "monospace": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
}
SHADOWS = {
    "none": "none",
    "sm": "0 .125rem .25rem rgba(0,0,0,.18)",
    "md": "0 .5rem 1.5rem rgba(0,0,0,.28)",
    "lg": "0 1rem 3rem rgba(0,0,0,.38)",
}


def branding_directory(app) -> Path:
    path = Path(app.config.get("BRANDING_DIR") or (Path(app.instance_path) / "branding")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def logo_path(app) -> Path:
    return branding_directory(app) / LOGO_FILENAME


def save_logo(app, uploaded) -> None:
    payload = uploaded.read(MAX_LOGO_BYTES + 1)
    if not payload or len(payload) > MAX_LOGO_BYTES:
        raise ValueError("logo must be a non-empty PNG, JPEG, or WebP image no larger than 2 MiB")
    try:
        with Image.open(io.BytesIO(payload)) as source:
            source.verify()
        with Image.open(io.BytesIO(payload)) as source:
            if source.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("logo must be PNG, JPEG, or WebP")
            width, height = source.size
            if width < 16 or height < 16 or width * height > MAX_LOGO_PIXELS:
                raise ValueError("logo dimensions must be at least 16 × 16 and at most 4 megapixels")
            normalized = source.convert("RGBA")
            target = logo_path(app)
            with NamedTemporaryFile(dir=target.parent, prefix=".logo-", suffix=".png", delete=False) as temporary:
                temporary_name = temporary.name
                normalized.save(temporary, format="PNG", optimize=True)
            os.replace(temporary_name, target)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("logo is not a valid PNG, JPEG, or WebP image") from exc


def remove_logo(app) -> bool:
    target = logo_path(app)
    if target.exists():
        target.unlink()
        return True
    return False


def hex_rgb(value: str) -> str:
    return ", ".join(str(int(value[index:index + 2], 16)) for index in (1, 3, 5))


def theme_context(values: dict[str, str]) -> dict[str, str]:
    colors = {key.removeprefix("theme.").replace(".", "_"): value for key, value in values.items() if key.startswith("theme.") and value.startswith("#")}
    colors.update({f"{key}_rgb": hex_rgb(value) for key, value in colors.items()})
    colors["radius"] = values["theme.radius"]
    colors["shadow"] = SHADOWS[values["theme.shadow"]]
    colors["font"] = FONT_STACKS[values["theme.font"]]
    return colors
