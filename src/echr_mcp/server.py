"""FastMCP server - 4 super-tools dla orzecznictwa ETPC (HUDOC).

Uruchamianie:
    python -m echr_mcp.server

Lub jako entry point po pip install:
    echr-mcp
"""

from __future__ import annotations

import re
import time
from datetime import UTC, date, datetime
from typing import Any

import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import audit
from .client import EchrClient
from .coverage import Coverage, build_coverage
from .filters import build_filter_reference
from .models import (
    JudgmentText,
    SearchResults,
    build_query,
    doc_kind,
    itemid_clause,
    judgment_from_api,
    sibling_clause,
)
from .text import docx_to_text

# ---------------------------------------------------------------------------
# Instructions (procedural orchestration) - wstrzykiwane do system promptu
# klienta MCP. LLM widzi to PRZED pierwszym tool call.
# ---------------------------------------------------------------------------

INSTRUCTIONS = """\
Ten serwer MCP udostepnia orzecznictwo Europejskiego Trybunalu Praw Czlowieka z oficjalnego HUDOC Rady Europy (hudoc.echr.coe.int, JSON, bez auth): indeks wyrokow, decyzji, uchwal Komitetu Ministrow i komunikatow prasowych oraz pelny tekst orzeczen.

## Kolejnosc wywolan

### 1. `list_hudoc_filters` - najpierw slownik, potem szukanie
Statyczny (bez sieci) opis gramatyki zapytan HUDOC: pola, operatory, kody typow dokumentow, kody jezykow, kody artykulow i kolekcje. Wywolaj to, zanim zbudujesz zapytanie niepewne co do wartosci pola (np. jaki kod ma "wyrok po angielsku" - `HEJUD`, albo jak zapisac art. 6 ust. 1 - `6-1`, nie `6`).

### 2. `search_judgments` - indeks orzecznictwa
`query` (fraza pelnotekstowa), `appno` (numer skargi, np. `"474/21"`), `article` (kod artykulu, np. `"6-1"`), `kpdate_from`/`kpdate_to` (YYYY-MM-DD, zakres daty kluczowej), `doctype` (np. `"HEJUD"`), plus `limit`/`offset`. Zwraca `resultcount` (wszystkie trafienia w HUDOC), `count` (strona) i `items` z `itemid`, `docname`, `appno`, `article`, `conclusion`, `kpdate`, `doctype`, `language`, `is_placeholder`.

### 3. `get_judgment_text` - pelny tekst po `itemid`
Pobiera tresc orzeczenia jako `.docx` z HUDOC i zwraca czysty tekst (`text`, `char_count`). `itemid` wez z `search_judgments`. `language` (default `"ENG"`) to preferencja jezyka - `itemid` jest jezykowo scisly, wiec jezeli wskazany dokument jest w innym jezyku, tool sprobuje uzyc wersji w jezyku zadanym; zwrocone `language` to jezyk tekstu, ktory faktycznie dostales.

### 4. `echr_coverage` - granice konektora
Wywolaj PRZED powiedzeniem uzytkownikowi, ze czegos "nie ma" w orzecznictwie ETPC, i zawsze gdy szukanie zwraca pustke. To moze byc luka konektora, a nie brak w orzecznictwie. Kazda luka ma `fallback`.

## Twarde ograniczenia

- **Orzeczenia ETPC to NIE zrodlo prawa polskiego.** Wyrok ETPC wiaze pozwane panstwo (art. 46), ale nie tworzy ani nie zmienia polskich przepisow. Nie podawaj wyroku ETPC jako podstawy prawnej obowiazujacego przepisu - do tego jest konektor `isap`/`eli`. Wyrok cytuj jako orzecznictwo, nie jako przepis.
- **`article` to kod gleboki, nie numer artykulu.** `article="6"` NIE zwroci dokumentow oznaczonych wylacznie jako `6-1`, `6-3-c` itd. Po kody idz do `list_hudoc_filters`.
- **`query` to wyszukiwanie frazowe.** Konektor zamienia `query` na fraze w cudzyslowie (`("excessive length of proceedings")`), wiec dostaniesz dokumenty z ta fraza, nie dokumenty z dowolnym z tych slow. Kolejnosc wynikow to ranking HUDOC - nie ma tu wlasnego sortowania.
- **`is_placeholder=True` to duplikat w jezyku niepodstawowym.** Takie dokumenty nie maja konwertowalnego tekstu. `search_judgments` pokazuje `is_placeholder`, a `get_judgment_text` sam probuje przejsc na wersje podstawowa - ale jezeli dostaniesz `upstream_error`, to wlasnie ta przyczyna.
- **`itemid` jest jezykowo scisly.** Kazda wersja jezykowa ma w HUDOC wlasny `itemid`; `appno` jest wspolny. Nie przenos `itemid` miedzy jezykami - nie zadziala.
- **`kpdate` to data kluczowa HUDOC** (w praktyce data orzeczenia). To nie data zdarzen, nie data uprawomocnienia i nie data wykonania. Nie wyciagaj z niej wnioskow o prawomocnosci.
- **Nie pobieramy zalacznikow ani skanow** - tylko tekst, ktory HUDOC potrafi przekonwertowac do Worda.
- **Bez modyfikacji tresci urzedowej** - `docname`, `conclusion` i tekst orzeczenia wracaja verbatim z HUDOC.
- **Audit log JSONL** - kazdy tool call zapisuje audit do `~/.matematic/audit/echr-mcp.jsonl` (bez pelnych tresci orzeczen).

## Iteracja po bledach

Tool zwraca structured error z prefixem `[code]`:
- `missing_arg` - brakujacy wymagany parametr (np. pusty `itemid`).
- `invalid_arg` - parametr poza zakresem albo zly format (np. `limit > 500`, `offset < 0`, `appno` nie w formacie `NNNN/NN`, `kpdate_from` po `kpdate_to`, `language` nie jest 3-literowym kodem).
- `not_found` - HUDOC nie zna tego `itemid` (albo nie ma wersji w zadanym jezyku). Wroc do `search_judgments` po poprawny `itemid`.
- `upstream_error` - blad HUDOC (HTTP, timeout, brak konwersji do .docx, pusty tekst). Retry raz przed surface do uzytkownika.

## Styl odpowiedzi

- Cytuj orzeczenie tak: nazwa sprawy (`docname`), numer skargi (`appno`), data (`kpdate`) i `itemid`, np. "sprawa SHEVCHUK v. UKRAINE, skarga nr 474/21, wyrok z 2026-06-25 (itemid 001-250747)".
- `docname` podawaj verbatim, w jezyku dokumentu - nie tlumacz nazwy sprawy.
- Przy wynikach zbiorczych podawaj `resultcount` (wszystkie trafienia) obok liczby pokazanej na stronie - inaczej liczba z `items` wprowadza w blad.
- Sprawy z ETPC cytuj po angielsku lub francusku tak, jak w HUDOC; `conclusion` (wynik) tlumacz ostroznie i nie skracaj do "naruszenie" bez artykulu.
- NIE wymyslaj numerow skarg, dat ani `itemid` - wszystko z `structuredContent`.
"""


