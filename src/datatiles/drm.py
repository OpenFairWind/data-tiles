from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

PACKAGE_MAGIC = b"DTPKG1\x00"
PACKAGE_PROFILE = "DataTiles-Protected-Distribution-1"
LICENSE_PROFILE = "DataTiles-Commercial-License-1"
POLICY_PROFILE = "W3C-ODRL-2.2"
CONTENT_ALGORITHM = "AES-256-GCM"
KEY_WRAP_ALGORITHM = "X25519-HKDF-SHA256+A256GCM"
SIGNATURE_ALGORITHM = "Ed25519"
DEFAULT_CHUNK_SIZE = 1024 * 1024


class DRMError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _require_crypto():
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    except ImportError as exc:
        raise DRMError("DRM support requires the optional 'drm' dependency: pip install 'datatiles[drm]'") from exc
    return hashes, serialization, Ed25519PrivateKey, Ed25519PublicKey, X25519PrivateKey, X25519PublicKey, Cipher, algorithms, modes, AESGCM, HKDF


def _sha256_file(path: str | Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _raw_public_key(public_key) -> bytes:
    _, serialization, *_ = _require_crypto()
    return public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(public_key) -> str:
    return "sha256:" + hashlib.sha256(_raw_public_key(public_key)).hexdigest()


def generate_recipient_keypair(private_key_path: str | Path, public_key_path: str | Path, *, overwrite: bool = False) -> dict[str, str]:
    _, serialization, _, _, X25519PrivateKey, _, *_ = _require_crypto()
    private_path, public_path = Path(private_key_path), Path(public_key_path)
    if not overwrite and (private_path.exists() or public_path.exists()):
        raise DRMError("refusing to overwrite an existing recipient key file")
    private = X25519PrivateKey.generate()
    public = private.public_key()
    private_path.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    try:
        os.chmod(private_path, 0o600)
    except OSError:
        pass
    public_path.write_bytes(public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    return {"private_key": str(private_path), "public_key": str(public_path), "key_id": key_id(public)}


def load_recipient_private_key(path: str | Path):
    _, serialization, _, _, X25519PrivateKey, *_ = _require_crypto()
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, X25519PrivateKey):
        raise DRMError("recipient private key must be X25519")
    return key


def load_recipient_public_key(path: str | Path):
    _, serialization, _, _, _, X25519PublicKey, *_ = _require_crypto()
    key = serialization.load_pem_public_key(Path(path).read_bytes())
    if not isinstance(key, X25519PublicKey):
        raise DRMError("recipient public key must be X25519")
    return key


def load_issuer_private_key(path: str | Path):
    _, serialization, Ed25519PrivateKey, *_ = _require_crypto()
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise DRMError("issuer private key must be Ed25519")
    return key


def load_issuer_public_key(path: str | Path):
    _, serialization, _, Ed25519PublicKey, *_ = _require_crypto()
    key = serialization.load_pem_public_key(Path(path).read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise DRMError("issuer public key must be Ed25519")
    return key


def write_content_key(path: str | Path, key: bytes, *, product_id: str) -> None:
    if len(key) != 32:
        raise DRMError("content key must be 32 bytes")
    p = Path(path)
    p.write_text(json.dumps({"profile": PACKAGE_PROFILE, "product_id": product_id, "content_key": _b64(key)}, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def read_content_key(path: str | Path, *, expected_product_id: str | None = None) -> tuple[str, bytes]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    product_id = data.get("product_id")
    key = _unb64(data.get("content_key", ""))
    if len(key) != 32 or not product_id:
        raise DRMError("invalid content-key file")
    if expected_product_id and product_id != expected_product_id:
        raise DRMError("content-key product_id does not match package")
    return product_id, key


def protect_file(source: str | Path, output: str | Path, *, content_key_file: str | Path, product_id: str | None = None,
                 issuer: str, issuer_uri: str | None = None, terms_uri: str, license_service_uri: str | None = None,
                 edition: str | None = None, metadata: dict[str, Any] | None = None, chunk_size: int = DEFAULT_CHUNK_SIZE) -> dict[str, Any]:
    *_, Cipher, algorithms, modes, _, _ = _require_crypto()
    source, output = Path(source), Path(output)
    if not source.is_file():
        raise DRMError("source must be a finalized DataTiles file")
    product_id = product_id or f"urn:uuid:{uuid.uuid4()}"
    content_key = os.urandom(32)
    nonce = os.urandom(12)
    plaintext_sha256 = _sha256_file(source, chunk_size)
    header = {
        "profile": PACKAGE_PROFILE,
        "product_id": product_id,
        "edition": edition,
        "issuer": issuer,
        "issuer_uri": issuer_uri,
        "terms_uri": terms_uri,
        "license_service_uri": license_service_uri,
        "content_algorithm": CONTENT_ALGORITHM,
        "nonce": _b64(nonce),
        "plaintext_sha256": plaintext_sha256,
        "plaintext_size": source.stat().st_size,
        "created_at": _utc_now(),
        "metadata": metadata or {},
    }
    header_bytes = _canonical_json(header)
    encryptor = Cipher(algorithms.AES(content_key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header_bytes)
    cipher_hash = hashlib.sha256()
    with source.open("rb") as src, output.open("wb") as dst:
        dst.write(PACKAGE_MAGIC); dst.write(struct.pack(">I", len(header_bytes))); dst.write(header_bytes)
        while True:
            chunk = src.read(chunk_size)
            if not chunk:
                break
            encrypted = encryptor.update(chunk)
            dst.write(encrypted); cipher_hash.update(encrypted)
        tail = encryptor.finalize()
        if tail:
            dst.write(tail); cipher_hash.update(tail)
        dst.write(encryptor.tag)
    write_content_key(content_key_file, content_key, product_id=product_id)
    return {**header, "ciphertext_sha256": cipher_hash.hexdigest(), "content_key_file": str(content_key_file), "package": str(output)}


def read_package_header(path: str | Path) -> dict[str, Any]:
    with open(path, "rb") as f:
        if f.read(len(PACKAGE_MAGIC)) != PACKAGE_MAGIC:
            raise DRMError("not a DataTiles protected-distribution package")
        raw = f.read(4)
        if len(raw) != 4:
            raise DRMError("truncated package header")
        length = struct.unpack(">I", raw)[0]
        if length < 2 or length > 1024 * 1024:
            raise DRMError("invalid package header length")
        header_bytes = f.read(length)
        if len(header_bytes) != length:
            raise DRMError("truncated package header")
    header = json.loads(header_bytes)
    if header.get("profile") != PACKAGE_PROFILE or header.get("content_algorithm") != CONTENT_ALGORITHM:
        raise DRMError("unsupported protected-distribution profile")
    return header


def _license_payload(*, package_header: dict[str, Any], recipient_public_key, recipient_id: str | None, content_key: bytes,
                     issuer: str, issuer_uri: str | None, valid_from: str | None, valid_until: str | None,
                     permissions: list[str], policy: dict[str, Any] | None) -> dict[str, Any]:
    hashes, serialization, _, _, X25519PrivateKey, _, _, _, _, AESGCM, HKDF = _require_crypto()
    ephemeral = X25519PrivateKey.generate()
    shared = ephemeral.exchange(recipient_public_key)
    recipient_key_id = key_id(recipient_public_key)
    salt = os.urandom(16)
    kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=("DataTiles DRM " + package_header["product_id"]).encode()).derive(shared)
    wrap_nonce = os.urandom(12)
    aad = _canonical_json({"profile": LICENSE_PROFILE, "product_id": package_header["product_id"], "recipient_key_id": recipient_key_id})
    wrapped = AESGCM(kek).encrypt(wrap_nonce, content_key, aad)
    ephemeral_raw = ephemeral.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {
        "profile": LICENSE_PROFILE,
        "product_id": package_header["product_id"],
        "package_plaintext_sha256": package_header["plaintext_sha256"],
        "issuer": issuer,
        "issuer_uri": issuer_uri,
        "recipient_id": recipient_id,
        "recipient_key_id": recipient_key_id,
        "permissions": sorted(set(permissions)),
        "valid_from": valid_from,
        "valid_until": valid_until,
        "issued_at": _utc_now(),
        "key_wrap": {
            "algorithm": KEY_WRAP_ALGORITHM,
            "ephemeral_public_key": _b64(ephemeral_raw),
            "salt": _b64(salt),
            "nonce": _b64(wrap_nonce),
            "wrapped_content_key": _b64(wrapped),
        },
        "odrl": policy or {"@context": "http://www.w3.org/ns/odrl.jsonld", "@type": "Agreement", "target": package_header["product_id"]},
    }


def issue_license(package: str | Path, content_key_file: str | Path, recipient_public_key_path: str | Path,
                  issuer_private_key_path: str | Path, output: str | Path, *, issuer: str, issuer_uri: str | None = None,
                  recipient_id: str | None = None, valid_from: str | None = None, valid_until: str | None = None,
                  permissions: list[str] | None = None, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    header = read_package_header(package)
    _, content_key = read_content_key(content_key_file, expected_product_id=header["product_id"])
    recipient = load_recipient_public_key(recipient_public_key_path)
    issuer_key = load_issuer_private_key(issuer_private_key_path)
    payload = _license_payload(package_header=header, recipient_public_key=recipient, recipient_id=recipient_id,
                               content_key=content_key, issuer=issuer, issuer_uri=issuer_uri, valid_from=valid_from,
                               valid_until=valid_until, permissions=permissions or ["read"], policy=policy)
    signature = issuer_key.sign(_canonical_json(payload))
    envelope = {
        "payload": payload,
        "signature": {"algorithm": SIGNATURE_ALGORITHM, "issuer_key_id": key_id(issuer_key.public_key()), "value": _b64(signature)},
    }
    Path(output).write_text(json.dumps(envelope, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return envelope


def _parse_time(value: str | None):
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DRMError(f"invalid ISO-8601 licence time: {value}") from exc


def verify_license(envelope: dict[str, Any], issuer_public_key, *, at_time: datetime | None = None) -> dict[str, Any]:
    payload = envelope.get("payload") or {}
    sig = envelope.get("signature") or {}
    if payload.get("profile") != LICENSE_PROFILE or sig.get("algorithm") != SIGNATURE_ALGORITHM:
        raise DRMError("unsupported licence envelope")
    issuer_key_id = key_id(issuer_public_key)
    key_matches = sig.get("issuer_key_id") == issuer_key_id
    crypto_valid = False
    if key_matches:
        try:
            issuer_public_key.verify(_unb64(sig.get("value", "")), _canonical_json(payload)); crypto_valid = True
        except Exception:
            crypto_valid = False
    now = at_time or datetime.now(timezone.utc)
    start, end = _parse_time(payload.get("valid_from")), _parse_time(payload.get("valid_until"))
    time_valid = (start is None or now >= start) and (end is None or now <= end)
    return {"cryptographically_valid": crypto_valid, "issuer_key_matches": key_matches, "time_valid": time_valid,
            "valid": crypto_valid and key_matches and time_valid, "product_id": payload.get("product_id"),
            "recipient_key_id": payload.get("recipient_key_id"), "permissions": payload.get("permissions", [])}


def unwrap_content_key(envelope: dict[str, Any], recipient_private_key, issuer_public_key) -> bytes:
    hashes, serialization, _, _, _, X25519PublicKey, _, _, _, AESGCM, HKDF = _require_crypto()
    status = verify_license(envelope, issuer_public_key)
    if not status["valid"]:
        raise DRMError("licence is not valid for the supplied issuer key and current time")
    payload = envelope["payload"]
    if key_id(recipient_private_key.public_key()) != payload.get("recipient_key_id"):
        raise DRMError("licence was issued to a different recipient key")
    wrap = payload["key_wrap"]
    ephemeral = X25519PublicKey.from_public_bytes(_unb64(wrap["ephemeral_public_key"]))
    shared = recipient_private_key.exchange(ephemeral)
    kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=_unb64(wrap["salt"]), info=("DataTiles DRM " + payload["product_id"]).encode()).derive(shared)
    aad = _canonical_json({"profile": LICENSE_PROFILE, "product_id": payload["product_id"], "recipient_key_id": payload["recipient_key_id"]})
    key = AESGCM(kek).decrypt(_unb64(wrap["nonce"]), _unb64(wrap["wrapped_content_key"]), aad)
    if len(key) != 32:
        raise DRMError("invalid unwrapped content key")
    return key


def decrypt_package(package: str | Path, output: str | Path, *, license_path: str | Path, recipient_private_key_path: str | Path,
                    issuer_public_key_path: str | Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> dict[str, Any]:
    *_, Cipher, algorithms, modes, _, _ = _require_crypto()
    envelope = json.loads(Path(license_path).read_text(encoding="utf-8"))
    recipient_key = load_recipient_private_key(recipient_private_key_path)
    issuer_key = load_issuer_public_key(issuer_public_key_path)
    content_key = unwrap_content_key(envelope, recipient_key, issuer_key)
    package = Path(package); output = Path(output)
    with package.open("rb") as src:
        if src.read(len(PACKAGE_MAGIC)) != PACKAGE_MAGIC:
            raise DRMError("not a DataTiles protected-distribution package")
        length = struct.unpack(">I", src.read(4))[0]
        header_bytes = src.read(length); header = json.loads(header_bytes)
        if envelope["payload"].get("product_id") != header.get("product_id") or envelope["payload"].get("package_plaintext_sha256") != header.get("plaintext_sha256"):
            raise DRMError("licence is bound to a different protected package")
        total = package.stat().st_size
        cipher_len = total - len(PACKAGE_MAGIC) - 4 - length - 16
        if cipher_len < 0:
            raise DRMError("truncated protected package")
        src.seek(total - 16); tag = src.read(16)
        src.seek(len(PACKAGE_MAGIC) + 4 + length)
        decryptor = Cipher(algorithms.AES(content_key), modes.GCM(_unb64(header["nonce"]), tag)).decryptor()
        decryptor.authenticate_additional_data(header_bytes)
        h = hashlib.sha256(); remaining = cipher_len
        try:
            with output.open("wb") as dst:
                while remaining:
                    chunk = src.read(min(chunk_size, remaining))
                    if not chunk:
                        raise DRMError("truncated protected package")
                    remaining -= len(chunk)
                    plain = decryptor.update(chunk); dst.write(plain); h.update(plain)
                tail = decryptor.finalize(); dst.write(tail); h.update(tail)
        except Exception:
            try: output.unlink()
            except FileNotFoundError: pass
            raise
    digest = h.hexdigest()
    if digest != header["plaintext_sha256"]:
        try: output.unlink()
        except FileNotFoundError: pass
        raise DRMError("decrypted product hash does not match protected package identity")
    return {"product_id": header["product_id"], "output": str(output), "plaintext_sha256": digest, "permissions": envelope["payload"].get("permissions", [])}
