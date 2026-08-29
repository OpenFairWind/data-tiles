CREATE TABLE datatiles_integrity_manifests (
  manifest_id TEXT PRIMARY KEY,
  profile TEXT NOT NULL,
  canonicalization TEXT NOT NULL,
  hash_algorithm TEXT NOT NULL CHECK(hash_algorithm = 'sha256'),
  root_sha256 TEXT NOT NULL UNIQUE CHECK(length(root_sha256) = 64),
  manifest_json TEXT NOT NULL,
  created_at TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE datatiles_signatures (
  signature_id TEXT PRIMARY KEY,
  manifest_id TEXT NOT NULL REFERENCES datatiles_integrity_manifests(manifest_id) ON DELETE CASCADE,
  signature_scheme TEXT NOT NULL,
  signature_encoding TEXT NOT NULL,
  signature BLOB NOT NULL,
  key_id TEXT NOT NULL,
  public_key BLOB,
  signer_agent_id TEXT REFERENCES datatiles_provenance_agents(agent_id) ON DELETE SET NULL,
  signed_at TEXT NOT NULL,
  verification_material_json TEXT,
  UNIQUE(manifest_id, signature_scheme, key_id, signature)
) WITHOUT ROWID;
CREATE INDEX datatiles_signatures_manifest ON datatiles_signatures(manifest_id);
CREATE INDEX datatiles_signatures_key ON datatiles_signatures(key_id);

INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:integrity_profile','DataTiles-Integrity-Manifest-1');
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:signature_profile','DataTiles-Ed25519-Signature-1');
PRAGMA user_version = 6;
