# MBTiles fallback for OpenLayers applications

DataTiles provides two compatibility levels. First, select one multidimensional coordinate set and an MBTiles reader sees that slice through `metadata` and the four-column `tiles` view. MBTiles 1.3 defines these schemas as interfaces and permits views.

Some OpenLayers deployments use an MBTiles adapter, server, or SQLite/WASM bridge that accepts only physical tables or rejects unknown extension objects. Materialize a standalone file for those deployments:

```bash
datatiles select ocean.datatiles --coord variable=seabed_portrayal
datatiles export-mbtiles ocean.datatiles ocean.mbtiles

# Or export an exact slice without changing selection:
datatiles export-mbtiles ocean.datatiles ocean.mbtiles \
  --coord variable=seabed_portrayal
```

The output contains only physical `metadata` and `tiles` tables, standard MBTiles metadata, TMS rows, and unchanged payloads from the chosen slice. It contains no `datatiles_*` objects. PNG, JPEG, WebP, and gzip MVT are directly exportable.

DNT1 is deliberately rejected because a conventional web map cannot interpret numeric arrays. Produce a PNG/WebP portrayal as a separate, provenance-linked coordinate set, recording its color scale, datum, units, nodata handling, and resampling. Export that portrayal while retaining DNT1 as the scientific source. Tiled GeoJSON likewise requires explicit conversion to gzip MVT rather than relabeling bytes.

OpenLayers usually consumes MBTiles through an HTTP adapter; a browser cannot portably open an arbitrary local SQLite file by itself. Adapter configuration is deployment-specific, but the exported schema is conservative MBTiles 1.3.

The regression suite checks physical object types, exact interface columns, standard-only metadata, byte preservation, zoom derivation, MVT layer metadata, unsupported-payload rejection, and refusal to overwrite an existing target.
