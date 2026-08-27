# Contributing to DataTiles

Contributions are welcome through focused issues and pull requests. Before changing storage or wire semantics, read `AGENTS.md`, `docs/specification.md`, and `docs/testing-and-release.md`.

Create a branch from `main`, add regression tests, update normative and explanatory documentation together, and run:

```bash
python -m pip install -e '.[demo,test]'
python -m compileall -q src tests
python -m pytest --cov=datatiles --cov-branch
```

Schema, encoding, canonicalization, CRS, provenance, or FAIR-profile changes must describe backward compatibility and migration. Demo-pipeline changes must pass the deterministic double-build test. Pull requests must not weaken validation or omit scientific limitations. By contributing, you agree that your contribution is licensed under Apache-2.0.
