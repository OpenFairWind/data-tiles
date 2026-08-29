from __future__ import annotations

import base64
import hashlib
import heapq
import json
import os
import sqlite3
import struct
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

INTEGRITY_PROFILE = "DataTiles-Integrity-Manifest-1"
CANONICALIZATION = "datatiles-sqlite-logical-v1"
HASH_ALGORITHM = "sha256"
PAYLOAD_TYPE = "application/vnd.openfairwind.datatiles.integrity-manifest.v1+json"
EXCLUDED_TABLES = {"datatiles_integrity_manifests", "datatiles_signatures"}


class IntegrityError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _normalise_sql(sql: str | None) -> str:
    return " ".join((sql or "").strip().split())


def _typed_value(value: Any) -> list[str]:
    if value is None:
        return ["null", ""]
    if isinstance(value, bool):
        return ["integer", "1" if value else "0"]
    if isinstance(value, int):
        return ["integer", str(value)]
    if isinstance(value, float):
        return ["real64be", struct.pack(">d", value).hex()]
    if isinstance(value, (bytes, bytearray, memoryview)):
        return ["blob", base64.b64encode(bytes(value)).decode("ascii")]
    if isinstance(value, str):
        return ["text", value]
    raise IntegrityError(f"unsupported SQLite value type: {type(value).__name__}")


def _row_digest(row: Iterable[Any]) -> bytes:
    return hashlib.sha256(_canonical_json([_typed_value(v) for v in row])).digest()


def _digest_sorted_rows(rows: Iterable[Iterable[Any]], *, chunk_size: int = 100_000) -> tuple[int, str]:
    """Digest a table as a deterministic multiset of row digests with bounded RAM.

    Row order in SQLite is intentionally ignored. Digests are externally sorted in
    temporary files and then streamed into the table digest, preserving duplicate
    multiplicity while avoiding an unbounded in-memory list for large tile tables.
    """
    if chunk_size < 1:
        raise IntegrityError("chunk_size must be positive")
    count = 0
    chunk: list[bytes] = []
    paths: list[str] = []
    try:
        for row in rows:
            count += 1
            chunk.append(_row_digest(row))
            if len(chunk) >= chunk_size:
                chunk.sort()
                f = tempfile.NamedTemporaryFile(prefix="datatiles-integrity-", suffix=".digests", delete=False)
                with f:
                    for digest in chunk:
                        f.write(digest.hex().encode("ascii") + b"\n")
                paths.append(f.name)
                chunk.clear()

        if not paths:
            chunk.sort()
            h = hashlib.sha256()
            for digest in chunk:
                h.update(digest)
            return count, h.hexdigest()

        if chunk:
            chunk.sort()
            f = tempfile.NamedTemporaryFile(prefix="datatiles-integrity-", suffix=".digests", delete=False)
            with f:
                for digest in chunk:
                    f.write(digest.hex().encode("ascii") + b"\n")
            paths.append(f.name)

        handles = [open(path, "rt", encoding="ascii") for path in paths]
        try:
            h = hashlib.sha256()
            for line in heapq.merge(*handles):
                h.update(bytes.fromhex(line.strip()))
            return count, h.hexdigest()
        finally:
            for handle in handles:
                handle.close()
    finally:
        for path in paths:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


def _schema_objects(db: sqlite3.Connection) -> list[dict[str, str]]:
    rows = db.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE type IN ('table','view','trigger') AND name NOT LIKE 'sqlite_%' ORDER BY type,name"
    )
    result = []
    for object_type, name, table_name, sql in rows:
        if name in EXCLUDED_TABLES or table_name in EXCLUDED_TABLES:
            continue
        result.append({
            "type": object_type,
            "name": name,
            "table": table_name,
            "sql": _normalise_sql(sql),
        })
    return result


def build_manifest(db: sqlite3.Connection, *, chunk_size: int = 100_000) -> dict[str, Any]:
    previous_row_factory = db.row_factory
    try:
        db.row_factory = None
        schema_revision = int(db.execute("PRAGMA user_version").fetchone()[0])
        objects = _schema_objects(db)
        tables = []
        for obj in objects:
            if obj["type"] != "table":
                continue
            table = obj["name"]
            quoted = '"' + table.replace('"', '""') + '"'
            cursor = db.execute(f"SELECT * FROM {quoted}")
            row_count, rows_sha256 = _digest_sorted_rows(cursor, chunk_size=chunk_size)
            tables.append({
                "name": table,
                "schema_sha256": hashlib.sha256(obj["sql"].encode("utf-8")).hexdigest(),
                "row_count": row_count,
                "rows_sha256": rows_sha256,
            })

        views_and_triggers = [
            {
                "type": obj["type"],
                "name": obj["name"],
                "schema_sha256": hashlib.sha256(obj["sql"].encode("utf-8")).hexdigest(),
            }
            for obj in objects if obj["type"] != "table"
        ]
        body = {
            "profile": INTEGRITY_PROFILE,
            "payload_type": PAYLOAD_TYPE,
            "canonicalization": CANONICALIZATION,
            "hash_algorithm": HASH_ALGORITHM,
            "schema_revision": schema_revision,
            "tables": sorted(tables, key=lambda x: x["name"]),
            "views_and_triggers": sorted(views_and_triggers, key=lambda x: (x["type"], x["name"])),
        }
        root = hashlib.sha256(_canonical_json(body)).hexdigest()
        return {**body, "root_sha256": root}
    finally:
        db.row_factory = previous_row_factory


