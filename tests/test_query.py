"""Offline testy budowania zapytan HUDOC.

Caly kontrakt zapytania zyje w `build_query` - to jedyne miejsce, gdzie moze sie
cicho zepsuc (i juz sie psulo: `f:"fraza"` zwraca zero trafien, `("fraza")` dziala).
"""

from __future__ import annotations

from datetime import date

from echr_mcp.models import (
    BASE_QUERY,
    build_query,
    free_text_clause,
    itemid_clause,
    sibling_clause,
)


def test_no_filters_is_just_the_base_condition():
    """Konektor NIGDY nie wypuszcza zapytania bez `(contentsitename=ECHR)`."""
    assert build_query() == BASE_QUERY


def test_appno_is_quoted_and_anded():
    assert build_query(appno="474/21") == '(contentsitename=ECHR) AND (appno="474/21")'


def test_article_uses_the_deep_code():
    assert build_query(article="6-1") == '(contentsitename=ECHR) AND (article="6-1")'


def test_kpdate_bounds_use_comparison_operators():
    assert build_query(kpdate_from=date(2024, 1, 1)) == '(contentsitename=ECHR) AND (kpdate>="2024-01-01")'
    assert build_query(kpdate_to=date(2024, 12, 31)) == '(contentsitename=ECHR) AND (kpdate<="2024-12-31")'


def test_doctype_is_quoted():
    assert build_query(doctype="HEJUD") == '(contentsitename=ECHR) AND (doctype="HEJUD")'


def test_free_text_is_a_bracketed_phrase_not_a_field_prefix():
    """`f:"fraza"` zwraca 0 trafien w HUDOC - dziala tylko `("fraza")`."""
    assert free_text_clause("excessive length of proceedings") == '("excessive length of proceedings")'
    assert '("excessive length of proceedings")' in build_query(query="excessive length of proceedings")
    assert 'f:"' not in build_query(query="cokolwiek")


def test_free_text_strips_quotes_and_backslashes_but_keeps_the_phrase():
    """Proba wyjscia z frazy nie moze rozsadzic gramatyki zapytania."""
    injected = build_query(query='x") OR (isplaceholder="True')
    assert injected.count("(") == injected.count(")")
    assert injected == '(contentsitename=ECHR) AND ("x ) OR (isplaceholder= True")'


def test_free_text_collapses_whitespace():
    assert free_text_clause("  a\t\tb \n c  ") == '("a b c")'


def test_all_filters_compose_in_a_stable_order():
    query = build_query(
        query="environment",
        appno="474/21",
        article="8-1",
        kpdate_from=date(2020, 1, 1),
        kpdate_to=date(2021, 1, 1),
        doctype="HEJUD",
    )
    assert query == (
        '(contentsitename=ECHR) AND ("environment") AND (appno="474/21") AND (article="8-1") '
        'AND (kpdate>="2020-01-01") AND (kpdate<="2021-01-01") AND (doctype="HEJUD")'
    )


def test_itemid_clause_is_exact():
    assert itemid_clause("001-250747") == '(itemid="001-250747")'


def test_sibling_clause_does_not_filter_by_doctype():
    """`doctype` jest jezykowo zalezny (HEJUD vs HFJUD) - filtr po nim zgubilby wersje."""
    clause = sibling_clause("474/21", date(2026, 6, 25))
    assert clause == '(appno="474/21") AND (kpdate="2026-06-25")'
    assert "doctype" not in clause
    assert sibling_clause("474/21") == '(appno="474/21")'
