# Documentation figure provenance

These explanatory figures are hand-authored SVG derivations of the DataTiles documentation and normative specification. They contain no measured or simulated scientific values and use no geographic coordinate reference system. Their layout is schematic and MUST NOT be interpreted as a database schema, byte-scale drawing, benchmark, FAIR certification, or navigation product.

| Figure | Inputs | Method and parameters | Scope |
|---|---|---|---|
| `datatiles-information-model.svg` | `docs/specification.md`, `docs/architecture.md`, `docs/mbtiles-fallback.md` | deterministic SVG boxes and directed relations in a 1200 × 680 view box | conceptual addressing, content declaration, and MBTiles projection |
| `dnt1-payload.svg` | `docs/specification.md`, `docs/numeric-tiles.md`, `src/datatiles/numeric.py` | deterministic SVG byte-field sequence and validation flow in a 1200 × 600 view box | schematic DNT1 layout and decoder obligations; field widths are not proportional |
| `reproducibility-evidence-chain.svg` | `docs/reproducibility.md`, `docs/fair-by-design.md`, `src/datatiles/demo.py` | deterministic SVG directed evidence flow in a 1200 × 700 view box | exact replay, scientific verification, and FAIR publication evidence |

The repository source commit is the provenance identifier for each figure revision. SVG text, geometry, colours, accessibility titles, and descriptions are stored directly in version control so the figures remain reviewable and reproducible without an opaque rendering tool.
