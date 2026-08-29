# DataTiles 1.0-draft specification (schema revision 8)

## Status, audience, and reading convention

This document is the complete normative contract for DataTiles 1.0-draft. It is written for scientists, implementers, reviewers, and code-generating agents. An implementation MUST be possible from this document alone; repository source code is informative evidence, not an unstated part of the format.

The words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are interpreted as in BCP 14. Tables headed “Normative” and fenced algorithms are normative. Rationale and examples are informative. A conformance claim MUST identify the DataTiles specification version, schema revision, component class, and optional profiles.

## 1. Purpose and model

DataTiles is MBTiles-compatible storage for multidimensional raster matrices and vector features. It adds an unordered, typed scientific coordinate map to the MBTiles spatial address:

```text
(zoom_level, tile_column, tile_row, {dimension_name: point_or_interval})
  -> (content_profile, tile_blob)
```

For example, two tiles may share `(z,x,y)` but differ by variable, valid time, depth, ensemble, scenario, or band. A coordinate set identifies one coherent two-dimensional slice. DataTiles retains an ordinary MBTiles `metadata` interface and exposes one selected slice through an ordinary four-column `tiles` interface.

DataTiles does not define interpolation, portrayal, a calendar other than timezone-aware ISO 8601 instants, an AI model, or a safety certification. Numeric measurements and rendered portrayals are distinct content profiles.

## 2. Conformance classes

| Class | Required behavior |
|---|---|
| Container reader | Open SQLite safely; verify identity and revision; discover dimensions, coordinate sets, content, CRS, provenance, and tiles; canonicalize values; read selected MBTiles slice. |
| Container writer | All reader behavior; create the schema in §5; enforce constraints; update managed metadata and slice state transactionally. |
| DNT1 codec | Encode or decode §11 exactly and enforce its resource limits. |
| MBTiles exporter | Materialize a compatible slice using §9.2. |
| HTTP service | Implement the core resources in §14 and state only conformance actually tested. |
| FAIR publication profile | Meet every MUST in §13 and retain validation evidence. |

A partial implementation MUST NOT claim the class whose requirements it omits.

## 3. Container identity and SQLite rules

- The file MUST be SQLite 3 and SHOULD use `.datatiles`.
- `PRAGMA application_id` MUST equal hexadecimal `0x44415441` (`DATA`).
- `PRAGMA user_version` MUST equal `8`.
- Foreign keys MUST be enabled by writers and validators.
- Text is UTF-8. JSON is UTF-8 and MUST reject NaN and infinities.
- The spatial tile matrix is Web Mercator; rows stored in the database use TMS orientation.
- `zoom_level` MUST be an integer in `[0,30]`; column and row MUST be in `[0,2^zoom_level)`.
- XYZ row `y_xyz` converts to stored row `2^z - 1 - y_xyz`.

The extension version is independent of the scientific dataset version. `datatiles:version` identifies this format; ordinary `version`, when present, identifies the dataset.

## 4. Logical object model

| Object | Identity | Meaning |
|---|---|---|
| dimension | unique name | typed scientific axis definition |
| value | dimension plus canonical value | point or interval on that axis |
| coordinate set | canonical SHA-256 key | unordered map of dimension to value |
| content profile | coordinate-set ID | raster/vector type and BLOB interpretation |
| tile | spatial address plus coordinate-set ID | payload BLOB |
| CRS | local ID and external identifier | spatial, vertical, temporal, compound, or engineering reference |
| provenance node/relation | stable application ID | evidence graph and tile lineage |
| selected slice | singleton | coordinate set visible to MBTiles readers |

Integer IDs are local implementation details. Portable identity comes from dimension names, canonical values, persistent metadata identifiers, and provenance identifiers.

## 5. Normative relational schema

An implementation MUST create the following columns, keys, checks, foreign-key actions, indexes, trigger, singleton row, and view. Additional namespaced objects MAY be added but MUST NOT change these meanings.

