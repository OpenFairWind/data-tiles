from __future__ import annotations

import datetime as dt
import hashlib
import importlib.resources
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Mapping


class DataTilesError(ValueError):
    pass


def _canonical(value_type: str, value: Any) -> tuple[str, str | None, int | None, float | None]:
    try:
        if value_type == "text":
            if value is None: raise ValueError("null is not a text coordinate")
            text = str(value)
            return text, text, None, None
        if value_type == "integer":
            if isinstance(value,bool) or isinstance(value,float) and not value.is_integer(): raise ValueError("expected an integer")
            number = int(value)
            return str(number), None, number, None
        if value_type == "float":
            if isinstance(value,bool): raise ValueError("expected a number, not boolean")
            number = float(value)
            if not (float("-inf") < number < float("inf")):
                raise ValueError("non-finite number")
            return format(number, ".17g"), None, None, number
        if value_type == "boolean":
            if isinstance(value, str):
                lowered = value.lower()
                if lowered not in {"true", "false", "1", "0"}:
                    raise ValueError("expected true/false")
                number = int(lowered in {"true", "1"})
            else:
                if value not in (True,False,0,1): raise ValueError("expected boolean or 0/1")
                number = int(bool(value))
            return ("true" if number else "false"), None, number, None
        if value_type == "datetime":
            text = str(value)
            parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("timezone is required")
            utc = parsed.astimezone(dt.timezone.utc)
            canonical = utc.isoformat(timespec="microseconds").replace("+00:00", "Z")
            return canonical, canonical, None, utc.timestamp()
    except (TypeError, ValueError) as exc:
        raise DataTilesError(f"invalid {value_type} value {value!r}: {exc}") from exc
    raise DataTilesError(f"unsupported value type: {value_type}")


