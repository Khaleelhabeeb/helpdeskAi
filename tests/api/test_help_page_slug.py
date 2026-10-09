import pytest
from fastapi import HTTPException

from api.agents.widget_deployment import _clean_help_slug, _clean_suggestions


@pytest.mark.parametrize("raw,expected", [
    ("Acme Support", "acme-support"),
    ("  acme--help  ", "acme-help"),
    ("ACME_2026", "acme-2026"),
])
def test_clean_help_slug_normalizes(raw, expected):
    assert _clean_help_slug(raw) == expected


@pytest.mark.parametrize("raw", ["ab", "", "---", "admin", "x" * 60])
def test_clean_help_slug_rejects(raw):
    with pytest.raises(HTTPException):
        _clean_help_slug(raw)


def test_clean_suggestions_trims_and_caps():
    assert _clean_suggestions([" a ", "", "b", "c", "d", "e"]) == ["a", "b", "c", "d"]
