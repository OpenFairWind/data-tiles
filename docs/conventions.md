# DataTiles interoperability conventions

This document defines the interoperability conventions used by the semantic-variable extension and the NetCDF/GRIB/Zarr import utilities. The container specification remains authoritative for byte-level and schema behavior; these conventions define how common scientific concepts should be represented so independently developed software can discover and compare them.

## Variable identity

A DataTiles coordinate named `variable` is a producer-facing token used in multidimensional addresses. It is not, by itself, the scientific definition of the quantity. Every token should resolve through the semantic variable registry.

CF Standard Names are the preferred canonical vocabulary when a valid CF concept exists. A producer-local variable without a valid CF name must use an explicitly different vocabulary such as `source`; software must never manufacture a CF name merely to satisfy validation.

External identifiers are crosswalks. WMO GRIB2 discipline/category/parameter, GRIB short names, SeaDataNet/NERC vocabulary URIs, GCMD identifiers and provider-specific codes can all coexist for one semantic variable.

## Units

Units remain explicit at both semantic-registry and numeric-payload levels. A CF Standard Name does not justify discarding the source unit. Validation against a pinned CF table can verify the declared CF canonical unit; physical equivalence between alternate units requires a UDUNITS-capable validation profile rather than string guessing.

## Vertical reference and CRS

Quantities involving depth, height or elevation must preserve the relevant vertical reference. Names such as `sea_floor_depth_below_geoid` and `sea_floor_depth_below_mean_sea_level` are not interchangeable. CRS/datum information remains first-class metadata even when the CF name carries part of that meaning.

Spatial tiles are stored using MBTiles/TMS row convention. XYZ is an interface convention and is converted at the boundary. Import utilities target Web Mercator (`EPSG:3857`) and must declare their resampling method.

## Time and other scientific dimensions

Time, pressure, depth/elevation, ensemble, model run, scenario, band and similar axes remain typed DataTiles dimensions. They must not be hidden in filenames or overloaded into variable names. Source dimensions that are not common to every imported variable may be optional, allowing heterogeneous variables to coexist in one container.

## Numeric data versus portrayal

Scientific numeric arrays are encoded as DNT1 and declared as `application/vnd.datatiles.numeric`. PNG, JPEG and WebP are portrayals, not substitutes for numeric evidence. Any portrayal used for MBTiles compatibility should be generated as a documented, provenance-linked derivation.

## Source identity and provenance

A source can be local or URL-identified. Single-file NetCDF/GRIB imports retain the original identifier and SHA-256 of the exact bytes used. Zarr requires a store-aware identity rule because it is normally a set of named objects: local stores use the canonical `zarr-tree-sha256-v1` digest defined in `zarr-source-profile.md`, while remote stores require an authoritative checksum for an immutable published store/snapshot. A transport location is provenance, not a semantic variable identifier. Reproducible workflows should prefer immutable/versioned source identifiers and independently published checksums.

## Import algorithm declaration

Conversion is a scientific transformation. The importer must expose the source grid assumptions, target CRS/grid, resampling algorithm, tile size, bounding region, selected variables and source checksum. Unsupported geometry must be rejected rather than silently approximated.

The initial utilities support rectilinear one-dimensional latitude/longitude grids and nearest-neighbour resampling to Web Mercator tile pixel centers. Curvilinear grids, rotated grids, projected native grids and conservative area remapping require separate declared algorithms.

## Integrity convention

Checksums identify source objects and reproducible derivations; optional revision-6 signatures attest a canonical final DataTiles manifest. Do not use a signature as a replacement for source checksums, provenance, semantic names, units, CRS/datum, citation, or rights. The native integrity profile is defined in `digital-signatures.md`.
