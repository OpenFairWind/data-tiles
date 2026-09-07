import { DataTilesClient, renderScalarToCanvas } from "../common/datatiles-client.js";

export function serverMapType(google, baseUrl, layerId, options = {}) {
  const dimensions = options.dimensions || {};
  return new google.maps.ImageMapType({
    tileSize: new google.maps.Size(options.tileSize || 256, options.tileSize || 256),
    maxZoom: options.maxZoom ?? 18,
    minZoom: options.minZoom ?? 0,
    opacity: options.opacity ?? 1,
    name: options.name || layerId,
    getTileUrl(coord, zoom) {
      const q = new URLSearchParams(dimensions).toString();
      return `${baseUrl.replace(/\/$/, "")}/maps/${encodeURIComponent(layerId)}/${zoom}/${coord.x}/${coord.y}.${options.format || "webp"}${q ? `?${q}` : ""}`;
    }
  });
}

export function clientMapType(google, baseUrl, dataset, portrayal, options = {}) {
  const api = new DataTilesClient(baseUrl);
  const dimensions = options.dimensions || {};
  return {
    tileSize: new google.maps.Size(options.tileSize || 256, options.tileSize || 256),
    maxZoom: options.maxZoom ?? 18,
    minZoom: options.minZoom ?? 0,
    name: options.name || dataset,
    getTile(coord, zoom, ownerDocument) {
      const canvas = ownerDocument.createElement("canvas");
      canvas.width = canvas.height = options.tileSize || 256;
      api.fetchDNT1(dataset, zoom, coord.x, coord.y, dimensions)
        .then(d => renderScalarToCanvas(d, portrayal, canvas))
        .catch(err => { canvas.title = err.message; });
      return canvas;
    },
    releaseTile() {}
  };
}
