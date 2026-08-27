# DataTiles contributor instructions

This repository is the reference implementation and specification of DataTiles. Preserve the distinction between numeric or categorical scientific arrays and pre-rendered map imagery. New visual products must be reproducible derivations from stored values and must identify their input variables, algorithms, parameters, coordinate reference systems, and provenance.

## Engineering invariants

- Preserve the conventional MBTiles `metadata` table and four-column `tiles` compatibility view.
- Preserve the standalone MBTiles fallback: compatible selected slices MUST export to physical standard tables without DataTiles extension objects; scientific arrays MUST NOT be mislabeled as portrayals.
- Treat dimension names and typed values as an unordered canonical coordinate set.
- Store Web Mercator rows in TMS order; perform XYZ conversion only at interfaces.
- Decode `DNT1` defensively and retain dtype, shape, byte order, nodata, scale, offset, unit, and compression semantics.
- Do not silently render, resample, classify, fuse, or transform scientific values. Record each such operation as provenance.
- Keep source acquisition immutable and checksum-locked. The Bay of Naples products are explicitly not for navigation.
- Maintain FAIR metadata and validation. Stable identifiers, license, provenance, CRS, dimensions, units, checksums, and access links are functional requirements.
- Keep the core Python package dependency-free. Optional demo and test dependencies belong in their declared extras.

## Change workflow

Read `docs/specification.md`, `docs/fair-by-design.md`, and the relevant implementation module before changing the schema or wire format. Update normative documentation, OpenAPI output, tests, version metadata, and `CHANGELOG.md` together. Use deterministic serialization and fixed iteration order. Add a regression test for each new endpoint, encoding, schema migration, or scientific derivation. Run `python -m compileall src tests` and `python -m pytest` before release; also run the double-build protocol described in `docs/reproducibility.md` when demo generation changes. Never weaken a quality gate merely to make a change pass; correct the implementation, test, dependency constraint, or documented invariant.

All documentation MUST be correct and consistent with the current code and the normative specification. A code or specification change is incomplete until every affected README, tutorial, example, API description, architecture explanation, reproducibility/replicability protocol, citation, and release note has been updated and verified. Documentation MUST NOT promise behavior, commands, formats, variables, endpoints, conformance, or guarantees that the implementation and tests do not provide.

All demos MUST remain coherent with the code, documentation, and normative specification. Demo variables, content profiles, dimensions, CRS/datum declarations, algorithms, provenance, licences, commands, expected outputs, and limitations MUST be exercised through supported interfaces and covered by regression or reproducibility tests. A demo MUST NOT use hidden shortcuts, stale fixtures, undocumented schema assumptions, or a portrayal presented as stored scientific data.

The OpenLayers playground is an explanatory scientific client. Its profile, contours, hillshade, textured depth surface, 3D mesh, cursor inspection, and compound queries must remain computed from DataTiles arrays. Never substitute a screenshot or opaque remote map layer for those demonstrations.

## Documentation language

Use precise academic prose. Clearly distinguish normative requirements (`MUST`, `SHOULD`, `MAY`) from implementation notes. State uncertainty, resolution, datum, limitations, and non-navigation status. Do not claim OGC conformance, FAIR compliance, or scientific validity beyond the validations actually performed.