### 5.1 MBTiles interface

```sql
CREATE TABLE metadata(name TEXT NOT NULL, value TEXT NOT NULL, UNIQUE(name));

CREATE VIEW tiles AS
SELECT t.zoom_level,t.tile_column,t.tile_row,t.tile_data
FROM datatiles_tiles AS t
JOIN datatiles_selected_slice AS s ON s.singleton=1
WHERE t.coordinate_set_id=s.coordinate_set_id;
```

The exposed column order MUST be exactly `zoom_level,tile_column,tile_row,tile_data`. MBTiles permits its schemas to be implemented as views; §9.2 supplies a physical-table fallback for conservative adapters.

### 5.2 Dimensions, values, and coordinate sets

```sql
CREATE TABLE datatiles_dimensions(
 dimension_id INTEGER PRIMARY KEY,
 name TEXT NOT NULL UNIQUE,
 value_type TEXT NOT NULL CHECK(value_type IN ('text','integer','float','datetime','boolean')),
 axis TEXT CHECK(axis IS NULL OR axis IN ('T','Z','E','C','O')),
 unit TEXT, description TEXT, ordering INTEGER NOT NULL DEFAULT 0,
 required INTEGER NOT NULL DEFAULT 1 CHECK(required IN (0,1)),
 extent_kind TEXT NOT NULL DEFAULT 'point'
   CHECK(extent_kind IN ('point','interval','point_or_interval')));

CREATE TABLE datatiles_values(
 value_id INTEGER PRIMARY KEY,
 dimension_id INTEGER NOT NULL REFERENCES datatiles_dimensions(dimension_id) ON DELETE CASCADE,
 canonical_value TEXT NOT NULL,
 text_value TEXT, integer_value INTEGER, float_value REAL,
 upper_canonical_value TEXT, upper_text_value TEXT,
 upper_integer_value INTEGER, upper_float_value REAL,
 lower_inclusive INTEGER NOT NULL DEFAULT 1 CHECK(lower_inclusive IN (0,1)),
 upper_inclusive INTEGER NOT NULL DEFAULT 1 CHECK(upper_inclusive IN (0,1)),
 is_interval INTEGER NOT NULL DEFAULT 0 CHECK(is_interval IN (0,1)),
 UNIQUE(dimension_id,canonical_value));

CREATE TABLE datatiles_coordinate_sets(
 coordinate_set_id INTEGER PRIMARY KEY, canonical_key TEXT NOT NULL UNIQUE);

CREATE TABLE datatiles_coordinates(
 coordinate_set_id INTEGER NOT NULL REFERENCES datatiles_coordinate_sets(coordinate_set_id) ON DELETE CASCADE,
 dimension_id INTEGER NOT NULL REFERENCES datatiles_dimensions(dimension_id) ON DELETE RESTRICT,
 value_id INTEGER NOT NULL REFERENCES datatiles_values(value_id) ON DELETE RESTRICT,
 PRIMARY KEY(coordinate_set_id,dimension_id), UNIQUE(coordinate_set_id,value_id));
```

Writers MUST create typed value indexes on `(dimension_id,text_value)`, `(dimension_id,integer_value)`, `(dimension_id,float_value)` and their lower/upper interval equivalents. They MUST reject a `datatiles_coordinates` row whose value belongs to another dimension, using a trigger or equivalent transactionally enforced logic.

### 5.3 Content and tiles

