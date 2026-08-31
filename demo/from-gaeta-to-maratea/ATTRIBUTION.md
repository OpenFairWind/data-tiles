# Data attribution and limitations

## Bundled ports demonstration resource

`resources/ports.json` is retained as the checksum-identified input supplied with the ports-import demonstration. Its inclusion is for reproducibility and does not establish authority, completeness, currency, or fitness for navigation. The resulting port slice and browser symbols are unofficial.

## EMODnet Bathymetry

EMODnet Digital Bathymetry (DTM) 2024, EMODnet Bathymetry Consortium, catalogue identifier `cf51df64-56f9-4a99-b1aa-36b8d7b743a1`, licensed under CC BY 4.0. Water depth is referenced to Lowest Astronomical Tide. **Do not use for navigation.** Individual surveys and composite DTMs retain their own originator metadata in the EMODnet source-reference system.

## JammeGaia22 / MGDS bathymetry

Foglini, F., Tonielli, R., and Rovere, M. (2024), *Multi-Resolution bathymetry grids of the Naples and Pozzuoli Gulf and Amalfi Coastal Area, Jamme_Gaia22 (2022)*, DOI `10.60521/331667`, CC BY 4.0. The build records each source-grid checksum and selected resolution. Its vertical datum is not silently asserted to be harmonized with EMODnet LAT.

## Land and coastline

GSHHG 2.3.7 full-resolution shoreline polygons provide the land/ocean mask: Wessel, P., and Smith, W. H. F. (1996), DOI `10.1029/96JB00104`. GSHHG topology remains distinct from bathymetry. S2Coast-2023, when enabled by a future declared profile, remains a separate high-water-line fact and is not silently substituted for GSHHG.

## EMODnet Geology

EMODnet Geology Seabed Substrates, 1:100,000 harmonized product, catalogue identifier `6eaf4c6bf28815e973b9c60aab5734e3ef9cd9c4`. Copyright is held by the European Community represented by the European Commission and the contributing EMODnet-Geology partners. No warranty of quality, accuracy, completeness, or suitability is provided.

## EMODnet Seabed Habitats

Credit: Licensed under CC BY 4.0 from the European Marine Observation and Data Network (EMODnet) Seabed Habitats initiative, funded by the European Commission. EUSeaMap 2025 catalogue identifier `cec07b5e-3a9c-4492-b115-126a17c08697`.

## Derived DataTiles artifact

OpenStreetMap `seamark:*` nodes and ways are © OpenStreetMap contributors and are used under the Open Database License 1.0. The bounded Overpass response is checksum-locked and stored as tiled GeoJSON; no C-MAP or OpenSeaMap raster portrayal is copied.

The derived classification is a deterministic technical generalization for demonstrating the DataTiles format. It is not a replacement for the original Folk, EUNIS, MSFD, or Barcelona Convention classifications and does not assert that every supported class occurs in the Gaeta-to-Maratea subset.
