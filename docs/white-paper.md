# DataTiles at the edge: a manifesto and implementation white paper

## Abstract

Onboard intelligence is constrained by intermittent connectivity, finite compute, uncertain observations, and decisions whose consequences may affect human life and the environment. DataTiles proposes a systems principle: put analysis-ready, spatially local, multidimensional data and its evidence in the same inspectable container used at the edge. The result is not an autonomous decision-maker. It is an offline-first evidence substrate from which deterministic algorithms, statistical models, and AI systems can retrieve bounded context, expose uncertainty, degrade safely, and leave an audit trail.

## The manifesto

1. **Data before portrayal.** Store numeric matrices and vector features, not only pictures. A rendered map records visualization choices, not the measured world.
2. **Context is part of the address.** Time, depth, scenario, ensemble, vehicle state, and model version must not hide in filenames or undocumented bands.
3. **Offline is a normal operating mode.** Critical context must remain queryable when networks disappear.
4. **Provenance travels with the tile.** Source, transformation, software, parameters, datum, license, and checksum are operational data.
5. **Uncertainty must survive the pipeline.** AI output without freshness, uncertainty, and applicability is not safety information.
6. **Interoperability includes graceful degradation.** Multidimensional data should yield a coherent MBTiles portrayal when only legacy mapping is available.
7. **FAIR and safety reinforce one another.** Identifiers, semantics, provenance, and reproducibility strengthen research and incident review.
8. **Human authority remains explicit.** DataTiles supports decisions; it is not, by itself, an approved chart, ECDIS, driving function, collision-avoidance system, or certified safety component.

## Practical onboard architecture

An edge deployment ingests authoritative products, local sensors, forecasts, vehicle telemetry, and observations from peers. It normalizes variables with explicit coordinates, CRS/datum, units, provenance, freshness, and uncertainty. A bounded spatial-temporal query extracts the neighborhood needed by an algorithm. Deterministic features and AI inference run locally. The application fuses outputs with rules, operational limits, and live sensors, presents evidence to a human or certified subsystem, and records the inference as new provenance.

Tile locality bounds I/O and decompression. Multidimensional coordinates prevent “latest file” ambiguity. Content profiles distinguish measurements, categorical classes, vector obstacles, and portrayals. A selected slice or standalone MBTiles export provides graceful map-only fallback.

## Maritime and navigation applications

Candidate decision-support products include under-keel-clearance context, bathymetric gradients, seabed class, shoreline and restricted-area vectors, waves, currents, winds, weather hazards, water quality, habitat sensitivity, and crowdsourced observations. A local model might estimate grounding exposure or recommend a lower-impact route, but its inputs must declare vertical datum, survey age, resolution, uncertainty, tide assumptions, vessel draft, and model limits.

The From Gaeta to Maratea demo illustrates the analytical substrate: depth and seabed classes remain numeric/categorical arrays; profiles, adaptive contours, relief, textures, and 3D views are derived live. Its northwest-wind shelter field is a land-interception proxy, not a wave model. EMODnet limitations and “not for navigation” warnings remain binding. Operational navigation requires authoritative hydrographic products, certified equipment, controlled updates, sensor fusion, applicable regulation, and a safety case.

Environmental uses include avoiding sensitive habitats, tracking pollution exposure, prioritizing sampling, and comparing routes by ecological cost. They require transparent vocabularies and must not infer coral, algae, or habitat condition from generic substrate labels.

## Automotive and mobile robotics applications

The same model can tile road geometry, grade, curvature, friction estimates, surface condition, flood depth, visibility, air quality, work zones, vulnerable-road-user observations, charging context, and weather forecasts across time, scenario, confidence, and source. Edge retrieval can supply context to perception or planning when cloud service is unavailable.

DataTiles must remain outside the safety boundary unless the complete system is engineered and assessed for that role. A portrayal is not a drivable-world model. Stale roadworks, uncertain floods, coordinate errors, or distribution shift can be hazardous. Deployment therefore needs integrity levels, authenticated updates, freshness rules, fail-operational or fail-safe behavior, independent sensing, runtime monitors, and applicable functional-safety and safety-of-the-intended-functionality processes.

## Data stewardship, source-specific citation, and licence boundaries

An edge evidence substrate is scientifically defensible only when the identity and legal status of its inputs survive transformation. DataTiles therefore treats **data acknowledgement as executable release evidence**, not as generic prose. A derived tile pyramid, MBTiles compatibility export, map, figure, service, model input, or paper MUST be traceable to the exact source objects that contributed cells or features. The frozen run manifest is the authority for contributor status.

