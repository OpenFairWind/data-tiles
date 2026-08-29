import pytest

from datatiles.semantic import (
    SemanticValidationError,
    load_cf_standard_name_table,
    validate_cf_standard_name,
)


def test_cf_table_validation(tmp_path):
    xml = tmp_path / "cf.xml"
    xml.write_text(
        '<?xml version="1.0"?><standard_name_table><entry id="sea_floor_depth_below_geoid">'
        '<canonical_units>m</canonical_units><description>Depth.</description>'
        '</entry></standard_name_table>'
    )
    table = load_cf_standard_name_table(xml)
    result = validate_cf_standard_name("sea_floor_depth_below_geoid", canonical_unit="m", table=table)
    assert result.canonical_units == "m"
    with pytest.raises(SemanticValidationError, match="unknown CF"):
        validate_cf_standard_name("depth", canonical_unit="m", table=table)
    with pytest.raises(SemanticValidationError, match="canonical unit mismatch"):
        validate_cf_standard_name("sea_floor_depth_below_geoid", canonical_unit="K", table=table)
