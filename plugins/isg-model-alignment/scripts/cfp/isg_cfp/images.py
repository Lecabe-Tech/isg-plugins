"""Image extraction (SPEC-004 S1): saves the pictures of a PDF as files, deterministically. No AI, no network.

JPEG streams are copied byte for byte; raw 8-bit streams are written as PNG with the standard library. Whatever cannot
be extracted is listed with the reason (REQ-SEX-02): nothing is skipped silently.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import pngwriter

MIN_SHORT_SIDE_PX = 200  # SPEC-004 Q-1 proposal: smaller pictures are not interpreted by default
MAX_SIDE_PX = 8000
MAX_BYTES = 10 * 1024 * 1024
CONTEXT_CHARS = 300
LEGEND_WORDS = ("figura", "gráfico", "grafico", "quadro", "tabela", "fonte", "imagem", "mapa", "infográfico")
SIMPLE_SPACES = {"/DeviceGray": ("L", 1), "/CalGray": ("L", 1), "/DeviceRGB": ("RGB", 3), "/CalRGB": ("RGB", 3), "/DeviceCMYK": ("CMYK", 4)}
SUPPORTED_FILTERS = ("/FlateDecode", "/Fl", "/LZWDecode", "/LZW", "/ASCII85Decode", "/A85", "/ASCIIHexDecode", "/AHx", "/RunLengthDecode", "/RL")


def _deref(o):
    try:
        return o.get_object()
    except Exception:
        return o


def _name(v) -> str:
    return str(v) if v is not None else ""


def _filters(xo) -> list:
    f = _deref(xo.get("/Filter"))
    if f is None:
        return []
    if isinstance(f, str):
        return [str(f)]
    try:
        return [_name(_deref(x)) for x in f]  # pypdf ArrayObject
    except TypeError:
        return [_name(f)]


def _colorspace_obj(cs):
    """(kind, components, palette) with kind in L, RGB, CMYK, P; None when unsupported."""
    cs = _deref(cs)
    if cs is None:
        return None
    if isinstance(cs, str):
        r = SIMPLE_SPACES.get(cs)
        return (r[0], r[1], None) if r else None
    try:
        items = [_deref(x) for x in cs]
    except TypeError:
        return None
    if not items:
        return None
    kind = _name(items[0])
    if kind in SIMPLE_SPACES:
        r = SIMPLE_SPACES[kind]
        return (r[0], r[1], None)
    if kind == "/ICCBased":
        try:
            n = int(items[1].get("/N"))
        except Exception:
            return None
        return {1: ("L", 1, None), 3: ("RGB", 3, None), 4: ("CMYK", 4, None)}.get(n)
    if kind in ("/Indexed", "/I") and len(items) >= 4:
        base = _colorspace_obj(items[1])
        if base is None or base[0] not in ("L", "RGB", "CMYK"):
            return None
        lookup = items[3]
        try:
            lookup = lookup.get_data() if hasattr(lookup, "get_data") else (lookup.original_bytes if hasattr(lookup, "original_bytes") else bytes(lookup))
        except Exception:
            return None
        pal = bytearray()
        for i in range(int(items[2]) + 1):
            if base[0] == "L":
                pal += (lookup[i:i + 1] or b"\x00") * 3
            elif base[0] == "RGB":
                pal += (lookup[i * 3:i * 3 + 3] or b"\x00\x00\x00").ljust(3, b"\x00")
            else:
                pal += pngwriter.cmyk_to_rgb((lookup[i * 4:i * 4 + 4] or b"\x00\x00\x00\x00").ljust(4, b"\x00"))
        return ("P", 1, bytes(pal))
    return None


def extract_image(xo) -> dict:
    """One image object -> {'ok': True, 'ext': 'jpg'|'png', 'data': bytes, 'w':, 'h':} or {'ok': False, 'motivo': str}."""
    try:
        w, h = int(xo.get("/Width")), int(xo.get("/Height"))
    except Exception:
        return {"ok": False, "motivo": "dimensões ausentes"}
    base = {"w": w, "h": h}
    if _name(_deref(xo.get("/ImageMask"))).lower() == "true":
        return {**base, "ok": False, "motivo": "máscara de imagem (stencil) não suportada"}
    filters = _filters(xo)
    try:
        if filters in (["/DCTDecode"], ["/DCT"]):
            data = bytes(getattr(xo, "_data", b"") or b"")
            if not (data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"):
                return {**base, "ok": False, "motivo": "JPEG inválido ou truncado"}
            return {**base, "ok": True, "ext": "jpg", "data": data}
        unsupported = [f for f in filters if f not in SUPPORTED_FILTERS]
        if unsupported:
            return {**base, "ok": False, "motivo": f"codificação não suportada ({unsupported[0].lstrip('/')})"}
        cs = _colorspace_obj(xo.get("/ColorSpace"))
        if cs is None:
            return {**base, "ok": False, "motivo": "espaço de cor não suportado"}
        bits = int(_deref(xo.get("/BitsPerComponent")) or 8)
        data = xo.get_data()
        kind, comps, palette = cs
        if bits == 1 and kind == "L":
            return {**base, "ok": True, "ext": "png", "data": pngwriter.encode_png(w, h, pngwriter.expand_1bit_gray(data, w, h), "L")}
        if bits != 8:
            return {**base, "ok": False, "motivo": f"{bits} bits por componente não suportado"}
        if len(data) < w * h * comps:
            return {**base, "ok": False, "motivo": "dados da imagem incompletos"}
        data = data[:w * h * comps]
        if kind == "CMYK":
            return {**base, "ok": True, "ext": "png", "data": pngwriter.encode_png(w, h, pngwriter.cmyk_to_rgb(data), "RGB")}
        return {**base, "ok": True, "ext": "png", "data": pngwriter.encode_png(w, h, data, kind, palette)}
    except Exception as e:  # a damaged stream must not stop the document
        return {**base, "ok": False, "motivo": f"falha ao ler a imagem ({type(e).__name__})"}


def valid_file(path: Path) -> bool:
    """Q12: the written file really is an image."""
    try:
        b = path.read_bytes()
    except OSError:
        return False
    if path.suffix == ".jpg":
        return b[:2] == b"\xff\xd8" and b[-2:] == b"\xff\xd9"
    try:
        pngwriter.decode_png_samples(b)
        return True
    except Exception:
        return False


def _legend(texts: list) -> str:
    for t in texts:
        s = t.strip()
        if any(s.lower().startswith(w) for w in LEGEND_WORDS):
            return s
    return ""


def extract_document_images(raw_pages: list, decorative: frozenset, outdir: Path, chunk_of_page: dict, include_small: bool = False) -> list:
    """Writes outdir/<id>.<ext> for each non-decorative image and returns the index entries (SPEC-004 4.5)."""
    from .organize import _is_small, image_id

    outdir.mkdir(parents=True, exist_ok=True)
    entries, seen = [], {}
    for rp in raw_pages:
        visible = [im for im in rp.images if im.sig not in decorative]
        page_area = max(rp.width * rp.height, 1.0)
        frags = sorted(rp.fragments, key=lambda f: -f.y)  # top of the page first (y grows upward)
        for k, im in enumerate(visible, 1):
            iid = image_id(rp.number, k)
            top, bottom = im.y, im.y - im.h  # ImageMark.y is the image's TOP edge (see extract.py)
            share = round((im.w * im.h) / page_area, 4)
            above = [f for f in frags if f.y > top]
            below = [f for f in frags if f.y < bottom]
            near = [f.text for f in below if bottom - f.y < 60] + [f.text for f in above if f.y - top < 40]
            whole = share >= 0.6 or not rp.fragments
            small = _is_small(im, rp)
            entry = {"id": iid, "pagina": rp.number, "x": round(im.x, 1), "y": round(im.y, 1), "largura": round(im.w, 1), "altura": round(im.h, 1),
                     "pixels": None, "formato": None, "arquivo": None, "sha256": None, "area_pagina": share, "pagina_inteira": whole, "igual_a": None,
                     "texto_antes": " ".join(f.text.strip() for f in above[-8:])[-CONTEXT_CHARS:], "texto_depois": " ".join(f.text.strip() for f in below[:8])[:CONTEXT_CHARS],
                     "legenda": _legend(near), "chunk": chunk_of_page.get(rp.number), "estado": "pendente", "motivo": None}
            if small and not include_small and not whole:
                entry.update(estado="pequena", motivo="ícone pequeno: não extraído (use --incluir-pequenas)")
                entries.append(entry)
                continue
            if im.obj is None:
                entry.update(estado="não extraível", motivo="imagem embutida no fluxo da página (inline) não suportada")
                entries.append(entry)
                continue
            r = extract_image(im.obj)
            entry["pixels"] = [r.get("w"), r.get("h")]
            if not r["ok"]:
                entry.update(estado="não extraível", motivo=r["motivo"])
                entries.append(entry)
                continue
            data = r["data"]
            digest = hashlib.sha256(data).hexdigest()
            entry.update(formato=r["ext"], sha256=digest)
            if max(r["w"], r["h"]) > MAX_SIDE_PX or len(data) > MAX_BYTES:
                entry.update(estado="grande demais", motivo="acima de 8000 px ou 10 MB (limite da visão do Claude)")
            elif min(r["w"], r["h"]) < MIN_SHORT_SIDE_PX and not include_small and not whole:
                entry.update(estado="pequena", motivo=f"lado menor abaixo de {MIN_SHORT_SIDE_PX} px: não interpretada por padrão")
            if digest in seen:
                entry["igual_a"] = seen[digest]
            else:
                path = outdir / f"{iid}.{r['ext']}"
                path.write_bytes(data)
                if not valid_file(path):
                    path.unlink(missing_ok=True)
                    entry.update(estado="não extraível", motivo="arquivo gravado não abre como imagem", formato=None, sha256=None)
                    entries.append(entry)
                    continue
                entry["arquivo"] = path.name
                seen[digest] = iid
            entries.append(entry)
    return entries


def write_index(outdir: Path, entries: list) -> None:
    (outdir / "index.json").write_text(json.dumps({"imagens": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def reextract(doc: Path, include_small: bool = False) -> list:
    """`cfp imagens`: extracts (again) the images of an already processed document from its original.pdf.

    Idempotent and non-destructive: image files are rewritten with identical bytes; interpretations (*.md) are kept and
    their state is carried over to the new index."""
    from .extract import extract_page, open_reader
    from .organize import _recurring_images

    reader, err = open_reader(doc / "original.pdf")
    if err:
        raise ValueError("Não consegui abrir original.pdf deste documento.")
    raw_pages = [extract_page(reader, i) for i in range(len(reader.pages))]
    index = json.loads((doc / "index.json").read_text(encoding="utf-8"))
    chunk_of_page = {}
    for c in index.get("chunks", []):
        a, _, b = str(c["paginas"]).partition("-")
        for p in range(int(a), int(b or a) + 1):
            chunk_of_page.setdefault(p, c["chunk"])
    old = {}
    p_old = doc / "imagens" / "index.json"
    if p_old.exists():
        old = {e["id"]: e for e in json.loads(p_old.read_text(encoding="utf-8"))["imagens"]}
    entries = extract_document_images(raw_pages, _recurring_images(raw_pages), doc / "imagens", chunk_of_page, include_small)
    for e in entries:
        o = old.get(e["id"])
        if o and o.get("estado") in ("interpretada", "corrigida") and o.get("sha256") == e.get("sha256"):
            e["estado"] = o["estado"]
    write_index(doc / "imagens", entries)
    return entries
