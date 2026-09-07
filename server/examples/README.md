# Server examples

With `weather.datatiles` installed and `layers.json` configured:

```bash
curl http://localhost:8080/maps/temperature/tilejson.json
curl http://localhost:8080/maps/temperature/dimensions
curl http://localhost:8080/maps/temperature/legend.json
curl -o raw.dnt1 'http://localhost:8080/api/datasets/weather/tiles/6/34/24?variable=air_temperature'
curl -o rendered.webp 'http://localhost:8080/maps/temperature/6/34/24.webp'
```

Both tile calls select the same logical scientific tile. The first keeps portrayal on the client; the second applies the published portrayal on the server. Coordinates in these URLs are XYZ. Replace the tile coordinate and exact dimension values with selections that exist in the container; use `/maps`, TileJSON, and `/dimensions` for discovery rather than guessing them.
