# NetCDF, GRIB, and Zarr import utilities

DataTiles treats NetCDF, GRIB, and Zarr as **source encodings**, not as the semantic identity of a quantity. The utilities under `utils/` translate those encodings into the DataTiles multidimensional model while retaining source identity, variable semantics, units, non-spatial coordinates, CRS and provenance.

## Input identifiers

A source argument may be a local filesystem path, a `file:` URI, or an HTTP(S) URL. URL sources are materialized to a temporary file because GRIB readers require seekable access and because byte-level SHA-256 provenance should be computed consistently. The converter records both the original source identifier and the checksum. It does not treat a downloaded temporary filename as scientific identity.

## NetCDF mapping

For each selected NetCDF data variable:

- the local NetCDF variable name becomes the DataTiles variable token;
- a CF `standard_name`, when present, becomes the canonical semantic name under vocabulary `CF`;
- `units` becomes the registered canonical/unit declaration and DNT1 tile unit;
- `long_name` remains descriptive metadata, never a substitute for a controlled standard name;
- non-spatial dimensions such as `time`, `depth`, `pressure`, `ensemble` or `scenario` become typed DataTiles dimensions;
- one-dimensional latitude/longitude coordinates define the source rectilinear grid.

If `standard_name` is absent, the converter registers the local token under vocabulary `source`. This preserves discoverability without inventing a CF Standard Name.

## GRIB2 mapping

GRIB is decoded through `cfgrib`/ecCodes. The decoded variable follows the same CF mapping as NetCDF. When cfgrib exposes GRIB metadata, the converter also records external identifiers:

- `WMO-GRIB2`: `discipline.parameterCategory.parameterNumber`;
- `GRIB-shortName`: the producer/ecCodes short name;
- `GRIB2-variable`: the decoded xarray variable name.

These identifiers are crosswalks. They do not replace the canonical CF semantic identity when a CF Standard Name is available.

## Zarr mapping

Zarr import uses xarray's Zarr backend and follows the same CF semantic mapping as NetCDF. Zarr format 2 and 3 are supported when the installed xarray/zarr stack supports them. Local directory stores receive a deterministic `zarr-tree-sha256-v1` digest over the complete object tree; remote Zarr stores require an authoritative `--source-sha256` for an immutable published store or snapshot. This distinction is normative: a multi-object store is not misrepresented as a single file.

The importer supports `--group`, `--consolidated`, `--zarr-format`, and repeatable fsspec `--storage-option` settings. Storage-option values can contain credentials and therefore are never persisted; provenance records only the option names. Signed or credential-bearing access URLs require a separate stable `--provenance-uri`, preventing secrets from entering the evidence graph. See `zarr-source-profile.md` for the complete ingestion contract.

## Spatial transformation

The utility profile is deliberately conservative. It supports rectilinear 1-D latitude/longitude source grids. Target pixels are Web Mercator tile pixel centers and source values are selected using nearest-neighbour sampling. Data are stored as DNT1 numeric arrays and written through the XYZ interface; DataTiles persists the corresponding TMS row.

This is an explicit algorithm, not a hidden portrayal step. The tile content schema records `resampling=nearest`, `grid=WebMercatorQuad`, tile size and source kind. Future higher-order or conservative remapping methods must declare different algorithm identifiers and parameters.

The utilities reject rather than guess for unsupported curvilinear/2-D coordinates, antimeridian-crossing bboxes, and non-rectilinear grids.

## Resource and safety bounds

`--max-tiles` limits accidental expansion at inappropriate zooms. `--bbox` can constrain the import domain. URL access has a timeout and is streamed to disk while hashing instead of being accumulated in memory. DNT1 itself retains its normal element and header bounds.

## Examples

```bash
python utils/netcdf2datatiles.py input.nc output.datatiles \
  --variable sea_floor_depth_below_geoid --zoom 8
```

```bash
python utils/grib2datatiles.py https://example.org/model.grib2 output.datatiles \
  --filter-by-keys typeOfLevel=surface --variable t2m --zoom 6
```

```bash
python utils/zarr2datatiles.py ./ocean.zarr output.datatiles \
  --variable depth --zoom 7
```

Validate semantic registration after import:

```bash
datatiles validate output.datatiles --require-variable-semantics
```

For strict CF-table membership validation, additionally provide the pinned official CF XML table used by the publication workflow.

## Signing imported products

The NetCDF, GRIB2, and Zarr utilities intentionally do not sign during ingestion. Import output is normally intermediate scientific evidence that may still undergo semantic curation, fusion, portrayal preparation, citation resolution, QA, and rights review. Sign the final frozen DataTiles object with `datatiles-integrity` only after those steps. This avoids producing apparently authoritative signatures over incomplete intermediate products.

## DRM is not an ingestion step

NetCDF, GRIB2, and Zarr importers do not encrypt or issue commercial licences. Source ingestion must preserve upstream rights and provenance first. DRM is applied only to a finalized lawful release after scientific QA, citation/licence review, FAIR metadata completion, and optional integrity signing.