# Strukturalne kody bledow - widoczne dla LLM z prefixem [code].
class EchrError(Exception):
    """Strukturalny blad dla echr-mcp tools."""

    VALID_CODES = frozenset({
        "missing_arg",
        "invalid_arg",
        "not_found",
        "upstream_error",
    })

    def __init__(self, code: str, message: str):
        if code not in self.VALID_CODES:
            raise ValueError(f"Unknown EchrError code: {code}. Valid: {sorted(self.VALID_CODES)}")
        self.code = code
        super().__init__(f"[{code}] {message}")


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=True,  # live HUDOC API
)


mcp = FastMCP(name="echr-mcp", instructions=INSTRUCTIONS)


# ---------- helpers ----------

_APPNO_RE = re.compile(r"^\d{1,7}/\d{2,4}$")
_ITEMID_RE = re.compile(r"^\d{3}-\d{3,}(-\d+)?$")
_ARTICLE_RE = re.compile(r"^[A-Za-z]{0,2}\d+([-+][A-Za-z0-9]+)*$")
_DOCTYPE_RE = re.compile(r"^[A-Z0-9_]{2,20}$")
_LANGUAGE_RE = re.compile(r"^[A-Z]{3}$")


def _parse_iso_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise EchrError("invalid_arg", f"`{field}` musi byc w formacie YYYY-MM-DD: {exc}") from exc


