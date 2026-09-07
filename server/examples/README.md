# Server examples

With `weather.datatiles` installed and `layers.json` configured:

```bash
curl http://localhost:8080/maps/temperature/tilejson.json
curl -o raw.dnt1 'http://localhost:8080/api/datasets/weather/tiles/6/34/24?variable=air_temperature'
curl -o rendered.webp 'http://localhost:8080/maps/temperature/6/34/24.webp'
```

Both tile calls select the same logical scientific tile. The first keeps portrayal on the client; the second applies the published portrayal on the server.
