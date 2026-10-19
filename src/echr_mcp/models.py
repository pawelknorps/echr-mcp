"""Modele Pydantic v2 + czyste transformacje dla echr-mcp.

Pola HUDOC sa mapowane aliasami (`docname`, `appno`, `isplaceholder`,
`languageisocode`), a nadmiarowe klucze sa ignorowane. Wszystkie funkcje
transformujace sa czyste - testowalne offline na fixture'ach.
"""

from __future__ import annotations

import datetime as _dt
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import BASE_URL
from .filters import ORIGINATING_BODIES

#: Pola, o ktore prosimy HUDOC w kazdym wyszukiwaniu.
SEARCH_SELECT = (
    "itemid,docname,appno,article,conclusion,kpdate,"
    "originatingbody,doctype,documentcollectionid2,rank,isplaceholder,languageisocode"
)

#: Warunek bazowy - zawsze AND-owany do zapytania (spec: HUDOC = zbior ECHR).
BASE_QUERY = "(contentsitename=ECHR)"


def _utcnow_iso() -> str:
    return datetime.now(_dt.UTC).isoformat(timespec="seconds")


def judgment_url(itemid: str) -> str:
    """Kanoniczny deep-link do dokumentu w HUDOC (do cytowania / audytu)."""
    return f"{BASE_URL}/eng?i={itemid}"


def docx_url(itemid: str) -> str:
    """URL konwersji pelnego tekstu (docx) dla danego `itemid`."""
    return f"{BASE_URL}/app/conversion/docx/?library=ECHR&id={itemid}&filename={itemid}&logEvent=false"


class JudgmentSummary(BaseModel):
    """Jeden dokument z listy wynikow HUDOC (rekord `columns`)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    itemid: str = Field(description="Identyfikator dokumentu - klucz dla get_judgment_text")
    docname: str | None = Field(default=None, description="np 'CASE OF SHEVCHUK v. UKRAINE'")
    appno: list[str] = Field(default_factory=list, description='numery skarg, np ["474/21"]')
    article: list[str] = Field(default_factory=list, description='kody artykulow, np ["6-1", "8-1"]')
    conclusion: str | None = Field(default=None, description="wynik sprawy jako tekst")
    kpdate: _dt.date | None = Field(default=None, description="data kluczowa dokumentu")
    originatingbody: str | None = Field(default=None, description="kod organu, np '23'")
    originatingbody_label: str | None = Field(default=None, description="np 'Court (Fifth Section)'")
    doctype: str | None = Field(default=None, description="kod typu, np 'HEJUD'")
    collections: list[str] = Field(
        default_factory=list, description='np ["CASELAW", "JUDGMENTS", "CHAMBER", "ENG"]'
    )
    rank: float | None = None
    is_placeholder: bool = Field(
        default=False,
        alias="isplaceholder",
        description="True = duplikat w jezyku niepodstawowym; brak konwertowalnego tekstu",
    )
    language: str | None = Field(default=None, alias="languageisocode", description="np 'ENG'")
    source_url: str = Field(default="", description="deep-link HUDOC do dokumentu")
    retrieved_at: str = Field(default_factory=_utcnow_iso)


class SearchResults(BaseModel):
    """Odpowiedz `search_judgments` - strona wynikow + metadane zapytania."""

    query: str = Field(description="zapytanie HUDOC faktycznie wyslane do API")
    limit: int
    offset: int
    resultcount: int = Field(description="laczna liczba trafien w HUDOC (nie tylko na tej stronie)")
    count: int = Field(description="liczba rekordow na tej stronie")
    items: list[JudgmentSummary] = Field(default_factory=list)
    source_url: str = Field(default="", description="URL wywolania API")
    retrieved_at: str = Field(default_factory=_utcnow_iso)


class JudgmentText(BaseModel):
    """Odpowiedz `get_judgment_text` - pelny tekst dokumentu."""

    itemid: str = Field(description="itemid dokumentu, z ktorego pochodzi tekst")
    language: str = Field(description="jezyk tekstu faktycznie zwroconego")
    text: str = Field(description="tresc orzeczenia z .docx, biale znaki znormalizowane")
    char_count: int
    source_url: str = Field(default="", description="URL konwersji .docx")
    retrieved_at: str = Field(default_factory=_utcnow_iso)


# ---------- czyste transformacje (testowalne offline) ----------


def _split_semicolons(value: Any) -> list[str]:
    """Rozbija `a;b;c` na liste; puste i nie-str puste wartosci wypadaja."""
    if not isinstance(value, str) or not value.strip():
        return []
    return [part.strip() for part in value.split(";") if part.strip()]


def _as_bool(value: Any) -> bool:
    """HUDOC podaje `isplaceholder` jako string 'True'/'False'."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true" if value is not None else False


