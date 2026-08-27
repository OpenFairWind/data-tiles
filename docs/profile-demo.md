# Numeric depth-profile demo

The depth-profile demonstration proves that DataTiles stores queryable multidimensional data rather than only rendered pictures.

Given two WGS 84 points, the implementation:

1. finds the coordinate set whose `variable` is `depth_below_lat_m`;
2. finds the coordinate set whose `variable` is `seafloor_class`;
3. chooses the highest zoom available to both variables unless the caller selects another zoom;
4. generates the requested number of sampling positions along the great-circle arc;
5. converts each point to `WebMercatorQuad` tile and pixel coordinates;
6. reads the relevant BLOB from `datatiles_tiles`;
7. decodes its DNT1 dtype, shape, compression, nodata, scale, and offset;
8. extracts depth and class values;
9. renders the profile, coloring each interval by its decoded seafloor class.

No PNG, JPEG, WebP, WMS portrayal, or previously rendered profile participates in this process.

## API

```text
GET /collections/{collection}/profile
    ?start={longitude},{latitude}
    &end={longitude},{latitude}
    &samples=256
    &zoom=11
    &f=json|csv|svg
```

JSON observations include:

- sample index;
- cumulative geodesic distance;
- longitude and latitude;
- depth in metres;
- class code and label;
- depth and class tile coordinates;
- pixel coordinates within each decoded tile.

The complete ordered observation array receives a canonical SHA-256 so results from independent calls or implementations can be compared.

Sampling is nearest-cell at the selected zoom because both source grids have finite resolution and class interpolation would be scientifically inappropriate. The output is for research demonstration only and not for navigation.
