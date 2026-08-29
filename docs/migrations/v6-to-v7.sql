CREATE TABLE datatiles_commercial_products (
  product_id TEXT PRIMARY KEY,
  edition TEXT,
  issuer TEXT NOT NULL,
  issuer_uri TEXT,
  terms_uri TEXT NOT NULL,
  license_service_uri TEXT,
  protection_profile TEXT NOT NULL DEFAULT 'DataTiles-Protected-Distribution-1',
  created_at TEXT NOT NULL,
  metadata_json TEXT
) WITHOUT ROWID;

CREATE TABLE datatiles_drm_policies (
  product_id TEXT NOT NULL REFERENCES datatiles_commercial_products(product_id) ON DELETE CASCADE,
  policy_id TEXT NOT NULL,
  policy_profile TEXT NOT NULL DEFAULT 'W3C-ODRL-2.2',
  policy_json TEXT NOT NULL,
  PRIMARY KEY(product_id, policy_id)
) WITHOUT ROWID;
CREATE INDEX datatiles_drm_policy_product ON datatiles_drm_policies(product_id);

INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:drm_profile','DataTiles-Protected-Distribution-1');
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:rights_policy_profile','W3C-ODRL-2.2');
PRAGMA user_version = 7;
