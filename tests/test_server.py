"""Testy serwera: powierzchnia toolow (fastmcp Client) + przeplywy offline.

Zadne z tych testow nie wychodzi do sieci - `EchrClient` jest podmieniany,
a `echr_coverage` / `list_hudoc_filters` nie dotykaja API wcale.
"""

from __future__ import annotations

import asyncio
import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest
from fastmcp import Client

from echr_mcp.client import EchrClient
from echr_mcp.models import BASE_QUERY
from echr_mcp.server import (
    INSTRUCTIONS,
    EchrError,
    echr_coverage,
    get_judgment_text,
    list_hudoc_filters,
    mcp,
    search_judgments,
)

EXPECTED_TOOLS = {"search_judgments", "get_judgment_text", "list_hudoc_filters", "echr_coverage"}

SEARCH_URL = (
    "https://hudoc.echr.coe.int/app/query/results?query=x&select=y&sort=&start=0&length=50"
)
DOCX_URL = "https://hudoc.echr.coe.int/app/conversion/docx/?library=ECHR&id=001-250747"


def _fn(tool):
    """fastmcp 3 owinien tool w FunctionTool - `fn` to oryginalna coroutine."""
    return getattr(tool, "fn", tool)


def _run(tool, **kwargs):
    return asyncio.run(_fn(tool)(**kwargs))


