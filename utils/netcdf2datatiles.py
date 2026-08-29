#!/usr/bin/env python3
"""Convert a local or URL-identified NetCDF dataset to numeric DataTiles."""
from __future__ import annotations

import argparse
from pathlib import Path

from common import ConversionError, convert_dataset, require_scientific_stack, resolve_source


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", help="local NetCDF path, file: URI, or HTTP(S) URL")
    p.add_argument("target", type=Path, help="new .datatiles file")
    p.add_argument("--variable", action="append", dest="variables", help="variable to import; repeatable")
    p.add_argument("--zoom", type=int, default=6, help="Web Mercator zoom level (default: 6)")
    p.add_argument("--tile-size", type=int, default=256)
    p.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    p.add_argument("--max-tiles", type=int, default=10000, help="safety bound (default: 10000)")
    p.add_argument("--engine", help="xarray NetCDF engine, e.g. netcdf4 or h5netcdf")
    p.add_argument("--timeout", type=float, default=60.0, help="URL download timeout in seconds")
    p.add_argument("--source-license", required=True, help="SPDX license expression for the source, e.g. CC-BY-4.0 or LicenseRef-Proprietary")
    p.add_argument("--source-license-uri", required=True, help="authoritative source licence/terms URI")
    p.add_argument("--source-attribution", required=True, help="verbatim attribution required by the source")
    p.add_argument("--dataset-license", required=True, help="SPDX expression concluded for the generated dataset")
    p.add_argument("--dataset-license-uri", required=True, help="authoritative generated-dataset licence URI")
    p.add_argument("--dataset-attribution", help="recommended citation/attribution for the generated dataset")
    p.add_argument("--access-rights", choices=("open","embargoed","restricted","closed"), default="open")
    return p


def main() -> int:
    args = parser().parse_args()
    _, xr = require_scientific_stack()
    try:
        with resolve_source(args.source, timeout=args.timeout) as source:
            kwargs = {"decode_cf": True}
            if args.engine:
                kwargs["engine"] = args.engine
            with xr.open_dataset(source.local_path, **kwargs) as ds:
                stats = convert_dataset(ds, args.target, source=source, source_kind="NetCDF",
                                        variables=args.variables, zoom=args.zoom, tile_size=args.tile_size,
                                        bbox=tuple(args.bbox) if args.bbox else None, max_tiles=args.max_tiles,
                                        source_license=args.source_license, source_license_uri=args.source_license_uri,
                                        source_attribution=args.source_attribution, dataset_license=args.dataset_license,
                                        dataset_license_uri=args.dataset_license_uri, dataset_attribution=args.dataset_attribution,
                                        access_rights=args.access_rights)
        print(f"created {args.target}: {stats['variables']} variables, {stats['slices']} slices, {stats['tiles']} tiles")
        return 0
    except ConversionError as exc:
        parser().error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
