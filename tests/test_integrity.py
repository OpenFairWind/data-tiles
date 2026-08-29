from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from datatiles.integrity import (
    IntegrityError, build_manifest, create_signature_envelope, generate_ed25519_keypair,
    load_private_key, load_public_key, store_envelope, verify_database_against_envelope,
    list_stored_signatures,
)


def make_db(path: Path):
    db = sqlite3.connect(path)
    db.executescript('''
      PRAGMA user_version=6;
      CREATE TABLE metadata(name TEXT PRIMARY KEY,value TEXT);
      CREATE TABLE tiles(z INTEGER,x INTEGER,y INTEGER,data BLOB,PRIMARY KEY(z,x,y));
      CREATE TABLE datatiles_integrity_manifests (
        manifest_id TEXT PRIMARY KEY, profile TEXT NOT NULL, canonicalization TEXT NOT NULL,
        hash_algorithm TEXT NOT NULL, root_sha256 TEXT NOT NULL UNIQUE, manifest_json TEXT NOT NULL,
        created_at TEXT NOT NULL
      ) WITHOUT ROWID;
      CREATE TABLE datatiles_signatures (
        signature_id TEXT PRIMARY KEY, manifest_id TEXT NOT NULL REFERENCES datatiles_integrity_manifests(manifest_id),
        signature_scheme TEXT NOT NULL, signature_encoding TEXT NOT NULL, signature BLOB NOT NULL,
        key_id TEXT NOT NULL, public_key BLOB, signer_agent_id TEXT, signed_at TEXT NOT NULL,
        verification_material_json TEXT, UNIQUE(manifest_id,signature_scheme,key_id,signature)
      ) WITHOUT ROWID;
      INSERT INTO metadata VALUES ('name','demo');
      INSERT INTO tiles VALUES (1,2,3,x'010203');
    ''')
    db.commit()
    return db


def test_manifest_is_stable_and_excludes_signature_tables(tmp_path):
    path = tmp_path / 'a.sqlite'
    db = make_db(path)
    m1 = build_manifest(db, chunk_size=1)
    db.execute("INSERT INTO datatiles_integrity_manifests VALUES (?,?,?,?,?,?,?)", ('m','DataTiles-Integrity-Manifest-1','datatiles-sqlite-logical-v1','sha256','0'*64,'{}','2026-01-01T00:00:00Z'))
    db.commit()
    m2 = build_manifest(db, chunk_size=1)
    assert m1 == m2
    db.close()


def test_manifest_changes_when_content_changes(tmp_path):
    path = tmp_path / 'a.sqlite'
    db = make_db(path)
    m1 = build_manifest(db)
    db.execute("UPDATE metadata SET value='changed' WHERE name='name'")
    db.commit()
    m2 = build_manifest(db)
    assert m1['root_sha256'] != m2['root_sha256']
    db.close()


def test_ed25519_sign_store_and_verify(tmp_path):
    path = tmp_path / 'a.sqlite'
    db = make_db(path)
    private_path = tmp_path / 'private.pem'
    public_path = tmp_path / 'public.pem'
    _, key_id = generate_ed25519_keypair(private_path, public_path)
    envelope = create_signature_envelope(build_manifest(db), load_private_key(private_path), signer='test')
    assert envelope['signature']['key_id'] == key_id
    signature_id = store_envelope(db, envelope)
    assert list_stored_signatures(db)[0]['signature_id'] == signature_id
    result = verify_database_against_envelope(db, envelope, public_key=load_public_key(public_path), expected_key_id=key_id)
    assert result['valid'] is True
    assert result['trusted_key_supplied'] is True
    db.execute("INSERT INTO tiles VALUES (4,5,6,x'ff')")
    db.commit()
    changed = verify_database_against_envelope(db, envelope, public_key=load_public_key(public_path))
    assert changed['cryptographically_valid'] is True
    assert changed['content_matches_signed_manifest'] is False
    assert changed['valid'] is False
    db.close()


def test_wrong_trusted_key_fails(tmp_path):
    path = tmp_path / 'a.sqlite'; db = make_db(path)
    p1, q1 = tmp_path/'p1.pem', tmp_path/'q1.pem'; generate_ed25519_keypair(p1,q1)
    p2, q2 = tmp_path/'p2.pem', tmp_path/'q2.pem'; generate_ed25519_keypair(p2,q2)
    envelope = create_signature_envelope(build_manifest(db), load_private_key(p1))
    with pytest.raises(IntegrityError):
        verify_database_against_envelope(db, envelope, public_key=load_public_key(q2))
    db.close()
