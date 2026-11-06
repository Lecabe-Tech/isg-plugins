"""Quote verification (SPEC-005 REQ-CRS-03, decision E4): a quote counts only if it is found in the cited page of the cited document.

The comparison ignores accents, case, spacing, punctuation, quotation marks, hyphens and line breaks (so a quote copied from
a PDF matches the chunk text), but the letters and digits must be the same: it is a verbatim check, not a similarity score.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

MIN_FRAGMENT = 20  # a fragment shorter than this (letters and digits) is too weak to prove anything
ELLIPSIS = re.compile(r"\[\s*\.\.\.\s*\]|\(\s*\.\.\.\s*\)|\.{3}|…")


def squash(text: str) -> str:
    """Letters and digits only, lower case, without accents."""
    t = unicodedata.normalize("NFKD", str(text))
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in t if not unicodedata.combining(c)).lower())


def fragments(quote: str) -> list:
    """A quote with '…' or '[...]' is checked piece by piece (each piece must be found, in any order on the page)."""
    parts = [squash(p) for p in ELLIPSIS.split(quote)]
    return [p for p in parts if p]


def verify(quote: str, page_text: str) -> dict:
    """{'ok': bool, 'motivo': str, 'fragmentos': n}. ok needs every fragment to be found and the quote to have substance."""
    frags = fragments(quote)
    if not frags:
        return {"ok": False, "motivo": "citação vazia", "fragmentos": 0}
    if sum(len(f) for f in frags) < MIN_FRAGMENT:
        return {"ok": False, "motivo": "citação curta demais para servir de prova", "fragmentos": len(frags)}
    page = squash(page_text)
    missing = [f for f in frags if f not in page]
    if missing:
        return {"ok": False, "motivo": "trecho não encontrado na página citada", "fragmentos": len(frags)}
    return {"ok": True, "motivo": "", "fragmentos": len(frags)}


def load_pages(doc_dir, folder: str = "chunks") -> dict:
    """{page number: text} of a CFP document: its ORIGINAL chunks by default; folder="chunks_com_imagens" for AI image interpretations."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cfp"))
    from isg_cfp.search import split_pages  # the same page splitting the CFP search uses

    pages: dict = {}
    for chunk in sorted((Path(doc_dir) / folder).glob("*.md")):
        for page, text in split_pages(chunk.read_text(encoding="utf-8")):
            pages[page] = pages.get(page, "") + "\n" + text
    return pages
