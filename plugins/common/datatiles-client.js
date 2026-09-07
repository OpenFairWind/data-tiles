/* DataTiles browser-side DNT1 decoding and deterministic scalar portrayal. */
export class DataTilesClient {
  constructor(baseUrl, options = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.fetch = options.fetch || globalThis.fetch.bind(globalThis);
  }

  tileUrl(dataset, z, x, y, dimensions = {}) {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(dimensions)) if (v !== undefined && v !== null) q.set(k, v);
    const suffix = q.size ? `?${q}` : "";
    return `${this.baseUrl}/api/datasets/${encodeURIComponent(dataset)}/tiles/${z}/${x}/${y}${suffix}`;
  }

  async fetchDNT1(dataset, z, x, y, dimensions = {}) {
    const r = await this.fetch(this.tileUrl(dataset, z, x, y, dimensions));
    if (!r.ok) throw new Error(`DataTiles ${r.status}: ${await r.text()}`);
    return decodeDNT1(await r.arrayBuffer());
  }
}

export async function decodeDNT1(buffer) {
  const bytes = new Uint8Array(buffer);
  if (bytes.length < 8 || String.fromCharCode(...bytes.slice(0, 4)) !== "DNT1") throw new Error("not a DNT1 tile");
  const dv = new DataView(buffer);
  const headerLength = dv.getUint32(4, false);
  if (headerLength > 1048576 || 8 + headerLength > bytes.length) throw new Error("invalid DNT1 header length");
  const header = JSON.parse(new TextDecoder().decode(bytes.slice(8, 8 + headerLength)));
  const required = ["dtype", "shape", "byteorder", "compression"];
  const allowed = new Set([...required, "nodata", "scale", "offset", "unit"]);
  if (!header || typeof header !== "object" || Array.isArray(header) || required.some(k => !(k in header)) || Object.keys(header).some(k => !allowed.has(k))) {
    throw new Error("invalid DNT1 header fields");
  }
  if (!Array.isArray(header.shape) || header.shape.length < 1 || header.shape.length > 8 || header.shape.some(v => !Number.isSafeInteger(v) || v <= 0)) {
    throw new Error("invalid DNT1 shape");
  }
  if (header.byteorder !== "little" && header.byteorder !== "big") throw new Error("invalid DNT1 byte order");
  const count = header.shape.reduce((a, b) => a * b, 1);
  if (!Number.isSafeInteger(count) || count > 16777216) throw new Error("DNT1 element limit exceeded");
  let payload = bytes.slice(8 + headerLength);
  if (header.compression === "zlib") {
    if (!("DecompressionStream" in globalThis)) throw new Error("zlib DNT1 requires browser DecompressionStream support");
    const stream = new Blob([payload]).stream().pipeThrough(new DecompressionStream("deflate"));
    payload = new Uint8Array(await new Response(stream).arrayBuffer());
  } else if (header.compression !== "none") throw new Error(`unsupported compression ${header.compression}`);

  const ctor = {
    int8: Int8Array, uint8: Uint8Array, int16: Int16Array, uint16: Uint16Array,
    int32: Int32Array, uint32: Uint32Array, int64: globalThis.BigInt64Array,
    uint64: globalThis.BigUint64Array, float32: Float32Array, float64: Float64Array
  }[header.dtype];
  if (!ctor) throw new Error(`unsupported browser dtype ${header.dtype}`);
  const size = ctor.BYTES_PER_ELEMENT;
  if (payload.byteLength !== count * size) throw new Error("DNT1 payload size mismatch");

  let values;
  const nativeLittle = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;
  const tileLittle = header.byteorder === "little";
  if (size === 1 || nativeLittle === tileLittle) values = new ctor(payload.buffer.slice(payload.byteOffset, payload.byteOffset + payload.byteLength));
  else {
    const copy = payload.slice();
    for (let i = 0; i < copy.length; i += size) copy.subarray(i, i + size).reverse();
    values = new ctor(copy.buffer);
  }
  return { header, values };
}

export function renderScalarToCanvas(decoded, portrayal, canvas = document.createElement("canvas")) {
  const shape = decoded.header.shape;
  if (shape.length < 2) throw new Error("scalar portrayal requires a 2-D DNT1 tile");
  const h = shape[shape.length - 2], w = shape[shape.length - 1];
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext("2d");
  const image = ctx.createImageData(w, h);
  const scale = decoded.header.scale ?? 1, offset = decoded.header.offset ?? 0, nodata = decoded.header.nodata;
  const stops = [...portrayal.palette].sort((a, b) => a[0] - b[0]);
  for (let i = 0; i < w * h; i++) {
    const raw = Number(decoded.values[i]);
    if ((nodata !== null && nodata !== undefined && raw === Number(nodata)) || !Number.isFinite(raw)) continue;
    const value = raw * scale + offset;
    const [r, g, b, a] = interpolate(stops, value);
    const p = i * 4; image.data[p] = r; image.data[p + 1] = g; image.data[p + 2] = b; image.data[p + 3] = a;
  }
  ctx.putImageData(image, 0, 0);
  return canvas;
}

function interpolate(stops, value) {
  if (!stops.length) return [0, 0, 0, 0];
  if (value <= stops[0][0]) return parseColor(stops[0][1]);
  if (value >= stops.at(-1)[0]) return parseColor(stops.at(-1)[1]);
  for (let i = 1; i < stops.length; i++) {
    if (value <= stops[i][0]) {
      const [[v0, c0], [v1, c1]] = [stops[i - 1], stops[i]];
      const a = parseColor(c0), b = parseColor(c1), t = (value - v0) / (v1 - v0);
      return a.map((x, j) => Math.round(x + (b[j] - x) * t));
    }
  }
  return [0, 0, 0, 0];
}
function parseColor(s) {
  const h = s.replace("#", "");
  if (h.length === 6) return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16), 255];
  if (h.length === 8) return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16), parseInt(h.slice(6,8),16)];
  throw new Error(`unsupported color ${s}`);
}
