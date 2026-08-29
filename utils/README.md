# DataTiles import utilities

`netcdf2datatiles.py`, `grib2datatiles.py`, and `zarr2datatiles.py` convert scientific source grids into DNT1 numeric DataTiles. They deliberately do **not** pre-render PNG/JPEG/WebP map imagery.

Both commands accept either a local path, a `file:` URI, or an HTTP(S) URL. HTTP(S) input is downloaded to a temporary seekable file, SHA-256 hashed, imported, and deleted. The original URL and checksum are retained as DataTiles source/provenance metadata.

The first implementation targets rectilinear one-dimensional latitude/longitude grids. It resamples to Web Mercator tile pixel centers using nearest-neighbour sampling and stores rows through the DataTiles XYZ interface, which converts them to MBTiles/TMS storage. Curvilinear grids, rotated poles, projected source grids, conservative remapping, and antimeridian-spanning imports must use a future specialized resampling path rather than being silently approximated.

Install optional dependencies from a repository checkout:

```bash
python -m pip install -e '.[utils]'
```

NetCDF example:

```bash
python utils/netcdf2datatiles.py ./ocean.nc ocean.datatiles \
  --variable depth --zoom 7 --bbox 12.8 39.9 15.8 41.3 \
  --source-license CC-BY-4.0 --source-license-uri https://creativecommons.org/licenses/by/4.0/ \
  --source-attribution "Required source credit" \
  --dataset-license CC-BY-4.0 --dataset-license-uri https://creativecommons.org/licenses/by/4.0/
```

URL example:

```bash
python utils/netcdf2datatiles.py \
  https://example.org/data/ocean.nc ocean.datatiles --variable depth \
  --source-license LicenseRef-Source-Terms --source-license-uri https://example.org/terms \
  --source-attribution "Required source credit" \
  --dataset-license LicenseRef-Output-Terms --dataset-license-uri https://example.org/output-terms
```

GRIB2 example:

```bash
python utils/grib2datatiles.py ./forecast.grib2 weather.datatiles \
  --variable t2m --zoom 6 \
  --source-license LicenseRef-Provider-Terms --source-license-uri https://example.org/model-terms \
  --source-attribution "Required model-provider credit" \
  --dataset-license LicenseRef-Derived-Terms --dataset-license-uri https://example.org/derived-terms
```

When one GRIB file contains incompatible hypercubes, use repeatable cfgrib filters:

```bash
python utils/grib2datatiles.py forecast.grib2 pressure.datatiles \
  --filter-by-keys typeOfLevel=isobaricInhPa --variable t
```

Important constraints:

- The utilities are optional import tooling; `datatiles` core remains dependency-free.
- NetCDF semantic identity comes from `standard_name` when present; otherwise the local variable is registered under the non-CF `source` vocabulary.
- GRIB import preserves the decoded CF name where available and adds WMO GRIB2 discipline/category/parameter and GRIB short-name identifiers when exposed by cfgrib.
- Inputs without a CF name are never falsely labelled as CF.
- Output uses `application/vnd.datatiles.numeric` + DNT1; portrayal is a downstream reproducible derivation.
- `--max-tiles` is an intentional resource guard.
- The guard counts every variable and every non-spatial slice, not merely one spatial pyramid per variable.
- The first variable/slice in deterministic input order becomes the selected MBTiles compatibility slice; numeric bytes remain DNT1 and are never relabelled as portrayal imagery.

## Zarr

Local directory store:

```bash
python utils/zarr2datatiles.py ./ocean.zarr ocean.datatiles \
  --variable depth --zoom 7 \
  --source-license CC-BY-4.0 --source-license-uri https://creativecommons.org/licenses/by/4.0/ \
  --source-attribution "Required source attribution" \
  --dataset-license CC-BY-4.0 --dataset-license-uri https://creativecommons.org/licenses/by/4.0/
```

Remote store:

```bash
python utils/zarr2datatiles.py https://example.org/ocean.zarr ocean.datatiles \
  --source-sha256 <authoritative-immutable-store-sha256> \
  --variable depth --zoom 7 \
  --source-license CC-BY-4.0 --source-license-uri https://creativecommons.org/licenses/by/4.0/ \
  --source-attribution "Required source attribution" \
  --dataset-license CC-BY-4.0 --dataset-license-uri https://creativecommons.org/licenses/by/4.0/
```

Zarr stores are multi-object datasets. Local stores use the documented `zarr-tree-sha256-v1` canonical store digest. Remote stores require an externally established SHA-256 for the immutable store/snapshot instead of pretending that a directory URL has single-file bytes. `--group`, `--zarr-format {2,3}`, `--consolidated {auto,true,false}`, and repeatable `--storage-option KEY=VALUE` are supported. Secret storage-option values are never recorded in provenance. Signed or credential-bearing remote URLs require `--provenance-uri` with a stable credential-free identifier. See `docs/zarr-source-profile.md`.

## Digital signatures

Converters do not accept private signing keys and do not auto-sign outputs. Cryptographic signing is a release operation, not an ingestion operation. After the final DataTiles object has passed scientific QA, provenance, citation, rights, and FAIR checks, use `datatiles-integrity sign`. This separation reduces private-key exposure and ensures the signature covers the final immutable release state.

## Commercial DRM

Import utilities intentionally contain no DRM keys and no licence issuance logic. After a lawful final product is frozen and optionally signed, use `datatiles-drm protect` and `datatiles-drm issue-license`. This keeps source acquisition reproducible and keeps commercial secrets out of scientific ingestion workflows.
