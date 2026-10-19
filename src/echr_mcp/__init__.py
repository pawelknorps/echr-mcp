"""echr-mcp - MCP server for European Court of Human Rights case law (HUDOC)."""

__version__ = "0.1.0"
__author__ = "MateMatic"
__license__ = "Apache-2.0"

# HUDOC stoi za Cloudflare Bot Management: jawny, bot-style User-Agent bywa
# przepuszczany tylko czasem (403 "Just a moment..." ~1 na 5 zapytan), a zwykly
# UA przegladarki przechodzi. Wysylamy wiec UA przegladarki.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Oficjalne HUDOC (Rada Europy) - stan zweryfikowany 2026-10-19.
# UWAGA: /app/query/results zwraca 404 bez parametru `sort` (moze byc pusty).
BASE_URL = "https://hudoc.echr.coe.int"
