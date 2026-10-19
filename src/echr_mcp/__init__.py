"""echr-mcp - MCP server for European Court of Human Rights case law (HUDOC)."""

__version__ = "0.1.0"
__author__ = "MateMatic"
__license__ = "Apache-2.0"

USER_AGENT = f"matematic-echr-mcp/{__version__} (+https://matematic.co; kontakt@matematic.co)"

# Oficjalne HUDOC (Rada Europy) - stan zweryfikowany 2026-10-19.
# UWAGA: /app/query/results zwraca 404 bez parametru `sort` (moze byc pusty).
BASE_URL = "https://hudoc.echr.coe.int"
