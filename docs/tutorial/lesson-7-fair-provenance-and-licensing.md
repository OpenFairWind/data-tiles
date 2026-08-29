# Lesson 7 — FAIR evidence, provenance, and licensing

## Objectives

You will turn a technically valid DataTiles file into a defensible scholarly research object by separating persistent identity, scientific provenance, legal rights, citation metadata, and repository-level FAIR evidence.

## 1. FAIR is not an adjective

The FAIR principles are individually testable obligations. A file can be richly structured but still fail F1/F4/A2 because no PID, catalogue deposit, or metadata-retention policy exists. Conversely, restricted data can be FAIR when metadata is persistent, access conditions are explicit, and authorized reuse is well described.

Run both local and publication-level checks:

```python
from datatiles import DataTiles
with DataTiles("study.datatiles") as s:
    print(s.fair_report())
    print(s.fair_report(strict_publication=True))
```

Explain every failed principle instead of reporting a percentage.

## 2. Record identity and scholarly relationships

A released revision receives a PID. Do not reuse one DOI for materially different immutable versions unless the repository's versioning model explicitly supports it.

```python
s.add_identifier("DOI", "10.xxxx/example.v1", uri="https://doi.org/10.xxxx/example.v1", primary=True)
s.add_related_identifier("DOI", "10.xxxx/source", "IsDerivedFrom", uri="https://doi.org/10.xxxx/source", resource_type="Dataset")
```

## 3. Separate rights layers

```python
s.add_rights("dataset", "CC-BY-4.0",
             license_uri="https://creativecommons.org/licenses/by/4.0/",
             rights_holder="Example University",
             attribution_text="Cite the dataset DOI and named creators")
s.add_rights("metadata", "CC0-1.0",
             license_uri="https://creativecommons.org/publicdomain/zero/1.0/")
```

Every source entity receives its own `source` rights record. Never infer source rights from the output licence.

## 4. Build a PROV graph

Create source and generated entities, the transformation activity, software and responsible agents. Connect source -> activity -> generated object with `used`, `wasGeneratedBy`, `wasDerivedFrom`, and activity-agent associations. Record exact parameters and software versions.

Export the graph:

```python
import json
print(json.dumps(s.prov_json(), indent=2))
```

Audit the graph: can an independent researcher identify every input that materially influenced a tile and the transformation that produced it?

## 5. Prepare DataCite metadata

```python
print(json.dumps(s.datacite_metadata(), indent=2))
```

This is a DataCite-4.7-shaped candidate record. It is **not** evidence that a DOI exists. Deposit it through the chosen repository, then record catalogue/landing-page/retention evidence in the container or release manifest.

## 6. Use the converters lawfully

```bash
python utils/netcdf2datatiles.py source.nc study.datatiles \
  --variable depth --zoom 7 \
  --source-license CC-BY-4.0 \
  --source-license-uri https://creativecommons.org/licenses/by/4.0/ \
  --source-attribution "Source provider citation/attribution" \
  --dataset-license CC-BY-4.0 \
  --dataset-license-uri https://creativecommons.org/licenses/by/4.0/
```

The utility records the exact source identifier, SHA-256, rights record and conversion activity. It does not decide licence compatibility for you.

## 7. Publication exercise

Prepare an evidence package containing the DataTiles file, checksums, source lock, rights manifest, runtime lock, configuration, PROV export, DataCite export, FAIR report and scientific QA. For a source that forbids redistribution, omit its raw bytes and document lawful reacquisition while retaining its checksum and provenance identity.

## Reflection

1. Why does a SHA-256 digest not replace a citation or licence?
2. Why must source and output licences be separate records?
3. Which FAIR principles cannot be proven by the SQLite container alone?
4. What is the difference between `wasDerivedFrom` and `used` in the provenance graph?
5. Why is a DataCite JSON export not proof of DOI registration?
