PRAGMA foreign_keys = ON;
PRAGMA application_id = 0x44415441; -- "DATA"
PRAGMA user_version = 8;

CREATE TABLE metadata (
  name TEXT NOT NULL,
  value TEXT NOT NULL,
  UNIQUE(name)
);

CREATE TABLE datatiles_dimensions (
  dimension_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  value_type TEXT NOT NULL CHECK(value_type IN ('text','integer','float','datetime','boolean')),
  axis TEXT CHECK(axis IS NULL OR axis IN ('T','Z','E','C','O')),
  unit TEXT,
  description TEXT,
  ordering INTEGER NOT NULL DEFAULT 0,
  required INTEGER NOT NULL DEFAULT 1 CHECK(required IN (0,1)),
  extent_kind TEXT NOT NULL DEFAULT 'point' CHECK(extent_kind IN ('point','interval','point_or_interval'))
);

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
CREATE TABLE datatiles_values (
  value_id INTEGER PRIMARY KEY,
  dimension_id INTEGER NOT NULL REFERENCES datatiles_dimensions(dimension_id) ON DELETE CASCADE,
  canonical_value TEXT NOT NULL,
  text_value TEXT,
  integer_value INTEGER,
  float_value REAL,
  upper_canonical_value TEXT,
  upper_text_value TEXT,
  upper_integer_value INTEGER,
  upper_float_value REAL,
  lower_inclusive INTEGER NOT NULL DEFAULT 1 CHECK(lower_inclusive IN (0,1)),
  upper_inclusive INTEGER NOT NULL DEFAULT 1 CHECK(upper_inclusive IN (0,1)),
  is_interval INTEGER NOT NULL DEFAULT 0 CHECK(is_interval IN (0,1)),
  UNIQUE(dimension_id, canonical_value)
);

CREATE INDEX datatiles_values_typed_text ON datatiles_values(dimension_id, text_value);
CREATE INDEX datatiles_values_typed_integer ON datatiles_values(dimension_id, integer_value);
CREATE INDEX datatiles_values_typed_float ON datatiles_values(dimension_id, float_value);
CREATE INDEX datatiles_values_interval_text ON datatiles_values(dimension_id, text_value, upper_text_value);
CREATE INDEX datatiles_values_interval_integer ON datatiles_values(dimension_id, integer_value, upper_integer_value);
CREATE INDEX datatiles_values_interval_float ON datatiles_values(dimension_id, float_value, upper_float_value);

CREATE TABLE datatiles_coordinate_sets (
  coordinate_set_id INTEGER PRIMARY KEY,
  canonical_key TEXT NOT NULL UNIQUE
);

CREATE TABLE datatiles_coordinates (
  coordinate_set_id INTEGER NOT NULL REFERENCES datatiles_coordinate_sets(coordinate_set_id) ON DELETE CASCADE,
  dimension_id INTEGER NOT NULL REFERENCES datatiles_dimensions(dimension_id) ON DELETE RESTRICT,
  value_id INTEGER NOT NULL REFERENCES datatiles_values(value_id) ON DELETE RESTRICT,
  PRIMARY KEY(coordinate_set_id, dimension_id),
  UNIQUE(coordinate_set_id, value_id)
);

CREATE INDEX datatiles_coordinates_value ON datatiles_coordinates(dimension_id, value_id, coordinate_set_id);