def _audit_lines(tmp_path: Path) -> list[dict]:
    return [
        json.loads(line)
        for f in tmp_path.rglob("*.jsonl")
        for line in f.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _docx(*paragraphs: str) -> bytes:
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("word/document.xml", f'<w:document xmlns:w="{w}"><w:body>{body}</w:body></w:document>')
    return buffer.getvalue()


def _columns(fixture_json, name: str) -> list[dict]:
    return [r["columns"] for r in fixture_json(name)["results"]]


PRIMARY_ENG = "001-250747"
PLACEHOLDER_FRE = "001-251115"


class _FakeSearch:
    """Podmiana `EchrClient.search`: routuje po typie zapytania HUDOC.

    `__get__` czyni z instancji deskryptor, wiec monkeypatch nie wstrzykuje `self` -
    podmiana zachowuje sie jak zwykla metoda `async def search(self, query, ...)`.
    """

    def __init__(self, itemid_columns, sibling_columns=()):
        self.itemid_columns = itemid_columns
        self.sibling_columns = list(sibling_columns)
        self.queries: list[str] = []

    def __get__(self, obj, objtype=None):
        return self

    async def __call__(self, query, limit=50, offset=0):
        self.queries.append(query)
        if query.startswith("(itemid="):
            if self.itemid_columns is None:
                return {"resultcount": 0, "results": []}, SEARCH_URL
            return {"resultcount": 1, "results": [{"columns": self.itemid_columns}]}, SEARCH_URL
        return (
            {"resultcount": len(self.sibling_columns), "results": [{"columns": c} for c in self.sibling_columns]},
            SEARCH_URL,
        )


# ---------- powierzchnia toolow ----------


@pytest.mark.asyncio
async def test_tool_surface_is_exactly_the_four_tools():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    assert {t.name for t in tools} == EXPECTED_TOOLS


@pytest.mark.asyncio
async def test_all_tools_are_marked_read_only():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    for tool in tools:
        assert tool.annotations is not None, f"{tool.name} bez adnotacji"
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False


@pytest.mark.asyncio
async def test_every_tool_is_documented_in_the_instructions():
    """INSTRUCTIONS to system prompt klienta - tool poza nim jest dla LLM niewidoczny."""
    async with Client(mcp) as client:
        tools = await client.list_tools()
    for tool in tools:
        assert tool.name in INSTRUCTIONS, f"{tool.name} nie wystepuje w INSTRUCTIONS"


@pytest.mark.asyncio
async def test_coverage_tool_returns_non_empty_gaps():
    result = await _fn(echr_coverage)()
    assert result.status == "ok"
    assert result.families
    assert result.known_gaps
    assert all(g.fallback for g in result.known_gaps)


@pytest.mark.asyncio
async def test_coverage_over_the_mcp_client(tmp_path):
    async with Client(mcp) as client:
        result = await client.call_tool("echr_coverage", {})
    payload = result.structured_content or result.data
    assert payload["known_gaps"]
    assert any(entry["tool"] == "echr_coverage" for entry in _audit_lines(tmp_path))


@pytest.mark.asyncio
async def test_list_hudoc_filters_is_offline_and_substantive():
    reference = await _fn(list_hudoc_filters)()
    assert isinstance(reference, dict) and reference
    assert reference["document_types"]["HEJUD"] == "Judgment - Eng"
    assert "6-1" in reference["articles"]
    assert reference["languages"]["ENG"] == "English"
    assert reference["originating_bodies"]["8"] == "Court (Grand Chamber)"
    assert reference["endpoint"]["search"].endswith("/app/query/results")
    # `sort` jest obowiazkowy w HUDOC - to musi byc udokumentowane dla modelu
    assert "sort" in reference["endpoint"]["required_params"]
    assert any("sort" in note for note in reference["notes"])


# ---------- przeplywy narzedzi (offline, klient podmieniony) ----------


def test_search_judgments_returns_counts_and_logs_audit(fixture_json, monkeypatch, tmp_path):
    raw = fixture_json("search_appno_474_21.json")
    calls: list[str] = []

    async def fake_search(self, query, limit=50, offset=0):
        calls.append(query)
        return raw, SEARCH_URL

    monkeypatch.setattr(EchrClient, "search", fake_search)

    result = _run(search_judgments, appno="474/21")

    assert calls == ['(contentsitename=ECHR) AND (appno="474/21")']
    assert result["query"] == calls[0]
    assert result["resultcount"] == 3
    assert result["count"] == 3
    assert result["limit"] == 50
    assert result["offset"] == 0
    assert result["items"][0]["itemid"] == PRIMARY_ENG
    assert result["items"][0]["source_url"] == "https://hudoc.echr.coe.int/eng?i=001-250747"
    assert result["source_url"] == SEARCH_URL

    lines = _audit_lines(tmp_path)
    assert lines and lines[-1]["tool"] == "search_judgments"
    assert lines[-1]["result_summary"] == {"resultcount": 3, "count": 3}
    assert lines[-1]["source_urls"] == [SEARCH_URL]


def test_search_judgments_composes_every_filter(fixture_json, monkeypatch):
    calls: list[str] = []

    async def fake_search(self, query, limit=50, offset=0):
        calls.append(query)
        return fixture_json("search_empty.json"), SEARCH_URL

    monkeypatch.setattr(EchrClient, "search", fake_search)

    result = _run(
        search_judgments,
        query="environment",
        appno="474/21",
        article="8-1",
        kpdate_from="2020-01-01",
        kpdate_to="2021-01-01",
        doctype="hejud",
        limit=10,
        offset=20,
    )

    assert calls == [
        (
            '(contentsitename=ECHR) AND ("environment") AND (appno="474/21") AND (article="8-1") '
            'AND (kpdate>="2020-01-01") AND (kpdate<="2021-01-01") AND (doctype="HEJUD")'
        )
    ]
    assert result["resultcount"] == 0
    assert result["items"] == []


def test_search_judgments_without_filters_keeps_the_base_condition(monkeypatch):
    calls: list[str] = []

    async def fake_search(self, query, limit=50, offset=0):
        calls.append(query)
        return {"resultcount": 0, "results": []}, SEARCH_URL

    monkeypatch.setattr(EchrClient, "search", fake_search)

    _run(search_judgments)

    assert calls == [BASE_QUERY]


def test_get_judgment_text_returns_body_and_logs_audit(fixture_json, monkeypatch, tmp_path):
    primary = next(c for c in _columns(fixture_json, "metadata_itemid_001-250747.json") if c["itemid"] == PRIMARY_ENG)
    fake = _FakeSearch(primary)
    downloads: list[str] = []

    async def fake_download(self, itemid):
        downloads.append(itemid)
        return _docx("CASE OF SHEVCHUK v. UKRAINE", "The applicant complained."), DOCX_URL

    monkeypatch.setattr(EchrClient, "search", fake)
    monkeypatch.setattr(EchrClient, "download_docx", fake_download)

    result = _run(get_judgment_text, itemid=PRIMARY_ENG)

    # jezyk sie zgadza, wiec jedno zapytanie o metadane i zero zapytan o rodzenstwo
    assert fake.queries == ['(itemid="001-250747")']
    assert downloads == [PRIMARY_ENG]
    assert result["itemid"] == PRIMARY_ENG
    assert result["language"] == "ENG"
    assert result["char_count"] == len("CASE OF SHEVCHUK v. UKRAINE\n\nThe applicant complained.")
    assert result["source_url"] == DOCX_URL
    assert result["text"].startswith("CASE OF SHEVCHUK")
    assert result["retrieved_at"]

    assert any(entry["tool"] == "get_judgment_text" for entry in _audit_lines(tmp_path))


def test_get_judgment_text_resolves_a_placeholder_to_the_primary_language(fixture_json, monkeypatch):
    """Placeholder (FRE) nie ma konwertowalnego tekstu - tool ma przejsc na ENG."""
    columns = _columns(fixture_json, "search_appno_474_21.json")
    placeholder = next(c for c in columns if c["itemid"] == PLACEHOLDER_FRE)
    fake = _FakeSearch(placeholder, sibling_columns=columns)
    downloads: list[str] = []

    async def fake_download(self, itemid):
        downloads.append(itemid)
        return _docx("CASE OF SHEVCHUK v. UKRAINE"), DOCX_URL

    monkeypatch.setattr(EchrClient, "search", fake)
    monkeypatch.setattr(EchrClient, "download_docx", fake_download)

    result = _run(get_judgment_text, itemid=PLACEHOLDER_FRE, language="ENG")

    assert fake.queries == [
        '(itemid="001-251115")',
        '(appno="474/21") AND (kpdate="2026-06-25")',
    ]
    # fixture zwraca tez HECOM (001-214427) z tej samej skargi - inny rodzaj dokumentu,
    # wiec NIE moze zostac podmieniony za wyrok
    assert downloads == [PRIMARY_ENG]
    assert result["itemid"] == PRIMARY_ENG
    assert result["language"] == "ENG"


def test_get_judgment_text_keeps_the_itemid_when_no_better_version_exists(fixture_json, monkeypatch):
    """Brak wersji w zadanym jezyku: zwracamy to, co jest, z PRAWDZIWYM jezykiem."""
    columns = _columns(fixture_json, "search_appno_474_21.json")
    french_only = next(c for c in columns if c["itemid"] == PLACEHOLDER_FRE)
    fake = _FakeSearch(french_only, sibling_columns=[french_only])

    async def fake_download(self, itemid):
        return _docx("AFFAIRE SHEVCHUK c. UKRAINE"), DOCX_URL

    monkeypatch.setattr(EchrClient, "search", fake)
    monkeypatch.setattr(EchrClient, "download_docx", fake_download)

    result = _run(get_judgment_text, itemid=PLACEHOLDER_FRE, language="ENG")

    assert result["itemid"] == PLACEHOLDER_FRE
    assert result["language"] == "FRE"  # nie udajemy, ze to ENG


# ---------- walidacja i kody bledow ----------


def test_missing_itemid_is_a_structured_error():
    with pytest.raises(EchrError) as exc:
        _run(get_judgment_text, itemid="")
    assert exc.value.code == "missing_arg"
    assert str(exc.value).startswith("[missing_arg]")


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"appno": "474-21"}, "invalid_arg"),
        ({"appno": "474/2021/x"}, "invalid_arg"),
        ({"article": "art. 6"}, "invalid_arg"),
        ({"doctype": "nie ma takiego!"}, "invalid_arg"),
        ({"kpdate_from": "01.01.2024"}, "invalid_arg"),
        ({"limit": 0}, "invalid_arg"),
        ({"limit": 501}, "invalid_arg"),
        ({"offset": -1}, "invalid_arg"),
    ],
)
def test_invalid_search_arguments_are_structured_errors(kwargs, code):
    with pytest.raises(EchrError) as exc:
        _run(search_judgments, **kwargs)
    assert exc.value.code == code


