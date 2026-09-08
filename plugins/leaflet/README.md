# Leaflet plugin

```js
import { serverLayer, clientLayer } from "../datatiles-leaflet.js";
```

`serverLayer()` uses a conventional Leaflet tile layer. `clientLayer()` uses a `GridLayer`, downloads DNT1, and renders into canvas tiles.

`clientLayer()` accepts either a fixed `dimensions` object or a function of the
Leaflet tile coordinates. The function form supports declared resolution
hierarchies whose `domain` coordinate changes by zoom; it MUST return the full
exact DataTiles coordinate selection and must not silently choose scientific
dimensions that have not been declared by the application.
