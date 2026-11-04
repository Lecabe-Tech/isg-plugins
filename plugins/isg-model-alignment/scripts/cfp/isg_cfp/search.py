"""Code-only search over the chunks (SPEC-003 2.7). Accent- and case-insensitive; zero AI tokens."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

MARKER = re.compile(r"^<!-- página (\d+)")
EXCERPT = 200


def fold(text: str) -> tuple[str, list]:
    """Lower-cases and removes accents; returns the folded text and, for each folded char, its index in the original."""
    out, idx = [], []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKD", ch):
            if unicodedata.combining(c):
                continue
            out.append(c.lower())
            idx.append(i)
    return "".join(out), idx


def parse_query(query: str) -> list:
    terms = []
    for m in re.finditer(r'"([^"]+)"|(\S+)', query):
        t = m.group(1) or m.group(2)
        folded, _ = fold(t)
        folded = re.sub(r"\s+", " ", folded).strip()
        if folded:
            terms.append(folded)
    return terms


def _body_without_front_matter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5:]
    return text


def split_pages(chunk_text: str) -> list:
    """[(page, text)] using the page markers (the marker line itself, with header/footer, belongs to its page)."""
    body = _body_without_front_matter(chunk_text)
    pages, cur_page, cur = [], None, []
    for line in body.split("\n"):
        m = MARKER.match(line)
        if m:
            if cur_page is not None:
                pages.append((cur_page, "\n".join(cur)))
            cur_page, cur = int(m.group(1)), [line]  # the marker line (with header/footer) belongs to its page
        else:
            cur.append(line)
    if cur_page is not None:
        pages.append((cur_page, "\n".join(cur)))
    return pages


def iter_documents(cfp_root: Path, uf=None, ano=None, doc=None):
    if doc:
        d = Path(doc)
        if not d.is_absolute():
            d = cfp_root / doc
        if d.is_dir():
            yield d
        return
    if not cfp_root.is_dir():
        return
    for uf_dir in sorted(p for p in cfp_root.iterdir() if p.is_dir()):
        if uf and uf_dir.name.upper() != uf.upper():
            continue
        for ano_dir in sorted(p for p in uf_dir.iterdir() if p.is_dir()):
            if ano and ano_dir.name != str(ano):
                continue
            for d in sorted(p for p in ano_dir.iterdir() if p.is_dir() and not p.name.endswith(".tmp") and ".tmp-" not in p.name):
                if (d / "chunks").is_dir() and "-substituido-" not in d.name:
                    yield d


def search(cfp_root: Path, query: str, uf=None, ano=None, doc=None, limit: int = 50, with_images: bool = False) -> dict:
    terms = parse_query(query)
    if not terms:
        return {"hits": [], "total": 0, "termos": []}
    hits = []
    for d in iter_documents(cfp_root, uf, ano, doc):
        folder = d / "chunks_com_imagens" if with_images and (d / "chunks_com_imagens").is_dir() else d / "chunks"
        for chunk_file in sorted(folder.glob("*.md")):
            for page, text in split_pages(chunk_file.read_text(encoding="utf-8")):
                folded, idx = fold(text)
                folded_flat = re.sub(r"\s+", " ", folded)
                if all(t in folded_flat for t in terms):
                    # the excerpt comes from the body when the first term is there (not from the marker line)
                    marker_line, _, body = text.partition("\n")
                    source = body if body.strip() and terms[0] in re.sub(r"\s+", " ", fold(body)[0]) else marker_line.replace("<!--", "").replace("-->", "")
                    sfolded, sidx = fold(source)
                    pos = sfolded.find(terms[0])
                    if pos < 0:  # first term only matches across a whitespace difference
                        pos = 0
                    start = max(0, sidx[pos] - EXCERPT // 3) if sidx else 0
                    excerpt = re.sub(r"\s+", " ", source[start:start + EXCERPT]).strip()
                    hit = {"documento": d.name, "pasta": f"{d.parent.parent.name}/{d.parent.name}/{d.name}", "chunk": chunk_file.stem, "pagina": page, "trecho": excerpt}
                    if with_images and _only_in_image_blocks(text, terms):
                        hit["origem"] = "interpretação de imagem"
                    hits.append(hit)
    total = len(hits)
    return {"hits": hits[:limit], "total": total, "termos": terms}


def _only_in_image_blocks(text: str, terms: list) -> bool:
    """True when the terms are found in the SIP blocks of the page but not in the page's own (original) text."""
    blocks = " ".join(m.group(0) for m in re.finditer(r"<!-- SIP início.*?<!-- SIP fim[^\n]*-->", text, re.S))
    if not blocks:
        return False
    rest = text.replace(blocks, "")
    for m in re.finditer(r"<!-- SIP início.*?<!-- SIP fim[^\n]*-->", text, re.S):
        rest = rest.replace(m.group(0), " ")
    folded_rest = re.sub(r"\s+", " ", fold(rest)[0])
    return not all(t in folded_rest for t in terms)


def list_documents(cfp_root: Path, uf=None, ano=None) -> list:
    p = cfp_root / "catalogo.json"
    if not p.exists():
        return []
    docs = json.loads(p.read_text(encoding="utf-8")).get("documentos", [])
    return [d for d in docs if (not uf or d["uf"] == uf.upper()) and (not ano or str(d["ano"]) == str(ano))]