The From Gaeta to Maratea reference build illustrates this principle. Its primary finite bathymetry is the JammeGaia22/MGDS multi-resolution multibeam product (Foglini, Tonielli & Rovere, 2024; doi:10.60521/331667). EMODnet Digital Bathymetry DTM 2024 (doi:10.12770/cf51df64-56f9-4a99-b1aa-36b8d7b743a1) is a conditional fallback only where JammeGaia22 has no finite measurement. This priority rule is scientific provenance: a consumer must be able to distinguish measured/local primary cells from harmonised fallback cells. Source coverage is therefore retained as data rather than erased after fusion.

Land/ocean topology is an independent evidence class. GSHHG 2.3.7, cited through Wessel & Smith (1996; doi:10.1029/96JB00104), provides hierarchical shoreline/topology information. When enabled, S2Coast-2023 (Duan et al.; doi:10.5281/zenodo.17092775) contributes a Sentinel-2-derived high-water-line/coastline fact. These products must not be collapsed into a single undocumented notion of “coastline”: their definitions, resolutions, epochs, licences, and error modes differ. OpenStreetMap context remains separately attributable as © OpenStreetMap contributors under ODbL 1.0.

This separation is both FAIR and operational. Findability requires persistent identifiers and indexed metadata; accessibility requires resolvable, documented access conditions; interoperability requires controlled semantics, units, CRS/datums, and explicit source roles; reusability requires qualified provenance, licences, attribution, limitations, and transformation history. A downloadable object is not necessarily reusable, and an open-source software licence does not relicense source data.

DataTiles release engineering consequently applies four invariants:

1. **No anonymous contribution.** Every contributing source is represented by a PID/stable URI, immutable object identity, rights record, and provenance entity.
2. **No generic acknowledgement.** Visible credits are source-specific and must agree with the frozen manifest. Candidate sources that contributed nothing are not credited as data contributors.
3. **No licence laundering.** Software, source-data, generated-dataset, metadata, and portrayal rights remain distinguishable. Combining data does not silently erase upstream obligations.
4. **No provenance-free fusion.** Priority, masking, resampling, reprojection, fallback and feature-selection decisions are generating activities with parameters and software identity; conditional fusion retains a source-coverage field or equivalent lineage evidence.

For the current reference production build, the complete bibliographic records, required short-form map credit, licence statements, coverage/resolution cautions, manifest requirements, and FAIR release checklist are normative project guidance in `docs/data_sources_and_citation.md`. The map credit is a projection of the actual run evidence, not immutable boilerplate. GMRT, GEBCO, EMODnet thematic products, ISPRA, and other candidate/reference datasets must not be represented as contributors unless the specific run manifest proves their use.

This discipline also constrains AI and statistical consumers. A model must be able to retrieve not merely a depth value but the source identity and transformation lineage that produced it. Where primary and fallback datasets differ in resolution, survey age, datum, or uncertainty, that distinction is part of the feature contract and may affect applicability. FAIR stewardship therefore becomes part of uncertainty management and reproducibility rather than a post-publication metadata exercise.

## Cryptographic integrity, authenticity, and scholarly chain of custody

DataTiles optionally signs a canonical logical manifest of the complete scientific object. This is deliberately stronger than attaching a checksum to the SQLite file: the manifest is invariant to storage-layout operations such as VACUUM while remaining sensitive to changes in scientific cells, vectors, metadata, semantics, provenance, rights, selected-slice state, and signed schema definitions. The native profile uses SHA-256 and Ed25519; the signing tables are excluded from the signed domain so multiple independent signatures can attest the same immutable scientific state.

The trust claim is intentionally narrow. A mathematically valid signature proves possession of the corresponding private key at signing time, not the institutional identity of that key holder. Publication workflows must authenticate public keys independently, bind signers to persistent scholarly agents, preserve historical keys through rotation, and archive detached signatures and verification material with the research object. Sigstore/in-toto evidence can supplement the offline profile with certificate identity, transparency inclusion, and timestamps, but is not required for basic DataTiles verification.

Cryptographic signatures complement FAIR metadata, W3C PROV lineage, DataCite identity, source-specific citation, and SPDX rights; they do not replace any of them. Nor do they establish scientific truth, licence compatibility, hydrographic authority, or navigation fitness. An unsigned object can still be FAIR; an institution may separately impose a signed-release policy for chain-of-custody assurance.

## AI evidence contract

Every onboard inference should identify:

- source object and coordinate-set identifiers;
- source tile/pixel or feature identifiers and query geometry;
- units, CRS/datum, acquisition/valid time, freshness, and uncertainty;
- model name, immutable digest, feature schema, calibration, and runtime;
- preprocessing, missing-data policy, and out-of-distribution flags;
- output, confidence, threshold, consuming component, and timestamp.

Derived model products should be new variables linked by `used`, `wasGeneratedBy`, and `wasDerivedFrom`. A model must never fabricate absent map evidence or silently substitute a portrayal for numeric input. Conflicting sources remain separately addressable; reconciliation is an explicit activity.

## Safety and environmental assurance

