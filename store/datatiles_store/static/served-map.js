(() => {
  "use strict";

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const lon2x = (lon, z) => ((lon + 180) / 360) * 256 * (1 << z);
  const lat2y = (lat, z) => {
    const r = clamp(lat, -85.05112878, 85.05112878) * Math.PI / 180;
    return (1 - Math.asinh(Math.tan(r)) / Math.PI) / 2 * 256 * (1 << z);
  };

  function withQuery(url, params) {
    const out = new URL(url, window.location.href);
    Object.entries(params || {}).forEach(([k, v]) => {
      if (v !== undefined && v !== null && String(v) !== "") out.searchParams.set(k, String(v));
    });
    return out.toString();
  }

  async function discover(serverBase, dataset) {
    if (!serverBase || !dataset) return null;
    const response = await fetch(`${serverBase.replace(/\/$/, "")}/maps`, {mode: "cors", cache: "no-cache"});
    if (!response.ok) throw new Error(`online-layer discovery failed (${response.status})`);
    const payload = await response.json();
    const candidates = (payload.layers || [])
      .filter(layer => layer.dataset === dataset && (!layer.catalog || layer.catalog.enabled !== false))
      .sort((a, b) => Number(b.catalog?.priority || 0) - Number(a.catalog?.priority || 0));
    if (!candidates.length) return null;
    const layer = candidates[0];
    const tj = await fetch(`${serverBase.replace(/\/$/, "")}/maps/${encodeURIComponent(layer.id)}/tilejson.json`, {mode: "cors", cache: "no-cache"});
    if (!tj.ok) throw new Error(`TileJSON discovery failed (${tj.status})`);
    return {layer, tilejson: await tj.json()};
  }

  class ServedMap {
    constructor(element, options) {
      this.el = element;
      this.serverBase = options.serverBase;
      this.dataset = options.dataset;
      this.bounds = options.bounds || null;
      this.interactive = options.interactive !== false;
      this.zoom = 0;
      this.center = [0, 0];
      this.tilejson = null;
      this.layer = null;
      this.drag = null;
      this.el.classList.add("served-map");
      this.tiles = document.createElement("div");
      this.tiles.className = "served-map-tiles";
      this.el.replaceChildren(this.tiles);
      if (this.interactive) this.installControls();
    }

    installControls() {
      const controls = document.createElement("div");
      controls.className = "served-map-controls";
      controls.innerHTML = '<button type="button" data-delta="1" aria-label="Zoom in">+</button><button type="button" data-delta="-1" aria-label="Zoom out">−</button>';
      controls.addEventListener("click", event => {
        const button = event.target.closest("button");
        if (!button) return;
        this.zoom = clamp(this.zoom + Number(button.dataset.delta), this.minZoom(), this.maxZoom());
        this.render();
      });
      this.el.appendChild(controls);
      this.el.addEventListener("pointerdown", event => {
        this.el.setPointerCapture(event.pointerId);
        this.drag = {x: event.clientX, y: event.clientY, center: [...this.center]};
      });
      this.el.addEventListener("pointermove", event => {
        if (!this.drag) return;
        const scale = 256 * (1 << this.zoom);
        const cx = lon2x(this.drag.center[0], this.zoom) - (event.clientX - this.drag.x);
        const cy = lat2y(this.drag.center[1], this.zoom) - (event.clientY - this.drag.y);
        const lon = cx / scale * 360 - 180;
        const n = Math.PI - 2 * Math.PI * cy / scale;
        const lat = 180 / Math.PI * Math.atan(Math.sinh(n));
        this.center = [lon, lat];
        this.render();
      });
      const stop = event => { if (this.drag) { this.drag = null; this.el.releasePointerCapture?.(event.pointerId); } };
      this.el.addEventListener("pointerup", stop);
      this.el.addEventListener("pointercancel", stop);
    }

    minZoom() { return Number(this.tilejson?.minzoom ?? this.layer?.minzoom ?? 0); }
    maxZoom() { return Number(this.tilejson?.maxzoom ?? this.layer?.maxzoom ?? 18); }

    fit() {
      const bounds = this.tilejson?.bounds || this.bounds;
      if (!bounds || bounds.length !== 4) {
        this.center = [0, 0];
        this.zoom = this.minZoom();
        return;
      }
      const [w, s, e, n] = bounds.map(Number);
      this.center = [(w + e) / 2, (s + n) / 2];
      const width = Math.max(64, this.el.clientWidth || 320), height = Math.max(64, this.el.clientHeight || 160);
      let best = this.minZoom();
      for (let z = this.minZoom(); z <= this.maxZoom(); z += 1) {
        const px = Math.abs(lon2x(e, z) - lon2x(w, z));
        const py = Math.abs(lat2y(s, z) - lat2y(n, z));
        if (px <= width * 0.86 && py <= height * 0.80) best = z; else break;
      }
      this.zoom = best;
    }

    tileUrl(z, x, y) {
      const template = this.tilejson.tiles?.[0];
      if (!template) return null;
      let url = template.replace("{z}", z).replace("{x}", x).replace("{y}", y);
      return withQuery(url, this.layer?.catalog?.query || {});
    }

    render() {
      if (!this.tilejson) return;
      const width = this.el.clientWidth, height = this.el.clientHeight;
      const centerX = lon2x(this.center[0], this.zoom), centerY = lat2y(this.center[1], this.zoom);
      const left = centerX - width / 2, top = centerY - height / 2;
      const x0 = Math.floor(left / 256), y0 = Math.floor(top / 256);
      const x1 = Math.floor((left + width) / 256), y1 = Math.floor((top + height) / 256);
      const limit = 1 << this.zoom;
      this.tiles.replaceChildren();
      for (let ty = y0; ty <= y1; ty += 1) {
        if (ty < 0 || ty >= limit) continue;
        for (let tx = x0; tx <= x1; tx += 1) {
          const wrapped = ((tx % limit) + limit) % limit;
          const src = this.tileUrl(this.zoom, wrapped, ty);
          if (!src) continue;
          const img = document.createElement("img");
          img.alt = "";
          img.decoding = "async";
          img.loading = "eager";
          img.draggable = false;
          img.src = src;
          img.style.left = `${tx * 256 - left}px`;
          img.style.top = `${ty * 256 - top}px`;
          this.tiles.appendChild(img);
        }
      }
    }

    async start() {
      const found = await discover(this.serverBase, this.dataset);
      if (!found) return false;
      this.layer = found.layer;
      this.tilejson = found.tilejson;
      this.el.dataset.layer = this.layer.id;
      this.fit();
      this.render();
      new ResizeObserver(() => this.render()).observe(this.el);
      return true;
    }
  }

  async function mountAll(selector = "[data-served-map]") {
    for (const el of document.querySelectorAll(selector)) {
      try {
        const bounds = el.dataset.bounds ? JSON.parse(el.dataset.bounds) : null;
        const map = new ServedMap(el, {
          serverBase: el.dataset.server,
          dataset: el.dataset.dataset,
          bounds,
          interactive: el.dataset.interactive !== "0"
        });
        const ok = await map.start();
        el.classList.toggle("served-map-unavailable", !ok);
        if (!ok && el.dataset.fallback) el.textContent = el.dataset.fallback;
      } catch (error) {
        el.classList.add("served-map-unavailable");
        if (el.dataset.fallback) el.textContent = el.dataset.fallback;
        console.warn("DataTiles served-map preview unavailable:", error);
      }
    }
  }

  window.DataTilesServedMap = {ServedMap, discover, mountAll};
})();
