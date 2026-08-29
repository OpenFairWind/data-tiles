"""FAIR, provenance, rights, and citation helpers for DataTiles.

The module is deliberately dependency-free. It validates the conservative lexical
subset of SPDX expressions needed at the container boundary; authoritative SPDX
list membership remains a publication/CI check against a pinned SPDX License List.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

SPDX_TOKEN = re.compile(r"(?:DocumentRef-[A-Za-z0-9.-]+:)?LicenseRef-[A-Za-z0-9.-]+|[A-Za-z0-9.-]+\+?")
SPDX_OPERATORS = {"AND", "OR", "WITH"}
PID_SCHEMES = {"DOI", "Handle", "ARK", "URN", "SWHID", "RAiD", "URL"}
ACCESS_RIGHTS = {"open", "embargoed", "restricted", "closed"}
RIGHTS_SCOPES = {"dataset", "metadata", "source", "portrayal", "software", "other"}

class FairValidationError(ValueError):
    pass


def validate_spdx_expression(expression: str) -> str:
    """Reject malformed/ambiguous SPDX-like expressions without network access."""
    if not isinstance(expression, str) or not expression.strip() or expression != expression.strip():
        raise FairValidationError("SPDX expression must be non-empty and trimmed")
    tokens = re.findall(r"\(|\)|[A-Za-z0-9.+:-]+", expression)
    if "".join(tokens).replace("(", "").replace(")", "") == "":
        raise FairValidationError("empty SPDX expression")
    # Ensure no unparsed punctuation/whitespace ambiguity.
    rebuilt = " ".join(tokens).replace("( ", "(").replace(" )", ")")
    normalized = re.sub(r"\s+", " ", expression).replace("( ", "(").replace(" )", ")")
    if rebuilt != normalized:
        raise FairValidationError("invalid SPDX expression syntax")
    depth = 0
    expect_operand = True
    for token in tokens:
        if token == "(":
            if not expect_operand: raise FairValidationError("missing SPDX operator")
            depth += 1
        elif token == ")":
            if expect_operand or depth == 0: raise FairValidationError("unbalanced SPDX parentheses")
            depth -= 1; expect_operand = False
        elif token in SPDX_OPERATORS:
            if expect_operand: raise FairValidationError("misplaced SPDX operator")
            expect_operand = True
        else:
            if not SPDX_TOKEN.fullmatch(token): raise FairValidationError(f"invalid SPDX token: {token}")
            if not expect_operand: raise FairValidationError("missing SPDX operator")
            expect_operand = False
    if depth or expect_operand: raise FairValidationError("incomplete SPDX expression")
    return expression


def datacite_metadata(store: Any) -> dict[str, Any]:
    """Produce a DataCite-4.7-shaped publication record from explicit container facts.

    This is an export helper, not a claim that a DOI has been registered.
    """
    meta = store.metadata()
    primary = store.primary_identifier()
    creators = store.fair_agents(role="creator")
    rights = store.rights()
    related = store.related_identifiers()
    result: dict[str, Any] = {
        "schemaVersion": "http://datacite.org/schema/kernel-4",
        "titles": [{"title": meta.get("name", store.path.stem)}],
        "publisher": meta.get("datatiles:publisher", "UNSPECIFIED"),
        "publicationYear": meta.get("datatiles:publication_year", "UNSPECIFIED"),
        "types": {"resourceTypeGeneral": "Dataset", "resourceType": "DataTiles multidimensional tiled dataset"},
        "creators": creators,
        "rightsList": [{"rights": r["license_expression"], "rightsUri": r.get("license_uri")} for r in rights if r["scope"] in ("dataset","metadata")],
        "relatedIdentifiers": related,
    }
    if primary:
        result["identifier"] = {"identifier": primary["identifier"], "identifierType": primary["scheme"]}
    return result


def prov_json(store: Any) -> dict[str, Any]:
    """Export the internal graph with explicit W3C PROV term mappings."""
    entities = {r["entity_id"]: {"prov:type": r["entity_type"], "prov:label": r["label"], **({"prov:location": r["uri"]} if r["uri"] else {})}
                for r in store.db.execute("SELECT * FROM datatiles_provenance_entities")}
    activities = {r["activity_id"]: {"prov:type": r["activity_type"], "prov:label": r["label"], "prov:startedAtTime": r["started_at"], "prov:endedAtTime": r["ended_at"]}
                  for r in store.db.execute("SELECT * FROM datatiles_provenance_activities")}
    agents = {r["agent_id"]: {"prov:type": r["agent_type"], "prov:label": r["label"], **({"prov:location": r["uri"]} if r["uri"] else {})}
              for r in store.db.execute("SELECT * FROM datatiles_provenance_agents")}
    relations = [dict(r) for r in store.db.execute("SELECT * FROM datatiles_provenance_relations ORDER BY subject_id,predicate,object_id")]
    return {"prefix": {"prov": "http://www.w3.org/ns/prov#"}, "entity": entities, "activity": activities, "agent": agents, "relations": relations}
