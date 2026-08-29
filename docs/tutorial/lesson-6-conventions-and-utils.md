# Lesson 6 — DataTiles conventions and source utilities

## Learning goals

This chapter connects the DataTiles container model to existing scientific conventions. At the end you should be able to explain why a local variable name is insufficient for interoperability, map NetCDF/CF, GRIB2, and Zarr metadata into DataTiles, import local or URL-identified sources, and verify that imported numeric tiles remain data rather than pre-rendered cartography.

## 1. Convention before conversion

A file format answers *how bytes are encoded*. A convention or controlled vocabulary answers *what a quantity means*. A NetCDF variable called `depth`, a GRIB short name, and a provider field called `z` may refer to the same physical quantity—or to materially different vertical references. DataTiles therefore separates the local variable token used in coordinates from the semantic variable registry.

The preferred canonical vocabulary is CF Standard Names. External identifiers such as WMO GRIB2 parameter triples and SeaDataNet/NERC identifiers are crosswalks. Units, CRS/datum and provenance remain explicit because a standard variable name alone cannot fully define every geospatial measurement.

A useful interoperability test is:

```text
producer-local name -> controlled semantic name -> units/datum/CRS -> DataTiles coordinate
```

A consumer should be able to discover the semantic name without knowing the producer-local name.

## 2. NetCDF convention mapping

Consider a NetCDF variable:

```text
float depth(time, lat, lon)
  standard_name = "sea_floor_depth_below_geoid"
  units = "m"
```

The importer maps it conceptually to:

```text
variable coordinate token: depth
standard vocabulary: CF
standard name: sea_floor_depth_below_geoid
unit: m
other dimension: time
horizontal target CRS: EPSG:3857
payload: DNT1 numeric matrix
```

If `standard_name` is missing, `netcdf2datatiles` does **not** invent a CF name. The token is registered with vocabulary `source` and can be curated later.

## 3. GRIB2 convention mapping

GRIB2 identifies parameters primarily using WMO tables. `grib2datatiles` decodes the file with cfgrib/ecCodes and preserves both semantic views when available:

```text
CF standard_name          canonical semantic discovery
WMO discipline.category.parameter   GRIB2 crosswalk
GRIB shortName            source/ecCodes crosswalk
```

This is why DataTiles should not choose either NetCDF variable names or GRIB codes as its only universal naming system.

## 4. Install the import profile

The DataTiles core remains dependency-free. Import utilities are an optional profile:

```bash
python -m pip install -e '.[utils]'
```

This installs xarray/NetCDF support, the cfgrib/ecCodes stack required for GRIB, and the Zarr/fsspec stack required for chunked local or remote stores.

## 5. Import a local NetCDF file

```bash
python utils/netcdf2datatiles.py samples/ocean.nc ocean.datatiles \
  --variable depth \
  --zoom 7 \
  --bbox 12.8 39.9 15.8 41.3
```

The source must expose a rectilinear latitude/longitude grid. The converter creates typed DataTiles dimensions for every non-spatial dimension, registers the semantic variable, resamples the selected grid to Web Mercator tile pixel centers with nearest-neighbour sampling, encodes the matrices as DNT1, and records source SHA-256 provenance.

Inspect the result:

```bash
datatiles variables ocean.datatiles
datatiles validate ocean.datatiles --require-variable-semantics
```

## 6. Import from a URL

The source identifier can be HTTP(S):

```bash
python utils/netcdf2datatiles.py \
  https://example.org/archive/ocean.nc \
  ocean.datatiles --variable depth --zoom 7
```

The URL is downloaded to a temporary seekable file, hashed while streaming, converted, then deleted. The DataTiles provenance stores the original URL plus SHA-256 checksum. Reproducible publication should prefer immutable or versioned source URLs and independently published checksums where available.

## 7. Import GRIB2

```bash
python utils/grib2datatiles.py forecast.grib2 forecast.datatiles \
  --variable t2m --zoom 6
```

A GRIB file may contain messages that cannot be represented as one xarray hypercube. Narrow the cfgrib view with repeatable keys:

```bash
python utils/grib2datatiles.py forecast.grib2 pressure.datatiles \
  --filter-by-keys typeOfLevel=isobaricInhPa \
  --variable t --zoom 6
```

After import, query by semantic identity rather than by source encoding whenever possible:

```bash
datatiles find-variable forecast.datatiles air_temperature
```

## 8. Import Zarr

A local Zarr directory store is imported directly:

```bash
python utils/zarr2datatiles.py samples/ocean.zarr ocean-zarr.datatiles \
  --variable depth --zoom 7
```

A Zarr store is not one file. For a local store, DataTiles computes a deterministic digest over the sorted store keys, byte lengths, and exact object bytes (`zarr-tree-sha256-v1`). For a remote immutable store, supply the archival checksum published for that snapshot:

```bash
python utils/zarr2datatiles.py \
  https://example.org/archive/ocean.zarr ocean-zarr.datatiles \
  --source-sha256 <64-hex-authoritative-sha256> \
  --group analysis --consolidated true --variable depth --zoom 7
```

Object-store URLs such as `s3://` and `gcs://` can be used when the corresponding fsspec backend is installed. Runtime credentials belong in backend configuration or storage options; secret values must never enter DataTiles provenance. The converter records only storage-option names. A signed or credential-bearing access URL requires `--provenance-uri` with a stable credential-free source/PID URI.

Zarr v2 and v3 differ in metadata and fill-value behavior. Use `--zarr-format 2` or `--zarr-format 3` when the publication workflow needs to require a specific format. Consolidated metadata improves store discovery but is not evidence of scientific validity or stronger provenance.

## 9. Why the utility does not create image tiles

The output is `application/vnd.datatiles.numeric` using DNT1. A color ramp, contour layer, shaded relief or nautical-style display is a reproducible *derivation* from the numeric evidence. Converting scientific source grids directly into PNG tiles would destroy machine-readable values and undermine the interoperability objective of this chapter.

## 10. Limits are part of the convention

The first utility profile intentionally rejects unsupported geometry rather than approximating it silently. Curvilinear coordinates, rotated grids, projected source grids, antimeridian-spanning extents and conservative cell-area remapping need explicit algorithms and provenance. `--max-tiles` is also part of the safety model: a mistaken high zoom must not expand an import without a deliberate operator decision.

## 11. Laboratory checks

Run an import and confirm all of the following: the source URI/checksum are present in metadata/provenance; `datatiles variables` exposes a CF name or explicitly says `source`; the DNT1 unit matches the imported variable unit; time/pressure/depth dimensions are typed rather than embedded in filenames; the horizontal CRS is explicit; and no raster portrayal has been substituted for the numeric payload.

### Reflection

1. Why is `depth` insufficient as a universal semantic identifier?
2. When should a WMO GRIB2 parameter be a crosswalk rather than the canonical name?
3. Why must an importer refuse to manufacture a CF `standard_name`?
4. Which provenance fields make a URL import reproducible?
5. Why is nearest-neighbour resampling acceptable only when declared explicitly?
6. Why must a Zarr directory store not be described as having the SHA-256 of a single file?
7. Why should credentials for S3/GCS/HTTP backends never be copied into provenance metadata?
