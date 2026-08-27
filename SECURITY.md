# Security policy

The latest release line receives security fixes. Do not disclose suspected vulnerabilities in a public issue. Use GitHub’s private security-advisory interface for the repository and include the affected version, minimal reproducer, impact, and suggested mitigation when known.

DataTiles treats SQLite files, compressed BLOBs, numeric headers, metadata JSON, GeoJSON, and HTTP parameters as untrusted. Deployments should serve files read-only, disable SQLite extensions, impose request/concurrency limits, and keep the dependency-free decoder limits enabled. This research software is not a navigation system.
