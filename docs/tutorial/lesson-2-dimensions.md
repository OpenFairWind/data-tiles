# Lesson 2 — Multidimensional coordinate algebra

## Objectives

You will model scientific axes with typed points and intervals, understand canonical coordinate-set identity, perform exact retrieval independent of map ordering, and recognize operations that require an explicit interpolation policy.

## Theory: coordinates are semantic identity

A multidimensional tile is not identified by an ordered tuple of axis positions. Different communities order axes differently, and an implementation may assign different local integer IDs. DataTiles therefore defines a coordinate set as an unordered mapping from unique dimension names to typed values. Every required dimension must appear exactly once.

Supported types are text, integer, finite float, timezone-qualified datetime, and Boolean. Types matter: text `"10"`, integer `10`, and float `10.0` may share a human rendering but do not share a semantic domain. Datetimes normalize to UTC. Boolean accepts only Boolean values or `0/1`; treating every nonzero integer as true would destroy canonical identity.

A coordinate may be a point or an interval. Interval boundaries independently carry inclusivity, producing `[a,b]`, `[a,b)`, `(a,b]`, or `(a,b)`. An equal-bound interval is valid only when closed at both ends. Replacing an interval with a midpoint is forbidden because an aggregation window and an instantaneous observation have different meaning.

Canonical identity is computed as SHA-256 over compact UTF-8 JSON containing `[dimension-name,canonical-value]` pairs sorted by dimension name. The hash is independent of insertion order and local database IDs:

```text
SHA256([["release","tutorial-v1"],
        ["valid_time","[2026-08-27T00:00:00.000000Z,2026-08-27T06:00:00.000000Z]"],
        ["variable","depth_below_lat_m"]])
```

This is an identity rule, not an interpolation rule. Exact lookup requires a complete coordinate set. “Nearest time,” “intersects this interval,” and “interpolate at 7.5 m” are higher-level operations that must declare tolerance, calendar, boundary, and missing-value semantics.

## Laboratory

List dimensions and values:

```bash
python - <<'PY'
from datatiles import DataTiles
with DataTiles('tutorial.datatiles',read_only=True) as s:
    for row in s.db.execute('SELECT name,value_type,axis,extent_kind,required FROM datatiles_dimensions ORDER BY ordering'):
        print(tuple(row))
    for profile in s.content_profiles():
        print(profile['coordinate_set_id'],profile['coordinates'])
PY
```

Prove order independence through the public API:

```bash
python - <<'PY'
from datatiles import DataTiles
interval=('2026-08-27T00:00:00Z','2026-08-27T06:00:00Z',True,True)
a={'variable':'depth_below_lat_m','valid_time':interval,'release':'tutorial-v1'}
b={'release':'tutorial-v1','valid_time':interval,'variable':'depth_below_lat_m'}
with DataTiles('tutorial.datatiles',read_only=True) as s:
    first=s.get(0,0,0,a); second=s.get(0,0,0,b)
    assert first is not None and first==second
    print('order-independent bytes:',len(first))
PY
```

Observe exact failure rather than silent approximation:

```bash
python - <<'PY'
from datatiles import DataTiles
with DataTiles('tutorial.datatiles',read_only=True) as s:
    incomplete={'variable':'depth_below_lat_m'}
    try: s.get(0,0,0,incomplete)
    except ValueError as e: print('correctly rejected:',e)
PY
```

Use indexed discovery when only part of the coordinate set is known:

```bash
python - <<'PY'
from datatiles import DataTiles
with DataTiles('tutorial.datatiles',read_only=True) as s:
    for set_id in s.find_coordinate_sets({'release':'tutorial-v1'}):
        print(set_id,s.coordinate_set_values(set_id))
PY
```

## Verification and reflection

1. Explain why dimension order must not affect identity but dimension names must.
2. Contrast an interval coordinate with a query interval that intersects stored coordinates.
3. Identify the metadata needed before vertical interpolation is scientifically defensible.
4. Explain why partial discovery may return several coordinate sets while exact retrieval returns at most one BLOB.

As an exercise, attempt to insert an open interval with equal bounds and a Boolean value of `2` into a new file. Both must be rejected.
