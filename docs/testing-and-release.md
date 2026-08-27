# Testing, continuous integration, and delivery

DataTiles uses independent quality gates because format correctness, scientific reproducibility, browser behavior, and package integrity are distinct claims. A green unit-test result alone is insufficient evidence for a release.

## Local test protocol

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[demo,test]'
python -m compileall -q src tests
python -m pytest --cov=datatiles --cov-branch --cov-report=term-missing
```

The suite covers storage and MBTiles views, physical-table MBTiles fallback and rejection of non-representable payloads, typed and interval coordinates, DNT1 cross-product and hostile-input cases, CLI round trips, HTTP discovery and errors, scientific-analysis endpoints, specification/documentation contracts, playground contracts, FAIR validation, and deterministic double builds. Coverage is diagnostic evidence, not a substitute for the scientific acceptance criteria in `reproducibility.md`.

## CI workflow

`.github/workflows/ci.yml` executes on pull requests and pushes to `main`. It applies four required gates:

1. The complete suite runs on Python 3.10, 3.11, 3.12, and 3.13 with branch coverage.
2. Node.js parses the playground program and verifies its live-rendering contracts.
3. PEP 517 builds source and wheel distributions, Twine validates metadata, and a fresh environment installs and invokes the wheel.
4. The controlled scientific fixture is rebuilt twice and checked for byte identity.

The terminal `ci-success` job depends on every gate and is the recommended branch-protection status check. Configure `main` to require pull requests and this check, dismiss stale approvals, require conversation resolution, prohibit force pushes, and restrict deletion.

## CD and release protocol

`.github/workflows/release.yml` builds from a semantic version tag `vX.Y.Z`. It rejects a tag differing from `datatiles.__version__` or lacking the corresponding `CHANGELOG.md` heading. It reruns tests, builds distributions, checks metadata, records SHA-256 checksums, and retains the products as an artifact.

For a tag release, GitHub produces build-provenance attestations, creates a GitHub Release, and publishes through PyPI Trusted Publishing. No API token is stored. A manual run builds and validates artifacts; PyPI delivery occurs only when the operator enables its input.

Repository administrators must create a protected GitHub environment named `pypi`, preferably with an authorized reviewer and protected-tag restriction, and register this repository plus `release.yml` as a PyPI Trusted Publisher. Protect tags matching `v*`. If cryptographically signed tags are required, enforce them using an organization ruleset or approved verifier with a pinned trust root; the workflow does not infer trust merely from a tag name.

## Release checklist

- Update package version, changelog, specification status, citation metadata, and runtime lock together.
- Run the full local protocol and controlled double build.
- Confirm licences, identifiers, checksums, provenance, CRS, vertical datum, and non-navigation warning.
- Merge through a protected pull request and wait for `CI success`.
- Push the protected `vX.Y.Z` tag from the reviewed commit.
- Approve `pypi` only after inspecting artifacts and checksums.
- Verify the GitHub Release, attestation, and clean PyPI installation.
