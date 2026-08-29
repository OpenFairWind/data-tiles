#!/usr/bin/env python3
"""Convert a local or URL-identified Zarr dataset to numeric DataTiles."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    ConversionError,
    convert_dataset,
    require_zarr_stack,
    resolve_zarr_source,
)


def _storage_options(values: list[str] | None) -> dict[str, object]:
    """Parse repeatable KEY=JSON_VALUE storage options without guessing types."""
    result: dict[str, object] = {}
    for item in values or []:
        if "=" not in item:
            raise ConversionError("--storage-option must be KEY=VALUE")
        key, raw = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ConversionError("--storage-option key must not be empty")
        raw = raw.strip()
        try:
            value: object = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        result[key] = value
    return result


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", help="local Zarr store path, file: URI, or fsspec URL such as https://, s3://, or gcs://")
    p.add_argument("target", type=Path, help="new .datatiles file")
    p.add_argument("--group", help="Zarr group/path within the store")
    p.add_argument("--variable", action="append", dest="variables", help="variable to import; repeatable")
    p.add_argument("--zoom", type=int, default=6, help="Web Mercator zoom level (default: 6)")
    p.add_argument("--tile-size", type=int, default=256)
    p.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    p.add_argument("--max-tiles", type=int, default=10000, help="safety bound (default: 10000)")
    p.add_argument("--consolidated", choices=("auto", "true", "false"), default="auto",
                   help="Zarr consolidated metadata policy (default: auto)")
    p.add_argument("--zarr-format", type=int, choices=(2, 3), help="require Zarr format 2 or 3")
    p.add_argument("--storage-option", action="append", metavar="KEY=VALUE",
                   help="fsspec backend option; repeatable; VALUE may be JSON")
    p.add_argument("--provenance-uri", help="stable credential-free source/PID URI recorded in provenance when the access URL is signed or temporary")
    p.add_argument("--source-sha256",
                   help="authoritative SHA-256 for a remote immutable Zarr store/snapshot; required for non-local stores")
    p.add_argument("--source-license", required=True, help="SPDX license expression for the source")
    p.add_argument("--source-license-uri", required=True, help="authoritative source licence/terms URI")
    p.add_argument("--source-attribution", required=True, help="verbatim attribution required by the source")
    p.add_argument("--dataset-license", required=True, help="SPDX expression concluded for the generated dataset")
    p.add_argument("--dataset-license-uri", required=True, help="authoritative generated-dataset licence URI")
    p.add_argument("--dataset-attribution", help="recommended citation/attribution for the generated dataset")
    p.add_argument("--access-rights", choices=("open", "embargoed", "restricted", "closed"), default="open")
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        _, xr = require_zarr_stack()
        storage_options = _storage_options(args.storage_option)
        with resolve_zarr_source(args.source, source_sha256=args.source_sha256, provenance_uri=args.provenance_uri) as source:
            consolidated = None if args.consolidated == "auto" else args.consolidated == "true"
            kwargs = {
                "group": args.group,
                "decode_cf": True,
                "consolidated": consolidated,
                "chunks": None,
            }
            if args.zarr_format is not None:
                kwargs["zarr_format"] = args.zarr_format
            if source.local_path is None and storage_options:
                kwargs["storage_options"] = storage_options
            store_arg = str(source.local_path) if source.local_path is not None else args.source
            with xr.open_zarr(store_arg, **kwargs) as ds:
                stats = convert_dataset(
                    ds,
                    args.target,
                    source=source,
                    source_kind="Zarr",
                    variables=args.variables,
                    zoom=args.zoom,
                    tile_size=args.tile_size,
                    bbox=tuple(args.bbox) if args.bbox else None,
                    max_tiles=args.max_tiles,
                    source_license=args.source_license,
                    source_license_uri=args.source_license_uri,
                    source_attribution=args.source_attribution,
                    dataset_license=args.dataset_license,
                    dataset_license_uri=args.dataset_license_uri,
                    dataset_attribution=args.dataset_attribution,
                    access_rights=args.access_rights,
                    provenance_parameters={
                        "zarr_group": args.group,
                        "consolidated": args.consolidated,
                        "zarr_format": args.zarr_format,
                        "storage_option_keys": sorted(storage_options),
                    },
                )
        print(f"created {args.target}: {stats['variables']} variables, {stats['slices']} slices, {stats['tiles']} tiles")
        return 0
    except ConversionError as exc:
        parser().error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