```sql
CREATE TABLE datatiles_contents(
 coordinate_set_id INTEGER PRIMARY KEY REFERENCES datatiles_coordinate_sets(coordinate_set_id) ON DELETE CASCADE,
 data_type TEXT NOT NULL CHECK(data_type IN ('raster','vector')),
 media_type TEXT NOT NULL, encoding TEXT NOT NULL,
 schema_json TEXT NOT NULL DEFAULT '{}');

CREATE TABLE datatiles_tiles(
 zoom_level INTEGER NOT NULL CHECK(zoom_level BETWEEN 0 AND 30),
 tile_column INTEGER NOT NULL CHECK(tile_column>=0),
 tile_row INTEGER NOT NULL CHECK(tile_row>=0),
 coordinate_set_id INTEGER NOT NULL REFERENCES datatiles_coordinate_sets(coordinate_set_id) ON DELETE CASCADE,
 tile_data BLOB NOT NULL,
 PRIMARY KEY(zoom_level,tile_column,tile_row,coordinate_set_id)) WITHOUT ROWID;
```

Writers MUST index `datatiles_contents(data_type,media_type,encoding)` and `datatiles_tiles(coordinate_set_id,zoom_level,tile_column,tile_row)`.

### 5.4 CRS

```sql
CREATE TABLE datatiles_crs(
 crs_id INTEGER PRIMARY KEY,
 role TEXT NOT NULL CHECK(role IN ('horizontal','vertical','temporal','compound','engineering')),
 authority TEXT, code TEXT, uri TEXT, wkt2 TEXT, projjson TEXT,
 coordinate_epoch REAL, UNIQUE(role,authority,code));
```

A CRS row MUST have at least one of authority+code, URI, WKT2, or PROJJSON. URI values, when non-null, MUST be unique. Dynamic CRSs SHOULD state coordinate epoch.

### 5.5 Provenance

```sql
CREATE TABLE datatiles_provenance_agents(
 agent_id TEXT PRIMARY KEY, agent_type TEXT NOT NULL DEFAULT 'organization'
 CHECK(agent_type IN ('person','organization','software')),
 label TEXT NOT NULL, uri TEXT, attributes_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE datatiles_provenance_activities(
 activity_id TEXT PRIMARY KEY, activity_type TEXT NOT NULL, label TEXT NOT NULL,
 started_at TEXT, ended_at TEXT, software TEXT, parameters_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE datatiles_provenance_entities(
 entity_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, label TEXT NOT NULL,
 uri TEXT, checksum_algorithm TEXT, checksum TEXT, attributes_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE datatiles_provenance_relations(
 subject_id TEXT NOT NULL,
 predicate TEXT NOT NULL CHECK(predicate IN
 ('wasGeneratedBy','used','wasDerivedFrom','wasAttributedTo','wasAssociatedWith','specializationOf')),
 object_id TEXT NOT NULL, attributes_json TEXT NOT NULL DEFAULT '{}',
 PRIMARY KEY(subject_id,predicate,object_id));
CREATE TABLE datatiles_tile_provenance(
 zoom_level INTEGER NOT NULL,tile_column INTEGER NOT NULL,tile_row INTEGER NOT NULL,
 coordinate_set_id INTEGER NOT NULL,
 entity_id TEXT NOT NULL REFERENCES datatiles_provenance_entities(entity_id) ON DELETE CASCADE,
 PRIMARY KEY(zoom_level,tile_column,tile_row,coordinate_set_id,entity_id),
 FOREIGN KEY(zoom_level,tile_column,tile_row,coordinate_set_id)
 REFERENCES datatiles_tiles(zoom_level,tile_column,tile_row,coordinate_set_id) ON DELETE CASCADE) WITHOUT ROWID;
```

All `*_json` values MUST be JSON objects. Provenance IDs SHOULD be URIs or stable application identifiers. Checksums SHOULD accompany source and generated entities.

### 5.6 Selection state

```sql
CREATE TABLE datatiles_selected_slice(
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 coordinate_set_id INTEGER REFERENCES datatiles_coordinate_sets(coordinate_set_id) ON DELETE SET NULL);
INSERT INTO datatiles_selected_slice VALUES(1,NULL);
```

There MUST be exactly one singleton row.

## 6. Typed values and canonicalization

