# Data sources, acknowledgement, licensing, and citation

## Status and scope

This document is the authoritative source-by-source citation register for DataTiles demonstration derivatives, especially the **From Gaeta to Maratea** production workflow. It is part of the release evidence, not optional narrative documentation.

A source MUST be credited only when the frozen run manifest and provenance graph prove that the source contributed cells, features, topology, or contextual data to the released derivative. Conversely, every source that actually contributed MUST appear in the human-readable acknowledgement and machine-readable provenance/rights records.

Data licensing is independent of software licensing. The repository's current public `LICENSE` is Apache-2.0; no software licence grants rights in third-party input data. If the repository software licence changes, this document and the README statement MUST be reconciled in the same release.

## Mandatory release rule

Every map, MBTiles export, DataTiles container, static playground, figure, service, paper, archive, and release derived from the demo MUST:

1. identify the exact frozen source objects used by the run;
2. preserve source URI/PID, cryptographic identity or documented immutable-store identity, retrieval time, licence and required attribution;
3. record the transformation activity, software/version, parameters, CRS/datum handling, resampling/masking/fallback decisions, and generated-object identity;
4. visibly acknowledge every source that contributed to the displayed or distributed result;
5. distribute machine-readable provenance and rights with the artifact;
6. avoid crediting sources that were merely candidates, configured fallbacks, documentation references, or unused downloads; and
7. retain the **Not for navigation** warning for the research/demo products.

The frozen manifest is the evidentiary boundary. A generic project-level acknowledgement MUST NOT override it.

## Current From Gaeta to Maratea production sources

### 1. Primary bathymetry — JammeGaia22 / MGDS

**Role.** Primary finite bathymetric measurements wherever the selected JammeGaia22 grids contain usable values.

**Bibliographic citation.** Foglini, F., Tonielli, R., & Rovere, M. (2024). *Multi-Resolution bathymetry grids of the Naples and Pozzuoli Gulf and the Amalfi Coastal Area collected during cruise Jamme_Gaia22, 2022*. Marine Geoscience Data System (MGDS). https://doi.org/10.60521/331667

**Persistent identifier.** DOI `10.60521/331667`.

**Licence.** Creative Commons Attribution 4.0 International (CC BY 4.0).

**Required acknowledgement.** `Bathymetry: Foglini, Tonielli & Rovere (2024), JammeGaia22/MGDS, doi:10.60521/331667.`

**Scientific limitations.** This is multi-resolution multibeam bathymetry rather than a uniform-resolution navigation surface. MGDS describes GeoTIFF grids whose nominal resolutions vary with depth (2, 5, 15, 20, 30 and 40 m in the published products). Users MUST preserve the source grid identity and applicable resolution in provenance. The dataset is scientific bathymetry and is not an official nautical chart.

**Release evidence.** The frozen manifest MUST name the exact downloaded MGDS object(s), SHA-256 digest(s), source DOI, retrieval timestamp, spatial coverage used, and transformation activity that produced DataTiles cells.

### 2. Bathymetric fallback — EMODnet Digital Bathymetry DTM 2024

**Role.** Fallback bathymetry **only where JammeGaia22 contains no finite measurement**. The fallback decision is a transformation rule and MUST be recorded; it must not overwrite finite JammeGaia22 values.

**Bibliographic citation.** EMODnet Bathymetry Consortium (2024). *EMODnet Digital Bathymetry (DTM 2024)*. https://doi.org/10.12770/cf51df64-56f9-4a99-b1aa-36b8d7b743a1

**Persistent identifier.** DOI `10.12770/cf51df64-56f9-4a99-b1aa-36b8d7b743a1`.

**Licence for this project profile.** CC BY 4.0; the frozen acquisition metadata/terms retained by the release remain authoritative for the exact downloaded object.

**Required acknowledgement when it contributed.** `EMODnet Bathymetry Consortium DTM 2024, doi:10.12770/cf51df64-56f9-4a99-b1aa-36b8d7b743a1.`

**Scientific limitations.** EMODnet DTM is a harmonised composite product assembled from heterogeneous source datasets. Resolution, survey age, source quality, vertical reference and uncertainty can vary spatially. It MUST NOT be represented as equivalent to the local JammeGaia22 multibeam measurements. The DataTiles source-coverage variable MUST retain which source supplied each output cell.

