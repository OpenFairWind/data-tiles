import { DataTilesClient, renderScalarToCanvas } from "../common/datatiles-client.js";

export function serverLayer(L, baseUrl, layerId, options = {}) {
  const dimensions = options.dimensions || {};
  const q = new URLSearchParams(dimensions).toString();
  const suffix = q ? `?${q}` : "";
  return L.tileLayer(`${baseUrl.replace(/\/$/, "")}/maps/${encodeURIComponent(layerId)}/{z}/{x}/{y}.${options.format || "webp"}${suffix}`, options.leaflet || {});
}

export function clientLayer(L, baseUrl, dataset, portrayal, options = {}) {
  const api = new DataTilesClient(baseUrl);
  const dimensions = options.dimensions || {};
  const Grid = L.GridLayer.extend({
    createTile(coords, done) {
      const tile = document.createElement("canvas");
      tile.width = tile.height = options.tileSize || 256;
      api.fetchDNT1(dataset, coords.z, coords.x, coords.y, dimensions)
        .then(d => { renderScalarToCanvas(d, portrayal, tile); done(null, tile); })
        .catch(err => done(err, tile));
      return tile;
    }
  });
  return new Grid(options.leaflet || {});
}
