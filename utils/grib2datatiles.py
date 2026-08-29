#!/usr/bin/env python3
"""Convert a local or URL-identified GRIB/GRIB2 dataset to numeric DataTiles."""
from __future__ import annotations

import argparse
from pathlib import Path

from common import ConversionError, convert_dataset, require_scientific_stack, resolve_source


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", help="local GRIB/GRIB2 path, file: URI, or HTTP(S) URL")
    p.add_argument("target", type=Path, help="new .datatiles file")
    p.add_argument("--variable", action="append", dest="variables", help="decoded xarray variable; repeatable")
    p.add_argument("--zoom", type=int, default=6, help="Web Mercator zoom level (default: 6)")
    p.add_argument("--tile-size", type=int, default=256)
    p.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    p.add_argument("--max-tiles", type=int, default=10000, help="safety bound (default: 10000)")
    p.add_argument("--filter-by-keys", action="append", default=[], metavar="KEY=VALUE",
                   help="cfgrib filter_by_keys entry; repeatable")
    p.add_argument("--timeout", type=float, default=60.0, help="URL download timeout in seconds")
    p.add_argument("--source-license", required=True, help="SPDX license expression for the source, e.g. CC-BY-4.0 or LicenseRef-Proprietary")
    p.add_argument("--source-license-uri", required=True, help="authoritative source licence/terms URI")
    p.add_argument("--source-attribution", required=True, help="verbatim attribution required by the source")
    p.add_argument("--dataset-license", required=True, help="SPDX expression concluded for the generated dataset")
    p.add_argument("--dataset-license-uri", required=True, help="authoritative generated-dataset licence URI")
    p.add_argument("--dataset-attribution", help="recommended citation/attribution for the generated dataset")
    p.add_argument("--access-rights", choices=("open","embargoed","restricted","closed"), default="open")
    return p


def parse_filters(items: list[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    for item in items:
        if "=" not in item:
            raise ConversionError(f"invalid --filter-by-keys value: {item!r}")
        key, value = item.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key:
            raise ConversionError("empty cfgrib filter key")
        try:
            result[key] = int(value)
        except ValueError:
            result[key] = value
    return result


def main() -> int:
    args = parser().parse_args()
    _, xr = require_scientific_stack()
    try:
        filters = parse_filters(args.filter_by_keys)
        with resolve_source(args.source, timeout=args.timeout) as source:
            backend_kwargs = {"indexpath": ""}
            if filters:
                backend_kwargs["filter_by_keys"] = filters
            try:
                with xr.open_dataset(source.local_path, engine="cfgrib", backend_kwargs=backend_kwargs) as ds:
                    stats = convert_dataset(ds, args.target, source=source, source_kind="GRIB2",
                                            variables=args.variables, zoom=args.zoom, tile_size=args.tile_size,
                                            bbox=tuple(args.bbox) if args.bbox else None, max_tiles=args.max_tiles,
                                        source_license=args.source_license, source_license_uri=args.source_license_uri,
                                        source_attribution=args.source_attribution, dataset_license=args.dataset_license,
                                        dataset_license_uri=args.dataset_license_uri, dataset_attribution=args.dataset_attribution,
                                        access_rights=args.access_rights)
            except ImportError as exc:
                raise ConversionError("GRIB conversion requires cfgrib and ecCodes; install .[utils]") from exc
        print(f"created {args.target}: {stats['variables']} variables, {stats['slices']} slices, {stats['tiles']} tiles")
        return 0
    except ConversionError as exc:
        parser().error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