def _parse_appno(appno: str | None) -> str | None:
    if not appno:
        return None
    value = str(appno).strip()
    if not _APPNO_RE.match(value):
        raise EchrError(
            "invalid_arg",
            f"`appno` musi byc w formacie NNNN/NN (np '474/21'), dostano {appno!r}.",
        )
    return value


def _parse_article(article: str | None) -> str | None:
    if not article:
        return None
    value = str(article).strip()
    if not _ARTICLE_RE.match(value):
        raise EchrError(
            "invalid_arg",
            f"`article` musi byc kodem artykulu (np '6', '6-1', 'P1-1', '35-3-a'), dostano {article!r}. "
            "Pelna liste kodow zwraca `list_hudoc_filters`.",
        )
    return value


def _parse_doctype(doctype: str | None) -> str | None:
    if not doctype:
        return None
    value = str(doctype).strip().upper()
    if not _DOCTYPE_RE.match(value):
        raise EchrError(
            "invalid_arg",
            f"`doctype` musi byc kodem typu dokumentu (np 'HEJUD'), dostano {doctype!r}. "
            "Znane kody zwraca `list_hudoc_filters`.",
        )
    return value


def _parse_language(language: str) -> str:
    value = str(language).strip().upper()
    if not _LANGUAGE_RE.match(value):
        raise EchrError(
            "invalid_arg",
            f"`language` musi byc 3-literowym kodem jezyka HUDOC (np 'ENG', 'FRE', 'POL'), "
            f"dostano {language!r}.",
        )
    return value


def _require_itemid(itemid: str) -> str:
    value = str(itemid).strip()
    if not value:
        raise EchrError(
            "missing_arg",
            "Parametr `itemid` jest wymagany (np '001-250747'). Ustal go przez `search_judgments`.",
        )
    if not _ITEMID_RE.match(value):
        raise EchrError(
            "invalid_arg",
            f"`itemid` musi miec format HUDOC (np '001-250747'), dostano {itemid!r}. "
            "Uzyj `itemid` z `search_judgments`, nie numeru skargi.",
        )
    return value


async def _fetch(coro) -> tuple[Any, str]:
    """Wykonuje request klienta, mapujac bledy HTTP na kody strukturalne."""
    try:
        return await coro
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 404:
            raise EchrError(
                "not_found",
                f"HUDOC nie zna tego zasobu (HTTP 404): {exc.request.url}.",
            ) from exc
        raise EchrError(
            "upstream_error",
            f"Blad HUDOC (HTTP {status}): {exc.request.url}. "
            "HTTP 500 z konwersji /app/conversion/docx/ oznacza zwykle dokument bez "
            "konwertowalnego tekstu (np. placeholder w jezyku niepodstawowym).",
        ) from exc
    except httpx.HTTPError as exc:
        raise EchrError("upstream_error", f"Blad HUDOC: {exc}") from exc


# ---------- TOOL 1: search_judgments ----------


