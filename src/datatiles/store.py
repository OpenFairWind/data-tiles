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
                ("datatiles:variable_semantics", "recommended"),
                ("datatiles:fair_profile", "FAIR-Guiding-Principles-2016"),
                ("datatiles:provenance_profile", "W3C-PROV-2013"),
                ("datatiles:metadata_profile", "DataCite-4.7"),
                ("datatiles:license_profile", "SPDX-3.0.1-expression"),
                ("datatiles:integrity_profile", "DataTiles-Integrity-Manifest-1"),
                ("datatiles:signature_profile", "DataTiles-Ed25519-Signature-1"),
                ("datatiles:drm_profile", "DataTiles-Protected-Distribution-1"),
                ("datatiles:rights_policy_profile", "W3C-ODRL-2.2"),
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
        if revision not in (2,3,4,5,6,7,8):
            raise DataTilesError(f"unsupported DataTiles schema revision: {revision}")
        objects={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        required={"metadata","tiles","datatiles_dimensions","datatiles_values","datatiles_coordinate_sets",
                  "datatiles_coordinates","datatiles_tiles","datatiles_selected_slice"}
        if revision>=3: required.add("datatiles_contents")
        if revision>=4: required.update({"datatiles_variables","datatiles_variable_identifiers"})
        if revision>=5: required.update({"datatiles_identifiers","datatiles_related_identifiers","datatiles_rights","datatiles_fair_agents","datatiles_publication_evidence"})
        if revision>=6: required.update({"datatiles_integrity_manifests","datatiles_signatures"})
        if revision>=7: required.update({"datatiles_commercial_products","datatiles_drm_policies"})
        if revision==8: required.add("datatiles_release")
        missing=required-objects
        if missing: raise DataTilesError("incomplete DataTiles schema: "+", ".join(sorted(missing)))
        if revision == 2:
            if read_only:
                raise DataTilesError("schema revision 2 requires writable migration to revision 4")
            self._migrate_v2_to_v3(); revision = 3
        if revision == 3:
            if read_only:
                raise DataTilesError("schema revision 3 requires writable migration to revision 4")
            self._migrate_v3_to_v4(); revision = 4
        if revision == 4:
            if read_only:
                raise DataTilesError("schema revision 4 requires writable migration to revision 5")
            self._migrate_v4_to_v5(); revision = 5
        if revision == 5:
            if read_only:
                raise DataTilesError("schema revision 5 requires writable migration to revision 6")
            self._migrate_v5_to_v6(); revision = 6
        if revision == 6:
            if read_only:
                raise DataTilesError("schema revision 6 requires writable migration to revision 7")
            self._migrate_v6_to_v7(); revision = 7
        if revision == 7:
            if read_only:
                raise DataTilesError("schema revision 7 requires writable migration to revision 8")
            self._migrate_v7_to_v8()

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

    def _migrate_v3_to_v4(self) -> None:
        with self.db:
            self.db.executescript("""
                CREATE TABLE datatiles_variables (
                  variable_id INTEGER PRIMARY KEY,
                  name TEXT NOT NULL UNIQUE,
                  standard_name TEXT NOT NULL,
                  standard_name_vocabulary TEXT NOT NULL DEFAULT 'CF',
                  standard_name_vocabulary_version TEXT,
                  canonical_unit TEXT,
                  long_name TEXT,
                  description TEXT,
                  CHECK(name <> '' AND trim(name) = name),
                  CHECK(standard_name <> '' AND trim(standard_name) = standard_name)
                );
                CREATE INDEX datatiles_variables_standard_name
                  ON datatiles_variables(standard_name_vocabulary, standard_name);
                CREATE TABLE datatiles_variable_identifiers (
                  variable_id INTEGER NOT NULL REFERENCES datatiles_variables(variable_id) ON DELETE CASCADE,
                  scheme TEXT NOT NULL,
                  identifier TEXT NOT NULL,
                  scheme_version TEXT,
                  uri TEXT,
                  PRIMARY KEY(variable_id, scheme, identifier),
                  UNIQUE(scheme, identifier),
                  CHECK(scheme <> '' AND trim(scheme) = scheme),
                  CHECK(identifier <> '' AND trim(identifier) = identifier)
                ) WITHOUT ROWID;
            """)
            self.db.execute("INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:variable_semantics','recommended')")
            self.db.execute("PRAGMA user_version = 4")

    def _migrate_v4_to_v5(self) -> None:
        sql = (Path(__file__).with_name("migration_v4_to_v5.sql").read_text() if Path(__file__).with_name("migration_v4_to_v5.sql").exists() else None)
        if sql is None:
            sql = """
CREATE TABLE datatiles_identifiers (identifier_id INTEGER PRIMARY KEY,scheme TEXT NOT NULL,identifier TEXT NOT NULL,uri TEXT,is_primary INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0,1)),UNIQUE(scheme,identifier));
CREATE UNIQUE INDEX datatiles_one_primary_identifier ON datatiles_identifiers(is_primary) WHERE is_primary=1;
CREATE TABLE datatiles_related_identifiers (scheme TEXT NOT NULL,identifier TEXT NOT NULL,relation_type TEXT NOT NULL,uri TEXT,resource_type TEXT,relation_information TEXT,PRIMARY KEY(scheme,identifier,relation_type)) WITHOUT ROWID;
CREATE TABLE datatiles_rights (rights_id INTEGER PRIMARY KEY,scope TEXT NOT NULL CHECK(scope IN ('dataset','metadata','source','portrayal','software','other')),license_expression TEXT NOT NULL,license_uri TEXT,rights_holder TEXT,rights_holder_uri TEXT,attribution_text TEXT,copyright_notice TEXT,access_rights TEXT NOT NULL DEFAULT 'open' CHECK(access_rights IN ('open','embargoed','restricted','closed')),source_entity_id TEXT REFERENCES datatiles_provenance_entities(entity_id) ON DELETE CASCADE,applies_to TEXT,UNIQUE(scope,source_entity_id,license_expression,applies_to));
CREATE INDEX datatiles_rights_scope ON datatiles_rights(scope,access_rights);
CREATE TABLE datatiles_fair_agents (agent_id TEXT NOT NULL REFERENCES datatiles_provenance_agents(agent_id) ON DELETE CASCADE,role TEXT NOT NULL,sequence INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(agent_id,role)) WITHOUT ROWID;
CREATE TABLE datatiles_publication_evidence (evidence_type TEXT NOT NULL,uri TEXT NOT NULL,checked_at TEXT,checksum_algorithm TEXT,checksum TEXT,notes TEXT,PRIMARY KEY(evidence_type,uri)) WITHOUT ROWID;
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:fair_profile','FAIR-Guiding-Principles-2016');
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:provenance_profile','W3C-PROV-2013');
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:metadata_profile','DataCite-4.7');
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:license_profile','SPDX-3.0.1-expression');
PRAGMA user_version = 5;
"""
        with self.db: self.db.executescript(sql)

    def _migrate_v5_to_v6(self) -> None:
        sql = (Path(__file__).with_name("migration_v5_to_v6.sql").read_text() if Path(__file__).with_name("migration_v5_to_v6.sql").exists() else None)
        if sql is None:
            sql = """
CREATE TABLE datatiles_integrity_manifests (manifest_id TEXT PRIMARY KEY,profile TEXT NOT NULL,canonicalization TEXT NOT NULL,hash_algorithm TEXT NOT NULL CHECK(hash_algorithm='sha256'),root_sha256 TEXT NOT NULL UNIQUE CHECK(length(root_sha256)=64),manifest_json TEXT NOT NULL,created_at TEXT NOT NULL) WITHOUT ROWID;
CREATE TABLE datatiles_signatures (signature_id TEXT PRIMARY KEY,manifest_id TEXT NOT NULL REFERENCES datatiles_integrity_manifests(manifest_id) ON DELETE CASCADE,signature_scheme TEXT NOT NULL,signature_encoding TEXT NOT NULL,signature BLOB NOT NULL,key_id TEXT NOT NULL,public_key BLOB,signer_agent_id TEXT REFERENCES datatiles_provenance_agents(agent_id) ON DELETE SET NULL,signed_at TEXT NOT NULL,verification_material_json TEXT,UNIQUE(manifest_id,signature_scheme,key_id,signature)) WITHOUT ROWID;
CREATE INDEX datatiles_signatures_manifest ON datatiles_signatures(manifest_id);
CREATE INDEX datatiles_signatures_key ON datatiles_signatures(key_id);
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:integrity_profile','DataTiles-Integrity-Manifest-1');
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:signature_profile','DataTiles-Ed25519-Signature-1');
PRAGMA user_version = 6;
"""
        with self.db: self.db.executescript(sql)

    def _migrate_v6_to_v7(self) -> None:
        sql = (Path(__file__).with_name("migration_v6_to_v7.sql").read_text() if Path(__file__).with_name("migration_v6_to_v7.sql").exists() else None)
        if sql is None:
            sql = """
CREATE TABLE datatiles_commercial_products (product_id TEXT PRIMARY KEY,edition TEXT,issuer TEXT NOT NULL,issuer_uri TEXT,terms_uri TEXT NOT NULL,license_service_uri TEXT,protection_profile TEXT NOT NULL DEFAULT 'DataTiles-Protected-Distribution-1',created_at TEXT NOT NULL,metadata_json TEXT) WITHOUT ROWID;
CREATE TABLE datatiles_drm_policies (product_id TEXT NOT NULL REFERENCES datatiles_commercial_products(product_id) ON DELETE CASCADE,policy_id TEXT NOT NULL,policy_profile TEXT NOT NULL DEFAULT 'W3C-ODRL-2.2',policy_json TEXT NOT NULL,PRIMARY KEY(product_id,policy_id)) WITHOUT ROWID;
CREATE INDEX datatiles_drm_policy_product ON datatiles_drm_policies(product_id);
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:drm_profile','DataTiles-Protected-Distribution-1');
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:rights_policy_profile','W3C-ODRL-2.2');
PRAGMA user_version = 7;
"""
        with self.db: self.db.executescript(sql)

    def _migrate_v7_to_v8(self) -> None:
        sql = (Path(__file__).with_name("migration_v7_to_v8.sql").read_text() if Path(__file__).with_name("migration_v7_to_v8.sql").exists() else None)
        if sql is None:
            sql = "CREATE TABLE datatiles_release (singleton INTEGER PRIMARY KEY CHECK(singleton=1),product_id TEXT NOT NULL,version TEXT NOT NULL,sequence INTEGER NOT NULL CHECK(sequence>=1),released_at TEXT NOT NULL,previous_version TEXT,previous_identifier TEXT,release_notes_uri TEXT,update_uri TEXT); INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:versioning_profile','DataTiles-Release-Versioning-1'); PRAGMA user_version=8;"
        with self.db: self.db.executescript(sql)

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
            if name == "variable" and not is_interval:
                policy = dict(self.db.execute("SELECT name,value FROM metadata")).get("datatiles:variable_semantics", "recommended")
                if policy == "required" and not self.db.execute("SELECT 1 FROM datatiles_variables WHERE name=?", (typed[0],)).fetchone():
                    raise DataTilesError(f"unregistered variable coordinate: {typed[0]}")
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

    def set_variable_semantics(self, policy: str) -> None:
        if policy not in ("required", "recommended"):
            raise DataTilesError("variable semantics policy must be required or recommended")
        with self.db:
            self.db.execute("INSERT INTO metadata(name,value) VALUES ('datatiles:variable_semantics',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value", (policy,))

    def add_variable(self, name: str, standard_name: str, *, vocabulary: str = "CF",
                     vocabulary_version: str | None = None, canonical_unit: str | None = None,
                     long_name: str | None = None, description: str | None = None) -> int:
        from .semantic import validate_standard_name_syntax, SemanticValidationError
        if not name or name.strip() != name:
            raise DataTilesError("variable name must be non-empty and trimmed")
        if not vocabulary or vocabulary.strip() != vocabulary:
            raise DataTilesError("variable vocabulary must be non-empty and trimmed")
        try:
            validate_standard_name_syntax(standard_name)
        except SemanticValidationError as exc:
            raise DataTilesError(str(exc)) from exc
        with self.db:
            cur = self.db.execute(
                "INSERT INTO datatiles_variables(name,standard_name,standard_name_vocabulary,standard_name_vocabulary_version,canonical_unit,long_name,description) VALUES (?,?,?,?,?,?,?)",
                (name, standard_name, vocabulary, vocabulary_version, canonical_unit, long_name, description),
            )
            return int(cur.lastrowid)

    def add_variable_identifier(self, variable: str, scheme: str, identifier: str, *,
                                scheme_version: str | None = None, uri: str | None = None) -> None:
        if not scheme or scheme.strip() != scheme or not identifier or identifier.strip() != identifier:
            raise DataTilesError("identifier scheme and value must be non-empty and trimmed")
        row = self.db.execute("SELECT variable_id FROM datatiles_variables WHERE name=?", (variable,)).fetchone()
        if row is None:
            raise DataTilesError(f"unknown registered variable: {variable}")
        with self.db:
            self.db.execute("INSERT INTO datatiles_variable_identifiers(variable_id,scheme,identifier,scheme_version,uri) VALUES (?,?,?,?,?)",
                            (row[0], scheme, identifier, scheme_version, uri))

    def variables(self) -> list[dict[str, Any]]:
        result = []
        for row in self.db.execute("SELECT * FROM datatiles_variables ORDER BY name"):
            item = dict(row)
            item["identifiers"] = [dict(r) for r in self.db.execute(
                "SELECT scheme,identifier,scheme_version,uri FROM datatiles_variable_identifiers WHERE variable_id=? ORDER BY scheme,identifier",
                (row["variable_id"],))]
            item["coordinate_set_ids"] = self.find_coordinate_sets({"variable": row["name"]}) if self.db.execute(
                "SELECT 1 FROM datatiles_dimensions WHERE name='variable'").fetchone() else []
            result.append(item)
        return result

    def find_coordinate_sets_by_standard_name(self, standard_name: str, *, vocabulary: str = "CF") -> list[int]:
        rows = self.db.execute("SELECT name FROM datatiles_variables WHERE standard_name_vocabulary=? AND standard_name=? ORDER BY name",
                               (vocabulary, standard_name)).fetchall()
        found: set[int] = set()
        for row in rows:
            found.update(self.find_coordinate_sets({"variable": row["name"]}))
        return sorted(found)

    def add_identifier(self, scheme: str, identifier: str, *, uri: str | None=None, primary: bool=False) -> None:
        if not scheme or not identifier: raise DataTilesError("identifier scheme and value are required")
        with self.db:
            if primary: self.db.execute("UPDATE datatiles_identifiers SET is_primary=0 WHERE is_primary=1")
            self.db.execute("INSERT INTO datatiles_identifiers(scheme,identifier,uri,is_primary) VALUES (?,?,?,?)",(scheme,identifier,uri,int(primary)))

    def primary_identifier(self) -> dict[str,Any] | None:
        row=self.db.execute("SELECT scheme,identifier,uri FROM datatiles_identifiers WHERE is_primary=1").fetchone()
        return dict(row) if row else None

    def add_related_identifier(self, scheme: str, identifier: str, relation_type: str, *, uri: str | None=None, resource_type: str | None=None, relation_information: str | None=None) -> None:
        with self.db: self.db.execute("INSERT INTO datatiles_related_identifiers VALUES (?,?,?,?,?,?)",(scheme,identifier,relation_type,uri,resource_type,relation_information))

    def related_identifiers(self) -> list[dict[str,Any]]:
        return [dict(r) for r in self.db.execute("SELECT scheme AS relatedIdentifierType,identifier AS relatedIdentifier,relation_type AS relationType,uri,resource_type AS resourceTypeGeneral,relation_information AS relationTypeInformation FROM datatiles_related_identifiers ORDER BY relation_type,scheme,identifier")]

    def add_rights(self, scope: str, license_expression: str, *, license_uri: str | None=None, rights_holder: str | None=None, rights_holder_uri: str | None=None, attribution_text: str | None=None, copyright_notice: str | None=None, access_rights: str="open", source_entity_id: str | None=None, applies_to: str | None=None) -> None:
        from .fair import validate_spdx_expression, RIGHTS_SCOPES, ACCESS_RIGHTS, FairValidationError
        if scope not in RIGHTS_SCOPES or access_rights not in ACCESS_RIGHTS: raise DataTilesError("invalid rights scope/access_rights")
        try: validate_spdx_expression(license_expression)
        except FairValidationError as exc: raise DataTilesError(str(exc)) from exc
        with self.db: self.db.execute("INSERT INTO datatiles_rights(scope,license_expression,license_uri,rights_holder,rights_holder_uri,attribution_text,copyright_notice,access_rights,source_entity_id,applies_to) VALUES (?,?,?,?,?,?,?,?,?,?)",(scope,license_expression,license_uri,rights_holder,rights_holder_uri,attribution_text,copyright_notice,access_rights,source_entity_id,applies_to))

    def rights(self) -> list[dict[str,Any]]:
        return [dict(r) for r in self.db.execute("SELECT * FROM datatiles_rights ORDER BY scope,rights_id")]

    def assign_fair_agent_role(self, agent_id: str, role: str, *, sequence: int=0) -> None:
        with self.db: self.db.execute("INSERT INTO datatiles_fair_agents VALUES (?,?,?)",(agent_id,role,sequence))

    def fair_agents(self, *, role: str) -> list[dict[str,Any]]:
        rows=self.db.execute("SELECT a.label,a.uri,a.attributes_json FROM datatiles_fair_agents f JOIN datatiles_provenance_agents a USING(agent_id) WHERE f.role=? ORDER BY f.sequence,a.agent_id",(role,))
        return [{"name":r["label"], **({"nameIdentifiers":[{"nameIdentifier":r["uri"],"nameIdentifierScheme":"URI"}]} if r["uri"] else {})} for r in rows]

    def add_publication_evidence(self, evidence_type: str, uri: str, *, checked_at: str | None=None, checksum_algorithm: str | None=None, checksum: str | None=None, notes: str | None=None) -> None:
        with self.db: self.db.execute("INSERT INTO datatiles_publication_evidence VALUES (?,?,?,?,?,?)",(evidence_type,uri,checked_at,checksum_algorithm,checksum,notes))

    def fair_report(self, *, strict_publication: bool=False) -> dict[str,Any]:
        meta=self.metadata(); checks=[]
        def check(code, ok, detail, external=False): checks.append({"principle":code,"status":"pass" if ok else "fail","detail":detail,"external":external})
        pid=self.primary_identifier(); check("F1/F3", bool(pid), "primary persistent identifier is explicitly recorded")
        check("F2", bool(meta.get("name") and list(self.db.execute("SELECT 1 FROM datatiles_dimensions LIMIT 1"))), "descriptive and structural metadata are embedded")
        evidence={r[0] for r in self.db.execute("SELECT evidence_type FROM datatiles_publication_evidence")}
        check("F4", "catalogue-registration" in evidence, "catalogue registration requires external publication evidence", True)
        check("A1", "landing-page" in evidence or bool(pid and pid.get("uri")), "identifier/landing page is recorded", True)
        check("A2", "metadata-retention-policy" in evidence, "metadata persistence after withdrawal requires repository evidence", True)
        check("I1/I2", bool(list(self.db.execute("SELECT 1 FROM datatiles_variables LIMIT 1"))) and bool(list(self.db.execute("SELECT 1 FROM datatiles_crs LIMIT 1"))), "semantic variables and CRS are machine-readable")
        check("I3/R1.2", bool(list(self.db.execute("SELECT 1 FROM datatiles_provenance_entities LIMIT 1"))) and bool(list(self.db.execute("SELECT 1 FROM datatiles_provenance_activities LIMIT 1"))), "PROV-aligned entities and activities are present")
        dataset_rights=list(self.db.execute("SELECT 1 FROM datatiles_rights WHERE scope='dataset' LIMIT 1")); metadata_rights=list(self.db.execute("SELECT 1 FROM datatiles_rights WHERE scope='metadata' LIMIT 1"))
        check("R1.1", bool(dataset_rights and metadata_rights), "dataset and metadata rights are separately declared")
        source_count=self.db.execute("SELECT count(*) FROM datatiles_provenance_entities WHERE entity_type='dataset'").fetchone()[0]
        licensed_sources=self.db.execute("SELECT count(DISTINCT source_entity_id) FROM datatiles_rights WHERE scope='source' AND source_entity_id IS NOT NULL").fetchone()[0]
        check("R1.1/R1.2", source_count==0 or licensed_sources>=source_count, "every source dataset entity has an explicit rights record")
        check("R1.3", meta.get("datatiles:fair_profile") is not None and meta.get("datatiles:metadata_profile")=="DataCite-4.7", "community profiles are declared")
        failures=[c for c in checks if c["status"]=="fail" and (strict_publication or not c["external"])]
        publishable=not failures
        return {"profile":"DataTiles FAIR publication profile","fair_principles":"Wilkinson et al. 2016","checks":checks,
                "publishable":publishable,"passes":publishable,"strict_publication":strict_publication,
                "integrity":{"optional":True,"signatures":len(self.signatures()),"note":"digital signatures strengthen integrity/provenance evidence but are not required for FAIRness"}}

    def datacite_metadata(self) -> dict[str,Any]:
        from .fair import datacite_metadata; return datacite_metadata(self)

    def prov_json(self) -> dict[str,Any]:
        from .fair import prov_json; return prov_json(self)

    def integrity_manifest(self, *, chunk_size: int = 100000) -> dict[str,Any]:
        from .integrity import build_manifest
        return build_manifest(self.db, chunk_size=chunk_size)

    def signatures(self) -> list[dict[str,Any]]:
        from .integrity import list_stored_signatures
        return list_stored_signatures(self.db)

    def integrity_status(self, *, recompute: bool=False, chunk_size: int=100000) -> dict[str,Any]:
        meta=self.metadata(); result={"profile":meta.get("datatiles:integrity_profile","DataTiles-Integrity-Manifest-1"),"signature_profile":meta.get("datatiles:signature_profile","DataTiles-Ed25519-Signature-1"),"signatures":self.signatures(),"trust_note":"embedded public keys establish cryptographic self-consistency, not publisher trust"}
        if recompute:
            result["current_manifest"]=self.integrity_manifest(chunk_size=chunk_size)
        return result

    def add_commercial_product(self, product_id: str, *, issuer: str, terms_uri: str, edition: str | None=None, issuer_uri: str | None=None, license_service_uri: str | None=None, metadata: dict[str,Any] | None=None) -> None:
        if not product_id or not issuer or not terms_uri: raise DataTilesError("product_id, issuer, and terms_uri are required")
        import json as _json
        from datetime import datetime as _dt, timezone as _tz
        created=_dt.now(_tz.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
        with self.db: self.db.execute("INSERT INTO datatiles_commercial_products(product_id,edition,issuer,issuer_uri,terms_uri,license_service_uri,protection_profile,created_at,metadata_json) VALUES (?,?,?,?,?,?,?,?,?)",(product_id,edition,issuer,issuer_uri,terms_uri,license_service_uri,"DataTiles-Protected-Distribution-1",created,_json.dumps(metadata or {},sort_keys=True,separators=(",",":"))))

    def add_drm_policy(self, product_id: str, policy_id: str, policy: dict[str,Any], *, profile: str="W3C-ODRL-2.2") -> None:
        import json as _json
        if not isinstance(policy,dict): raise DataTilesError("DRM/ODRL policy must be a JSON object")
        with self.db: self.db.execute("INSERT INTO datatiles_drm_policies(product_id,policy_id,policy_profile,policy_json) VALUES (?,?,?,?)",(product_id,policy_id,profile,_json.dumps(policy,sort_keys=True,separators=(",",":"),ensure_ascii=False)))

    def commercial_products(self) -> list[dict[str,Any]]:
        import json as _json
        rows=[]
        for r in self.db.execute("SELECT * FROM datatiles_commercial_products ORDER BY product_id"):
            d=dict(r); d["metadata"]=_json.loads(d.pop("metadata_json") or "{}"); rows.append(d)
        return rows

    def drm_policies(self, product_id: str | None=None) -> list[dict[str,Any]]:
        import json as _json
        q="SELECT * FROM datatiles_drm_policies"; args=()
        if product_id is not None: q+=" WHERE product_id=?"; args=(product_id,)
        q+=" ORDER BY product_id,policy_id"
        out=[]
        for r in self.db.execute(q,args): d=dict(r); d["policy"]=_json.loads(d.pop("policy_json")); out.append(d)
        return out

    def drm_status(self) -> dict[str,Any]:
        meta=self.metadata()
        return {"optional":True,"profile":meta.get("datatiles:drm_profile","DataTiles-Protected-Distribution-1"),"rights_policy_profile":meta.get("datatiles:rights_policy_profile","W3C-ODRL-2.2"),"products":self.commercial_products(),"policies":self.drm_policies(),"warning":"DRM enforces distribution access; it does not create copyright, relicence sources, establish scientific validity, or imply navigation safety."}

    def set_release(self, product_id: str, version: str, sequence: int, *, released_at: str, previous_version: str | None=None, previous_identifier: str | None=None, release_notes_uri: str | None=None, update_uri: str | None=None) -> None:
        if not product_id or not version or int(sequence) < 1:
            raise DataTilesError("product_id, version, and positive sequence are required")
        with self.db:
            self.db.execute("INSERT INTO datatiles_release(singleton,product_id,version,sequence,released_at,previous_version,previous_identifier,release_notes_uri,update_uri) VALUES (1,?,?,?,?,?,?,?,?) ON CONFLICT(singleton) DO UPDATE SET product_id=excluded.product_id,version=excluded.version,sequence=excluded.sequence,released_at=excluded.released_at,previous_version=excluded.previous_version,previous_identifier=excluded.previous_identifier,release_notes_uri=excluded.release_notes_uri,update_uri=excluded.update_uri", (product_id,version,int(sequence),released_at,previous_version,previous_identifier,release_notes_uri,update_uri))

    def release(self) -> dict[str,Any] | None:
        row = self.db.execute("SELECT product_id,version,sequence,released_at,previous_version,previous_identifier,release_notes_uri,update_uri FROM datatiles_release WHERE singleton=1").fetchone()
        return dict(row) if row else None

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

    def validate(self, *, cf_table: str | Path | None = None, require_variable_semantics: bool = False) -> list[str]:
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
        if int(self.db.execute("PRAGMA user_version").fetchone()[0]) != 8: errors.append("unsupported schema revision")
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
        policy=dict(self.db.execute("SELECT name,value FROM metadata")).get("datatiles:variable_semantics", "recommended")
        variable_dim=self.db.execute("SELECT dimension_id,value_type,extent_kind FROM datatiles_dimensions WHERE name='variable'").fetchone()
        if variable_dim is not None:
            if variable_dim["value_type"] != "text" or variable_dim["extent_kind"] != "point":
                errors.append("semantic variable dimension must be text with point extent")
            if policy == "required" or require_variable_semantics:
                missing=self.db.execute(
                    "SELECT v.canonical_value FROM datatiles_values v WHERE v.dimension_id=? AND NOT EXISTS (SELECT 1 FROM datatiles_variables r WHERE r.name=v.canonical_value) ORDER BY v.canonical_value",
                    (variable_dim["dimension_id"],)).fetchall()
                for row in missing: errors.append(f"unregistered variable coordinate: {row[0]}")
        if cf_table is not None:
            try:
                from .semantic import load_cf_standard_name_table, validate_cf_standard_name, SemanticValidationError
                table=load_cf_standard_name_table(cf_table)
                for row in self.db.execute("SELECT name,standard_name,standard_name_vocabulary,canonical_unit FROM datatiles_variables"):
                    if row["standard_name_vocabulary"].upper() == "CF":
                        try: validate_cf_standard_name(row["standard_name"], canonical_unit=row["canonical_unit"], table=table)
                        except SemanticValidationError as exc: errors.append(f"variable {row['name']}: {exc}")
            except (OSError, ValueError) as exc:
                errors.append(f"CF standard-name table: {exc}")
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
