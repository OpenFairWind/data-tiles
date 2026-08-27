# DataTiles zero to hero in five lessons

This course develops DataTiles from first principles and ends with a reproducible mixed raster/vector publication. It treats DataTiles as a scientific data model rather than merely a file-manipulation library. Every lesson contains theory, a hands-on laboratory, observable checks, and questions for critical reflection.

## Learning path

| Lesson | Theory | Practical result |
|---|---|---|
| [1. From maps to data tiles](lesson-1-foundations.md) | MBTiles, tiling, data versus portrayal, compatibility projection | Create and inspect a numeric DataTiles container |
| [2. Multidimensional coordinate algebra](lesson-2-dimensions.md) | Typed axes, point/interval coordinates, canonical identity, slicing | Store and retrieve multiple time/variable slices |
| [3. Raster matrices and vector features](lesson-3-raster-vector.md) | Coverage and feature models, content profiles, encoding semantics | Build one container containing DNT1 and tiled GeoJSON |
| [4. Querying and deriving live products](lesson-4-query-api.md) | Exact selection, sampling, interpolation boundaries, OGC API patterns | Serve and query point, profile, surface, contour, and content resources |
| [5. FAIR and reproducible publication](lesson-5-fair-publication.md) | Identity, provenance, CRS, licences, reproducibility versus replicability | Validate and prepare a citable research artifact |

## Prerequisites and setup

The course assumes basic Python, command-line, SQL, and geospatial concepts. From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[demo,test]'
datatiles --help
```

Windows PowerShell users activate with `.venv\Scripts\Activate.ps1`. Commands use POSIX shell syntax; the Python operations are platform-independent.

The reusable laboratory dataset is built without network access:

```bash
python docs/tutorial/examples/build_tutorial.py build tutorial.datatiles
python docs/tutorial/examples/build_tutorial.py verify tutorial.datatiles
```

The builder is part of the tested repository. It creates two DNT1 matrices and one tiled GeoJSON feature collection at the same spatial address but under different multidimensional coordinates. Its identifiers and landing-page URL are illustrative; Lesson 5 explains what a real publication must replace.

## Evidence of completion

A learner completing the course should be able to explain why the `tiles` view is necessary but insufficient, derive a canonical coordinate-set key, distinguish a numeric raster matrix from a portrayal, justify a vector content profile, query exact coordinates without silently interpolating, interpret the FAIR report conservatively, and reproduce the tutorial artifact from source.

The tutorial dataset is for education only and must not be used for navigation.