@mcp.tool(annotations=READ_ONLY)
async def search_judgments(
    query: str | None = None,
    appno: str | None = None,
    article: str | None = None,
    kpdate_from: str | None = None,
    kpdate_to: str | None = None,
    doctype: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Szuka orzeczen ETPC w HUDOC.

    Warunki sa AND-owane do bazy `(contentsitename=ECHR)`. `query` jest fraza
    pelnotekstowa (konektor opakowuje ja w cudzyslow), `article` to kod gleboki
    (np `6-1`, nie `6`).

    Args:
        query: fraza pelnotekstowa, np "excessive length of proceedings"
        appno: numer skargi w formacie NNNN/NN, np "474/21"
        article: kod artykulu Konwencji/protokolu, np "6-1", "P1-1", "35-3-a"
        kpdate_from: YYYY-MM-DD, dolna granica daty kluczowej (`kpdate`)
        kpdate_to: YYYY-MM-DD, gorna granica daty kluczowej (`kpdate`)
        doctype: kod typu dokumentu, np "HEJUD" (wyrok ang.), "HEDEC" (decyzja ang.)
        limit: ile rekordow na strone (default 50, max 500)
        offset: przesuniecie w wynikach HUDOC (default 0)

    Returns:
        dict: {query, limit, offset, resultcount, count, items: [...], source_url, retrieved_at}
    """
    t0 = time.monotonic()

    if limit < 1 or limit > 500:
        raise EchrError("invalid_arg", f"`limit` musi byc w zakresie 1-500, dostano {limit}.")
    if offset < 0:
        raise EchrError("invalid_arg", f"`offset` musi byc >= 0, dostano {offset}.")

    appno_parsed = _parse_appno(appno)
    article_parsed = _parse_article(article)
    doctype_parsed = _parse_doctype(doctype)
    date_from = _parse_iso_date(kpdate_from, "kpdate_from")
    date_to = _parse_iso_date(kpdate_to, "kpdate_to")
    if date_from and date_to and date_from > date_to:
        raise EchrError("invalid_arg", f"kpdate_from ({date_from}) jest po kpdate_to ({date_to}).")

    hudoc_query = build_query(
        query=query,
        appno=appno_parsed,
        article=article_parsed,
        kpdate_from=date_from,
        kpdate_to=date_to,
        doctype=doctype_parsed,
    )

    async with EchrClient() as client:
        raw, source_url = await _fetch(client.search(hudoc_query, limit=limit, offset=offset))

    items = [judgment_from_api(columns) for columns in _columns(raw)]
    result = SearchResults(
        query=hudoc_query,
        limit=limit,
        offset=offset,
        resultcount=int(raw.get("resultcount") or 0),
        count=len(items),
        items=items,
        source_url=source_url,
        retrieved_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )

    audit.log_event(
        tool="search_judgments",
        params={
            "query": query,
            "appno": appno,
            "article": article,
            "kpdate_from": kpdate_from,
            "kpdate_to": kpdate_to,
            "doctype": doctype,
            "limit": limit,
            "offset": offset,
        },
        result_summary={"resultcount": result.resultcount, "count": result.count},
        source_urls=[source_url],
        latency_ms=(time.monotonic() - t0) * 1000,
        cache_hit=False,
    )
    return result.model_dump(mode="json")


def _columns(raw: dict) -> list[dict]:
    """Wyciaga listy `columns` z odpowiedzi HUDOC (rekordy bez `columns` wypadaja)."""
    results = raw.get("results") or []
    return [r["columns"] for r in results if isinstance(r, dict) and isinstance(r.get("columns"), dict)]


# ---------- TOOL 2: get_judgment_text ----------


@mcp.tool(annotations=READ_ONLY)
async def get_judgment_text(itemid: str = "", language: str = "ENG") -> dict:
    """Pelny tekst orzeczenia ETPC z HUDOC, po `itemid` z `search_judgments`.

    HUDOC wydaje pelny tekst tylko jako `.docx`; konwertujemy go lokalnie (stdlib).
    `itemid` jest jezykowo scisly, wiec jezeli dokument nie jest w jezyku `language`,
    tool szuka wersji w tym jezyku (i omija placeholdery bez tekstu). Zwrocone
    `language` to jezyk tekstu, ktory faktycznie wrocil.

    Args:
        itemid: identyfikator dokumentu z `search_judgments` (np "001-250747")
        language: preferowany jezyk tekstu, 3-literowy kod HUDOC (default "ENG")

    Returns:
        dict: {itemid, language, text, char_count, source_url, retrieved_at}
    """
    t0 = time.monotonic()
    iid = _require_itemid(itemid)
    lang = _parse_language(language)

    async with EchrClient() as client:
        meta_raw, meta_url = await _fetch(client.search(itemid_clause(iid), limit=1, offset=0))
        columns = _columns(meta_raw)
        if not columns:
            raise EchrError(
                "not_found",
                f"HUDOC nie zna itemid {iid!r}. Uzyj `itemid` z `search_judgments`.",
            )
        resolved = await _resolve_language(client, judgment_from_api(columns[0]), lang)

        data, source_url = await _fetch(client.download_docx(resolved.itemid))

    try:
        text = docx_to_text(data)
    except ValueError as exc:
        raise EchrError(
            "upstream_error",
            f"HUDOC zwrocil plik, ktorego nie da sie odczytac jako .docx ({exc}). "
            f"Sprawdz dokument w HUDOC: {resolved.source_url}",
        ) from exc

    if not text.strip():
        raise EchrError(
            "upstream_error",
            f"HUDOC zwrocil pusty tekst dla itemid={resolved.itemid}. "
            f"Sprawdz dokument w HUDOC: {resolved.source_url}",
        )

    result = JudgmentText(
        itemid=resolved.itemid,
        language=resolved.language or lang,
        text=text,
        char_count=len(text),
        source_url=source_url,
        retrieved_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )

    audit.log_event(
        tool="get_judgment_text",
        params={"itemid": iid, "language": lang},
        result_summary={
            "itemid": result.itemid,
            "language": result.language,
            "char_count": result.char_count,
            "resolved_from": iid,
        },
        source_urls=[meta_url, source_url],
        latency_ms=(time.monotonic() - t0) * 1000,
        cache_hit=False,
    )
    return result.model_dump(mode="json")


async def _resolve_language(client: EchrClient, found, lang: str):
    """Znajduje wersje dokumentu w zadanym jezyku (i omija placeholdery).

    Bez tego `itemid` w innym jezyku albo placeholder (brak konwertowalnego tekstu)
    konczylyby sie tekstem w zlym jezyku albo bledem. Kandydaci sa ograniczeni do
    tego samego rodzaju dokumentu (`doc_kind`), zeby nie podmienic wyroku na decyzje.
    """
    if found.language == lang and not found.is_placeholder:
        return found
    if not found.appno:
        return found

    kind = doc_kind(found.doctype)
    raw, _ = await _fetch(
        client.search(sibling_clause(found.appno[0], found.kpdate), limit=50, offset=0)
    )
    same_kind = [
        judgment_from_api(columns)
        for columns in _columns(raw)
        if columns.get("itemid") != found.itemid and doc_kind(columns.get("doctype")) == kind
    ]
    if not same_kind:
        return found

    better = min(same_kind, key=lambda c: (c.language != lang, c.is_placeholder, c.itemid))
    if better.language == lang or found.is_placeholder:
        return better
    return found


# ---------- TOOL 3: list_hudoc_filters ----------


@mcp.tool(annotations=READ_ONLY)
async def list_hudoc_filters() -> dict:
    """Statyczny slownik zapytan HUDOC - bez sieci.

    Zwraca gramatyke zapytan, pola wyszukiwalne, operatory oraz enumeracje:
    kody typow dokumentow, kody jezykow, kody artykulow, kolekcje i organy
    wydajace. Wywolaj to, zanim zbudujesz zapytanie z niepewna wartoscia pola.

    Returns:
        dict: {endpoint, query_grammar, searchable_fields, operators,
        document_types, languages, articles, collections, originating_bodies, notes}
    """
    t0 = time.monotonic()
    reference = build_filter_reference()
    audit.log_event(
        tool="list_hudoc_filters",
        params={},
        result_summary={
            "document_types": len(reference["document_types"]),
            "languages": len(reference["languages"]),
            "articles": len(reference["articles"]),
        },
        source_urls=[reference["endpoint"]["search"]],
        latency_ms=(time.monotonic() - t0) * 1000,
        cache_hit=False,
    )
    return reference


# ---------- TOOL 4: echr_coverage ----------


@mcp.tool(annotations=READ_ONLY)
async def echr_coverage() -> Coverage:
    """Declare what this connector covers, how it is sourced, and what it does NOT cover.

    Call this before telling a user that the case law "does not contain" something,
    and whenever a search comes back empty: the absence may be a gap in this connector
    rather than in the ECHR record. Every gap carries a fallback saying where to look
    instead.

    Returns:
        ``Coverage`` with families, an as-of note, and a non-empty list of known gaps.
    """
    t0 = time.monotonic()
    coverage = build_coverage()
    audit.log_event(
        tool="echr_coverage",
        params={},
        result_summary={"families": len(coverage.families), "gaps": len(coverage.known_gaps)},
        source_urls=[],
        latency_ms=(time.monotonic() - t0) * 1000,
        cache_hit=False,
    )
    return coverage


# ---------- entry point ----------


def main() -> None:
    """Entry point dla stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