### 3. Land topology / coastline — GSHHG 2.3.7

**Role.** Independent land/ocean topology and land mask. It is not bathymetry and MUST remain a separate fact from high-water-line products.

**Citation.** Wessel, P., & Smith, W. H. F. (1996). A global, self-consistent, hierarchical, high-resolution shoreline database. *Journal of Geophysical Research*, 101(B4), 8741–8743. https://doi.org/10.1029/96JB00104

**Dataset/version.** GSHHG 2.3.7 (15 June 2017).

**Licence.** GNU Lesser General Public License (as stated by NOAA/NCEI for GSHHG 2.3.7). Preserve the exact distributed notice with frozen source material.

**Required acknowledgement.** `Land/coastline: GSHHG 2.3.7 (Wessel & Smith, 1996, doi:10.1029/96JB00104).`

**Limitations.** GSHHG is a global hierarchical shoreline/topology database in WGS84 with multiple resolution levels. The production manifest MUST identify the resolution level actually used (the reference workflow uses full resolution where specified) and any clipping/generalisation performed.

### 4. Optional high-water-line fact — S2Coast-2023

**Role.** Optional Sentinel-2-derived coastline/high-water-line evidence when explicitly enabled. It MUST remain distinguishable from GSHHG topology and from bathymetry.

**Dataset citation.** Duan, Y., Sanchez-Azofeifa, A., Chen, C., Tian, B., Li, X., Sengupta, D., & Zhou, Y. *S2Coast-2023: The First Global 10-Meter Resolution Coastline Dataset Derived from Enhanced Sentinel-2 Composite Imagery Using Google Earth Engine*. Zenodo. https://doi.org/10.5281/zenodo.17092775

**Associated article.** Duan, Y. et al. (2026). S2Coast-2023: The first global 10-meter resolution coastline dataset derived from enhanced Sentinel-2 composite imagery using Google Earth Engine. *Remote Sensing of Environment*, 334, 115186. https://doi.org/10.1016/j.rse.2025.115186

**Licence.** CC BY 4.0 for the project source profile; retain the licence metadata of the exact frozen Zenodo object.

**Required acknowledgement when enabled and contributing.** `S2Coast-2023 (Duan et al., doi:10.5281/zenodo.17092775), CC BY 4.0.`

**Limitations.** Nominal 10 m global coastline derived from annual Sentinel-2 imagery. It is a remotely sensed coastline fact with its own temporal/reference assumptions; it is not interchangeable with GSHHG topology or a hydrographic chart coastline.

### 5. Navigation and land context — OpenStreetMap

**Role.** Stored navigation/land contextual features actually obtained from OpenStreetMap, including the demo's stored seamark/context vectors where present.

**Attribution.** `© OpenStreetMap contributors`.

**Licence.** Open Data Commons Open Database License (ODbL) 1.0.

**Licence/copyright page.** https://www.openstreetmap.org/copyright

**Required acknowledgement when OSM data contributed.** `Context: © OpenStreetMap contributors, ODbL 1.0.`

**Licence note.** Publicly used produced works must provide attribution and make users aware that OpenStreetMap data are available under the ODbL. Distribution of a derivative database may trigger ODbL share-alike obligations. Release engineering MUST evaluate the actual distributed database/product rather than assuming that a software licence controls OSM-derived data.

## Required short-form map credit

For the current production build, when all named sources actually contributed, use:

> Bathymetry: Foglini, Tonielli & Rovere (2024), JammeGaia22/MGDS, doi:10.60521/331667; EMODnet Bathymetry Consortium DTM 2024, doi:10.12770/cf51df64-56f9-4a99-b1aa-36b8d7b743a1. Land/coastline: GSHHG 2.3.7 and S2Coast-2023. Context: © OpenStreetMap contributors, ODbL 1.0. Not for navigation.

The renderer/release process MUST remove a source from this credit when the run manifest proves that it contributed nothing. In particular, S2Coast-2023 must not be named when disabled or non-contributing, and EMODnet must not be named when no fallback cells were used.

## Sources that MUST NOT be credited without evidence of use

