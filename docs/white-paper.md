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

The Bay of Naples demo illustrates the analytical substrate: depth and seabed classes remain numeric/categorical arrays; profiles, contours, relief, textures, and 3D views are derived live. Its northwest-wind shelter field is a land-interception proxy, not a wave model. EMODnet limitations and “not for navigation” warnings remain binding. Operational navigation requires authoritative hydrographic products, certified equipment, controlled updates, sensor fusion, applicable regulation, and a safety case.

Environmental uses include avoiding sensitive habitats, tracking pollution exposure, prioritizing sampling, and comparing routes by ecological cost. They require transparent vocabularies and must not infer coral, algae, or habitat condition from generic substrate labels.

## Automotive and mobile robotics applications

The same model can tile road geometry, grade, curvature, friction estimates, surface condition, flood depth, visibility, air quality, work zones, vulnerable-road-user observations, charging context, and weather forecasts across time, scenario, confidence, and source. Edge retrieval can supply context to perception or planning when cloud service is unavailable.

DataTiles must remain outside the safety boundary unless the complete system is engineered and assessed for that role. A portrayal is not a drivable-world model. Stale roadworks, uncertain floods, coordinate errors, or distribution shift can be hazardous. Deployment therefore needs integrity levels, authenticated updates, freshness rules, fail-operational or fail-safe behavior, independent sensing, runtime monitors, and applicable functional-safety and safety-of-the-intended-functionality processes.

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