class DataTiles:
    def __init__(self, path: str | Path, *, create: bool = False, name: str | None = None,
                 tile_format: str | None = None, read_only: bool = False):
        self.path = Path(path)
        if create and read_only:
            raise DataTilesError("create and read_only are mutually exclusive")
        if create and self.path.exists():
            raise DataTilesError(f"file already exists: {self.path}")
        if not create and not self.path.is_file():
            raise DataTilesError(f"file does not exist: {self.path}")
        self.db = sqlite3.connect(self.path.resolve().as_uri()+"?mode=ro", uri=True) if read_only else sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        if read_only: self.db.execute("PRAGMA query_only = ON")
        if create:
            sql = importlib.resources.files("datatiles").joinpath("schema.sql").read_text()
            self.db.executescript(sql)
            default_media,_,default_encoding=self._normalize_content(tile_format or "png",None,None)
            self.db.executemany("INSERT INTO metadata(name,value) VALUES (?,?)", [
                ("name", name or self.path.stem),
                ("format", self._mbtiles_format(default_media,default_encoding)),
                ("datatiles:default_media_type", default_media),
                ("datatiles:version", "1.0-draft"),
                ("datatiles:dimensions", "[]"),
            ])
            self.db.commit()
        else:
            try: self._check_and_migrate(read_only)
            except Exception:
                self.db.close()
                raise

    def _check_and_migrate(self, read_only: bool) -> None:
        application_id=int(self.db.execute("PRAGMA application_id").fetchone()[0])
        if application_id != 0x44415441:
            raise DataTilesError("not a DataTiles container (application_id mismatch)")
        revision=int(self.db.execute("PRAGMA user_version").fetchone()[0])
        if revision not in (2,3):
            raise DataTilesError(f"unsupported DataTiles schema revision: {revision}")
        objects={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        required={"metadata","tiles","datatiles_dimensions","datatiles_values","datatiles_coordinate_sets",
                  "datatiles_coordinates","datatiles_tiles","datatiles_selected_slice"}
        if revision==3: required.add("datatiles_contents")
        missing=required-objects
        if missing: raise DataTilesError("incomplete DataTiles schema: "+", ".join(sorted(missing)))
        if revision == 2:
            if read_only:
                raise DataTilesError("schema revision 2 requires writable migration to revision 3")
            self._migrate_v2_to_v3()

    def _migrate_v2_to_v3(self) -> None:
        metadata=dict(self.db.execute("SELECT name,value FROM metadata"))
        media,kind,encoding=self._normalize_content(metadata.get("format","application/octet-stream"),None,None)
        with self.db:
            self.db.execute("CREATE TABLE datatiles_contents (coordinate_set_id INTEGER PRIMARY KEY REFERENCES datatiles_coordinate_sets(coordinate_set_id) ON DELETE CASCADE, data_type TEXT NOT NULL CHECK(data_type IN ('raster','vector')), media_type TEXT NOT NULL, encoding TEXT NOT NULL, schema_json TEXT NOT NULL DEFAULT '{}')")
            self.db.execute("CREATE INDEX datatiles_contents_type ON datatiles_contents(data_type,media_type,encoding)")
            self.db.execute("INSERT INTO datatiles_contents SELECT coordinate_set_id,?,?,?,? FROM datatiles_coordinate_sets",
                            (kind,media,encoding,metadata.get("json","{}")))
            self.db.execute("INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:default_media_type',?)",(media,))
            for set_row in self.db.execute("SELECT coordinate_set_id FROM datatiles_coordinate_sets").fetchall():
                pairs=[[r["name"],r["canonical_value"]] for r in self.db.execute(
                    "SELECT d.name,v.canonical_value FROM datatiles_coordinates c JOIN datatiles_dimensions d USING(dimension_id) JOIN datatiles_values v USING(value_id) WHERE c.coordinate_set_id=? ORDER BY d.name",
                    (set_row[0],))]
                key=hashlib.sha256(json.dumps(pairs,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
                self.db.execute("UPDATE datatiles_coordinate_sets SET canonical_key=? WHERE coordinate_set_id=?",(key,set_row[0]))
            self.db.execute("PRAGMA user_version = 3")

    def close(self) -> None:
        self.db.close()

    def metadata(self) -> dict[str,str]:
        """Return a snapshot of the MBTiles and DataTiles metadata interface."""
        return dict(self.db.execute("SELECT name,value FROM metadata ORDER BY name"))

    def set_metadata(self, name: str, value: str) -> None:
        """Set one metadata value without bypassing container invariants."""
        if not isinstance(name,str) or not name or name.strip()!=name or any(ord(c)<32 for c in name):
            raise DataTilesError("metadata name must be a non-empty trimmed text key")
        if not isinstance(value,str): raise DataTilesError("metadata value must be text")
        if name in ("format","datatiles:dimensions","datatiles:default_media_type"):
            raise DataTilesError(f"metadata {name!r} is managed by DataTiles")
        with self.db:
            self.db.execute("INSERT INTO metadata(name,value) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(name,value))

    def __enter__(self) -> "DataTiles":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def add_dimension(self, name: str, value_type: str, *, axis: str | None = None,
                      unit: str | None = None, description: str | None = None,
                      required: bool = True, extent_kind: str = "point") -> None:
        if not name or name.strip() != name:
            raise DataTilesError("dimension name must be non-empty and trimmed")
        with self.db:
            self.db.execute(
                "INSERT INTO datatiles_dimensions(name,value_type,axis,unit,description,ordering,required,extent_kind) "
                "VALUES (?,?,?,?,?,(SELECT count(*) FROM datatiles_dimensions),?,?)",
                (name, value_type, axis, unit, description, int(required), extent_kind),
            )
            self._refresh_dimensions_metadata()

    def _refresh_dimensions_metadata(self) -> None:
        rows = self.db.execute(
            "SELECT name,value_type,axis,unit,description,required,extent_kind FROM datatiles_dimensions ORDER BY ordering,name"
        ).fetchall()
        value = json.dumps([dict(row) for row in rows], separators=(",", ":"))
        self.db.execute("UPDATE metadata SET value=? WHERE name='datatiles:dimensions'", (value,))

    def _coordinate_set(self, coordinates: Mapping[str, Any], *, create: bool) -> int | None:
        definitions = {r["name"]: r for r in self.db.execute("SELECT * FROM datatiles_dimensions")}
        unknown = set(coordinates) - set(definitions)
        if unknown:
            raise DataTilesError(f"unknown dimensions: {', '.join(sorted(unknown))}")
        required = {name for name, row in definitions.items() if row["required"]}
        missing = required - set(coordinates)
        if missing:
            raise DataTilesError(f"missing required dimensions: {', '.join(sorted(missing))}")

        members = []
        for name, value in coordinates.items():
            row = definitions[name]
            is_interval = isinstance(value, (tuple, list)) and len(value) in (2, 4)
            if row["extent_kind"] == "interval" and not is_interval:
                raise DataTilesError(f"dimension {name} requires an interval")
            if row["extent_kind"] == "point" and is_interval:
                raise DataTilesError(f"dimension {name} requires a point")
            if is_interval:
                lower, upper = value[0], value[1]
                lower_inc, upper_inc = (bool(value[2]), bool(value[3])) if len(value) == 4 else (True, True)
                lo = _canonical(row["value_type"], lower)
                hi = _canonical(row["value_type"], upper)
                lo_cmp = lo[2] if lo[2] is not None else lo[3] if lo[3] is not None else lo[1]
                hi_cmp = hi[2] if hi[2] is not None else hi[3] if hi[3] is not None else hi[1]
                if lo_cmp is not None and hi_cmp is not None and (lo_cmp > hi_cmp or (lo_cmp == hi_cmp and not (lower_inc and upper_inc))):
                    raise DataTilesError(f"interval is empty or lower bound exceeds upper bound for {name}")
                canonical = f"{'[' if lower_inc else '('}{lo[0]},{hi[0]}{']' if upper_inc else ')'}"
                typed = (canonical, lo, hi, lower_inc, upper_inc, True)
            else:
                point = _canonical(row["value_type"], value)
                typed = (point[0], point, None, True, True, False)
            members.append((row["dimension_id"], name, typed))
        members.sort(key=lambda item:item[1])
        serial = json.dumps([[name, typed[0]] for _, name, typed in members], separators=(",", ":"), ensure_ascii=False)
        key = hashlib.sha256(serial.encode()).hexdigest()
        found = self.db.execute("SELECT coordinate_set_id FROM datatiles_coordinate_sets WHERE canonical_key=?", (key,)).fetchone()
        if found or not create:
            return found[0] if found else None
        cursor = self.db.execute("INSERT INTO datatiles_coordinate_sets(canonical_key) VALUES (?)", (key,))
        set_id = cursor.lastrowid
        for dimension_id, _, typed in members:
            canonical, lower, upper, lower_inc, upper_inc, is_interval = typed
            _, text_value, integer_value, float_value = lower
            upper_text = upper[1] if upper else None
            upper_integer = upper[2] if upper else None
            upper_float = upper[3] if upper else None
            self.db.execute(
                "INSERT OR IGNORE INTO datatiles_values(dimension_id,canonical_value,text_value,integer_value,float_value,"
                "upper_canonical_value,upper_text_value,upper_integer_value,upper_float_value,lower_inclusive,upper_inclusive,is_interval) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (dimension_id, canonical, text_value, integer_value, float_value,
                 upper[0] if upper else None, upper_text, upper_integer, upper_float,
                 int(lower_inc), int(upper_inc), int(is_interval)),
            )
            value_id = self.db.execute(
                "SELECT value_id FROM datatiles_values WHERE dimension_id=? AND canonical_value=?",
                (dimension_id, canonical),
            ).fetchone()[0]
            self.db.execute("INSERT INTO datatiles_coordinates VALUES (?,?,?)", (set_id, dimension_id, value_id))
        return set_id

    @staticmethod
    def _normalize_content(media_type: str, data_type: str | None, encoding: str | None) -> tuple[str,str,str]:
        original=media_type.lower()
        aliases={"png":"image/png","jpg":"image/jpeg","jpeg":"image/jpeg","webp":"image/webp",
                 "pbf":"application/vnd.mapbox-vector-tile","mvt":"application/vnd.mapbox-vector-tile"}
        media=aliases.get(media_type.lower(),media_type.lower())
        if "/" not in media: media="application/octet-stream"
        inferred="vector" if media in ("application/vnd.mapbox-vector-tile","application/geo+json") else "raster"
        kind=data_type or inferred
        if kind not in ("raster","vector"): raise DataTilesError("data_type must be raster or vector")
        if data_type and data_type != inferred and media.startswith("image/"):
            raise DataTilesError("image media types require raster data_type")
        default_encoding=("MVT+gzip" if original=="pbf" else "MVT" if media=="application/vnd.mapbox-vector-tile" else "GeoJSON" if media=="application/geo+json"
                          else "DNT1" if media=="application/vnd.datatiles.numeric" else media.rsplit("/",1)[-1].upper())
        return media,kind,encoding or default_encoding

    @staticmethod
    def _mbtiles_format(media_type: str, encoding: str) -> str:
        if media_type=="application/vnd.mapbox-vector-tile" and encoding.lower() in ("mvt+gzip","gzip+mvt"): return "pbf"
        return {"image/png":"png","image/jpeg":"jpg","image/webp":"webp"}.get(media_type,media_type)

    def _ensure_content(self, coordinate_set_id: int, *, media_type: str | None=None,
                        data_type: str | None=None, encoding: str | None=None,
                        schema: Mapping[str,Any] | None=None) -> None:
        existing=self.db.execute("SELECT * FROM datatiles_contents WHERE coordinate_set_id=?",(coordinate_set_id,)).fetchone()
        default=dict(self.db.execute("SELECT name,value FROM metadata")).get("datatiles:default_media_type",
                    dict(self.db.execute("SELECT name,value FROM metadata")).get("format","application/octet-stream"))
        media,kind,codec=self._normalize_content(media_type or default,data_type,encoding)
        try: schema_text=json.dumps(schema or {},sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
        except (TypeError,ValueError) as exc: raise DataTilesError(f"content schema is not finite JSON: {exc}") from exc
        if existing:
            conflicts=((data_type is not None and kind!=existing["data_type"]) or
                       (media_type is not None and media!=existing["media_type"]) or
                       (encoding is not None and codec!=existing["encoding"]) or
                       (schema is not None and schema_text!=existing["schema_json"]))
            if conflicts:
                raise DataTilesError("content profile conflicts with the existing coordinate set")
            return
        self.db.execute("INSERT INTO datatiles_contents VALUES (?,?,?,?,?)",(coordinate_set_id,kind,media,codec,schema_text))

    def content_profile(self, coordinate_set_id: int) -> dict[str,Any]:
        row=self.db.execute("SELECT data_type,media_type,encoding,schema_json FROM datatiles_contents WHERE coordinate_set_id=?",(coordinate_set_id,)).fetchone()
        if row is None: raise DataTilesError("coordinate set has no content profile")
        result=dict(row)
        try: result["schema"]=json.loads(result.pop("schema_json"))
        except json.JSONDecodeError as exc: raise DataTilesError("invalid content schema JSON") from exc
        return result

    def content_profiles(self) -> list[dict[str,Any]]:
        result=[]
        for row in self.db.execute("SELECT coordinate_set_id,data_type,media_type,encoding,schema_json FROM datatiles_contents ORDER BY coordinate_set_id"):
            item=dict(row); item["coordinates"]=self.coordinate_set_values(item["coordinate_set_id"])
            try: item["schema"]=json.loads(item.pop("schema_json"))
            except json.JSONDecodeError as exc: raise DataTilesError(f"invalid content schema JSON: {item['coordinate_set_id']}") from exc
            result.append(item)
        return result

    def add_crs(self, role: str, *, authority: str | None = None, code: str | None = None,
                uri: str | None = None, wkt2: str | None = None, projjson: str | None = None,
                coordinate_epoch: float | None = None) -> int:
        if not any((uri, wkt2, projjson, authority and code)):
            raise DataTilesError("CRS requires an authority/code, URI, WKT2, or PROJJSON")
        with self.db:
            cur = self.db.execute(
                "INSERT INTO datatiles_crs(role,authority,code,uri,wkt2,projjson,coordinate_epoch) VALUES (?,?,?,?,?,?,?)",
                (role, authority, code, uri, wkt2, projjson, coordinate_epoch),
            )
            return int(cur.lastrowid)

    def add_provenance_entity(self, entity_id: str, entity_type: str, label: str, *,
                              uri: str | None = None, checksum_algorithm: str | None = None,
                              checksum: str | None = None, attributes: Mapping[str, Any] | None = None) -> None:
        with self.db:
            self.db.execute("INSERT INTO datatiles_provenance_entities VALUES (?,?,?,?,?,?,?)",
                            (entity_id, entity_type, label, uri, checksum_algorithm, checksum,
                             json.dumps(attributes or {}, separators=(",", ":"))))

    def add_provenance_agent(self, agent_id: str, label: str, *, agent_type: str = "organization",
                             uri: str | None = None, attributes: Mapping[str, Any] | None = None) -> None:
        with self.db:
            self.db.execute("INSERT INTO datatiles_provenance_agents VALUES (?,?,?,?,?)",
                            (agent_id, agent_type, label, uri,
                             json.dumps(attributes or {}, separators=(",", ":"))))

    def add_provenance_activity(self, activity_id: str, activity_type: str, label: str, *,
                                started_at: str | None = None, ended_at: str | None = None,
                                software: str | None = None, parameters: Mapping[str, Any] | None = None) -> None:
        with self.db:
            self.db.execute("INSERT INTO datatiles_provenance_activities VALUES (?,?,?,?,?,?,?)",
                            (activity_id, activity_type, label, started_at, ended_at, software,
                             json.dumps(parameters or {}, separators=(",", ":"))))

    def add_provenance_relation(self, subject_id: str, predicate: str, object_id: str,
                                attributes: Mapping[str, Any] | None = None) -> None:
        with self.db:
            self.db.execute("INSERT INTO datatiles_provenance_relations VALUES (?,?,?,?)",
                            (subject_id, predicate, object_id,
                             json.dumps(attributes or {}, separators=(",", ":"))))

    def link_tile_provenance(self, z: int, x: int, y: int, coordinates: Mapping[str, Any], entity_id: str,
                             *, xyz: bool = False) -> None:
        y = self.tms_row(z, y, xyz)
        set_id = self._coordinate_set(coordinates, create=False)
        if set_id is None:
            raise DataTilesError("coordinate set does not exist")
        with self.db:
            self.db.execute("INSERT INTO datatiles_tile_provenance VALUES (?,?,?,?,?)", (z, x, y, set_id, entity_id))

    @staticmethod
    def tms_row(z: int, row: int, xyz: bool) -> int:
        if not isinstance(z,int) or isinstance(z,bool) or not 0<=z<=30 or not isinstance(row,int) or isinstance(row,bool) or row < 0 or row >= 2**z:
            raise DataTilesError("tile coordinate outside zoom matrix")
        return 2**z - 1 - row if xyz else row

    def put(self, z: int, x: int, y: int, data: bytes, coordinates: Mapping[str, Any], *, xyz: bool = False,
            data_type: str | None=None, media_type: str | None=None, encoding: str | None=None,
            schema: Mapping[str,Any] | None=None) -> None:
        if not isinstance(x,int) or isinstance(x,bool) or not 0<=z<=30 or x < 0 or x >= 2**z:
            raise DataTilesError("tile coordinate outside zoom matrix")
        if not isinstance(data,(bytes,bytearray,memoryview)): raise DataTilesError("tile data must be bytes-like")
        y = self.tms_row(z, y, xyz)
        with self.db:
            set_id = self._coordinate_set(coordinates, create=True)
            self._ensure_content(set_id,data_type=data_type,media_type=media_type,encoding=encoding,schema=schema)
            self.db.execute(
                "INSERT INTO datatiles_tiles VALUES (?,?,?,?,?) ON CONFLICT DO UPDATE SET tile_data=excluded.tile_data",
                (z, x, y, set_id, sqlite3.Binary(data)),
            )

    def get(self, z: int, x: int, y: int, coordinates: Mapping[str, Any], *, xyz: bool = False) -> bytes | None:
        y = self.tms_row(z, y, xyz)
        set_id = self._coordinate_set(coordinates, create=False)
        if set_id is None:
            return None
        row = self.db.execute(
            "SELECT tile_data FROM datatiles_tiles WHERE zoom_level=? AND tile_column=? AND tile_row=? AND coordinate_set_id=?",
            (z, x, y, set_id),
        ).fetchone()
        return bytes(row[0]) if row else None

    def find_coordinate_sets(self, coordinates: Mapping[str, Any]) -> list[int]:
        """Find coordinate sets containing all supplied point coordinates."""
        candidates: set[int] | None = None
        definitions = {r["name"]: r for r in self.db.execute("SELECT * FROM datatiles_dimensions")}
        unknown = set(coordinates) - set(definitions)
        if unknown:
            raise DataTilesError(f"unknown dimensions: {', '.join(sorted(unknown))}")
        for name, value in coordinates.items():
            if isinstance(value, (tuple, list)):
                raise DataTilesError("partial coordinate-set discovery currently accepts point values only")
            canonical = _canonical(definitions[name]["value_type"], value)[0]
            rows = self.db.execute(
                "SELECT c.coordinate_set_id FROM datatiles_coordinates c "
                "JOIN datatiles_dimensions d ON d.dimension_id=c.dimension_id "
                "JOIN datatiles_values v ON v.value_id=c.value_id "
                "WHERE d.name=? AND v.canonical_value=?",
                (name, canonical),
            ).fetchall()
            current = {int(row[0]) for row in rows}
            candidates = current if candidates is None else candidates & current
        if candidates is None:
            candidates = {int(row[0]) for row in self.db.execute("SELECT coordinate_set_id FROM datatiles_coordinate_sets")}
        return sorted(candidates)

    def coordinate_set_values(self, coordinate_set_id: int) -> dict[str, str]:
        return {row["name"]: row["canonical_value"] for row in self.db.execute(
            "SELECT d.name,v.canonical_value FROM datatiles_coordinates c "
            "JOIN datatiles_dimensions d ON d.dimension_id=c.dimension_id "
            "JOIN datatiles_values v ON v.value_id=c.value_id "
            "WHERE c.coordinate_set_id=? ORDER BY d.ordering,d.name", (coordinate_set_id,))}

    def get_by_coordinate_set(self, z: int, x: int, y: int, coordinate_set_id: int, *, xyz: bool = False) -> bytes | None:
        y = self.tms_row(z, y, xyz)
        row = self.db.execute(
            "SELECT tile_data FROM datatiles_tiles WHERE zoom_level=? AND tile_column=? AND tile_row=? AND coordinate_set_id=?",
            (z, x, y, coordinate_set_id),
        ).fetchone()
        return bytes(row[0]) if row else None

    def select(self, coordinates: Mapping[str, Any]) -> None:
        set_id = self._coordinate_set(coordinates, create=False)
        if set_id is None:
            raise DataTilesError("coordinate set does not exist")
        with self.db:
            self.db.execute("UPDATE datatiles_selected_slice SET coordinate_set_id=? WHERE singleton=1", (set_id,))
            profile=self.content_profile(set_id)
            mbformat=self._mbtiles_format(profile["media_type"],profile["encoding"])
            self.db.execute("INSERT INTO metadata(name,value) VALUES ('format',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(mbformat,))
            if profile["media_type"]=="application/vnd.mapbox-vector-tile":
                vector_json=profile["schema"] if "vector_layers" in profile["schema"] else {"vector_layers":profile["schema"].get("layers",[])}
                self.db.execute("INSERT INTO metadata(name,value) VALUES ('json',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                                (json.dumps(vector_json,sort_keys=True,separators=(",",":")),))
            else:
                self.db.execute("DELETE FROM metadata WHERE name='json'")

    def export_mbtiles(self, target: str | Path, coordinates: Mapping[str, Any] | None = None) -> Path:
        """Materialize one representable DataTiles slice as a standalone MBTiles file.

        The export deliberately contains physical ``metadata`` and ``tiles`` tables
        and no DataTiles extension objects. This supports conservative MBTiles
        adapters which reject views or unknown application identifiers.
        """
        target = Path(target)
        if target.exists():
            raise DataTilesError(f"export target already exists: {target}")
        if coordinates is None:
            selected = self.db.execute(
                "SELECT coordinate_set_id FROM datatiles_selected_slice WHERE singleton=1"
            ).fetchone()
            set_id = int(selected[0]) if selected and selected[0] is not None else None
            if set_id is None:
                raise DataTilesError("no selected slice; supply coordinates or select a slice first")
        else:
            set_id = self._coordinate_set(coordinates, create=False)
            if set_id is None:
                raise DataTilesError("coordinate set does not exist")

        profile = self.content_profile(set_id)
        mbformat = self._mbtiles_format(profile["media_type"], profile["encoding"])
        compatible = {"png", "jpg", "webp", "pbf"}
        if mbformat not in compatible:
            raise DataTilesError(
                "selected content is not directly representable by MBTiles; "
                "create a PNG/JPEG/WebP portrayal or gzip MVT slice first"
            )

        source_metadata = self.metadata()
        exported = {
            key: value for key, value in source_metadata.items()
            if key in {"name", "bounds", "center", "attribution", "description", "type", "version"}
        }
        exported["format"] = mbformat
        if mbformat == "pbf":
            schema = profile["schema"]
            vector_json = schema if "vector_layers" in schema else {"vector_layers": schema.get("layers", [])}
            exported["json"] = json.dumps(vector_json, sort_keys=True, separators=(",", ":"))

        zooms = self.db.execute(
            "SELECT min(zoom_level),max(zoom_level) FROM datatiles_tiles WHERE coordinate_set_id=?", (set_id,)
        ).fetchone()
        if zooms[0] is None:
            raise DataTilesError("selected slice contains no tiles")
        exported["minzoom"], exported["maxzoom"] = str(zooms[0]), str(zooms[1])

        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        os.close(descriptor)
        temporary = Path(temporary_name)
        output: sqlite3.Connection | None = None
        try:
            output = sqlite3.connect(temporary)
            output.executescript(
                "CREATE TABLE metadata (name TEXT NOT NULL, value TEXT NOT NULL);"
                "CREATE UNIQUE INDEX metadata_name ON metadata(name);"
                "CREATE TABLE tiles (zoom_level INTEGER NOT NULL, tile_column INTEGER NOT NULL, "
                "tile_row INTEGER NOT NULL, tile_data BLOB NOT NULL);"
                "CREATE UNIQUE INDEX tile_index ON tiles(zoom_level,tile_column,tile_row);"
            )
            output.executemany("INSERT INTO metadata(name,value) VALUES (?,?)", sorted(exported.items()))
            rows = self.db.execute(
                "SELECT zoom_level,tile_column,tile_row,tile_data FROM datatiles_tiles "
                "WHERE coordinate_set_id=? ORDER BY zoom_level,tile_column,tile_row", (set_id,)
            )
            output.executemany("INSERT INTO tiles VALUES (?,?,?,?)", rows)
            output.commit()
            if output.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise DataTilesError("exported MBTiles failed SQLite integrity check")
            output.execute("VACUUM")
            output.close()
            try:
                os.link(temporary, target)
            except FileExistsError as exc:
                raise DataTilesError(f"export target already exists: {target}") from exc
            temporary.unlink()
            return target
        except Exception:
            if output is not None:
                output.close()
            temporary.unlink(missing_ok=True)
            raise

    def validate(self) -> list[str]:
        errors: list[str] = []
        metadata_columns=[row[1] for row in self.db.execute("PRAGMA table_info(metadata)")]
        tiles_columns=[row[1] for row in self.db.execute("PRAGMA table_info(tiles)")]
        if metadata_columns != ["name","value"]: errors.append("metadata interface must have exactly name,value columns")
        if tiles_columns != ["zoom_level","tile_column","tile_row","tile_data"]: errors.append("tiles interface must have exactly four MBTiles columns")
        for key in ("name", "format"):
            if not self.db.execute("SELECT 1 FROM metadata WHERE name=?", (key,)).fetchone():
                errors.append(f"missing metadata: {key}")
        integrity = self.db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            errors.append(f"SQLite integrity: {integrity}")
        fk = self.db.execute("PRAGMA foreign_key_check").fetchall()
        if fk:
            errors.append(f"foreign-key violations: {len(fk)}")
        if int(self.db.execute("PRAGMA application_id").fetchone()[0]) != 0x44415441: errors.append("invalid DataTiles application_id")
        if int(self.db.execute("PRAGMA user_version").fetchone()[0]) != 3: errors.append("unsupported schema revision")
        missing_profiles=self.db.execute("SELECT count(*) FROM datatiles_coordinate_sets s WHERE EXISTS (SELECT 1 FROM datatiles_tiles t WHERE t.coordinate_set_id=s.coordinate_set_id) AND NOT EXISTS (SELECT 1 FROM datatiles_contents c WHERE c.coordinate_set_id=s.coordinate_set_id)").fetchone()[0]
        if missing_profiles: errors.append(f"coordinate sets missing content profiles: {missing_profiles}")
        for set_row in self.db.execute("SELECT coordinate_set_id,canonical_key FROM datatiles_coordinate_sets"):
            pairs=[[r["name"],r["canonical_value"]] for r in self.db.execute(
                "SELECT d.name,v.canonical_value FROM datatiles_coordinates c JOIN datatiles_dimensions d USING(dimension_id) JOIN datatiles_values v USING(value_id) WHERE c.coordinate_set_id=? ORDER BY d.dimension_id",
                (set_row["coordinate_set_id"],))]
            expected=hashlib.sha256(json.dumps(sorted(pairs),separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
            if expected!=set_row["canonical_key"]: errors.append(f"coordinate-set canonical key mismatch: {set_row['coordinate_set_id']}")
        for row in self.db.execute("SELECT coordinate_set_id,schema_json FROM datatiles_contents"):
            try:
                value=json.loads(row["schema_json"])
                if not isinstance(value,dict): raise ValueError
                profile=self.db.execute("SELECT data_type,media_type FROM datatiles_contents WHERE coordinate_set_id=?",(row["coordinate_set_id"],)).fetchone()
                if profile["data_type"]=="vector" and profile["media_type"]=="application/vnd.mapbox-vector-tile":
                    layers=value.get("vector_layers")
                    if not isinstance(layers,list) or any(not isinstance(layer,dict) or not isinstance(layer.get("id"),str) or not isinstance(layer.get("fields"),dict) for layer in layers):
                        errors.append(f"invalid MVT vector_layers schema: {row['coordinate_set_id']}")
            except (json.JSONDecodeError,ValueError): errors.append(f"invalid content schema JSON: {row['coordinate_set_id']}")
        for row in self.db.execute("SELECT c.coordinate_set_id,c.data_type,c.media_type,c.encoding,c.schema_json,t.tile_data FROM datatiles_contents c JOIN datatiles_tiles t USING(coordinate_set_id)"):
            encoding=row["encoding"].lower(); blob=bytes(row["tile_data"])
            if len(blob)>67_108_864: errors.append(f"tile exceeds 64 MiB validation limit: {row['coordinate_set_id']}")
            if "/" not in row["media_type"]: errors.append(f"invalid media type: {row['coordinate_set_id']}")
            if row["data_type"]=="vector" and encoding in ("mvt+gzip","gzip+mvt") and not blob.startswith(b"\x1f\x8b"):
                errors.append(f"vector tile is not gzip encoded: {row['coordinate_set_id']}")
            if encoding=="dnt1":
                try:
                    from .numeric import decode_numeric_tile
                    decode_numeric_tile(blob)
                except ValueError as exc: errors.append(f"invalid DNT1 tile {row['coordinate_set_id']}: {exc}")
            if encoding=="geojson":
                try:
                    value=json.loads(blob)
                    if not isinstance(value,dict) or value.get("type") not in ("FeatureCollection","Feature"): raise ValueError
                except (UnicodeDecodeError,json.JSONDecodeError,ValueError): errors.append(f"invalid GeoJSON tile: {row['coordinate_set_id']}")
        selected=self.db.execute("SELECT coordinate_set_id FROM datatiles_selected_slice WHERE singleton=1").fetchone()
        if selected is None: errors.append("selected-slice singleton is missing")
        elif selected[0] is not None:
            try:
                profile=self.content_profile(int(selected[0])); metadata_now=dict(self.db.execute("SELECT name,value FROM metadata"))
                expected_format=self._mbtiles_format(profile["media_type"],profile["encoding"])
                if metadata_now.get("format")!=expected_format: errors.append("selected content profile disagrees with MBTiles format metadata")
                if profile["media_type"]=="application/vnd.mapbox-vector-tile" and "json" not in metadata_now: errors.append("selected MVT slice lacks MBTiles json metadata")
                if profile["media_type"]!="application/vnd.mapbox-vector-tile" and "json" in metadata_now: errors.append("selected non-MVT slice retains stale vector json metadata")
            except DataTilesError as exc: errors.append(str(exc))
        bad = self.db.execute(
            "SELECT count(*) FROM datatiles_tiles WHERE zoom_level NOT BETWEEN 0 AND 30 OR (zoom_level BETWEEN 0 AND 30 AND (tile_column >= (1 << zoom_level) OR tile_row >= (1 << zoom_level)))"
        ).fetchone()[0]
        if bad:
            errors.append(f"out-of-range spatial coordinates: {bad}")
        metadata=dict(self.db.execute("SELECT name,value FROM metadata"))
        if metadata.get("datatiles:fair_profile") == "1":
            required=("datatiles:identifier","datatiles:license","datatiles:access_rights","datatiles:creators",
                      "datatiles:keywords","datatiles:issued","datatiles:modified","datatiles:landing_page")
            errors.extend(f"missing FAIR metadata: {key}" for key in required if not metadata.get(key))
            if not self.db.execute("SELECT 1 FROM datatiles_provenance_entities LIMIT 1").fetchone(): errors.append("missing FAIR provenance entities")
            if not self.db.execute("SELECT 1 FROM datatiles_provenance_activities LIMIT 1").fetchone(): errors.append("missing FAIR provenance activities")
            if not self.db.execute("SELECT 1 FROM datatiles_crs WHERE role='horizontal' LIMIT 1").fetchone(): errors.append("missing FAIR horizontal CRS")
        return errors

    def fair_report(self) -> dict[str, Any]:
        metadata=self.metadata(); validation=self.validate()
        checks={
            "persistent_identifier":bool(metadata.get("datatiles:identifier")),
            "rich_metadata":bool(metadata.get("description") and metadata.get("datatiles:keywords")),
            "standard_access":bool(metadata.get("datatiles:landing_page")),
            "formal_semantics":bool(self.db.execute("SELECT 1 FROM datatiles_dimensions LIMIT 1").fetchone()),
            "qualified_provenance":bool(self.db.execute("SELECT 1 FROM datatiles_provenance_relations LIMIT 1").fetchone()),
            "explicit_license":bool(metadata.get("datatiles:license")),
            "community_crs":bool(self.db.execute("SELECT 1 FROM datatiles_crs LIMIT 1").fetchone()),
        }
        return {"profile":"DataTiles FAIR-by-design 1.0-draft","declared":metadata.get("datatiles:fair_profile")=="1",
                "checks":checks,"container_validation":validation,"passes":all(checks.values()) and not validation,
                "caveat":"Catalogue registration, PID resolution, and metadata-retention policy require repository-level verification."}
