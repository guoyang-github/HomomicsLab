"""Tests for natural-language HITL parsing."""

import pytest

from homomics_lab.hitl.nlu import HITLNLUParser


@pytest.fixture
def options():
    return [
        {"id": "proceed", "label": "Proceed"},
        {"id": "cancel", "label": "Cancel"},
        {"id": "modify", "label": "Modify parameters"},
    ]


def test_parse_option_label(options):
    result = HITLNLUParser.parse("I want to proceed", options)
    assert result["choice"] == "proceed"
    assert result["confidence"] == "high"


def test_parse_affirmative(options):
    result = HITLNLUParser.parse("yes please", options)
    assert result["choice"] == "proceed"
    assert result["confidence"] == "medium"


def test_parse_negative(options):
    result = HITLNLUParser.parse("skip it", options)
    assert result["choice"] == "cancel"
    assert result["confidence"] == "medium"


def test_parse_modify(options):
    result = HITLNLUParser.parse("modify the parameters", options)
    assert result["choice"] == "modify"


def test_parse_parameters(options):
    result = HITLNLUParser.parse("min_genes=200 max_genes=5000", options)
    assert result["parameters"] == {"min_genes": 200, "max_genes": 5000}
    assert result["choice"] in {"modify", "proceed"}
