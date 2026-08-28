# Replicability: constructing another DataTiles dataset

## Scientific premise

Replication asks whether an independent team can apply the declared method to independently acquired data and obtain results consistent with a predeclared scientific acceptance protocol. It is not byte identity. A new region, sensor, release, variable, or implementation will normally change checksums while preserving the DataTiles information model.

## Protocol

1. **State the research object.** Define the phenomenon, spatial/temporal domain, target variables, intended uses, exclusions, resolution, accuracy requirements, and responsible agent. Assign a dataset identifier and semantic version before publication.
2. **Select authoritative inputs.** Record catalogue identifiers, releases, service requests, licences, access dates, CRSs, units, uncertainty, and known limitations. Preserve retrieved bytes and SHA-256 values. Avoid an unlabeled “latest” source in a citable release.
3. **Design dimensions.** Separate physical axes (time, vertical level, ensemble), components/variables, and observational qualifiers. Choose point versus interval semantics deliberately. Define vocabulary URIs, canonical units, nodata, and interpolation policy per variable.
4. **Declare spatial tiling.** Record tile matrix set, zoom range, resampling kernel, pixel registration, source-to-tile transformation, antimeridian behavior, and edge padding. Categorical fields normally require nearest-neighbour resampling; continuous fields require a justified kernel.
5. **Declare transformations.** Version every classification crosswalk and derived algorithm. State precedence, thresholds, uncertainty propagation, and failure behavior. A derived variable receives its own coordinate set and provenance activity.
6. **Build deterministically.** Pin runtime dependencies, canonicalize configuration, sort features, control compression and timestamps, use stable insertion order, and eliminate ambient locale/timezone effects.
7. **Validate independently.** Check structural conformance, random decoded tiles, spatial alignment, range and nodata fractions, class totals, boundary cases, and reference points. Compare predeclared tolerances rather than tuning them after inspection.
8. **Publish FAIRly.** Deposit data and metadata, register the PID, expose standardized HTTPS/OpenAPI resources, provide licence and access rights, retain tombstone metadata, and publish source, configuration, locks, tests, and evidence.

## Permission and licence gate

Acquisition MUST be an explicit, auditable human decision. Before a downloader is run, the operator MUST visit the authoritative landing page, identify the release and licence, determine whether login, click-through terms, institutional authorization, or provider permission is required, and accept those conditions outside the software where necessary. The operator SHOULD retain a private ledger containing the dataset PID, landing page, licence URI/version, accepted terms revision, acceptance timestamp, responsible person or organization, permission/ticket identifier, requested spatial extent, request URL, and resulting SHA-256. Secrets, session cookies, personal data, and licence tokens MUST NOT enter configuration files, logs, source locks, or published evidence bundles.

The command-line acquisition component MAY consume already authorized URLs or local frozen assets, but MUST NOT bypass access controls or infer consent. If terms are unavailable, ambiguous, incompatible with redistribution, or not accepted, acquisition MUST stop. Publication metadata MUST distinguish open access, authenticated access, embargo, and restricted redistribution. Reusers remain responsible for satisfying upstream attribution and share-alike obligations; the DataTiles licence does not replace source licences.

## Minimal adaptation of the Naples workflow

Copy `demo/from-gaeta-to-maratea/config.json` to a new demo directory and change `demo_id`, title, bounding box, grid/tile parameters, sources, release identifiers, and classification profile. Complete the permission and licence gate first. Implement domain-specific readers/classifiers rather than encoding assumptions in configuration strings. Run acquisition once to create a candidate source lock; review the bytes and catalogue evidence before accepting that lock. Build twice and require identical outputs. Then execute independent scientific checks against source-native tools.

## Acceptance matrix

| Property | Suggested comparison |
|---|---|
| Geometry | bounds, grid registration, coastline mask, reference coordinates |
| Continuous variables | units, min/max, quantiles, RMSE/absolute tolerance at checkpoints |
| Categories | vocabulary mapping, confusion matrix, area totals, boundary inspection |
| Missingness | nodata semantics and fraction per variable/zoom |
| Provenance | every tile linked to sufficient source entities and generating activity |
| FAIR publication | PID resolution, licence, catalogue indexing, API links, metadata retention |

An acceptance report must identify software version, input identities, parameters, hardware/runtime where numerically relevant, observed deviations, and the decision rule. A replication that fails is still scientifically informative when evidence and deviations are preserved.
