import pytest

from datatiles.fair import FairValidationError, validate_spdx_expression


@pytest.mark.parametrize(
    "expression",
    ["CC-BY-4.0", "ODbL-1.0", "LicenseRef-Proprietary", "CC-BY-4.0 AND ODbL-1.0", "(CC-BY-4.0 OR CC0-1.0)"],
)
def test_spdx_expression_accepts_machine_actionable_forms(expression):
    assert validate_spdx_expression(expression) == expression


@pytest.mark.parametrize("expression", ["", " CC-BY-4.0", "CC-BY-4.0 & MIT", "AND MIT", "MIT OR"])
def test_spdx_expression_rejects_ambiguous_forms(expression):
    with pytest.raises(FairValidationError):
        validate_spdx_expression(expression)