def _as_date(value: Any) -> _dt.date | None:
    """`kpdate` przychodzi jako '2026-06-25T00:00:00' - bierzemy czesc data."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return _dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def judgment_from_api(columns: dict[str, Any]) -> JudgmentSummary:
    """Buduje `JudgmentSummary` z surowego rekordu `columns` HUDOC."""
    data = dict(columns)
    data["appno"] = _split_semicolons(columns.get("appno"))
    data["article"] = _split_semicolons(columns.get("article"))
    data["collections"] = _split_semicolons(columns.get("documentcollectionid2"))
    data["kpdate"] = _as_date(columns.get("kpdate"))
    data["rank"] = _as_float(columns.get("rank"))
    data["isplaceholder"] = _as_bool(columns.get("isplaceholder"))
    body = columns.get("originatingbody")
    data["originatingbody_label"] = ORIGINATING_BODIES.get(str(body)) if body is not None else None
    # itemid jest kluczem rekordu - brak (uszkodzony rekord) daje "" zamiast wywalac walidacje
    data["itemid"] = str(columns.get("itemid") or "")
    itemid = data["itemid"]
    data["source_url"] = judgment_url(itemid) if itemid else ""
    return JudgmentSummary.model_validate(data)


def doc_kind(doctype: str | None) -> str | None:
    """Rodzaj dokumentu bez prefiksu jezyka: `HEJUD`/`HFJUD` -> `JUD`, `HECOM` -> `COM`.

    HUDOC koduje jezyk na drugiej pozycji kodu typu, wiec dwa kody o roznym jezyku
    moga opisac ten sam rodzaj dokumentu. Bez tego `get_judgment_text` moglby
    podmienic wyrok na decyzje wydana tego samego dnia dla tej samej skargi.
    """
    if not doctype or len(doctype) < 3:
        return doctype
    return doctype[2:]


# ---------- budowanie zapytan HUDOC (czyste funkcje) ----------

_WHITESPACE = re.compile(r"\s+")


def _clean_phrase(query: str) -> str:
    """Usuwa z frazy znaki, ktore rozsadzilyby gramatyke zapytania HUDOC."""
    return _WHITESPACE.sub(" ", query.replace('"', " ").replace("\\", " ")).strip()


def free_text_clause(query: str) -> str:
    """Warunek pelnotekstowy HUDOC - dziala WYLACZNIE jako fraza w nawiasie.

    `("fraza")` zwraca trafienia, `f:"fraza"` zwraca zero (HUDOC 2026-10).
    """
    return f'("{_clean_phrase(query)}")'


def itemid_clause(itemid: str) -> str:
    """Zapytanie po dokladnym `itemid` (do rozpoznania dokumentu przed pobraniem)."""
    return f'(itemid="{itemid}")'


def sibling_clause(appno: str, kpdate: _dt.date | None = None) -> str:
    """Zapytanie po innych wersjach tego samego dokumentu (inne jezyki).

    Filtrujemy po `appno` + `kpdate`, a NIE po `doctype`: kod typu dokumentu jest
    jezykowo zalezny (`HEJUD` vs `HFJUD`), wiec filtr po `doctype` zgubilby
    wlasnie te wersje, ktorych szukamy.
    """
    clause = f'(appno="{appno}")'
    if kpdate:
        clause += f' AND (kpdate="{kpdate.isoformat()}")'
    return clause


def build_query(
    query: str | None = None,
    appno: str | None = None,
    article: str | None = None,
    kpdate_from: _dt.date | None = None,
    kpdate_to: _dt.date | None = None,
    doctype: str | None = None,
) -> str:
    """Sklada zapytanie HUDOC z parametrow strukturalnych.

    Kazdy warunek jest AND-owany do bazy `(contentsitename=ECHR)` - konektor
    nigdy nie wypuszcza zapytania bez tego warunku.
    """
    parts = [BASE_QUERY]
    if query:
        parts.append(free_text_clause(query))
    if appno:
        parts.append(f'(appno="{appno}")')
    if article:
        parts.append(f'(article="{article}")')
    if kpdate_from:
        parts.append(f'(kpdate>="{kpdate_from.isoformat()}")')
    if kpdate_to:
        parts.append(f'(kpdate<="{kpdate_to.isoformat()}")')
    if doctype:
        parts.append(f'(doctype="{doctype}")')
    return " AND ".join(parts)
