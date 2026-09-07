# DataTiles web-map plugins

These adapters expose the same logical DataTiles layer in two modes:

- **server**: standard PNG/WebP tiles from `/maps/{layer}/{z}/{x}/{y}.{format}`;
- **client**: raw DNT1 tiles from `/api/datasets/{dataset}/tiles/{z}/{x}/{y}` decoded and portrayed in the browser.

The portrayal object and dimension selection are intentionally shared. Applications may choose a mode per layer and may switch modes at runtime without changing the scientific dataset.

Directories:

- `leaflet/` - Leaflet `GridLayer` / `TileLayer` adapters;
- `openlayers/` - OpenLayers tile adapters;
- `google-maps/` - Google Maps `MapType` / `ImageMapType` adapters;
- `common/` - DNT1 decoder and deterministic scalar renderer.

See each `examples/` directory. Run the reference server first and serve the repository over HTTP; ES modules cannot normally be loaded from `file://` URLs.
