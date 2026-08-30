# Zarr source-ingestion profile

## Historical context

The DataTiles project identifies Montella and Foster's 2010 chapter, “Using Hybrid Grid/Cloud Computing Technologies for Environmental Data Elastic Storage, Processing, and Provisioning,” as an early project-lineage precursor to later cloud-native multidimensional storage approaches, including Zarr. The chapter predates Zarr and concerns elastic storage, processing, and delivery of environmental data across grid/cloud infrastructure; it is cited as intellectual context, not as part of the Zarr normative specification or as publisher evidence of a direct influence claim. See `references.md` and [doi:10.1007/978-1-4419-6524-0_26](https://doi.org/10.1007/978-1-4419-6524-0_26).

This document defines the DataTiles utility profile for importing Zarr datasets. It is normative for `utils/zarr2datatiles.py` and informative for independent implementations unless they claim this profile.

## Scope

Zarr is a chunked, N-dimensional storage format. DataTiles treats Zarr as a **source encoding**, not as the semantic identity of a scientific quantity. An importer MUST preserve or explicitly map variable semantics, units, scientific dimensions, source identity, provenance, rights, and transformation parameters before writing DNT1 numeric tiles.

The profile supports Zarr format 2 and 3 stores that xarray can interpret as a Dataset. The source data variables used by the profile MUST expose rectilinear one-dimensional latitude and longitude coordinates. Unsupported curvilinear, projected, rotated, or antimeridian-crossing source grids MUST be rejected rather than silently approximated.

## Source identifiers

A source MAY be:

- a local directory store or `file:` URI;
- an HTTP(S) URL;
- another fsspec URL such as `s3://` or `gcs://`, provided the required backend is installed and the operator supplies any necessary storage options.

Authentication material is runtime configuration and MUST NOT be copied into DataTiles metadata, provenance attributes, logs, manifests, or tutorial artifacts. The importer records storage-option **keys only**, never secret values.

## Store identity and checksums

A Zarr store is a set of named objects, not a single file. Implementations MUST NOT describe a digest of a directory serialization as the SHA-256 of a Zarr file.

For a local directory store, `zarr2datatiles` computes `zarr-tree-sha256-v1` as follows:

1. Initialize SHA-256 with the ASCII/UTF-8 byte string `DataTiles-Zarr-Tree-SHA256-v1` followed by NUL.
2. Recursively enumerate regular files beneath the store root. Reject symbolic links.
3. Sort objects by their relative POSIX key using Unicode code-point order on the UTF-8 path string.
4. For each object, update the digest with `key`, NUL, decimal byte length, NUL, exact object bytes, NUL.
5. Store the lowercase hexadecimal digest with checksum algorithm `zarr-tree-sha256-v1`.

This digest identifies the complete local object set and its byte content at the time of hashing. For rigorous publication, the source store SHOULD be immutable or snapshot/version identified so hashing and conversion cannot observe different states.

For a remote store, the utility requires `--source-sha256`. If the access URL contains credentials, user-info, or a signed query string, the operator MUST also supply a stable credential-free `--provenance-uri`; the access URL is used only at runtime and MUST NOT be persisted. That value MUST identify the immutable published store or snapshot according to the provider's archival record. The utility does not traverse an arbitrary remote object store a second time merely to synthesize a checksum: doing so may be unbounded, expensive, authorization-sensitive, and still race with concurrent mutation. Publication workflows SHOULD record an object-version ID, DOI/PID, ETag/version manifest, or repository snapshot identifier in addition to the checksum when available.

## Metadata and semantic mapping

For every selected xarray data variable:

- the source variable name becomes the local DataTiles variable token;
- a valid CF `standard_name`, when present, is the preferred canonical semantic identity;
- source `units` and `long_name` are retained;
- non-spatial dimensions are represented as typed DataTiles dimensions;
- producer-local names without a CF standard name remain in vocabulary `source` and MUST NOT be promoted to CF by inference;
- the native Zarr/xarray variable name is retained as a `Zarr-variable` external identifier.

Zarr chunk shape, compressor/codec configuration, fill-value representation, and consolidated-metadata status are source-encoding properties. They MAY be retained as provenance attributes but MUST NOT replace scientific semantics.

## Zarr v2/v3 and fill values

An importer MAY accept either Zarr format 2 or 3. If `--zarr-format` is supplied, failure to match that format MUST be an error. CF decoding is delegated to xarray. Because Zarr v2 and v3 have different fill-value semantics in the xarray ecosystem, producers SHOULD make `_FillValue`/masking intent explicit in the source and SHOULD test the resulting nodata behavior before publication.

## Consolidated metadata

`--consolidated auto` delegates discovery to xarray: consolidated metadata is attempted where supported with fallback according to the backend. `true` requires consolidated metadata; `false` explicitly disables it. The selected policy is recorded in import provenance. Consolidation is a performance/discovery property and MUST NOT be interpreted as stronger scientific provenance.

## Transformation and output

The initial profile uses the same declared spatial transformation as the NetCDF/GRIB utilities: Web Mercator target tiles, nearest-neighbour sampling at tile-pixel centers, explicit source/bbox clipping, DNT1 numeric payloads, and a maximum-tile resource guard. The content schema records `source_kind=Zarr` and the resampling/grid parameters.

A portrayal (PNG/JPEG/WebP, shaded relief, contour image, color ramp) is a downstream reproducible derivation. The importer MUST NOT substitute portrayal pixels for scientific arrays.

## FAIR, provenance, and rights

Transport accessibility does not imply permission. The operator MUST provide the source license/terms URI, SPDX expression or explicit `LicenseRef-*`, required attribution, generated-dataset license, and generated-dataset license URI. These are recorded separately.

The source provenance entity MUST include the original source identifier, checksum algorithm, checksum, and source kind. The conversion activity MUST record zoom, tile size, bbox, Zarr group, requested Zarr format, consolidated-metadata policy, and non-secret storage-option keys. Tile-level lineage links generated tiles to the source entity.

A DataTiles file created from Zarr is FAIR only to the extent supported by the complete DataTiles FAIR publication profile; successful conversion alone is not a FAIR certification.

## Standards references

This profile is designed against the Zarr core specification, with Zarr v3 core specification 3.1 as the current reference at the time of this extension, and the xarray Zarr backend contract. The Zarr core specification defines stores as mappings from keys to bytes and explicitly allows filesystem- and object-store realizations; that store model is the reason DataTiles uses a store-aware digest rather than pretending a Zarr hierarchy is one file. Xarray provides the dataset-level bridge used here and requires dimension/coordinate metadata that it can interpret.

- Zarr core specification: https://zarr-specs.readthedocs.io/en/latest/v3/core/
- Xarray `open_zarr`: https://docs.xarray.dev/en/latest/generated/xarray.open_zarr.html
- Xarray Zarr I/O guidance: https://docs.xarray.dev/en/latest/user-guide/io.html#zarr
