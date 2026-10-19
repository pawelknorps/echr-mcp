"""Offline testy ekstrakcji tekstu z .docx (HUDOC wydaje pelny tekst tylko tak)."""

from __future__ import annotations

import io
import zipfile

import pytest

from echr_mcp.text import docx_to_text

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

EXPECTED = (
    "CASE OF TEST v. POLAND\n\n"
    "1. The applicant complained under Article 8 of the Convention.\n\n"
    "STRASBOURG\n\n"
    "11 April 2023"
)


def _docx(*chunks: str, part: str = "word/document.xml") -> bytes:
    """Sklada .docx z surowych fragmentow body (kazdy test daje wlasne <w:p>)."""
    xml = f'<w:document xmlns:w="{W}"><w:body>{"".join(chunks)}</w:body></w:document>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(part, xml.encode("utf-8"))
    return buffer.getvalue()


def _p(*runs: str) -> str:
    return f"<w:p>{''.join(runs)}</w:p>"


def test_extracts_paragraphs_from_the_crafted_fixture(fixture_bytes):
    assert docx_to_text(fixture_bytes("minimal.docx")) == EXPECTED


def test_collapses_whitespace_and_drops_empty_paragraphs():
    data = _docx(
        _p("<w:r><w:t xml:space='preserve'>  spaced   </w:t></w:r>"),
        _p(),
        _p("<w:r><w:t>a</w:t></w:r><w:r><w:t xml:space='preserve'>   </w:t></w:r>"),
    )
    assert docx_to_text(data) == "spaced\n\na"


def test_tabs_become_a_single_space():
    assert docx_to_text(_docx(_p("<w:r><w:t>L</w:t><w:tab/><w:t>R</w:t></w:r>"))) == "L R"


def test_nbsp_is_collapsed():
    assert docx_to_text(_docx(_p("<w:r><w:t>Article\u00a08</w:t></w:r>"))) == "Article 8"


def test_text_in_a_table_cell_is_kept():
    table = "<w:tbl><w:tr><w:tc>" + _p("<w:r><w:t>cell</w:t></w:r>") + "</w:tc></w:tr></w:tbl>"
    assert docx_to_text(_docx(table)) == "cell"


def test_not_a_zip_raises_value_error():
    with pytest.raises(ValueError, match="word/document.xml"):
        docx_to_text(b"<html>HTTP 500 - konwersja sie nie udala</html>")


def test_zip_without_document_xml_raises_value_error():
    with pytest.raises(ValueError, match="word/document.xml"):
        docx_to_text(_docx(_p("<w:r><w:t>x</w:t></w:r>"), part="word/other.xml"))
