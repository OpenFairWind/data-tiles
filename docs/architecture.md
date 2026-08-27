# Architecture

The design separates four concerns:

1. `metadata` describes the tileset using the MBTiles interface.
2. `datatiles_dimensions` and `datatiles_values` define typed scientific axes and point/interval coordinate values.
3. `datatiles_coordinate_sets` plus `datatiles_coordinates` normalize arbitrary N-dimensional coordinates into stable identities.
4. `datatiles_contents` declares whether each coordinate set contains raster matrices or vector features, together with media type, encoding, and schema.
5. `datatiles_tiles` stores spatial tiles, while the `tiles` view and selected content metadata project one coordinate set into ordinary MBTiles.
6. `datatiles_crs` describes scientific coordinate systems without collapsing horizontal, vertical, and temporal roles.
7. Provenance tables record entities, activities, agents, relations, and tile/entity associations.
8. `numeric.py` encodes scientific arrays; `server.py` exposes raster and vector content through OGC API building blocks.
9. `analysis.py` decodes and caches numeric raster tiles to derive point observations, profiles, contours, and conjunctive spatial selections.
10. The OpenLayers playground is a replaceable client of those APIs; it contains no authoritative scientific values or pre-rendered map tiles.

This normalized model is preferable to adding fixed columns such as `time` and `elevation`: it supports arbitrary axes without schema migration. It is preferable to a JSON-only coordinate key because SQL can index typed values and execute range queries.

Exact reads first canonicalize a coordinate map, compute its SHA-256 identity, resolve the local coordinate-set ID, and then use the `datatiles_tiles` primary key. Discovery and range queries run through the inverted `datatiles_coordinates(dimension_id, value_id, coordinate_set_id)` index.

SQLite transactions provide atomic writes and slice changes. WAL mode is an application deployment choice and is not stored as a format requirement.

## Deliberate boundaries

- The format stores tiles; it does not prescribe rendering.
- Raster and vector are content semantics, not implicit guesses from arbitrary bytes.
- Spatial addressing remains Web Mercator/TMS for MBTiles interoperability.
- Variable vocabularies and non-Gregorian calendars remain future profiles.
- Irregular bounds are represented as intervals and are never silently approximated as points.

FAIR responsibilities cross these layers. The file carries machine-readable identity, semantics, CRS, lineage, licences, and access descriptions; the publishing repository supplies PID resolution, catalogue indexing, authentication policy when needed, and persistent metadata after withdrawal. The built-in FAIR report distinguishes container checks from those repository-level obligations.