def test_date_range_is_validated():
    with pytest.raises(EchrError) as exc:
        _run(search_judgments, kpdate_from="2024-01-01", kpdate_to="2023-01-01")
    assert exc.value.code == "invalid_arg"


def test_invalid_itemid_format_is_a_structured_error():
    with pytest.raises(EchrError) as exc:
        _run(get_judgment_text, itemid="474/21")  # numer skargi, nie itemid
    assert exc.value.code == "invalid_arg"


def test_invalid_language_is_a_structured_error():
    with pytest.raises(EchrError) as exc:
        _run(get_judgment_text, itemid=PRIMARY_ENG, language="english")
    assert exc.value.code == "invalid_arg"


def test_unknown_itemid_maps_to_not_found(monkeypatch):
    monkeypatch.setattr(EchrClient, "search", _FakeSearch(None))

    with pytest.raises(EchrError) as exc:
        _run(get_judgment_text, itemid="001-999999999")
    assert exc.value.code == "not_found"


def test_404_maps_to_not_found(monkeypatch):
    async def fake_search(self, query, limit=50, offset=0):
        request = httpx.Request("GET", SEARCH_URL)
        raise httpx.HTTPStatusError("404", request=request, response=httpx.Response(404, request=request))

    monkeypatch.setattr(EchrClient, "search", fake_search)

    with pytest.raises(EchrError) as exc:
        _run(search_judgments, appno="474/21")
    assert exc.value.code == "not_found"


