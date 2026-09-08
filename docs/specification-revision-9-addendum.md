# DataTiles 1.0-draft — optional Online Delivery profile addendum

This addendum is normative for implementations claiming the optional **Online Delivery** profile. It is a specification-profile addition, not an on-disk schema revision: conforming containers remain at schema revision 8, the canonical DataTiles tile address is unchanged, and no server-specific SQLite objects are required.

## Conformance classes

Add:

| Class | Required behavior |
|---|---|
| Online scientific delivery | Publish a canonical DataTiles tile over HTTP without altering its declared scientific content semantics. |
| Online server portrayal | Resolve the same canonical tile selection and return a deterministic display portrayal. |
| Online discovery | Advertise both scientific and portrayal representations, dimensions, media types, and portrayal metadata. |

An implementation MUST NOT claim a class it does not implement.

## Representation rule

For canonical address `A=(z,x,y,C)`, where `C` is the canonical typed coordinate map, a server MAY expose multiple representations `R(A,p)` where `p` identifies a representation/portrayal. A representation MUST NOT change the identity or physical meaning of `A`.

A scientific representation MUST preserve the declared DataTiles payload/content profile. A portrayal representation MUST be explicitly identified as derived/display content and MUST NOT be presented as a scientific measurement payload.

## Rendering equivalence

When the same published portrayal recipe is supported on both server and client, both implementations MUST use the same units, scale/offset interpretation, nodata semantics, class breaks/palette stops, interpolation rule, and declared transformations. Pixel-for-pixel equality is NOT required unless the portrayal profile explicitly requires it.

## HTTP resources

A conforming reference path set is:

`/api/datasets/{dataset}/tiles/{z}/{x}/{y}` for scientific delivery and `/maps/{layer}/{z}/{x}/{y}.{format}` for portrayal delivery. Equivalent paths are allowed when discoverable.

Dimension query parameters MUST be canonicalized using the same rules as container exact reads. Fixed published-layer dimensions and request dimensions MUST resolve to one explicit canonical coordinate map before tile lookup.

## Discovery

TileJSON or an equivalent discovery document MUST advertise at least one tile URL and SHOULD advertise both rendering modes using namespaced extension members. Discovery MUST state supported media types and any fixed/default dimensions. A portrayal recipe SHOULD be retrievable as canonical JSON.

## Caching and provenance

Server portrayals MUST be reproducible from: source dataset/release identity, canonical tile address, portrayal recipe, and renderer profile/version. Cache identity MUST include every input capable of changing output pixels. A service SHOULD emit ETag and Cache-Control headers. A server portrayal remains derived data and SHOULD preserve a provenance link to its DataTiles source.

### Direct scientific derivation from NetCDF archives

An Online Delivery implementation MAY expose a numeric DNT1 tile derived on demand from a NetCDF source without first persisting a DataTiles container. Such a response is a scientific derivation, not a stored tile and not a portrayal. The service MUST identify the source frame, selected variable, source CRS, output tile-matrix CRS, sampling or resampling algorithm, nodata rule, unit, and every non-spatial selection. It MUST NOT silently select a non-singleton dimension, and it MUST NOT expose an undeclared variable. Implementations SHOULD restrict source resolution to a configured archive root and deterministic filename grammar, and SHOULD provide an integrity or release identifier suitable for cache and provenance identity.

## Security and deployment

Online services MUST treat dimension values, layer IDs and dataset IDs as untrusted input; MUST prevent path traversal; MUST enforce DNT1 resource limits before allocation/decompression; and SHOULD constrain CORS to intended origins in production. Containers SHOULD mount scientific datasets read-only.

## Online server concurrency and performance conformance

An implementation claiming the Online Server Portrayal conformance class SHALL remain semantically invariant under concurrent requests: concurrency MUST NOT alter tile values, dimension selection, portrayal semantics, cache identity, or response representation.

A server implementation SHOULD support concurrent execution suitable for interactive slippy-map workloads. It SHOULD expose bounded concurrency rather than unbounded task creation, and it SHOULD support deployment with multiple execution workers on multi-core systems. Threading, process workers, asynchronous I/O, native-code parallelism, GPU execution, or combinations thereof are implementation choices and are not encoded into the DataTiles container format.

Where a shared portrayal cache is used, cache publication MUST be atomic. Two workers rendering the same cache key concurrently MUST either coalesce the work or produce equivalent content without exposing partial cache objects. Cache keys MUST include all inputs that affect portrayal output, including the source dataset identity or immutable release identity, canonical coordinate set, z/x/y coordinate, portrayal definition or digest, output media type, and any encoder parameters that materially affect the representation.

Implementations SHOULD emit validators such as `ETag` and appropriate `Cache-Control` headers. Immutable render products SHOULD be suitable for reverse-proxy and CDN caching. Implementations serving mutable aliases such as `latest` MUST NOT apply immutable caching semantics to an alias whose target can change.

## Catalogue-preview discovery

An implementation MAY advertise an Online Delivery portrayal as suitable for catalogue visual browsing. When it does so, discovery metadata SHOULD contain a stable dataset identifier, geographic bounds, zoom limits, and an optional catalogue-preview descriptor.

The namespaced TileJSON member `datatiles:catalog` MAY contain:

* `enabled` — whether the portrayal is intended to appear in catalogue/map previews;
* `priority` — relative preference when several portrayals represent the same dataset;
* `query` — deterministic default dimension values used only for the catalogue portrayal.

A catalogue preview MUST remain explicitly a portrayal. It MUST NOT be presented as the underlying numeric scientific values. Catalogue systems SHOULD use server-rendered portrayals for low-latency visual browsing and MAY additionally expose the scientific representation for client-side inspection.

Publishing a catalogue preview does not weaken rights or access controls. An operator MUST NOT mark a portrayal as publicly discoverable when the associated data rights prohibit such display. Protected deployments MAY place the portrayal endpoint behind the same authorization gateway as the catalogue.