| Type | Accepted value | Canonical text | Typed storage |
|---|---|---|---|
| text | non-null string representation | unchanged Unicode | lower `text_value` |
| integer | integer, never Boolean or fractional float | base-10, no leading `+` | lower `integer_value` |
| float | finite number, never Boolean | 17-significant-digit round-trip representation | lower `float_value` |
| datetime | ISO 8601 instant with timezone | UTC with six fractional digits and `Z` | text plus epoch seconds in float |
| boolean | Boolean, 0/1, or case-insensitive `true,false,0,1` | `true` or `false` | lower integer 1 or 0 |

Point values set `is_interval=0`, both inclusive flags to 1, upper columns to NULL, and `canonical_value` to the canonical point text.

Intervals preserve lower/upper values and flags. Their canonical text is `[lower,upper]`, `[lower,upper)`, `(lower,upper]`, or `(lower,upper)`. Lower MUST NOT exceed upper. Equal bounds are valid only when both inclusive. `extent_kind` MUST be enforced.

## 7. Coordinate identity algorithm

Given a map `coordinates`:

```text
1. Reject unknown dimension names.
2. Reject every missing dimension whose required flag is 1.
3. Canonicalize each point or interval using §6.
4. Form pairs [dimension_name, canonical_value].
5. Sort pairs ascending by Unicode dimension name.
6. Serialize as UTF-8 JSON with no whitespace and with non-ASCII preserved.
7. canonical_key = lowercase_hex(SHA-256(serialized_bytes)).
8. Reuse the matching coordinate set, or insert it and its members atomically.
```

Test vector: the coordinate map `{"pressure":850,"variable":"temperature"}` serializes as `[["pressure","850"],["variable","temperature"]]`. Dimension insertion order MUST NOT affect the digest.

## 8. Content profiles

Every coordinate set containing tiles MUST have exactly one profile. All its tiles share `data_type`, `media_type`, `encoding`, and `schema_json`. `media_type` is lowercase and contains `/`; `schema_json` is a JSON object.

| Data | media type | encoding | requirements |
|---|---|---|---|
| numeric matrix | `application/vnd.datatiles.numeric` | `DNT1` | §11 |
| PNG portrayal | `image/png` | `PNG` | valid PNG |
| JPEG portrayal | `image/jpeg` | `JPEG` | valid JPEG |
| WebP portrayal | `image/webp` | `WEBP` | valid WebP |
| vector features | `application/vnd.mapbox-vector-tile` | `MVT+gzip` | gzip-framed MVT; schema contains valid `vector_layers` |
| vector features | `application/geo+json` | `GeoJSON` | UTF-8 Feature or FeatureCollection |

`raster` means a spatial matrix or image; `vector` means spatial features. A portrayal MUST NOT be represented as original numeric measurement. Mixed profiles MAY coexist in one file because coordinate sets distinguish them.

## 9. MBTiles compatibility and fallback

### 9.1 Zero-copy selected slice

Selection MUST run in one transaction:

```text
1. Resolve the complete coordinate set; reject if absent.
2. Set the singleton coordinate_set_id.
3. Project the content profile to metadata.format:
   image/png -> png; image/jpeg -> jpg; image/webp -> webp;
   application/vnd.mapbox-vector-tile with MVT+gzip -> pbf;
   otherwise -> its media type.
4. For MVT, write compact deterministic metadata.json containing vector_layers.
5. For non-MVT, remove stale metadata.json.
```

An MBTiles-aware SQLite consumer can then read the selected `tiles` view. It cannot discover or change multidimensional coordinates.

### 9.2 Standalone physical-table export

Adapters sometimes implement less than MBTiles permits and reject views, extension tables, or nonzero application IDs. An MBTiles exporter MUST therefore be able to materialize a selected compatible slice as a separate `.mbtiles` file:

1. Resolve an explicitly supplied complete coordinate set, or the selected singleton.
2. Accept only PNG, JPEG, WebP, or gzip MVT. Reject DNT1, GeoJSON, and unknown encodings rather than relabel bytes.
3. Create a new SQLite file; never overwrite an existing target implicitly.
4. Create physical `metadata(name,value)` and `tiles(zoom_level,tile_column,tile_row,tile_data)` tables with unique indexes.
5. Copy BLOBs in stored TMS orientation, ordered by `(z,x,y)`, without transformation.
6. Copy only standard MBTiles metadata: `name,bounds,center,attribution,description,type,version`; set `format`; derive `minzoom,maxzoom`; add valid `json` for MVT.
7. Do not copy `datatiles_*` objects or `datatiles:*` metadata. Leave the output application ID at SQLite default unless a registered MBTiles ID is deliberately used.
8. Commit, run `integrity_check`, and publish atomically.

For numeric data a producer MUST first create a provenance-linked portrayal slice with an explicit color scale, nodata rule, resampling method, and units. Silent conversion would destroy meaning. OpenLayers applications then consume the exported file through their MBTiles adapter, tile server, or SQLite/WASM bridge. See `mbtiles-fallback.md`.

## 10. Scientific CRS and provenance semantics

Horizontal and vertical datums MUST be explicit for scientific elevation/depth use. A vertical value such as “10 m” is incomplete without its positive direction and datum in metadata or referenced CRS. Temporal dimensions MUST state their semantics (valid time, analysis time, acquisition time, and so on) in description.

Derived data MUST identify source entities, the generating activity, software version, parameters, and responsible agent. Tile-level links SHOULD be used when lineage differs spatially. A derived AI output SHOULD record model identifier and digest, training-data reference, feature schema, calibration/version, uncertainty semantics, and inference activity.

## 11. DNT1 numeric-array encoding

### 11.1 Byte layout

| Offset | Length | Meaning |
|---|---:|---|
| 0 | 4 | ASCII `DNT1` |
| 4 | 4 | unsigned big-endian JSON header byte length |
| 8 | header length | UTF-8 compact JSON object |
| remainder | derived | raw or zlib-compressed numeric payload |

The only header keys are `dtype,shape,byteorder,compression,nodata,scale,offset,unit`. Required keys are `dtype,shape,byteorder,compression`. Unknown keys MUST be rejected.

| Field | Allowed values/default |
|---|---|
| dtype | `int8,uint8,int16,uint16,int32,uint32,int64,uint64,float32,float64` |
| shape | array of 1–8 positive integers; product at most 16,777,216 |
| byteorder | `little` or `big` |
| compression | `none` or `zlib` |
| nodata | finite number or null; default null |
| scale | finite number; default 1.0 |
| offset | finite number; default 0.0 |
| unit | string up to 1024 characters or null |

Header length MUST NOT exceed 1,048,576 bytes. Decoded element count MUST NOT exceed 16,777,216. The uncompressed payload length MUST exactly equal `product(shape) * sizeof(dtype)`. A zlib stream MUST end exactly at that length with no unused trailing data. Array order is C row-major. Physical value is `stored_value * scale + offset`; nodata comparison occurs against the stored value before scaling.

### 11.2 Decoder algorithm

```text
verify magic and minimum length
read big-endian header length; enforce limit and bounds
parse UTF-8 JSON object; require allowed fields and finite metadata
compute element count with overflow/limit checks
compute exact expected byte length
decompress with an output cap of expected+1, or use raw payload
require exact length, complete zlib stream, and no trailing data
unpack using declared byte order and dtype in C order
return values plus shape, dtype, nodata, scale, offset, and unit
```

## 12. Metadata

All MBTiles 1.3 rules apply to the interface. Required extension keys are `datatiles:version` (`1.0-draft`), `datatiles:dimensions` (compact JSON array generated from ordered definitions), and `datatiles:default_media_type`.

