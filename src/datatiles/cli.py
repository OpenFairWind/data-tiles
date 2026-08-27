from __future__ import annotations

import argparse
import json
from pathlib import Path

from .store import DataTiles, DataTilesError


def coords(items: list[str]) -> dict[str, str]:
    result = {}
    for item in items:
        if "=" not in item:
            raise argparse.ArgumentTypeError(f"coordinate must be NAME=VALUE: {item}")
        name, value = item.split("=", 1)
        if value.startswith(("[", "(")) and value.endswith(("]", ")")) and "," in value:
            lower, upper = value[1:-1].split(",", 1)
            result[name] = (lower, upper, value[0] == "[", value[-1] == "]")
        else:
            result[name] = value
    return result


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="datatiles")
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("file"); init.add_argument("--name"); init.add_argument("--format", default="png")
    dim = sub.add_parser("add-dimension")
    dim.add_argument("file"); dim.add_argument("name"); dim.add_argument("type", choices=["text","integer","float","datetime","boolean"])
    dim.add_argument("--axis", choices=["T","Z","E","C","O"]); dim.add_argument("--unit"); dim.add_argument("--description")
    dim.add_argument("--optional", action="store_true")
    dim.add_argument("--extent", choices=["point","interval","point_or_interval"], default="point")
    crs = sub.add_parser("add-crs")
    crs.add_argument("file"); crs.add_argument("role", choices=["horizontal","vertical","temporal","compound","engineering"])
    crs.add_argument("--authority"); crs.add_argument("--code"); crs.add_argument("--uri"); crs.add_argument("--wkt2"); crs.add_argument("--projjson")
    crs.add_argument("--coordinate-epoch", type=float)
    put = sub.add_parser("put")
    put.add_argument("file"); put.add_argument("z", type=int); put.add_argument("x", type=int); put.add_argument("y", type=int); put.add_argument("input")
    put.add_argument("--coord", action="append", default=[]); put.add_argument("--xyz", action="store_true")
    put.add_argument("--data-type", choices=["raster","vector"]); put.add_argument("--media-type"); put.add_argument("--encoding")
    put.add_argument("--schema", type=Path, help="JSON Schema or vector_layers metadata object")
    get = sub.add_parser("get")
    get.add_argument("file"); get.add_argument("z", type=int); get.add_argument("x", type=int); get.add_argument("y", type=int); get.add_argument("output")
    get.add_argument("--coord", action="append", default=[]); get.add_argument("--xyz", action="store_true")
    select = sub.add_parser("select")
    select.add_argument("file"); select.add_argument("--coord", action="append", default=[])
    export = sub.add_parser("export-mbtiles", help="materialize one compatible slice as standalone MBTiles")
    export.add_argument("file"); export.add_argument("output")
    export.add_argument("--coord", action="append", default=[], help="exact slice coordinate; otherwise use selected slice")
    contents = sub.add_parser("contents", help="list raster/vector content profiles as JSON")
    contents.add_argument("file")
    metadata = sub.add_parser("set-metadata", help="set one non-managed metadata value")
    metadata.add_argument("file"); metadata.add_argument("name"); metadata.add_argument("value")
    validate = sub.add_parser("validate"); validate.add_argument("file")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            with DataTiles(args.file, create=True, name=args.name, tile_format=args.format): pass
        elif args.command == "add-dimension":
            with DataTiles(args.file) as store:
                store.add_dimension(args.name, args.type, axis=args.axis, unit=args.unit, description=args.description,
                                    required=not args.optional, extent_kind=args.extent)
        elif args.command == "add-crs":
            with DataTiles(args.file) as store:
                store.add_crs(args.role, authority=args.authority, code=args.code, uri=args.uri,
                              wkt2=args.wkt2, projjson=args.projjson, coordinate_epoch=args.coordinate_epoch)
        elif args.command == "put":
            with DataTiles(args.file) as store:
                schema=json.loads(args.schema.read_text()) if args.schema else None
                if schema is not None and not isinstance(schema,dict): raise DataTilesError("content schema must be a JSON object")
                store.put(args.z, args.x, args.y, Path(args.input).read_bytes(), coords(args.coord), xyz=args.xyz,
                          data_type=args.data_type,media_type=args.media_type,encoding=args.encoding,schema=schema)
        elif args.command == "get":
            with DataTiles(args.file) as store:
                data = store.get(args.z, args.x, args.y, coords(args.coord), xyz=args.xyz)
                if data is None: return 2
                Path(args.output).write_bytes(data)
        elif args.command == "select":
            with DataTiles(args.file) as store: store.select(coords(args.coord))
        elif args.command == "export-mbtiles":
            with DataTiles(args.file) as store:
                store.export_mbtiles(args.output, coords(args.coord) if args.coord else None)
        elif args.command == "contents":
            with DataTiles(args.file) as store: print(json.dumps({"contents":store.content_profiles()},indent=2,ensure_ascii=False))
        elif args.command == "set-metadata":
            with DataTiles(args.file) as store: store.set_metadata(args.name,args.value)
        elif args.command == "validate":
            with DataTiles(args.file) as store: errors = store.validate()
            if errors:
                for error in errors: print(error)
                return 1
            print("valid")
        return 0
    except (DataTilesError, OSError) as exc:
        parser().error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
