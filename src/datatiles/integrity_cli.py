from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from .integrity import (
    IntegrityError, build_manifest, create_signature_envelope, envelope_from_stored_signature,
    generate_ed25519_keypair, list_stored_signatures, load_private_key, load_public_key,
    store_envelope, verify_database_against_envelope,
)


def _db(path: str, *, writable: bool = False) -> sqlite3.Connection:
    if writable:
        db = sqlite3.connect(path)
    else:
        db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    db.execute("PRAGMA foreign_keys=ON")
    return db


def _dump(value, output: str | None = None):
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="datatiles-integrity", description="Create and verify DataTiles integrity manifests and optional Ed25519 signatures")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate-key", help="generate an Ed25519 signing keypair")
    g.add_argument("--private-key", required=True); g.add_argument("--public-key", required=True); g.add_argument("--overwrite", action="store_true")

    m = sub.add_parser("manifest", help="compute the canonical logical integrity manifest")
    m.add_argument("file"); m.add_argument("--output"); m.add_argument("--chunk-size", type=int, default=100000)

    s = sub.add_parser("sign", help="sign the current canonical manifest")
    s.add_argument("file"); s.add_argument("--private-key", required=True); s.add_argument("--signer"); s.add_argument("--signer-agent-id")
    s.add_argument("--detached", help="write a detached signature envelope JSON")
    s.add_argument("--no-store", action="store_true", help="do not store the signature inside the DataTiles container")
    s.add_argument("--chunk-size", type=int, default=100000)

    v = sub.add_parser("verify", help="verify a stored or detached signature and current DataTiles content")
    v.add_argument("file"); v.add_argument("--signature-id"); v.add_argument("--detached"); v.add_argument("--public-key")
    v.add_argument("--require-key-id"); v.add_argument("--chunk-size", type=int, default=100000)

    l = sub.add_parser("list", help="list signatures stored in a DataTiles container")
    l.add_argument("file")

    args = p.parse_args(argv)
    try:
        if args.command == "generate-key":
            private_path, key_id = generate_ed25519_keypair(args.private_key, args.public_key, overwrite=args.overwrite)
            _dump({"private_key": private_path, "public_key": args.public_key, "key_id": key_id}); return 0
        if args.command == "manifest":
            with _db(args.file) as db: manifest = build_manifest(db, chunk_size=args.chunk_size)
            _dump(manifest, args.output); return 0
        if args.command == "sign":
            key = load_private_key(args.private_key)
            with _db(args.file, writable=not args.no_store) as db:
                manifest = build_manifest(db, chunk_size=args.chunk_size)
                envelope = create_signature_envelope(manifest, key, signer=args.signer)
                signature_id = None
                if not args.no_store:
                    signature_id = store_envelope(db, envelope, signer_agent_id=args.signer_agent_id)
            if args.detached: _dump(envelope, args.detached)
            _dump({"signature_id": signature_id, "root_sha256": manifest["root_sha256"], "key_id": envelope["signature"]["key_id"], "detached": args.detached}); return 0
        if args.command == "list":
            with _db(args.file) as db: result = list_stored_signatures(db)
            _dump({"signatures": result}); return 0
        if args.command == "verify":
            key = load_public_key(args.public_key) if args.public_key else None
            with _db(args.file) as db:
                if args.detached:
                    envelope = json.loads(Path(args.detached).read_text(encoding="utf-8"))
                else:
                    signature_id = args.signature_id
                    if not signature_id:
                        rows = list_stored_signatures(db)
                        if len(rows) != 1:
                            raise IntegrityError("specify --signature-id when the container does not contain exactly one signature")
                        signature_id = rows[0]["signature_id"]
                    envelope = envelope_from_stored_signature(db, signature_id)
                result = verify_database_against_envelope(db, envelope, public_key=key, expected_key_id=args.require_key_id, chunk_size=args.chunk_size)
            _dump(result); return 0 if result["valid"] else 2
    except (IntegrityError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"datatiles-integrity: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