def manifest_bytes(manifest: dict[str, Any]) -> bytes:
    required = {"profile", "payload_type", "canonicalization", "hash_algorithm", "schema_revision", "tables", "views_and_triggers", "root_sha256"}
    missing = required - manifest.keys()
    if missing:
        raise IntegrityError("manifest missing fields: " + ", ".join(sorted(missing)))
    body = {k: manifest[k] for k in manifest if k != "root_sha256"}
    expected = hashlib.sha256(_canonical_json(body)).hexdigest()
    if expected != manifest["root_sha256"]:
        raise IntegrityError("manifest root_sha256 does not match canonical manifest body")
    return _canonical_json(manifest)


def key_id_from_public_bytes(public_key_raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(public_key_raw).hexdigest()


def _require_crypto():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    except ImportError as exc:
        raise IntegrityError("digital signatures require the optional 'integrity' dependency: pip install 'datatiles[integrity]'") from exc
    return serialization, Ed25519PrivateKey, Ed25519PublicKey


def generate_ed25519_keypair(private_key_path: str | Path, public_key_path: str | Path, *, overwrite: bool = False) -> tuple[str, str]:
    serialization, Ed25519PrivateKey, _ = _require_crypto()
    private_path, public_path = Path(private_key_path), Path(public_key_path)
    if not overwrite and (private_path.exists() or public_path.exists()):
        raise IntegrityError("refusing to overwrite an existing key file")
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    private_pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public_pem = public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    private_path.write_bytes(private_pem)
    try:
        os.chmod(private_path, 0o600)
    except OSError:
        pass
    public_path.write_bytes(public_pem)
    raw_public = public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return str(private_path), key_id_from_public_bytes(raw_public)


def load_private_key(path: str | Path):
    serialization, Ed25519PrivateKey, _ = _require_crypto()
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise IntegrityError("only Ed25519 private keys are supported by the native DataTiles signature profile")
    return key


def load_public_key(path: str | Path):
    serialization, _, Ed25519PublicKey = _require_crypto()
    key = serialization.load_pem_public_key(Path(path).read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise IntegrityError("only Ed25519 public keys are supported by the native DataTiles signature profile")
    return key


def create_signature_envelope(manifest: dict[str, Any], private_key, *, signer: str | None = None, signed_at: str | None = None) -> dict[str, Any]:
    serialization, Ed25519PrivateKey, _ = _require_crypto()
    if not isinstance(private_key, Ed25519PrivateKey):
        raise IntegrityError("native signing requires an Ed25519 private key")
    payload = manifest_bytes(manifest)
    signature = private_key.sign(payload)
    raw_public = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {
        "profile": "DataTiles-Ed25519-Signature-1",
        "payload_type": PAYLOAD_TYPE,
        "manifest": manifest,
        "signature": {
            "scheme": "Ed25519",
            "encoding": "base64",
            "value": base64.b64encode(signature).decode("ascii"),
            "key_id": key_id_from_public_bytes(raw_public),
            "public_key_raw_base64": base64.b64encode(raw_public).decode("ascii"),
            "signed_at": signed_at or _utc_now(),
            **({"signer": signer} if signer else {}),
        },
    }


def verify_signature_envelope(envelope: dict[str, Any], *, public_key=None, expected_key_id: str | None = None) -> dict[str, Any]:
    serialization, _, Ed25519PublicKey = _require_crypto()
    if envelope.get("profile") != "DataTiles-Ed25519-Signature-1":
        raise IntegrityError("unsupported signature envelope profile")
    sig = envelope.get("signature") or {}
    if sig.get("scheme") != "Ed25519" or sig.get("encoding") != "base64":
        raise IntegrityError("unsupported signature scheme/encoding")
    manifest = envelope.get("manifest")
    if not isinstance(manifest, dict):
        raise IntegrityError("signature envelope has no manifest")
    payload = manifest_bytes(manifest)
    embedded_raw = base64.b64decode(sig.get("public_key_raw_base64", ""), validate=True)
    embedded_key_id = key_id_from_public_bytes(embedded_raw)
    if embedded_key_id != sig.get("key_id"):
        raise IntegrityError("embedded public key does not match signature key_id")
    if expected_key_id and embedded_key_id != expected_key_id:
        raise IntegrityError("signature key_id does not match the required key")
    trusted = public_key is not None
    if public_key is None:
        public_key = Ed25519PublicKey.from_public_bytes(embedded_raw)
    else:
        supplied_raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        if supplied_raw != embedded_raw:
            raise IntegrityError("supplied trusted public key does not match the embedded signature key")
    try:
        public_key.verify(base64.b64decode(sig["value"], validate=True), payload)
    except Exception as exc:
        raise IntegrityError("digital signature verification failed") from exc
    return {
        "cryptographically_valid": True,
        "trusted_key_supplied": trusted,
        "key_id": embedded_key_id,
        "root_sha256": manifest["root_sha256"],
        "signed_at": sig.get("signed_at"),
        "signer": sig.get("signer"),
    }


def verify_database_against_envelope(db: sqlite3.Connection, envelope: dict[str, Any], *, public_key=None, expected_key_id: str | None = None, chunk_size: int = 100_000) -> dict[str, Any]:
    signature_result = verify_signature_envelope(envelope, public_key=public_key, expected_key_id=expected_key_id)
    current = build_manifest(db, chunk_size=chunk_size)
    expected = envelope["manifest"]
    content_match = current["root_sha256"] == expected["root_sha256"]
    return {
        **signature_result,
        "content_matches_signed_manifest": content_match,
        "current_root_sha256": current["root_sha256"],
        "signed_root_sha256": expected["root_sha256"],
        "valid": bool(signature_result["cryptographically_valid"] and content_match),
    }


def store_envelope(db: sqlite3.Connection, envelope: dict[str, Any], *, signer_agent_id: str | None = None, verification_material: dict[str, Any] | None = None) -> str:
    manifest = envelope["manifest"]
    sig = envelope["signature"]
    manifest_id = "urn:uuid:" + str(uuid.uuid4())
    signature_id = "urn:uuid:" + str(uuid.uuid4())
    manifest_json = _canonical_json(manifest).decode("utf-8")
    created_at = sig.get("signed_at") or _utc_now()
    with db:
        row = db.execute("SELECT manifest_id FROM datatiles_integrity_manifests WHERE root_sha256=?", (manifest["root_sha256"],)).fetchone()
        if row:
            manifest_id = row[0]
        else:
            db.execute(
                "INSERT INTO datatiles_integrity_manifests(manifest_id,profile,canonicalization,hash_algorithm,root_sha256,manifest_json,created_at) VALUES (?,?,?,?,?,?,?)",
                (manifest_id, manifest["profile"], manifest["canonicalization"], manifest["hash_algorithm"], manifest["root_sha256"], manifest_json, created_at),
            )
        db.execute(
            "INSERT INTO datatiles_signatures(signature_id,manifest_id,signature_scheme,signature_encoding,signature,key_id,public_key,signer_agent_id,signed_at,verification_material_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                signature_id, manifest_id, sig["scheme"], sig["encoding"], base64.b64decode(sig["value"]), sig["key_id"],
                base64.b64decode(sig["public_key_raw_base64"]), signer_agent_id, sig.get("signed_at") or _utc_now(),
                json.dumps(verification_material, sort_keys=True, separators=(",", ":")) if verification_material else None,
            ),
        )
    return signature_id


def list_stored_signatures(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT s.signature_id,s.signature_scheme,s.signature_encoding,s.key_id,s.signer_agent_id,s.signed_at,m.manifest_id,m.profile,m.root_sha256,s.verification_material_json "
        "FROM datatiles_signatures s JOIN datatiles_integrity_manifests m USING(manifest_id) ORDER BY s.signed_at,s.signature_id"
    )
    result = []
    for row in rows:
        item = {
            "signature_id": row[0], "scheme": row[1], "encoding": row[2], "key_id": row[3],
            "signer_agent_id": row[4], "signed_at": row[5], "manifest_id": row[6],
            "manifest_profile": row[7], "root_sha256": row[8],
        }
        if row[9]:
            item["verification_material"] = json.loads(row[9])
        result.append(item)
    return result


def envelope_from_stored_signature(db: sqlite3.Connection, signature_id: str) -> dict[str, Any]:
    row = db.execute(
        "SELECT m.manifest_json,s.signature_scheme,s.signature_encoding,s.signature,s.key_id,s.public_key,s.signed_at,s.signer_agent_id "
        "FROM datatiles_signatures s JOIN datatiles_integrity_manifests m USING(manifest_id) WHERE s.signature_id=?",
        (signature_id,),
    ).fetchone()
    if row is None:
        raise IntegrityError(f"unknown signature: {signature_id}")
    manifest = json.loads(row[0])
    return {
        "profile": "DataTiles-Ed25519-Signature-1",
        "payload_type": PAYLOAD_TYPE,
        "manifest": manifest,
        "signature": {
            "scheme": row[1], "encoding": row[2], "value": base64.b64encode(row[3]).decode("ascii"),
            "key_id": row[4], "public_key_raw_base64": base64.b64encode(row[5]).decode("ascii"),
            "signed_at": row[6], **({"signer_agent_id": row[7]} if row[7] else {}),
        },
    }
