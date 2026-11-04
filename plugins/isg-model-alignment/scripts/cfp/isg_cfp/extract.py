"""Extraction with pypdf (bundled): page fragments with position, font and size; image positions.

Nothing here uses AI. Every page of the document is extracted (REQ-CEX-01).
"""
from __future__ import annotations

import math
import unicodedata
import zlib
from collections import Counter
from dataclasses import dataclass, field

LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st",
}
PAINT_OPS = frozenset((b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"))
GARBLED_RANGES = ((0xE000, 0xF8FF), (0xFFF0, 0xFFFF))


@dataclass
class Fragment:
    text: str
    x: float
    y: float
    size: float
    bold: bool
    width: float
    exact_width: bool


@dataclass
class ImageMark:
    x: float
    y: float
    w: float = 0.0  # size on the page, in points
    h: float = 0.0
    sig: tuple = ()  # identity of the image (same picture repeated on many pages = decoration)
    obj: object = None  # the pypdf image object (None for inline images), used by the extractor (SPEC-004)


@dataclass
class RawPage:
    number: int  # 1-based
    width: float
    height: float
    fragments: list = field(default_factory=list)
    images: list = field(default_factory=list)
    rotate: int = 0
    ligatures: Counter = field(default_factory=Counter)  # expanded ligatures (logged, REQ-CEX-03)
    paint_ops: int = 0  # path-painting operators (stroke/fill): many of them = a drawn chart, not a picture (SPEC-004 REQ-SEX-07)


def normalize_text(text: str, ligatures: Counter | None = None) -> str:
    """NFC + ligature expansion. Nothing else changes (REQ-CEX-03)."""
    out = []
    for ch in unicodedata.normalize("NFC", text):
        rep = LIGATURES.get(ch)
        if rep is not None:
            if ligatures is not None:
                ligatures[ch] += 1
            out.append(rep)
        else:
            out.append(ch)
    return "".join(out)


def is_garbled_char(ch: str) -> bool:
    o = ord(ch)
    if ch == "�":
        return True
    if o < 0x20 and ch not in "\t\n\r":
        return True
    return any(lo <= o <= hi for lo, hi in GARBLED_RANGES)


def _text_width(text: str, size: float, font) -> tuple[float, bool]:
    """Width of text in points. Exact from the font's /Widths when available, else 0.5 em per character."""
    try:
        first = int(font.get("/FirstChar"))
        widths = font.get("/Widths")
        if widths is not None:
            total = 0.0
            for ch in text:
                code = ord(ch) - first
                if code < 0 or code >= len(widths):
                    raise ValueError("outside widths")
                total += float(widths[code])
            return total / 1000.0 * size, True
    except Exception:
        pass
    return len(text) * size * 0.5, False


def _effective(cm, tm, font_size):
    a, b, c, d, e, f = (float(v) for v in cm)
    a2, b2, c2, d2, e2, f2 = (float(v) for v in tm)
    x = e2 * a + f2 * c + e
    y = e2 * b + f2 * d + f
    scale = math.hypot(c2, d2) * math.hypot(c, d)
    size = abs(float(font_size or 0) * (scale if scale > 0 else 1.0))
    return x, y, size


def open_reader(path):
    """Returns (reader, error_code). error_code: None | 'PDF_PROTEGIDO' | 'PDF_INVALIDO'."""
    from pypdf import PdfReader  # vendored; imported lazily so the CLI can report a missing library

    try:
        reader = PdfReader(str(path))
    except Exception:
        return None, "PDF_INVALIDO"
    try:
        if reader.is_encrypted:
            return None, "PDF_PROTEGIDO"
        if len(reader.pages) == 0:
            return None, "PDF_INVALIDO"
    except Exception:
        return None, "PDF_PROTEGIDO"
    return reader, None


def extract_page(reader, index: int) -> RawPage:
    page = reader.pages[index]
    box = page.mediabox
    left, bottom = float(box.left), float(box.bottom)
    width, height = float(box.width), float(box.height)
    raw = RawPage(number=index + 1, width=width, height=height)
    try:
        raw.rotate = int(page.get("/Rotate", 0) or 0)
    except Exception:
        raw.rotate = 0

    resources = page.get("/Resources")
    xobjects = None
    try:
        xobjects = resources.get_object().get("/XObject") if resources is not None else None
        xobjects = xobjects.get_object() if xobjects is not None else None
    except Exception:
        xobjects = None

    def visitor_text(text, cm, tm, font_dict, font_size):
        if text is None or text == "" or text.strip() == "":
            return
        x, y, size = _effective(cm, tm, font_size)
        norm = normalize_text(text, raw.ligatures)
        font = font_dict if font_dict is not None else {}
        try:
            base = str(font.get("/BaseFont", "")).lower()
        except Exception:
            base = ""
        bold = any(k in base for k in ("bold", "black", "heavy", "semibold", "demi"))
        w, exact = _text_width(text, size, font)
        raw.fragments.append(Fragment(norm, x - left, y - bottom, size if size > 0 else float(font_size or 10), bold, w, exact))

    def visitor_operand(operator, operand_args, cm, tm):
        if operator in PAINT_OPS:
            raw.paint_ops += 1
        if operator == b"Do" and xobjects is not None and operand_args:
            try:
                xo = xobjects.get(operand_args[0])
                xo = xo.get_object() if xo is not None else None
                if xo is not None and xo.get("/Subtype") == "/Image":
                    a, b, c, d, e, f = (float(v) for v in cm)
                    data = getattr(xo, "_data", b"") or b""
                    sig = (int(xo.get("/Width", 0) or 0), int(xo.get("/Height", 0) or 0), len(data), zlib.crc32(data))  # same bytes = same picture
                    raw.images.append(ImageMark(e - left, (f + d) - bottom, math.hypot(a, b), math.hypot(c, d), sig, xo))
            except Exception:
                pass
        elif operator == b"INLINE IMAGE":
            try:
                a, b, c, d, e, f = (float(v) for v in cm)
                raw.images.append(ImageMark(e - left, (f + d) - bottom, math.hypot(a, b), math.hypot(c, d), ("inline", round(a), round(d))))
            except Exception:
                pass

    page.extract_text(visitor_text=visitor_text, visitor_operand_before=visitor_operand)
    return raw


def raw_plain_text(reader, index: int) -> str:
    """pypdf's own plain extraction of a page, for side-by-side checks (`cfp pagina`)."""
    return normalize_text(reader.pages[index].extract_text() or "")


def pdf_metadata(reader) -> dict:
    out = {}
    try:
        md = reader.metadata
        if md:
            for key, name in (("title", "titulo"), ("author", "autor"), ("producer", "produtor"), ("creator", "criador")):
                v = getattr(md, key, None)
                if v:
                    out[name] = str(v)
            raw = md.get("/CreationDate") if hasattr(md, "get") else None
            if raw:
                out["criacao"] = str(raw)
    except Exception:
        pass
    return out
