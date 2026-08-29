# Versioning, user library, and update notifications

Revision-8 DataTiles may declare stable `product_id`, human `version`, monotonic integer `sequence`, release timestamp, predecessor, release-notes URI, and update URI. The Store indexes these fields.

The user library records purchases and actual downloads. Download history retains the exact file SHA-256. When a higher sequence for the same product enters the catalog, the Store can notify users who previously purchased/downloaded an older sequence. A notification does not grant entitlement to the new release.

Never overwrite a published release's bytes. Publish a new object with a larger sequence, checksum, and new signature where used.
