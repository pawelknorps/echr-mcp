"""Ekstrakcja tekstu z .docx bez zaleznosci zewnetrznych (stdlib only).

HUDOC podaje pelny tekst tylko jako `.docx` (`/app/conversion/docx/`).
Ten modul jest czysty: `bytes` -> `str`, wiec testuje sie offline na
malym, recznie zrobionym docx-ie.
"""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree as ET

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

_WHITESPACE_RUN = re.compile(r"[ \t\u00a0]+")
_BLANK_LINES = re.compile(r"\n{2,}")


def docx_to_text(data: bytes) -> str:
    """Zamienia bajty .docx na tekst: akapity oddzielone pustym wierszem.

    Biale znaki sa normalizowane (wielokrotne spacje/taby -> jedna spacja,
    >2 puste linie -> 1). Puste akapity wypadaja.

    Raises:
        ValueError: gdy `data` nie jest archiwum .docx z `word/document.xml`.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise ValueError(f"Nie jest poprawnym .docx (word/document.xml): {exc}") from exc

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError(f"Niepoprawny XML w word/document.xml: {exc}") from exc

    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_W}p"):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{_W}t":
                parts.append(node.text or "")
            elif node.tag == f"{_W}tab":
                parts.append(" ")
        line = _WHITESPACE_RUN.sub(" ", "".join(parts)).strip()
        if line:
            paragraphs.append(line)

    return _BLANK_LINES.sub("\n\n", "\n\n".join(paragraphs))
