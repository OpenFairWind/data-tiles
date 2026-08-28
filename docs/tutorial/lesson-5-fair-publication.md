# Lesson 5 — FAIR and reproducible publication

## Objectives

You will distinguish FAIR principles from vague “open data” claims, inspect identity and provenance evidence, reproduce an artifact, and prepare a DataTiles release for independent reuse and replication.

## Theory: FAIR is an evidence architecture

FAIR means Findable, Accessible, Interoperable, and Reusable. It does not mean that every dataset is public, free of access control, or scientifically valid. A restricted dataset can be FAIR when its metadata remains findable, its authorization procedure is explicit, and its semantics and licence support legitimate reuse.

Findability requires a globally unique persistent identifier, rich indexed metadata, and explicit linkage between metadata and data. Accessibility requires a standardized retrieval protocol and durable metadata even if bytes are withdrawn. Interoperability requires formal types, shared CRS identifiers, units, vocabularies, media types, and machine-readable relationships. Reusability requires licence, provenance, source identity, versioning, domain-relevant metadata, and declared limitations.

DataTiles places evidence at the object boundary: metadata, dimensions, content schemas, CRS records, provenance entities/activities/agents, relations, tile lineage, and checksums travel with the SQLite object. A repository still has obligations the file cannot prove: resolving the persistent identifier, indexing metadata, enforcing access policy, retaining tombstone metadata, and preserving versions. The FAIR report therefore separates local checks from repository-level caveats.

Reproducibility and replicability are also distinct. Reproducibility recreates the same artifact from the same locked inputs, code, parameters, and runtime. Replicability applies the method to independently acquired data, another region, or another implementation. Byte identity is powerful evidence of deterministic engineering, but it does not establish ecological correctness or fitness for navigation.

## Laboratory

Inspect the tutorial’s FAIR evidence:

```bash
python - <<'PY'
import json
from datatiles import DataTiles
with DataTiles('tutorial.datatiles',read_only=True) as s:
    print(json.dumps(s.fair_report(),indent=2))
    print('\nCRS:')
    for row in s.db.execute('SELECT role,authority,code,uri FROM datatiles_crs'): print(tuple(row))
    print('\nProvenance relations:')
    for row in s.db.execute('SELECT subject_id,predicate,object_id FROM datatiles_provenance_relations'): print(tuple(row))
PY
```

The report passes object-boundary checks, but `https://example.org/datatiles/tutorial` is deliberately illustrative. A real publication must replace it with a maintained landing page and register a DOI, Handle, ARK, or institutional PID. Never report the tutorial object itself as globally published FAIR data.

Test reproducibility from two clean outputs:

```bash
python docs/tutorial/examples/build_tutorial.py build tutorial-a.datatiles
python docs/tutorial/examples/build_tutorial.py build tutorial-b.datatiles
sha256sum tutorial-a.datatiles tutorial-b.datatiles
```

SQLite files may differ byte-for-byte when page history or library behavior changes even if their logical content is equivalent. The production From Gaeta to Maratea pipeline adds stable insertion order, vacuuming, runtime locks, canonical manifests, fixed ZIP metadata, and double-build tests. Compare `docs/reproducibility.md` with `docs/replicability.md` and classify every step as input locking, deterministic transformation, scientific validation, or publication evidence.

Before publishing your own dataset:

1. Replace illustrative identifiers and URLs.
2. Declare horizontal and vertical CRS, datum direction, units, nodata, spatial/temporal extent, and uncertainty.
3. Record immutable source identifiers, exact requests, checksums, licences, and attribution.
4. Describe every classification, fusion, resampling, contour, shelter, or rendering algorithm.
5. Run container validation and independent scientific acceptance tests.
6. Create a source lock, runtime lock, artifact manifest, citation, and evidence bundle.
7. Publish through protected CI/CD and retain checksums plus build provenance.
8. State limitations prominently; marine demonstration outputs remain “DO NOT USE FOR NAVIGATION.”

## Capstone

Design one independent DataTiles object containing at least one numeric raster variable and one vector feature variable across two times. Write its dimension table, content profiles, CRS set, provenance graph, licences, validation criteria, and replication plan before implementing it. Then build it twice and explain whether you achieved semantic equivalence, logical database equivalence, or byte identity.

## Verification and reflection

1. Why can a file pass local FAIR checks while its publication remains non-FAIR?
2. Which provenance relation connects a generated entity to its activity?
3. Why are a source checksum and a source citation both necessary?
4. What evidence would distinguish a reproducible artifact from a replicable method?
5. Which assertions require domain validation rather than container validation?

You are now ready to use DataTiles as a scientific publication format rather than simply as a tile database.
