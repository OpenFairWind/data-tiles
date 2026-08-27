# Design evaluation against the concise DataTiles definition

## Definition under evaluation

> DataTiles is MBTiles for multidimensional data, storing both raster matrices and vector feature tiles.

This definition imposes four non-negotiable properties. Spatial indexing must retain MBTiles semantics; non-spatial coordinates must be first-class and typed; raster matrices and vector features must be distinguishable without inspecting arbitrary bytes; and one multidimensional slice must remain consumable through the standard MBTiles interface.

## Evaluation and corrections

| Concern | Earlier condition | Evaluation | Revision 3 resolution |
|---|---|---|---|
| MBTiles interface | Four-column `tiles` view selected one coordinate set | Sound | Preserved exactly; selection also projects content metadata |
| Multidimensional identity | Canonical key used coordinate iteration ordered by local dimension ID | Semantically unstable across independently constructed files | Canonical pairs are sorted by dimension name; revision-2 migration recomputes keys |
| Raster semantics | DNT1 existed, but the global `format` row described every slice | Adequate only for homogeneous files | Each populated coordinate set declares `raster`, media type, encoding, and schema |
| Vector semantics | Arbitrary vector BLOBs were technically possible but not modeled | Failed the concise definition because type and schema were implicit | Explicit `vector` profiles support MVT+gzip, tiled GeoJSON, and declared extensions |
| Mixed content | Changing variables could change meaning without changing global format | Ambiguous and unsafe | Selection transactionally projects `format` and `json`; stale vector metadata is removed |
| File opening | A misspelled path silently created an empty SQLite file | Data-loss and debugging hazard | Missing paths, unrelated SQLite files, incomplete schemas, and unsupported revisions are rejected |
| HTTP service | Requests opened the database with a writable connection | Unnecessary mutation surface | The service uses SQLite URI read-only mode and `query_only` |
| Value validity | Open equal-bound intervals and nonzero integers as Booleans were accepted | Noncanonical semantics | Empty intervals and values other than Boolean/0/1 are rejected |
| Numeric security | DNT1 accepted unknown header fields and weak metadata types | Forward-compatibility and resource ambiguity | Strict fields, finite transforms/nodata, bounded units/shapes, and normalized decoder errors |
| Spatial bounds | Excessive zooms and non-finite/out-of-domain query extents were possible | Resource-exhaustion and invalid-analysis risk | Zoom is bounded to 0–30; CRS84 analysis extents must be finite and ordered |
| Publication | Core files existed but community and security surfaces were incomplete | Not yet GitHub-ready | Citation, contribution, conduct, security, issue, PR, dependency, CI, CD, licence, and notice files added |

## Resulting model

The identity of a stored object is:

```text
(z, x, y, canonical multidimensional coordinate set)
```

Its interpretation is supplied by exactly one content profile:

```text
(raster | vector, IETF media type, encoding, machine-readable schema)
```

Raster and vector are deliberately parallel content classes. A DNT1 bathymetric matrix, PNG portrayal, MVT observation layer, and tiled GeoJSON classification may coexist when their coordinate selectors differ. Content type is not encoded as a special spatial key and is not guessed from the BLOB.

## Compatibility conclusion

The revised design satisfies the concise definition while retaining MBTiles 1.3 compatibility. MBTiles permits views to implement its interfaces and permits raw image or vector BLOBs. DataTiles uses this latitude conservatively: an unaware reader receives one selected, metadata-consistent two-dimensional slice; an aware reader discovers all dimensions and content profiles. The extension does not claim that an ordinary MBTiles program can navigate the multidimensional space.

The HTTP design follows OGC API – Tiles resource patterns for tiled coverages, maps, and vector data, but the project makes no certification claim. MVT metadata follows MBTiles 1.3, while the actual protobuf payload remains governed by the Mapbox Vector Tile specification.
