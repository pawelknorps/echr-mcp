"""Element 9 of the MateMatic MCP canon: this connector declares its own coverage.

Knowledge about what a corpus does NOT hold is useless while it lives only as prose
in the server instructions - the model has to remember it and choose to relay it, and
an agent has no way to ask. Here it is callable.

Every gap below is grounded in this connector's own source and tool surface. The list
is deliberately never empty: no legal corpus is complete, so an empty gap list would
mean "nobody checked", not "there are no gaps".
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _CoverageBase(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class CoverageFamily(_CoverageBase):
    """One data family this connector exposes."""

    name: str = Field(description="Data family, e.g. 'ECHR case law (HUDOC)'.")
    tool: str = Field(description="Tool or tools that reach this family.")
    source: str = Field(description="Official source the data comes from.")
    captured_at: str | None = Field(
        default=None,
        description="Date this family was last captured (ISO). None when queried live.",
    )
    live: bool = Field(default=True, description="True when queried live instead of from a snapshot.")


class CoverageGap(_CoverageBase):
    """A known, named hole in this connector's coverage - plus the way around it."""

    id: str = Field(description="Stable gap identifier.")
    family: str = Field(description="Which family the gap belongs to.")
    missing: str = Field(description="What is NOT available through this connector.")
    fallback: str = Field(description="Where to go instead.")


class Coverage(_CoverageBase):
    """What this connector covers, how it is sourced, and what it does not cover."""

    status: Literal["ok", "degraded", "failed"] = "ok"
    as_of_note: str = Field(description="States what the dates mean, and what they do not promise.")
    families: list[CoverageFamily] = Field(default_factory=list)
    known_gaps: list[CoverageGap] = Field(
        default_factory=list,
        description="Never empty. An empty list would mean 'not checked', not 'no gaps'.",
    )


SOURCE = "hudoc.echr.coe.int (official HUDOC, Council of Europe, no auth)"

AS_OF_NOTE = (
    "Every answer is queried live against HUDOC, so there is no local snapshot date. Dates "
    "carried by a record come from HUDOC's own `kpdate` (the key date, in practice the date "
    "of the judgment or decision) - they say nothing about the facts, and nothing about the "
    "date the judgment became final or was executed. HUDOC assigns a separate `itemid` to "
    "each language version of a document, so an `itemid` is language-specific."
)

_FAMILIES: list[dict] = [
    {
        "name": "ECHR case law index (judgments, decisions, resolutions, press releases)",
        "tool": "search_judgments / list_hudoc_filters",
    },
    {"name": "Full text of ECHR judgments and decisions", "tool": "get_judgment_text"},
]

_GAPS: list[dict] = [
    {
        "id": "ECHR-MCP-001",
        "family": "Full text of ECHR judgments and decisions",
        "missing": "Full text is only available where HUDOC can convert the document to Word. Anything HUDOC stores without a convertible body (some old scanned or restricted documents) surfaces as `upstream_error`.",
        "fallback": "Open the document page in HUDOC (the `source_url` on the record) and read the PDF there, or use another case-law database.",
    },
    {
        "id": "ECHR-MCP-002",
        "family": "Full text of ECHR judgments and decisions",
        "missing": "`isplaceholder=True` records are duplicates in a non-primary language and have no convertible full text. `get_judgment_text` on such an `itemid` answers `upstream_error` (HTTP 500 upstream).",
        "fallback": "Take the sibling record for the primary language - `get_judgment_text` already tries this automatically - or search HUDOC for the same `appno` in another `languageisocode`.",
    },
    {
        "id": "ECHR-MCP-003",
        "family": "ECHR case law index (judgments, decisions, resolutions, press releases)",
        "missing": "`kpdate` is HUDOC's key date, not the date of the facts and not the date the judgment became final. There is no finality or execution field in this connector.",
        "fallback": "The judgment text itself states finality (usually the Article 44 paragraph); HUDOC-EXE / coe.int tracks execution by the Committee of Ministers.",
    },
    {
        "id": "ECHR-MCP-004",
        "family": "ECHR case law index (judgments, decisions, resolutions, press releases)",
        "missing": "`article` filtering is a deep code, not a bare article number: `article=\"6\"` does not return documents tagged only `6-1`. A model that filters by article number alone will silently miss judgments.",
        "fallback": "Read the allowed codes from `list_hudoc_filters().articles` and pass the exact code (e.g. `6-1`, `P1-1`, `35-3-a`), or filter on the free text / `conclusion` instead.",
    },
    {
        "id": "ECHR-MCP-005",
        "family": "ECHR case law index (judgments, decisions, resolutions, press releases)",
        "missing": "`conclusion` is one free-text string per document, in the document's own language. There is no structured per-article violation/inadmissibility field, so counting violations per article is not reliable from this connector.",
        "fallback": "Read the judgment text (`get_judgment_text`) or use HUDOC's own Article/Violation filters on the website.",
    },
    {
        "id": "ECHR-MCP-006",
        "family": "ECHR case law index (judgments, decisions, resolutions, press releases)",
        "missing": "This connector is not a source of Polish law and not a source of domestic law at all. An ECHR judgment binds the respondent State under Art. 46 (res judicata) - it does not enact or amend Polish legislation.",
        "fallback": "For Polish legislation in force use the isap / ELI connector (eli.gov.pl); cite an ECHR judgment as case law, never as the legal basis of a Polish rule.",
    },
    {
        "id": "ECHR-MCP-007",
        "family": "ECHR case law index (judgments, decisions, resolutions, press releases)",
        "missing": "Free text is matched as a phrase against the whole document (`(\"excessive length of proceedings\")`), and results come back in HUDOC's own relevancy order. There is no boolean full-text grammar exposed by this connector, and no way to re-rank or to search only part of a judgment (facts / law / separate opinions).",
        "fallback": "Narrow with `article`, `doctype` and the `kpdate` range, page with `offset`, or use HUDOC's advanced search on the website for fielded full-text queries.",
    },
    {
        "id": "ECHR-MCP-008",
        "family": "ECHR case law index (judgments, decisions, resolutions, press releases)",
        "missing": "Press releases and advisory opinions carry their application number in `extractedappno` / `advopidentifier`, not in `appno`, so an `appno` search returns the court documents and misses those companion records.",
        "fallback": "Search by `docname` or by the free-text phrase instead, or look the application up on hudoc.echr.coe.int directly.",
    },
]


def build_coverage() -> Coverage:
    """Assemble the declared coverage for this connector."""
    return Coverage(
        status="ok",
        as_of_note=AS_OF_NOTE,
        families=[CoverageFamily(source=SOURCE, live=True, **f) for f in _FAMILIES],
        known_gaps=[CoverageGap(**g) for g in _GAPS],
    )