Writers MUST manage `format`, `json`, `datatiles:dimensions`, and `datatiles:default_media_type`; generic setters MUST NOT modify them. `bounds,center,minzoom,maxzoom` SHOULD be supplied when known.

## 13. FAIR-by-design publication profile

A published object MUST provide directly or through a resolvable catalog record: globally unique object identifier; title and abstract; publisher and creators/contributors; issued/modified dates; spatial and temporal extents; variable definitions and units; horizontal and vertical CRS; license URI and access rights; scientific version; vocabulary-qualified keywords; provenance; source identifiers and checksums; and distribution/access URLs.

Recommended keys are `datatiles:identifier,datatiles:license,datatiles:access_rights,datatiles:creators,datatiles:keywords,datatiles:issued,datatiles:modified,datatiles:provenance,datatiles:landing_page`. The object identifier MUST NOT be merely a temporary download URL. A new scientific revision MUST receive a new version and SHOULD receive a new persistent identifier. Metadata SHOULD remain resolvable if data bytes are withdrawn. License MUST NOT be inferred from attribution.

FAIR is a property of the object plus its stewardship system, not a checkbox inside SQLite. Catalog registration, PID resolution, long-term metadata retention, open protocol access, vocabulary governance, and community standards require external evidence. See `fair-by-design.md`.

## 14. Query and HTTP semantics

Exact lookup MUST use the complete coordinate set. Partial discovery MAY intersect coordinate-set IDs by supplied point dimensions. Typed range searches SHOULD use the appropriate lower/upper columns and inclusivity. Nearest-neighbor selection and interpolation MUST NOT be implicit.

The HTTP profile uses OGC API patterns without claiming certification. Core resources are landing `/`, `/conformance`, `/api`, `/collections`, `/collections/{id}`, `/dimensions`, `/crs`, `/provenance`, `/contents`, `/tiles`, and `/tiles/WebMercatorQuad/{z}/{x}/{y}`. URL tile rows are XYZ and convert at the database boundary. Point coordinates are query parameters; intervals use `lower/upper`.

Derived point, profile, contour, predicate-query, and surface resources MAY be supplied. Each result MUST identify inputs, parameters, units, missing-data semantics, derivation status, and deterministic digest where ordering is defined. A numeric surface is data, not portrayal. Servers MUST bound sample counts, grids, extents, concurrency, and execution time.

## 15. Validation and security

A container validator MUST check application ID, schema revision, required objects and exact interface columns; SQLite integrity and foreign keys; canonical keys and required dimensions; matrix bounds; content profiles and payload framing; selected-profile metadata; declared JSON structure; and FAIR evidence when declared.

Readers MUST treat SQLite, JSON, compressed streams, shapes, coordinate counts, strings, and BLOBs as hostile input. Untrusted files SHOULD be read-only with extension loading disabled. Implementations MUST cap allocation and decompression before performing them.

Scientific validation is separate and SHOULD test units, datum, ranges, nodata fraction, extent, vocabulary, uncertainty, lineage, and declared reference statistics.

## 16. Writer implementation recipe

1. Create §5 objects, pragmas, indexes, trigger, and singleton in one empty SQLite file.
2. Insert `name`, `format`, and the three managed DataTiles metadata keys.
3. Implement §6 canonicalization and verify §7 test vector.
4. Add dimensions; regenerate `datatiles:dimensions` deterministically.
5. Insert/reuse values and coordinate sets transactionally.
6. Insert one immutable content profile before the first tile in that set.
7. Validate spatial coordinates, convert XYZ only at the API boundary, and upsert tile bytes.
8. Implement selection exactly as §9.1.
9. Add CRS and provenance through validated JSON-object interfaces.
10. Implement validation before HTTP or export features.
11. Add the DNT1 class only after passing all §11 bounds tests.
12. Add standalone fallback using §9.2 and confirm physical tables and no extension objects.

An implementation MUST NOT guess payload type from BLOB signatures when a content profile is available.

## 17. Interoperability test vectors