-- A coordinate set identifies an N-dimensional slice; its content profile
-- states whether the BLOB is a raster matrix or vector feature tile.
CREATE TABLE datatiles_contents (
  coordinate_set_id INTEGER PRIMARY KEY REFERENCES datatiles_coordinate_sets(coordinate_set_id) ON DELETE CASCADE,
  data_type TEXT NOT NULL CHECK(data_type IN ('raster','vector')),
  media_type TEXT NOT NULL,
  encoding TEXT NOT NULL,
  schema_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX datatiles_contents_type ON datatiles_contents(data_type, media_type, encoding);

CREATE TABLE datatiles_tiles (
  zoom_level INTEGER NOT NULL CHECK(zoom_level BETWEEN 0 AND 30),
  tile_column INTEGER NOT NULL CHECK(tile_column >= 0),
  tile_row INTEGER NOT NULL CHECK(tile_row >= 0),
  coordinate_set_id INTEGER NOT NULL REFERENCES datatiles_coordinate_sets(coordinate_set_id) ON DELETE CASCADE,
  tile_data BLOB NOT NULL,
  PRIMARY KEY(zoom_level, tile_column, tile_row, coordinate_set_id)
) WITHOUT ROWID;

CREATE INDEX datatiles_tiles_slice ON datatiles_tiles(coordinate_set_id, zoom_level, tile_column, tile_row);

CREATE TABLE datatiles_crs (
  crs_id INTEGER PRIMARY KEY,
  role TEXT NOT NULL CHECK(role IN ('horizontal','vertical','temporal','compound','engineering')),
  authority TEXT,
  code TEXT,
  uri TEXT,
  wkt2 TEXT,
  projjson TEXT,
  coordinate_epoch REAL,
  UNIQUE(role, authority, code)
);
CREATE UNIQUE INDEX datatiles_crs_uri ON datatiles_crs(uri) WHERE uri IS NOT NULL;

CREATE TABLE datatiles_provenance_agents (
  agent_id TEXT PRIMARY KEY,
  agent_type TEXT NOT NULL DEFAULT 'organization' CHECK(agent_type IN ('person','organization','software')),
  label TEXT NOT NULL,
  uri TEXT,
  attributes_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE datatiles_provenance_activities (
  activity_id TEXT PRIMARY KEY,
  activity_type TEXT NOT NULL,
  label TEXT NOT NULL,
  started_at TEXT,
  ended_at TEXT,
  software TEXT,
  parameters_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE datatiles_provenance_entities (
  entity_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  label TEXT NOT NULL,
  uri TEXT,
  checksum_algorithm TEXT,
  checksum TEXT,
  attributes_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE datatiles_provenance_relations (
  subject_id TEXT NOT NULL,
  predicate TEXT NOT NULL CHECK(predicate IN ('wasGeneratedBy','used','wasDerivedFrom','wasAttributedTo','wasAssociatedWith','specializationOf')),
  object_id TEXT NOT NULL,
  attributes_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(subject_id, predicate, object_id)
);

CREATE TABLE datatiles_tile_provenance (
  zoom_level INTEGER NOT NULL,
  tile_column INTEGER NOT NULL,
  tile_row INTEGER NOT NULL,
  coordinate_set_id INTEGER NOT NULL,
  entity_id TEXT NOT NULL REFERENCES datatiles_provenance_entities(entity_id) ON DELETE CASCADE,
  PRIMARY KEY(zoom_level,tile_column,tile_row,coordinate_set_id,entity_id),
  FOREIGN KEY(zoom_level,tile_column,tile_row,coordinate_set_id)
    REFERENCES datatiles_tiles(zoom_level,tile_column,tile_row,coordinate_set_id) ON DELETE CASCADE
) WITHOUT ROWID;

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
CREATE TABLE datatiles_identifiers (
  identifier_id INTEGER PRIMARY KEY,
  scheme TEXT NOT NULL,
  identifier TEXT NOT NULL,
  uri TEXT,
  is_primary INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0,1)),
  UNIQUE(scheme,identifier)
);
CREATE UNIQUE INDEX datatiles_one_primary_identifier ON datatiles_identifiers(is_primary) WHERE is_primary=1;
CREATE TABLE datatiles_related_identifiers (
  scheme TEXT NOT NULL, identifier TEXT NOT NULL, relation_type TEXT NOT NULL, uri TEXT,
  resource_type TEXT, relation_information TEXT,
  PRIMARY KEY(scheme,identifier,relation_type)
) WITHOUT ROWID;
CREATE TABLE datatiles_rights (
  rights_id INTEGER PRIMARY KEY,
  scope TEXT NOT NULL CHECK(scope IN ('dataset','metadata','source','portrayal','software','other')),
  license_expression TEXT NOT NULL, license_uri TEXT, rights_holder TEXT, rights_holder_uri TEXT,
  attribution_text TEXT, copyright_notice TEXT,
  access_rights TEXT NOT NULL DEFAULT 'open' CHECK(access_rights IN ('open','embargoed','restricted','closed')),
  source_entity_id TEXT REFERENCES datatiles_provenance_entities(entity_id) ON DELETE CASCADE,
  applies_to TEXT, UNIQUE(scope,source_entity_id,license_expression,applies_to)
);
CREATE INDEX datatiles_rights_scope ON datatiles_rights(scope,access_rights);
CREATE TABLE datatiles_fair_agents (
  agent_id TEXT NOT NULL REFERENCES datatiles_provenance_agents(agent_id) ON DELETE CASCADE,
  role TEXT NOT NULL, sequence INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(agent_id,role)
) WITHOUT ROWID;
CREATE TABLE datatiles_publication_evidence (
  evidence_type TEXT NOT NULL, uri TEXT NOT NULL, checked_at TEXT, checksum_algorithm TEXT, checksum TEXT, notes TEXT,
  PRIMARY KEY(evidence_type,uri)
) WITHOUT ROWID;
CREATE TABLE datatiles_selected_slice (
  singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
  coordinate_set_id INTEGER REFERENCES datatiles_coordinate_sets(coordinate_set_id) ON DELETE SET NULL
);
INSERT INTO datatiles_selected_slice(singleton, coordinate_set_id) VALUES (1, NULL);

CREATE VIEW tiles AS
SELECT t.zoom_level, t.tile_column, t.tile_row, t.tile_data
FROM datatiles_tiles AS t
JOIN datatiles_selected_slice AS s ON s.singleton = 1
WHERE t.coordinate_set_id = s.coordinate_set_id;

CREATE TRIGGER datatiles_values_dimension_guard_insert
BEFORE INSERT ON datatiles_coordinates
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM datatiles_values v
    WHERE v.value_id = NEW.value_id AND v.dimension_id = NEW.dimension_id
  ) THEN RAISE(ABORT, 'value does not belong to dimension') END;
END;
