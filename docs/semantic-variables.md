# Semantic variable interoperability profile

## Status

Proposed additive extension for DataTiles schema revision 4.

## Goal

A DataTiles consumer must be able to discover a physical quantity without knowing a producer-specific coordinate value such as `depth`, `DEPTH`, `h`, or `bathymetry`.

The `variable` scientific dimension remains part of tile addressing. A separate semantic registry maps each local variable token to a controlled semantic identity.

## Canonical vocabulary

For geophysical and environmental physical quantities, DataTiles uses **CF Standard Names** as the preferred canonical semantic vocabulary. The registry records the vocabulary and version explicitly; examples in this profile target CF Standard Name Table v94 (2026-06-09).

A registered CF variable SHOULD include the CF canonical unit. Actual numeric payload units may be physically equivalent rather than textually identical. Core DataTiles does not claim UDUNITS dimensional-equivalence validation because the project keeps its core dependency-free.

DataTiles MUST NOT invent a CF standard name. If no suitable CF name exists, the producer should use an explicitly named external vocabulary or propose a new CF name through the CF process.

## External identifiers

Additional identifiers are first-class crosswalks, not replacements for the canonical semantic identity. Typical schemes include:

- `WMO-GRIB2`
- `SeaDataNet-P01`
- `NERC-NVS`
- `GCMD`
- provider-specific namespaces

Each mapping stores a scheme, identifier, optional scheme version, and optional persistent URI.

## Example: bathymetry

Local tile coordinate:

```text
variable=bathymetry
```

Semantic registry entry:

```json
{
  "name": "bathymetry",
  "standard_name": "sea_floor_depth_below_geoid",
  "standard_name_vocabulary": "CF",
  "standard_name_vocabulary_version": "94",
  "canonical_unit": "m",
  "long_name": "Sea floor depth below geoid"
}
```

CF distinguishes this quantity from sea-floor depth below mean sea level, a geopotential datum, a reference ellipsoid, or the instantaneous sea surface. The datum/reference surface therefore remains semantically significant and must not be collapsed into a generic `depth` concept.

## Enforcement policy

`metadata['datatiles:variable_semantics']` is one of:

- `required`: every point value of a text `variable` dimension must have a registry entry before tiles using that value may be written; validation also rejects unregistered values.
- `recommended`: legacy-compatible mode. Unregistered values are permitted, but semantic validation may report them when strict validation is requested.

New schema-revision-4 containers SHOULD default to `required`. Migration from revision 3 SHOULD set `recommended` so old containers remain readable and writable until curated.

## Offline CF validation

The core implementation must not download vocabularies implicitly. A strict validator accepts a local, pinned official CF standard-name-table XML snapshot. It checks that the standard name exists and, when `canonical_unit` is supplied, that it matches the CF table's canonical-unit string.

This exact-string canonical-unit check is intentionally narrower than UDUNITS equivalence. DataTiles must not claim full CF unit conformance without a real UDUNITS-compatible implementation.

## Discovery

Consumers should be able to query by semantic identity:

```text
standard_name=sea_floor_depth_below_geoid
```

and receive the matching local variable(s), external identifiers, and coordinate-set IDs. The HTTP service should expose the same registry under:

```text
/collections/{collectionId}/variables
```

This enables independent software to discover compatible DataTiles datasets without prior knowledge of producer-local variable names.