| Case | Expected result |
|---|---|
| same coordinate map in two insertion orders | same canonical key |
| naive datetime | reject |
| `2026-08-27T01:00:00+01:00` | canonical `2026-08-27T00:00:00.000000Z` |
| interval `(1,1]` | reject as empty |
| XYZ `(z=3,y=1)` | stored TMS row 6 |
| selected gzip MVT | `format=pbf` and valid `json.vector_layers` |
| select PNG after MVT | `format=png`, stale `json` absent |
| standalone PNG export | physical two-column metadata and four-column tiles tables |
| standalone DNT1 export | reject until explicit portrayal exists |
| DNT1 unknown header key or trailing zlib bytes | reject |
| populated set without content profile | invalid |

## 18. Evolution

Readers MUST reject unsupported schema revisions rather than infer them. A migration MUST be transactional, deterministic, documented, and preserve scientific identity. Existing columns MUST NOT be reinterpreted. Future revisions may define non-Gregorian calendars, content deduplication, tile checksums, dimension overviews, additional vector encodings, and further OGC API profiles.


## Zarr source-ingestion profile

A conforming `zarr2datatiles` source utility MUST follow `zarr-source-profile.md`. Zarr is a multi-object N-dimensional store rather than a single-file checksum domain. Local directory stores MUST use the canonical `zarr-tree-sha256-v1` digest defined there; remote stores MUST be bound to an immutable store/snapshot by an authoritative checksum supplied by the publication workflow. The importer MUST preserve the source identifier, checksum algorithm/value, CF semantics when present, dimensions, units, declared resampling, source/output rights, and tile-level lineage. It MUST NOT persist backend credentials or infer data licensing from transport accessibility. Zarr format 2 and 3 MAY be accepted; any required format, group, consolidated-metadata policy, and non-secret storage-option keys MUST be recorded as conversion parameters. Scientific arrays MUST remain numeric DNT1 evidence rather than being silently converted to portrayal imagery.


## Cryptographic integrity profile

Schema revision 6 adds optional canonical integrity manifests and digital signatures. Implementations claiming the native profile MUST follow `digital-signatures.md` and `specification-revision-6-addendum.md`. The signed subject is the canonical logical DataTiles object, not raw SQLite file bytes. The native signature algorithm is Ed25519 over `DataTiles-Integrity-Manifest-1`; SHA-256 remains the digest primitive. Signature metadata MUST distinguish cryptographic validity from trust in signer identity. Signature presence is optional and MUST NOT be presented as proof of FAIRness, scientific correctness, legal compliance, hydrographic authority, or navigation safety. Servers MUST NOT expose private-key signing endpoints as part of the standard DataTiles read service.


## Optional commercial protected distribution

Schema revision 7 adds commercial-product and machine-readable policy metadata. Implementations supporting commercial protected distribution MUST follow `drm-and-commercial-licensing.md` and `specification-revision-7-addendum.md`. `DataTiles-Protected-Distribution-1` is an optional outer encrypted distribution package; after authorized decryption the payload MUST be the exact ordinary DataTiles SQLite object. W3C ODRL 2.2 is the default machine-readable rights-policy model. Technical DRM grants MUST NOT be interpreted as source relicensing, scientific certification, hydrographic authority, FAIR certification, or navigation safety. Secrets MUST remain outside the DataTiles metadata/provenance graph and standard read-only service.


## Release versioning

Schema revision 8 defines `DataTiles-Release-Versioning-1`. A published DataTiles object MAY declare one `datatiles_release` record containing stable `product_id`, human `version`, monotonically increasing integer `sequence`, RFC 3339 `released_at`, and optional predecessor/release-notes/update links. Consumers MUST use `sequence`, not lexical `version`, to order releases. Published versions are immutable; a correction is a new DataTiles object with a larger sequence, new checksum, and new signature where signing is used. See `specification-revision-8-addendum.md`.
