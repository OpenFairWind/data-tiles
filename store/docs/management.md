# Store management

## Roles

Administrators manage configuration, users, groups, roles, audit evidence, and catalog operations. Members of the `managers` group carry the catalog-manager role and can create, read, replace/rename, and delete DataTiles files.

## Catalog CRUD

Create uploads a complete DataTiles/MBTiles-compatible SQLite file. Update validates a replacement before atomic publication. Delete removes the catalog item and file. Read includes catalog metadata, preview, agreement state, and download according to permissions.

Replacing a file changes its SHA-256 and invalidates prior licence/safety acceptance for protected interactions. Never edit a signed scientific release in place merely to change Store metadata.

## Indexing

The Store automatically extracts searchable metadata, semantic variables, rights, provenance, bounds, zooms, signatures, and commercial metadata. A rescan reconciles the catalog database with the filesystem.

## User administration

Use groups for authorization. Keep ordinary users out of `administrators` and `managers` unless their duties require those capabilities. Disable accounts promptly when access is withdrawn.


## Pricing and releases
Managers can set purchase-required, price, and currency on a catalog release through the API. Publish new versioned DataTiles files rather than mutating released bytes.


### Versioned release immutability

Versioned revision-8 releases are immutable in the Store. The replace operation returns HTTP 409 for a release that declares `product_id` and `sequence`; publish the successor as a new file/catalog item. This keeps historical purchase/download records and cryptographic citations meaningful. Unversioned staging assets may still use replacement CRUD.
