from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


class SemanticValidationError(ValueError):
    pass


@dataclass(frozen=True)
class CFStandardName:
    name: str
    canonical_units: str
    description: str | None = None


def load_cf_standard_name_table(path: str | Path) -> dict[str, CFStandardName]:
    """Load an official CF standard-name-table XML file using only stdlib.

    The caller supplies a local, pinned XML snapshot. DataTiles never downloads a
    vocabulary implicitly, preserving offline/reproducible behavior.
    """
    root = ET.parse(Path(path)).getroot()
    result: dict[str, CFStandardName] = {}
    for entry in root.findall("entry"):
        name = entry.attrib.get("id", "").strip()
        if not name:
            continue
        units_node = entry.find("canonical_units")
        description_node = entry.find("description")
        result[name] = CFStandardName(
            name=name,
            canonical_units=(units_node.text or "").strip() if units_node is not None else "",
            description=(description_node.text or "").strip() if description_node is not None and description_node.text else None,
        )
    if not result:
        raise SemanticValidationError("CF table contains no standard-name entries")
    return result


def validate_standard_name_syntax(name: str) -> None:
    if not isinstance(name, str) or not name or name.strip() != name:
        raise SemanticValidationError("standard name must be non-empty trimmed text")
    if any(ch.isspace() for ch in name):
        raise SemanticValidationError("standard name must not contain whitespace")


def validate_cf_standard_name(
    standard_name: str,
    *,
    canonical_unit: str | None,
    table: dict[str, CFStandardName],
) -> CFStandardName:
    """Validate a CF standard name against a caller-pinned table.

    If canonical_unit is supplied, it must exactly match the canonical unit in
    the CF table. This deliberately does not claim to perform UDUNITS physical
    equivalence. Dataset/tile units may still differ when physically equivalent.
    """
    validate_standard_name_syntax(standard_name)
    try:
        entry = table[standard_name]
    except KeyError as exc:
        raise SemanticValidationError(f"unknown CF standard name: {standard_name}") from exc
    if canonical_unit is not None and canonical_unit != entry.canonical_units:
        raise SemanticValidationError(
            f"canonical unit mismatch for {standard_name}: expected {entry.canonical_units!r}, got {canonical_unit!r}"
        )
    return entry
