"""Offline testy parsowania modeli na kanonicznych JSON-ach z HUDOC."""

from __future__ import annotations

from datetime import date

from echr_mcp.models import doc_kind, judgment_from_api


def _columns(fixture_json, name: str) -> list[dict]:
    return [r["columns"] for r in fixture_json(name)["results"]]


def test_summary_maps_hudoc_columns(fixture_json):
    columns = next(c for c in _columns(fixture_json, "search_appno_474_21.json") if c["itemid"] == "001-250747")
    doc = judgment_from_api(columns)

    assert doc.itemid == "001-250747"
    assert doc.docname == "CASE OF SHEVCHUK v. UKRAINE"
    assert doc.appno == ["474/21"]
    assert doc.article == ["35", "35-3-a", "6", "6-1", "8", "8-1", "8-2", "41"]
    assert doc.doctype == "HEJUD"
    assert doc.kpdate == date(2026, 6, 25)
    assert doc.language == "ENG"
    assert doc.rank is not None
    assert doc.conclusion and "Violation of Article 8" in doc.conclusion
    assert doc.source_url == "https://hudoc.echr.coe.int/eng?i=001-250747"
    assert doc.retrieved_at


def test_collections_are_split_and_keep_the_language_code(fixture_json):
    columns = next(c for c in _columns(fixture_json, "search_appno_474_21.json") if c["itemid"] == "001-250747")
    assert judgment_from_api(columns).collections == ["CASELAW", "JUDGMENTS", "CHAMBER", "ENG"]


def test_originating_body_code_is_labelled(fixture_json):
    columns = _columns(fixture_json, "search_appno_474_21.json")[0]
    doc = judgment_from_api(columns)
    assert doc.originatingbody == "23"
    assert doc.originatingbody_label == "Court (Fifth Section)"


def test_placeholder_flag_is_parsed_from_string(fixture_json):
    columns = _columns(fixture_json, "search_appno_474_21.json")
    primary = next(c for c in columns if c["itemid"] == "001-250747")
    placeholder = next(c for c in columns if c["itemid"] == "001-251115")

    assert judgment_from_api(primary).is_placeholder is False
    assert judgment_from_api(placeholder).is_placeholder is True
    assert judgment_from_api(placeholder).language == "FRE"


def test_summary_tolerates_missing_and_null_fields():
    """Rekordy z HUDOC czesto maja `appno: null` (komunikaty prasowe, uchwaly)."""
    doc = judgment_from_api({"itemid": "003-8665339-12356636", "docname": "Annonce d'arrets", "appno": None})

    assert doc.appno == []
    assert doc.article == []
    assert doc.collections == []
    assert doc.kpdate is None
    assert doc.rank is None
    assert doc.is_placeholder is False
    assert doc.originatingbody_label is None
    assert doc.language is None


def test_summary_ignores_unknown_api_fields():
    doc = judgment_from_api({"itemid": "001-1", "cosNowegoWAPI": {"a": 1}})
    assert "cosNowegoWAPI" not in doc.model_dump()


def test_empty_itemid_gets_no_source_url():
    assert judgment_from_api({"itemid": None}).source_url == ""


def test_garbage_kpdate_and_rank_do_not_explode():
    doc = judgment_from_api({"itemid": "001-1", "kpdate": "brak-daty", "rank": "nie-liczba"})
    assert doc.kpdate is None
    assert doc.rank is None


def test_doc_kind_ignores_the_language_prefix():
    """`HEJUD`/`HFJUD` to ten sam rodzaj dokumentu w roznych jezykach."""
    assert doc_kind("HEJUD") == doc_kind("HFJUD") == "JUD"
    assert doc_kind("HECOM") == "COM"
    assert doc_kind("HEDEC") != doc_kind("HEJUD")
    assert doc_kind(None) is None
    assert doc_kind("HE") == "HE"


def test_summary_serialises_to_json(fixture_json):
    dumped = judgment_from_api(_columns(fixture_json, "metadata_itemid_001-250747.json")[0]).model_dump(
        mode="json"
    )
    assert dumped["itemid"] == "001-250747"
    assert dumped["kpdate"] == "2026-06-25"
    assert isinstance(dumped["appno"], list)
    assert isinstance(dumped["is_placeholder"], bool)
