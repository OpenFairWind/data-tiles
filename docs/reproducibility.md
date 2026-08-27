# Reproducing the Bay of Naples demonstration

## Claim and scope

This protocol reconstructs the Bay of Naples DataTiles object from the exact input bytes, canonical configuration, and locked runtime. Success means that the resulting SQLite file and evidence ZIP have the recorded SHA-256 values. Reacquiring nominally identical data from mutable network services is a *replication* unless the acquired bytes match the source lock.

The demonstration integrates EMODnet DTM 2024 bathymetry, EMODnet Geology seabed substrate, and EUSeaMap 2025 habitat data. It emits continuous depth, source substrate, source habitat, fused seafloor class, and a derived north-west land-interception shelter proxy. It is a scientific software demonstration and must not be used for navigation.

![Bay of Naples reproducibility and evidence chain](figures/reproducibility-evidence-chain.svg)

*Figure 1. Exact reconstruction couples immutable inputs and runtime/configuration locks to deterministic derivation and byte-identity checks. Scientific verification and FAIR publication evidence are separate obligations; none of these checks makes the demonstration suitable for navigation.*

## Prerequisites

- a POSIX-like environment with `make`;
- the exact Python version in `runtime-lock.json`;
- SQLite and zlib versions matching that lock;
- Python dependencies in `requirements-demo.lock`;
- sufficient storage for retained raw responses and the evidence ZIP;
- network access to the service URLs in `config.json` for first acquisition.

Use an isolated environment. From the project root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[demo,test]'
python -c 'from datatiles.demo import runtime_versions; print(runtime_versions())'
```

Compare the printed object with `demo/bay-of-naples/runtime-lock.json`. The build intentionally stops on a difference because SQLite, zlib, or library variation can change container bytes even when decoded values agree.

## First acquisition and review

```bash
cd demo/bay-of-naples
make acquire
```

Acquisition stores raw WCS/WFS/catalogue responses, the complete request URLs, sizes, and SHA-256 values under `work/`. Before accepting these bytes as a reference snapshot, inspect HTTP diagnostics, verify that TIFF and GeoJSON responses are complete, compare catalogue identifiers/releases with `config.json`, review licence terms, and archive the resulting `source-lock.json`. A lock is an evidence decision, not merely build output.

For controlled replay, place the accepted raw files in `work/raw/` with the accepted `work/source-lock.json`; do not contact live services. Build and verify:

```bash
make build
make verify
sha256sum work/bay-of-naples.datatiles work/bay-of-naples-evidence.zip
```

For reacquisition against an accepted lock, use the CLI’s `--expect-lock` option. Incoming bytes are downloaded separately and promoted only when every checksum matches. Differences are preserved as a new candidate snapshot and must not silently overwrite the reference.

## Deterministic transformation

The implementation fixes request geometry and raster dimensions; canonicalizes JSON; sorts vector features; uses deterministic polygon rasterization and class precedence; applies nearest-cell resampling for categorical grids; inserts tiles in stable zoom/column/row/variable order; vacuums SQLite; fixes ZIP timestamps and permissions; and records the runtime and configuration digests. Depth sign conversion is recorded in provenance. The north-west shelter proxy traces a finite north-west ray through the source water/land mask using the configured reach.

The evidence bundle contains configuration, runtime lock, source lock, manifest, DataTiles object, diagnostic previews, and all raw source responses. Tile-level provenance links derived cells to the source entities. The verifier checks source and output digests, database integrity and foreign keys, previews, and evidence-bundle integrity.

## Required reproducibility test

Run the test suite and require two clean builds from the same fixture to be byte-identical:

```bash
python -m pytest -q
```

For the retained EMODnet snapshot, delete only a safely marked `work/` directory using `make clean`, restore the evidence inputs, build twice, and compare both DataTiles and evidence ZIP SHA-256 values. Record the host, runtime report, commands, start/end times, checksums, and test log in the reproduction report.

## Scientific verification

Byte identity detects pipeline drift but does not establish scientific correctness. Independently inspect source-versus-tile values at stratified checkpoints, coastline/nodata alignment, depth distribution and units relative to Lowest Astronomical Tide, class crosswalk and precedence, per-class cell totals, profile endpoints, contour levels, and predicate-query boundary conditions. The shelter proxy must be assessed only against its declared land-interception semantics.

## Failure interpretation

A raw checksum difference indicates upstream revision or transport difference. A runtime mismatch invalidates the byte-identity claim until reproduced in the locked environment. An output checksum difference with identical inputs indicates nondeterminism or software drift. Identical bytes with failed scientific checks indicate a reproducible error and require a new dataset version—not alteration of the historical evidence bundle.
