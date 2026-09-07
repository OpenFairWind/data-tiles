import { DataTilesClient, renderScalarToCanvas } from "../common/datatiles-client.js";

export function serverLayer(ol, baseUrl, layerId, options = {}) {
  const q = new URLSearchParams(options.dimensions || {}).toString();
  const suffix = q ? `?${q}` : "";
  return new ol.layer.Tile({
    opacity: options.opacity ?? 1,
    source: new ol.source.XYZ({
      url: `${baseUrl.replace(/\/$/, "")}/maps/${encodeURIComponent(layerId)}/{z}/{x}/{y}.${options.format || "webp"}${suffix}`,
      crossOrigin: "anonymous"
    })
  });
}

export function clientLayer(ol, baseUrl, dataset, portrayal, options = {}) {
  const api = new DataTilesClient(baseUrl);
  const dimensions = options.dimensions || {};
  const source = new ol.source.XYZ({
    url: `${baseUrl.replace(/\/$/, "")}/api/datasets/${encodeURIComponent(dataset)}/tiles/{z}/{x}/{y}`,
    crossOrigin: "anonymous",
    tileLoadFunction(tile) {
      const xyz = tile.getTileCoord();
      const z = xyz[0], x = xyz[1], y = -xyz[2] - 1;
      api.fetchDNT1(dataset, z, x, y, dimensions).then(decoded => {
        const canvas = renderScalarToCanvas(decoded, portrayal);
        canvas.toBlob(blob => { tile.getImage().src = URL.createObjectURL(blob); }, "image/png");
      }).catch(() => { tile.getImage().src = "data:image/gif;base64,R0lGODlhAQABAAAAACw="; });
    }
  });
  return new ol.layer.Tile({ opacity: options.opacity ?? 1, source });
}
