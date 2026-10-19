# echr-mcp

Serwer MCP dla **orzecznictwa Europejskiego Trybunału Praw Człowieka**: indeks
wyroków, decyzji, uchwał Komitetu Ministrów i komunikatów prasowych oraz pełny
tekst orzeczeń. Źródło: oficjalne **HUDOC** Rady Europy
(`hudoc.echr.coe.int`, JSON, bez auth).

Orzeczenia ETPC to **nie** źródło prawa polskiego — wyrok wiąże pozwane państwo
(art. 46), ale nie tworzy ani nie zmienia polskich przepisów. Po polskie prawo
idź do konektora `isap`/`eli`.

## Instalacja

```bash
uv venv && uv pip install -e ".[dev]"
```

## Narzędzia

| Tool | Opis |
|------|------|
| `search_judgments(query, appno, article, kpdate_from, kpdate_to, doctype, limit, offset)` | indeks HUDOC; warunki AND-owane do bazy `(contentsitename=ECHR)`; zwraca `resultcount` (wszystkie trafienia) + stronę `items` |
| `get_judgment_text(itemid, language)` | pełny tekst orzeczenia (HUDOC wydaje go tylko jako `.docx`; konwersja lokalnie, stdlib) |
| `list_hudoc_filters()` | statyczny słownik zapytań: gramatyka, pola, operatory, kody typów dokumentów, języków, artykułów, kolekcji (bez sieci) |
| `echr_coverage()` | co konektor pokrywa, a czego nie (każda luka ma `fallback`) |

## Uruchomienie

```bash
echr-mcp                        # stdio
python -m echr_mcp.server
```

## Kontrakt HUDOC (zweryfikowany 2026-10-19)

Wyszukiwanie:

```
GET /app/query/results?query=<urlencoded>&select=<pola>&sort=&start=<offset>&length=<n>
```

- **`sort` musi być obecny** (może być pusty) — bez niego HUDOC zwraca HTTP 404.
- Pełny tekst: `GET /app/conversion/docx/?library=ECHR&id=<itemid>&filename=<itemid>`
  zwraca `.docx` (ZIP). Wariant HTML (bez `docx`) zwraca 404, a dokument bez
  konwertowalnego tekstu — HTTP 500.

## Rozwój

```bash
pytest              # offline (fixture'y + mock klienta)
ruff check src tests
pytest -m smoke -v  # live hudoc.echr.coe.int
```

Audit log: `~/.matematic/audit/echr-mcp.jsonl`
(override: `ECHR_MCP_AUDIT_DIR`). Logowane są metadane wywołań
(params_hash, result_summary, source_urls, latency_ms) — bez pełnych treści orzeczeń.