Do **not** list GMRT, GEBCO, EMODnet thematic products, ISPRA, or any other candidate/reference source as a contributor unless the specific frozen run manifest proves that its data contributed cells or features to the released product. A bibliography may discuss related datasets as background, but that is distinct from a data acknowledgement.

Citation is source-specific evidence, not generic project boilerplate.

## Frozen-manifest requirements

Every production release SHOULD archive a manifest under the release evidence tree (for the reference demo, under `demo/from-gaeta-to-maratea/dist/` or the immutable evidence bundle produced by the build). At minimum, each source record MUST contain:

- stable source key and human title;
- source role (`primary_bathymetry`, `fallback_bathymetry`, `land_topology`, `high_water_line`, `context`, etc.);
- PID/DOI and canonical landing URI where available;
- exact acquired object URI without credentials;
- retrieval timestamp;
- SHA-256 or the format-specific immutable-store identity defined by the DataTiles source profile;
- media/format and source version;
- licence identifier, licence URI, attribution text and notices;
- spatial/temporal coverage and resolution relevant to the run;
- transformation activity identifier;
- number/extent of output cells or features contributed; and
- an explicit `contributed: true|false` outcome determined by the build.

The manifest itself MUST be checksummed and referenced by the generated DataTiles provenance graph. A source with `contributed: false` remains useful acquisition evidence but MUST NOT appear in contributor acknowledgements.

## Machine-readable provenance and rights

The DataTiles object and release package MUST preserve, for every contributing source:

- a provenance entity carrying its PID/URI and cryptographic identity;
- a source-rights record separate from the generated dataset and metadata rights;
- the generating activity and its parameters;
- `used` / `wasDerivedFrom` relationships connecting output variables/tiles to inputs;
- source-coverage evidence for conditional fusion such as JammeGaia22 → EMODnet fallback;
- creator/provider attribution and citation metadata; and
- the generated object's own persistent identifier when published.

Human-visible credits and machine-readable provenance are complementary; neither substitutes for the other.

## FAIR release checklist

Before a scholarly or public demo release, verify all of the following:

- [ ] Every contributing source has a PID or stable URI and immutable object identity.
- [ ] Every contributing source has explicit licence/rights metadata and required attribution.
- [ ] No licence is inferred merely from successful download/access.
- [ ] Source and output licences are represented separately.
- [ ] The frozen manifest records `contributed` status and quantitative contribution evidence.
- [ ] Conditional fallback/fusion rules are explicit and reproducible.
- [ ] CF/controlled semantic names, units, CRS and vertical datum are retained where applicable.
- [ ] Machine-readable provenance links each derived product to the exact source objects and transformation activities.
- [ ] Human-visible acknowledgements are generated/checked against the frozen manifest.
- [ ] Non-contributing candidate sources are absent from contributor acknowledgements.
- [ ] DataCite/citation metadata includes appropriate related identifiers for contributing datasets.
- [ ] The release archive contains the manifest, provenance, rights, checksums, citation register and software/environment identity.
- [ ] `Not for navigation` is visible on the demo/map artifacts.
- [ ] Repository software licensing and data licensing are not conflated.

## Verification sources for this register

The citations and licence statements above should be periodically rechecked against the authoritative provider records before publication. At the time this register was prepared, the controlling public records were MGDS DOI `10.60521/331667`, the EMODnet Bathymetry DTM 2024 citation page, NOAA/NCEI GSHHG 2.3.7 documentation, Zenodo DOI `10.5281/zenodo.17092775`, and the OpenStreetMap copyright/licensing page.

## Optional signed-release checklist

When the release policy requires cryptographic integrity, sign only after the frozen run manifest has established actual source contribution and the visible acknowledgements have been derived from it. Archive the DataTiles object, detached signature envelope, trusted public key/certificate reference, and any external timestamp/transparency evidence. A signature never licenses a source and never changes which sources must be cited.

## Commercial products remain source-specific

Selling or encrypting a product does not change source attribution. The frozen contribution manifest remains authoritative: every source that actually contributed cells/features must be cited according to its licence, and a source must not be listed merely because it was a candidate. Commercialization must be blocked when a contributing source's terms do not permit the intended use.
