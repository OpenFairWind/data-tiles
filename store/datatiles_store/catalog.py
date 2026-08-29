from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from .models import CatalogItem


def _ro_engine(path: Path):
    # SQLite URI mode=ro keeps published DataTiles immutable. SQLAlchemy remains the
    # sole database interface for both the Store DB and inspected DataTiles files.
    uri = f"sqlite+pysqlite:///file:{quote(str(path.resolve()), safe='/')}?mode=ro&uri=true"
    return create_engine(uri, future=True, poolclass=NullPool)


def _objects(con: Connection) -> set[str]:
    return {r[0] for r in con.exec_driver_sql("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}


def _safe_rows(con: Connection, sql: str, params=(), limit=10000) -> list[dict[str, Any]]:
    try:
        result = con.exec_driver_sql(sql, params)
        return [dict(r._mapping) for r in result.fetchmany(limit)]
    except Exception:
        return []


def sha256_file(path: Path, block=4 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(block): h.update(chunk)
    return h.hexdigest()


def extract_metadata(path: Path) -> dict[str, Any]:
    engine = _ro_engine(path)
    try:
        with engine.connect() as con:
            con.exec_driver_sql("PRAGMA query_only=ON")
            objects = _objects(con)
            metadata = {r["name"]: r["value"] for r in _safe_rows(con, "SELECT name,value FROM metadata") } if "metadata" in objects else {}
            revision = int(con.exec_driver_sql("PRAGMA user_version").scalar_one())
            variables = _safe_rows(con, "SELECT name,standard_name,standard_name_vocabulary,standard_name_vocabulary_version,canonical_unit,long_name,description FROM datatiles_variables ORDER BY name") if "datatiles_variables" in objects else []
            rights = _safe_rows(con, "SELECT scope,license_expression,license_uri,rights_holder,attribution_text,access_rights,applies_to FROM datatiles_rights ORDER BY scope,rights_id") if "datatiles_rights" in objects else []
            entities = _safe_rows(con, "SELECT entity_id,entity_type,label,uri,checksum_algorithm,checksum FROM datatiles_provenance_entities ORDER BY entity_id", limit=500) if "datatiles_provenance_entities" in objects else []
            activities = _safe_rows(con, "SELECT activity_id,activity_type,label,started_at,ended_at,software_name,software_version FROM datatiles_provenance_activities ORDER BY activity_id", limit=500) if "datatiles_provenance_activities" in objects else []
            contents = _safe_rows(con, "SELECT coordinate_set_id,data_type,media_type,encoding,schema_json FROM datatiles_contents ORDER BY coordinate_set_id", limit=500) if "datatiles_contents" in objects else []
            dims = _safe_rows(con, "SELECT name,value_type,axis,unit,description,ordering,required,extent_kind FROM datatiles_dimensions ORDER BY dimension_id", limit=500) if "datatiles_dimensions" in objects else []
            integrity = _safe_rows(con, "SELECT s.signature_id,s.manifest_id,s.signature_scheme,s.signature_encoding,s.key_id,s.signer_agent_id,s.signed_at,m.root_sha256 FROM datatiles_signatures AS s JOIN datatiles_integrity_manifests AS m USING(manifest_id) ORDER BY s.signed_at", limit=200) if "datatiles_signatures" in objects else []
            commercial = _safe_rows(con, "SELECT product_id,edition,issuer,issuer_uri,terms_uri,license_service_uri,protection_profile,created_at,metadata_json FROM datatiles_commercial_products ORDER BY product_id", limit=100) if "datatiles_commercial_products" in objects else []
            release_rows = _safe_rows(con, "SELECT product_id,version,sequence,released_at,previous_version,previous_identifier,release_notes_uri,update_uri FROM datatiles_release WHERE singleton=1", limit=1) if "datatiles_release" in objects else []
    finally:
        engine.dispose()
    bounds = metadata.get("bounds", "").split(",")
    try:
        parsed_bounds = [float(x) for x in bounds] if len(bounds) == 4 else None
    except ValueError:
        parsed_bounds = None
    return {
        "metadata": metadata, "revision": revision, "variables": variables, "rights": rights,
        "provenance": {"entities": entities, "activities": activities}, "contents": contents,
        "dimensions": dims, "integrity": integrity, "commercial": commercial, "release": (release_rows[0] if release_rows else {}), "bounds": parsed_bounds,
    }


def index_file(db: Session, catalog_root: Path, path: Path) -> CatalogItem:
    path = path.resolve(); root = catalog_root.resolve()
    if root not in path.parents: raise ValueError("catalog file escapes configured catalog root")
    rel = path.relative_to(root).as_posix(); st = path.stat()
    existing = db.scalar(select(CatalogItem).where(CatalogItem.relative_path == rel))
    if existing and existing.file_mtime_ns == st.st_mtime_ns and existing.size_bytes == st.st_size:
        existing.available = True; return existing
    ext = extract_metadata(path); meta = ext["metadata"]
    title = meta.get("name") or meta.get("title") or path.stem
    desc = meta.get("description") or meta.get("abstract"); b = ext["bounds"]
    search_parts = [title, desc or "", path.name]
    search_parts.extend(f"{k} {v}" for k,v in meta.items())
    search_parts.extend(" ".join(str(v or "") for v in x.values()) for x in ext["variables"])
    search_parts.extend(" ".join(str(v or "") for v in x.values()) for x in ext["rights"])
    for e in ext["provenance"]["entities"]:
        search_parts.extend(str(e.get(k) or "") for k in ("label","uri","entity_type"))
    values = dict(
        filename=path.name, title=title, description=desc, format=meta.get("format", "DataTiles"),
        schema_revision=ext["revision"], size_bytes=st.st_size, file_mtime_ns=st.st_mtime_ns, sha256=sha256_file(path),
        bounds_west=str(b[0]) if b else None, bounds_south=str(b[1]) if b else None,
        bounds_east=str(b[2]) if b else None, bounds_north=str(b[3]) if b else None,
        minzoom=_int_or_none(meta.get("minzoom")), maxzoom=_int_or_none(meta.get("maxzoom")),
        metadata_json=json.dumps(meta, sort_keys=True), variables_json=json.dumps(ext["variables"], sort_keys=True),
        rights_json=json.dumps(ext["rights"], sort_keys=True), provenance_json=json.dumps(ext["provenance"], sort_keys=True),
        search_text="\n".join(search_parts).casefold(), indexed_at=datetime.now(timezone.utc), available=True,
        product_id=(ext.get("release") or {}).get("product_id"), product_version=(ext.get("release") or {}).get("version"), product_sequence=_int_or_none((ext.get("release") or {}).get("sequence")), released_at=(ext.get("release") or {}).get("released_at"), previous_version=(ext.get("release") or {}).get("previous_version"), release_notes_uri=(ext.get("release") or {}).get("release_notes_uri"), update_uri=(ext.get("release") or {}).get("update_uri"),
    )
    if existing is None:
        existing = CatalogItem(relative_path=rel, **values); db.add(existing)
    else:
        for k,v in values.items(): setattr(existing, k, v)
    return existing


def scan_catalog(db: Session, catalog_root: Path, extensions: tuple[str,...]) -> dict[str,int]:
    catalog_root.mkdir(parents=True, exist_ok=True)
    for item in db.scalars(select(CatalogItem)): item.available = False
    indexed = failed = 0
    for path in sorted(catalog_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in extensions: continue
        try: index_file(db, catalog_root, path); indexed += 1
        except Exception: failed += 1
    db.commit(); return {"indexed": indexed, "failed": failed}


def resolve_item_path(item: CatalogItem, root: Path) -> Path:
    p = (root / item.relative_path).resolve()
    if root.resolve() not in p.parents or not p.is_file(): raise FileNotFoundError(item.relative_path)
    return p


def tile_bytes(path: Path, z: int, x: int, y_xyz: int):
    y_tms = (1 << z) - 1 - y_xyz
    engine = _ro_engine(path)
    try:
        with engine.connect() as con:
            con.exec_driver_sql("PRAGMA query_only=ON")
            if "tiles" not in _objects(con): return None
            row = con.exec_driver_sql("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?", (z,x,y_tms)).first()
            if row is None: return None
            data = bytes(row[0])
    finally:
        engine.dispose()
    if data.startswith(b"\x89PNG\r\n\x1a\n"): return data, "image/png"
    if data.startswith(b"\xff\xd8\xff"): return data, "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP": return data, "image/webp"
    if data[:2] == b"\x1f\x8b": return data, "application/vnd.mapbox-vector-tile"
    return data, "application/octet-stream"


def preview_tile(path: Path):
    """Return one exact tile from the selected slice without portrayal."""
    engine = _ro_engine(path)
    try:
        with engine.connect() as con:
            con.exec_driver_sql("PRAGMA query_only=ON")
            required = {"datatiles_selected_slice", "datatiles_contents", "datatiles_tiles"}
            if not required.issubset(_objects(con)):
                return None
            row = con.exec_driver_sql(
                "SELECT t.zoom_level,t.tile_column,t.tile_row,t.tile_data,c.data_type,c.media_type,c.encoding,c.schema_json "
                "FROM datatiles_selected_slice AS s "
                "JOIN datatiles_contents AS c ON c.coordinate_set_id=s.coordinate_set_id "
                "JOIN datatiles_tiles AS t ON t.coordinate_set_id=s.coordinate_set_id "
                "WHERE s.singleton=1 ORDER BY t.zoom_level,t.tile_column,t.tile_row LIMIT 1"
            ).first()
            if row is None:
                return None
            result = dict(row._mapping)
            result["tile_data"] = bytes(result["tile_data"])
            return result
    finally:
        engine.dispose()


def _int_or_none(value):
    try: return int(value) if value is not None else None
    except (TypeError, ValueError): return None
