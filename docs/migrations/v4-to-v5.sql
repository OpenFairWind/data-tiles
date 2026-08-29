-- DataTiles schema revision 5: FAIR publication identity and rights.
-- Revision 5 makes rights machine-actionable and separates object identifiers,
-- related identifiers, and publication evidence from generic MBTiles metadata.

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
  scheme TEXT NOT NULL,
  identifier TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  uri TEXT,
  resource_type TEXT,
  relation_information TEXT,
  PRIMARY KEY(scheme,identifier,relation_type)
) WITHOUT ROWID;

CREATE TABLE datatiles_rights (
  rights_id INTEGER PRIMARY KEY,
  scope TEXT NOT NULL CHECK(scope IN ('dataset','metadata','source','portrayal','software','other')),
  license_expression TEXT NOT NULL,
  license_uri TEXT,
  rights_holder TEXT,
  rights_holder_uri TEXT,
  attribution_text TEXT,
  copyright_notice TEXT,
  access_rights TEXT NOT NULL DEFAULT 'open' CHECK(access_rights IN ('open','embargoed','restricted','closed')),
  source_entity_id TEXT REFERENCES datatiles_provenance_entities(entity_id) ON DELETE CASCADE,
  applies_to TEXT,
  UNIQUE(scope,source_entity_id,license_expression,applies_to)
);
CREATE INDEX datatiles_rights_scope ON datatiles_rights(scope,access_rights);

CREATE TABLE datatiles_fair_agents (
  agent_id TEXT NOT NULL REFERENCES datatiles_provenance_agents(agent_id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  sequence INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(agent_id,role)
) WITHOUT ROWID;

CREATE TABLE datatiles_publication_evidence (
  evidence_type TEXT NOT NULL,
  uri TEXT NOT NULL,
  checked_at TEXT,
  checksum_algorithm TEXT,
  checksum TEXT,
  notes TEXT,
  PRIMARY KEY(evidence_type,uri)
) WITHOUT ROWID;

INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:fair_profile','FAIR-Guiding-Principles-2016');
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:provenance_profile','W3C-PROV-2013');
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:metadata_profile','DataCite-4.7');
INSERT OR IGNORE INTO metadata(name,value) VALUES ('datatiles:license_profile','SPDX-3.0.1-expression');
PRAGMA user_version = 5;
