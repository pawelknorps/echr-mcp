"""Smoke testy online - hit live hudoc.echr.coe.int.

Uruchamia sie jawnie (nie wchodza w domyslny `pytest`):
    pytest -m smoke -v -s

Te testy moga byc flaky jezeli:
- HUDOC zmieni ksztalt JSON -> modele w `models.py` wymagaja update
- HUDOC zmieni kontrakt zapytania (np. znowu przestanie wymagac `sort=`) -> `client.py`
- HUDOC jest down / pod load
- brak sieci

W razie failure - PIERWSZE: sprawdz `search_url`/`source_url` z bledu, potem odswiez
fixture'y i uruchom testy offline; jesli offline tez padaja, HUDOC zmienilo kontrakt
i trzeba poprawic aliasy w `models.py` albo parametry w `client.py`.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.smoke

APPNO = "474/21"  # SHEVCHUK v. UKRAINE, wyrok 2026-06-25


async def _english_primary(limit: int = 50) -> dict:
    """Pierwszy nie-placeholderowy rekord w jezyku angielskim dla APPNO."""
    from echr_mcp.server import search_judgments

    result = await search_judgments(appno=APPNO, limit=limit)
    assert result["resultcount"] >= 1, "HUDOC nie zna skargi 474/21 - kontrakt zapytania sie zmienil"
    assert result["items"], "resultcount > 0, ale strona jest pusta"
    item = next(
        (i for i in result["items"] if not i["is_placeholder"] and i["language"] == "ENG"),
        None,
    )
    assert item is not None, f"brak angielskiego, nie-placeholderowego rekordu: {result['items']}"
    assert item["appno"] == [APPNO]
    return item


@pytest.mark.asyncio
async def test_smoke_search_judgments_returns_a_real_itemid():
    item = await _english_primary()
    assert item["itemid"].startswith("001-")
    assert item["docname"]
    assert item["doctype"] == "HEJUD"
    assert item["source_url"].endswith(item["itemid"])
    assert item["originatingbody_label"]


@pytest.mark.asyncio
async def test_smoke_search_judgments_filters_by_article_doctype_and_date():
    from echr_mcp.server import search_judgments

    result = await search_judgments(
        article="6-1",
        doctype="HEJUD",
        kpdate_from="2024-01-01",
        kpdate_to="2024-12-31",
        limit=5,
    )
    assert result["resultcount"] > 0, "article+doctype+kpdate nie zwraca nic - kody sie zmienily?"
    assert result["items"]
    for item in result["items"]:
        assert item["doctype"] == "HEJUD"
        assert "6-1" in item["article"]
        assert "2024-01-01" <= item["kpdate"] <= "2024-12-31"


@pytest.mark.asyncio
async def test_smoke_free_text_phrase_search_is_not_empty():
    """`f:"fraza"` zwraca zero - konektor MUSI wysylac `("fraza")`."""
    from echr_mcp.server import search_judgments

    result = await search_judgments(query="excessive length of proceedings", limit=3)
    assert result["resultcount"] > 0, "fraza pelnotekstowa nie dziala - gramatyka HUDOC sie zmienila"
    assert result["items"]


@pytest.mark.asyncio
async def test_smoke_get_judgment_text_returns_a_long_body(capsys):
    from echr_mcp.server import get_judgment_text

    item = await _english_primary()
    result = await get_judgment_text(itemid=item["itemid"])

    assert result["itemid"] == item["itemid"]
    assert result["language"] == "ENG"
    assert result["char_count"] > 500, "pelny tekst jest podejrzanie krotki - konwersja docx padla?"
    assert result["char_count"] == len(result["text"])
    assert "SHEVCHUK" in result["text"].upper()
    assert f"id={item['itemid']}&" in result["source_url"]
    assert "/app/conversion/docx/" in result["source_url"]

    # Dowod: pierwsze ~400 znakow prawdziwego orzeczenia.
    with capsys.disabled():
        print(f"\n--- get_judgment_text({item['itemid']}) ---")
        print(result["text"][:400])
        print(f"--- char_count={result['char_count']} ---")


@pytest.mark.asyncio
async def test_smoke_list_hudoc_filters_returns_a_non_empty_reference():
    from echr_mcp.server import list_hudoc_filters

    reference = await list_hudoc_filters()
    assert isinstance(reference, dict)
    assert reference
    assert reference["document_types"] and reference["languages"] and reference["articles"]


@pytest.mark.asyncio
async def test_smoke_unknown_itemid_is_not_found():
    """Nieznany itemid -> structured not_found, nie puste body i nie HTTP 500."""
    from echr_mcp.server import EchrError, get_judgment_text

    with pytest.raises(EchrError) as exc:
        await get_judgment_text(itemid="001-999999999")
    assert exc.value.code == "not_found"
