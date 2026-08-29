CREATE TABLE datatiles_release (
  singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
  product_id TEXT NOT NULL,
  version TEXT NOT NULL,
  sequence INTEGER NOT NULL CHECK(sequence >= 1),
  released_at TEXT NOT NULL,
  previous_version TEXT,
  previous_identifier TEXT,
  release_notes_uri TEXT,
  update_uri TEXT,
  CHECK(product_id <> '' AND trim(product_id) = product_id),
  CHECK(version <> '' AND trim(version) = version)
);
CREATE UNIQUE INDEX datatiles_release_product_version ON datatiles_release(product_id, version);
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:versioning_profile','DataTiles-Release-Versioning-1');
PRAGMA user_version = 8;