| Layer | Required evidence |
|---|---|
| data | authority, license, checksum, CRS/datum, units, uncertainty, age, coverage, limitations |
| transformation | deterministic implementation, parameters, tests, source links, reproducible environment |
| model | training scope, evaluation, calibration, OOD behavior, version/digest, failure modes |
| operation | update authentication, monitoring, fallback, human factors, incident log, regulatory approval |

Safe degradation is designed. When a coordinate set is absent, stale, corrupt, outside coverage, or incompatible, the system should report “unavailable/invalid,” preserve the reason, and enter an independently justified fallback or safer operational state. It should not interpolate or choose the nearest scenario unless policy explicitly authorizes and records that choice.

Cybersecurity matters because a plausible malicious tile can alter an AI decision. Deployments should verify signed manifests, use immutable digests, disable SQLite extension loading, open external files read-only, bound decompression, isolate parsers, authenticate updates, support rollback, and log source transitions. Privacy-sensitive mobility and sensor observations require minimization, retention rules, and access control beyond the public FAIR profile.

## Implementation blueprint

1. Define operational questions and failure consequences before variables.
2. Specify variables, dimensions, CRS/datums, units, uncertainties, profiles, and authoritative sources.
3. Build deterministic acquisition and transformation with checksums and provenance.
4. Publish analysis-ready DNT1/MVT data and separate portrayal slices.
5. Validate container structure and independent scientific acceptance criteria.
6. Implement bounded local queries and explicit feature contracts.
7. Evaluate models across geography, seasons, rare events, missing data, latency, corruption, and distribution shift.
8. Design human presentation, fallback, and minimum-risk behavior.
9. Package signed releases and exercise offline update and rollback.
10. Retain replayable evidence; repeat validation after every data, code, model, or specification change.

## Research agenda and conclusion

Future work includes uncertainty profiles, signed tile manifests, incremental synchronization, content-addressed deduplication, safety-oriented freshness policies, model/provenance profiles, non-Web-Mercator matrices, efficient vector/numeric co-query, and evaluation on real edge hardware.

DataTiles is a bridge between scientific stewardship and edge intelligence. Its claim is not that a SQLite file makes autonomy safe. Its contribution is to make the data boundary explicit, local, inspectable, reproducible, interoperable, and accountable—conditions that systems protecting life and the environment need before algorithms can be trusted.

## Commercial distribution, rights expression, and DRM

DataTiles does not equate FAIR with open or zero-cost access. Commercial and institutionally restricted research/cartographic products can remain machine-discoverable and semantically interoperable while the data payload is distributed under controlled access. Revision 7 therefore separates four layers: scholarly/data rights, machine-readable ODRL usage policy, cryptographic integrity/authenticity, and optional DRM enforcement.

The portable DRM profile wraps the finalized DataTiles SQLite object rather than encrypting individual scientific rows. This preserves the canonical research object, allows the existing integrity signature to attest the exact plaintext release, and ensures authorized decryption recovers byte-identical DataTiles content. AES-256-GCM provides authenticated confidentiality; recipient-specific X25519/HKDF key wrapping avoids sharing a universal customer secret; Ed25519 issuer signatures authenticate licence grants.

DRM cannot manufacture legal rights. A publisher may sell a derivative only when every contributing source and contractual term permits the intended commercial exploitation. Source-specific citation, attribution, provenance, licence compatibility, and database-right obligations remain enforceable independently of the encryption layer. Nor can portable DRM prevent an authorized endpoint from copying plaintext after decryption. It should therefore be described as distribution/access control, not as an absolute anti-copy guarantee.

For FAIR publication, public metadata should disclose the existence of access restrictions, product identity, terms, issuer, and access mechanism even when the payload requires purchase or authorization. Conversely, secrets, customer identifiers not required for scholarly provenance, private keys, and payment information are intentionally excluded from the scientific object and FAIR graph.

## Versioned dissemination, acquisition history, and payment abstraction

A scientific data product must distinguish identity of the logical product from identity of an individual release. Revision 8 therefore introduces a stable product identifier and an explicit monotonic release sequence in addition to the human-facing version label. This design prevents ambiguous lexical version ordering and supports reproducible citation of the exact release used in analysis. Published versioned objects are immutable; an update is a successor object, not a silent byte replacement.

The Store uses this release identity to maintain user-level acquisition evidence. Purchases and downloads are separate records: a purchase represents a commercial entitlement transaction, while a download records actual delivery of an exact checksum-identified release. A higher sequence for the same product can generate an update notification to prior users without implying that the successor is free, licensed identically, or scientifically interchangeable.

Commercial payment processing is intentionally abstracted from the scientific format and Store entitlement schema. A payment provider implements a narrow checkout/capture contract; PayPal Orders v2 is the reference implementation. Provider credentials and financial payment details remain outside DataTiles provenance. Commercial entitlement, data licensing, FAIR evidence, provenance, cryptographic signatures, DRM, scientific validity, and navigation fitness remain independent claims that must not be conflated.