def test_500_from_the_docx_conversion_maps_to_upstream_error(monkeypatch, fixture_json):
    primary = _columns(fixture_json, "metadata_itemid_001-250747.json")[0]
    monkeypatch.setattr(EchrClient, "search", _FakeSearch(primary))

    async def fake_download(self, itemid):
        request = httpx.Request("GET", DOCX_URL)
        raise httpx.HTTPStatusError("500", request=request, response=httpx.Response(500, request=request))

    monkeypatch.setattr(EchrClient, "download_docx", fake_download)

    with pytest.raises(EchrError) as exc:
        _run(get_judgment_text, itemid=PRIMARY_ENG)
    assert exc.value.code == "upstream_error"
    assert "500" in str(exc.value)


def test_a_body_that_is_not_a_docx_maps_to_upstream_error(monkeypatch, fixture_json):
    primary = _columns(fixture_json, "metadata_itemid_001-250747.json")[0]
    monkeypatch.setattr(EchrClient, "search", _FakeSearch(primary))

    async def fake_download(self, itemid):
        return b"<html>konwersja sie nie udala</html>", DOCX_URL

    monkeypatch.setattr(EchrClient, "download_docx", fake_download)

    with pytest.raises(EchrError) as exc:
        _run(get_judgment_text, itemid=PRIMARY_ENG)
    assert exc.value.code == "upstream_error"


def test_an_empty_converted_body_maps_to_upstream_error(monkeypatch, fixture_json):
    primary = _columns(fixture_json, "metadata_itemid_001-250747.json")[0]
    monkeypatch.setattr(EchrClient, "search", _FakeSearch(primary))

    async def fake_download(self, itemid):
        return _docx(), DOCX_URL  # poprawne .docx, ale bez akapitow

    monkeypatch.setattr(EchrClient, "download_docx", fake_download)

    with pytest.raises(EchrError) as exc:
        _run(get_judgment_text, itemid=PRIMARY_ENG)
    assert exc.value.code == "upstream_error"


def test_network_failure_maps_to_upstream_error(monkeypatch):
    async def fake_search(self, query, limit=50, offset=0):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(EchrClient, "search", fake_search)

    with pytest.raises(EchrError) as exc:
        _run(search_judgments, appno="474/21")
    assert exc.value.code == "upstream_error"
