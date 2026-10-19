"""httpx async client dla HUDOC (hudoc.echr.coe.int, Rada Europy).

API jest publiczne, bez auth, JSON-only (`Accept: application/json`).

Dwie pulapki kontraktu, zweryfikowane na zywym HUDOC 2026-10-19:
  - `/app/query/results` zwraca **404**, gdy brakuje parametru `sort` (moze byc pusty) -
    dlatego `sort=""` jedzie w kazdym zapytaniu.
  - pelny tekst jest tylko jako `.docx` (`/app/conversion/docx/`); wariant HTML
    (`/app/conversion/...` bez `docx`) zwraca 404, a brak konwersji daje HTTP 500.
"""

from __future__ import annotations

import asyncio
from typing import Self

import httpx

from . import BASE_URL, USER_AGENT
from .models import SEARCH_SELECT

_QUERY_RESULTS = "/app/query/results"
_DOCX_CONVERSION = "/app/conversion/docx/"

#: .docx to ZIP - po tym poznajemy, ze konwersja naprawde zwrocila dokument.
_ZIP_MAGIC = b"PK\x03\x04"


class EchrClient:
    """Async HTTP client dla HUDOC.

    Uzywaj jako async context manager:
        async with EchrClient() as c:
            raw, url = await c.search("(contentsitename=ECHR)", limit=50, offset=0)
    """

    def __init__(self, timeout: float = 60.0):
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                # Cloudflare na HUDOC fingerprintuje KOMPLETNOSC naglowkow, nie UA:
                # sam UA+Accept -> 403 "Just a moment..." (text/html, bez JS nie do przejscia),
                # a ten sam httpx z pelnym zestawem przegladarki -> 200 JSON.
                # Zweryfikowane 2026-10-19 (6/6 zapytan + .docx). Nie skracac tego zbioru.
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "sec-ch-ua": '"Chromium";v="126", "Not.A/Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
            },
            timeout=timeout,
            follow_redirects=True,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, url: str, params: dict, max_retries: int = 3) -> httpx.Response:
        """GET + retry/backoff na 429/503. 4xx/5xx leca jako HTTPStatusError."""
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                resp = await self._client.get(url, params=params)
            except httpx.RequestError as exc:
                last_exc = exc
                await asyncio.sleep(2**attempt)
                continue

            # 403 z HTML-em "Just a moment..." to challenge Cloudflare, nie odmowa
            # API. Ten sam request go nie przejdzie (brak JS), ale ponowienie ma sens:
            # challenge bywa tez przejsciowym rate-limitowym odbiciem przy burstach.
            challenged = resp.status_code == 403 and "text/html" in (
                resp.headers.get("content-type") or ""
            )
            if resp.status_code in (429, 503) or challenged:
                wait = resp.headers.get("Retry-After")
                try:
                    delay = float(wait) if wait is not None else 2**attempt
                except ValueError:
                    delay = 2**attempt
                await asyncio.sleep(min(delay, 60.0))
                continue

            resp.raise_for_status()
            return resp

        if last_exc is not None:
            raise last_exc
        raise httpx.HTTPError(f"Failed after {max_retries} retries: {url}")

    async def search(self, query: str, limit: int = 50, offset: int = 0) -> tuple[dict, str]:
        """Wyszukiwanie HUDOC; `query` to gotowe zapytanie w gramatyce HUDOC.

        Returns:
            (parsed_json, full_url)
        """
        resp = await self._get(
            _QUERY_RESULTS,
            params={
                "query": query,
                "select": SEARCH_SELECT,
                "sort": "",  # wymagane przez HUDOC - brak = HTTP 404
                "start": offset,
                "length": limit,
            },
        )
        return resp.json(), str(resp.request.url)

    async def download_docx(self, itemid: str) -> tuple[bytes, str]:
        """Pobiera pelny tekst dokumentu jako `.docx` (ZIP).

        Returns:
            (bajty docx, full_url)
        """
        resp = await self._get(
            _DOCX_CONVERSION,
            params={"library": "ECHR", "id": itemid, "filename": itemid, "logEvent": "false"},
        )
        if not resp.content.startswith(_ZIP_MAGIC):
            raise httpx.HTTPError(
                f"HUDOC nie zwrocil .docx dla itemid={itemid} "
                f"(content-type={resp.headers.get('content-type')!r})."
            )
        return resp.content, str(resp.request.url)
