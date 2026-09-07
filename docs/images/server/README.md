# Online Delivery client screenshot provenance

This directory records executed visual evidence for a client of the DataTiles Online Delivery reference server. The screenshot is a presentation artifact, not a stored scientific variable, source observation, proof of conformance, official chart, ENC/ECDIS substitute, or navigation product.

## Capture environment and inputs — 2026-09-07

- screenshot: `openlayers-online-delivery.jpg`;
- viewport: 1280 × 720 pixels;
- screenshot SHA-256: `023b0af2cc26b783a333c19b425d57f0d94c6a5462a1fe57302c48e399295590`;
- input container: `dist/from-gaeta-to-maratea.datatiles`;
- input container SHA-256: `e4aad57e2ec7d3904bf64ed4cfc270c693fb5078e05f80ca3d5f1e363a203ade`;
- client: OpenLayers 10.6.1;
- client centre: `14.25° E, 40.62° N`;
- client zoom: `8.35`, constrained to zooms 8–12;
- server layer id: `bathymetry`;
- input coordinate set: `variable=depth_below_lat_m`, `dataset_release=JammeGaia22 with EMODnet DTM 2024 fallback`;
- output: lossless WebP requested through the XYZ `/maps/bathymetry/{z}/{x}/{y}.webp` interface;
- portrayal algorithm: DNT1 scale/offset and nodata decoding followed by linear RGBA interpolation;
- palette parameters: `0:#dff8ff`, `50:#a8e0ef`, `200:#55a8cf`, `1000:#235a91`, `3000:#102b55`, in metres below LAT;
- layer release cache identity: `from-gaeta-to-maratea-v3`.

![OpenLayers Online Delivery client](openlayers-online-delivery.jpg)

The coloured pixels are a server-derived portrayal of stored numeric arrays. They were not read from an opaque map service and were not inserted into the DataTiles container as scientific data. The blank surrounding area is outside the available tiled extent. Visible cell boundaries, coastline shape, colour interpolation, and resolution remain limited by the declared inputs and algorithms. The Gaeta-to-Maratea reference products are explicitly not for navigation.
