"""Organising the extracted text of each page (SPEC-003 2.3).

NOTHING is removed from the text. Running headers/footers and printed page numbers are moved into the page
marker; line breaks inside paragraphs and line-end hyphens are joined (every hyphen join is logged).
Doubtful layouts (columns, tables, images, empty pages) are flagged, never hidden.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field

from .extract import Fragment, RawPage, is_garbled_char

BAND = 0.08  # top/bottom 8 % of the page height
RUNNING_SHARE = 0.5
SMALL_IMAGE_SHARE = 0.02

NUMBER_LINE = re.compile(r"^(?:p[áa]gina|p[áa]g\.?|p\.)?\s*\d{1,4}(?:\s*(?:/|de)\s*\d{1,4})?$", re.IGNORECASE)
LIST_START = re.compile(r"^(?:[•·▪●○◦■□–—\-*]\s|\d{1,3}[.)]\s|[a-zA-Z][.)]\s|\([a-zA-Z0-9]{1,3}\)\s)")
HEADING_NUMBERING = re.compile(
    r"^(?:\d+(?:\.\d+){0,3}\.?\s+\S|[IVX]{1,6}\s*[–—.\-]\s*\S|CAP[ÍI]TULO\b|Cap[íi]tulo\b|COMPONENTE\b|Componente curricular\b|"
    r"UNIDADE\b|Unidade\b|[ÁA]REA\b|[Áá]rea de conhecimento\b)"
)

TOC_LEADER = re.compile(r"(\.{4,}|…{2,}|(?:\. ){4,})")  # table-of-contents lines: "Capítulo 1 ........ 5"
BULLET_ONLY = re.compile(r"^(?:[•·▪●○◦■□–—\-*]|\d{1,3}[.)]|[a-zA-Z][.)])$")
BULLET_START = re.compile(r"^[•·▪●○◦■□–—\-*]\s")
LINE_END_HYPHENS = {"-", "‐", "­"}
FLAG_COLUMNS = "duas colunas — ordem de leitura inferida"
FLAG_TABLE = "tabela"
FLAG_IMAGE = "imagem não processada"
FLAG_NOTEXT = "página sem texto extraível"
FLAG_IMAGE_ONLY = "página quase só imagem"
FLAG_GARBLED = "texto possivelmente corrompido"
FLAG_ROTATED = "página rotacionada"
FLAG_VECTOR = "possível gráfico vetorial — conferir no PDF"
VECTOR_OPS_THRESHOLD = 200
FLAG_UNCERTAIN = "ordem de leitura incerta"


@dataclass
class Seg:
    x0: float
    x1: float
    text: str
    size: float
    bold: bool


@dataclass
class Line:
    y: float
    segs: list
    kind: str = "text"  # text | image
    small: bool = False  # image: less than 2 % of the page area (icon, bullet, logo)
    frags: list = field(default_factory=list)  # the text fragments of this line (used for column detection)
    ref: str = ""  # image id, for image lines

    @property
    def text(self) -> str:
        return "    ".join(s.text for s in self.segs) if len(self.segs) > 1 else (self.segs[0].text if self.segs else "")

    @property
    def x0(self) -> float:
        return min(s.x0 for s in self.segs)

    @property
    def x1(self) -> float:
        return max(s.x1 for s in self.segs)

    @property
    def size(self) -> float:
        return max((s.size for s in self.segs), default=0.0)

    @property
    def bold(self) -> bool:
        return bool(self.segs) and all(s.bold for s in self.segs)


@dataclass
class Block:
    type: str  # para | heading | image | table_start | table_end | table_row | notext
    text: str = ""
    page: int = 0
    level: int = 0
    ref: str = ""  # image id (SPEC-004), e.g. p047-02


@dataclass
class PageResult:
    number: int
    header: list = field(default_factory=list)
    footer: list = field(default_factory=list)
    printed_number: list = field(default_factory=list)
    blocks: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    images: int = 0  # images that are not recurring decoration
    images_small: int = 0
    vector_ops: int = 0
    images_decorative: int = 0  # the same picture on many pages (header/footer bands, logos): counted, not flagged
    chars: int = 0
    lines: int = 0
    garbled: int = 0
    hyphens_removed: Counter = field(default_factory=Counter)
    hyphen_joins: list = field(default_factory=list)
    ligatures: dict = field(default_factory=dict)
    widths_estimated: bool = False
    raw_chars: Counter = field(default_factory=Counter)


def non_space_counter(text: str) -> Counter:
    return Counter(ch for ch in text if not ch.isspace())


def _median(values, default=0.0):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else default


# ---------------------------------------------------------------- lines

def _is_small(im, raw: RawPage) -> bool:
    return raw.width * raw.height > 0 and (im.w * im.h) / (raw.width * raw.height) < SMALL_IMAGE_SHARE


def _line_from_fragments(texts: list, y: float) -> Line:
    """One text line from the fragments of one y-group (sorted by x): joins words, splits far-apart segments."""
    size = _median([f.size for f in texts], 10.0)
    seg_gap = max(1.6 * size, 14.0)
    segs: list = []
    cur_text, cur_x0, cur_x1, cur_size, cur_bold, prev = "", 0.0, 0.0, [], [], None
    for f in texts:
        if prev is None:
            cur_text, cur_x0, cur_x1, cur_size, cur_bold = f.text, f.x, f.x + f.width, [f.size], [f.bold]
        else:
            gap = f.x - (prev.x + prev.width)
            if gap > seg_gap:
                segs.append(Seg(cur_x0, cur_x1, cur_text, max(cur_size), all(cur_bold)))
                cur_text, cur_x0, cur_size, cur_bold = f.text, f.x, [f.size], [f.bold]
            else:
                need_space = (gap > 0.12 * size) if prev.exact_width and f.exact_width else (gap > -0.35 * size)
                if need_space and not cur_text.endswith(" ") and not f.text.startswith(" "):
                    cur_text += " "
                cur_text += f.text
                cur_size.append(f.size)
                cur_bold.append(f.bold)
            cur_x1 = f.x + f.width
        prev = f
    segs.append(Seg(cur_x0, cur_x1, cur_text, max(cur_size), all(cur_bold)))
    for s in segs:
        s.text = s.text.strip()
    segs = [s for s in segs if s.text]
    while len(segs) >= 2 and BULLET_ONLY.match(segs[0].text):  # "•" drawn apart from its text: one segment
        a, b = segs[0], segs[1]
        segs[0:2] = [Seg(a.x0, b.x1, f"{a.text} {b.text}", max(a.size, b.size), a.bold and b.bold)]
    return Line(y, segs, frags=list(texts))


def image_id(page: int, k: int) -> str:
    return f"p{page:03d}-{k:02d}"


def build_lines(raw: RawPage, decorative: frozenset = frozenset()) -> list:
    frags = [f for f in raw.fragments if f.text.strip()]
    visible = [im for im in raw.images if im.sig not in decorative]
    ids = {id(im): image_id(raw.number, k) for k, im in enumerate(visible, 1)}
    items = [("t", f.y, f) for f in frags] + [("i", im.y, im) for im in visible]
    items.sort(key=lambda it: (-it[1], getattr(it[2], "x", 0.0)))
    tol = 0.45 * _median([f.size for f in frags], 10.0)
    groups, ref = [], None
    for it in items:
        if ref is None or ref - it[1] > tol:
            groups.append([it])
            ref = it[1]
        else:
            groups[-1].append(it)
    lines = []
    for g in groups:
        texts = sorted((it[2] for it in g if it[0] == "t"), key=lambda f: f.x)
        # Justified text often draws the line-end hyphen as its own fragment at the right margin (found on a real
        # document): attach it to the last word so the hyphenation join can recognise it.
        if len(texts) >= 2 and texts[-1].text.strip() in LINE_END_HYPHENS and texts[-2].text.strip():
            last = texts.pop()
            prev = texts[-1]
            texts[-1] = Fragment(prev.text.rstrip() + last.text.strip(), prev.x, prev.y, prev.size, prev.bold, prev.width + last.width, prev.exact_width and last.exact_width)
        y = statistics.mean(it[1] for it in g)
        marks = [it[2] for it in g if it[0] == "i"]
        if not texts:
            lines.extend(Line(y, [], "image", small=_is_small(m, raw), ref=ids[id(m)]) for m in marks)
            continue
        extra_images = [Line(y - 0.01, [], "image", small=_is_small(m, raw), ref=ids[id(m)]) for m in marks]
        lines.append(_line_from_fragments(texts, y))
        lines.extend(extra_images)
    return [ln for ln in lines if ln.kind == "image" or ln.segs]


# ---------------------------------------------------------------- running headers / footers

def _norm_key(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", text.lower())).strip()


def find_running(all_lines: list, heights: list) -> tuple:
    """Returns (header_keys, footer_keys): normalised lines that repeat in >= 50 % of pages (min 3 pages)."""
    n = len(all_lines)
    if n < 3:
        return set(), set()
    head_count, foot_count = Counter(), Counter()
    for lines, h in zip(all_lines, heights):
        top = {_norm_key(ln.text) for ln in lines if ln.kind == "text" and ln.y > (1 - BAND) * h}
        bot = {_norm_key(ln.text) for ln in lines if ln.kind == "text" and ln.y < BAND * h}
        head_count.update(k for k in top if k)
        foot_count.update(k for k in bot if k)
    need = max(3, RUNNING_SHARE * n)
    return {k for k, c in head_count.items() if c >= need}, {k for k, c in foot_count.items() if c >= need}


def split_running(lines: list, height: float, header_keys: set, footer_keys: set) -> tuple:
    header, footer, number, body = [], [], [], []
    for ln in lines:
        if ln.kind == "text":
            top, bot = ln.y > (1 - BAND) * height, ln.y < BAND * height
            key = _norm_key(ln.text)
            if (top or bot) and NUMBER_LINE.match(ln.text.strip()):
                number.append(ln.text)
                continue
            if top and key in header_keys:
                header.append(ln.text)
                continue
            if bot and key in footer_keys:
                footer.append(ln.text)
                continue
        body.append(ln)
    return header, footer, number, body


# ---------------------------------------------------------------- layout: columns and tables

def _detect_columns(lines: list, width: float):
    """x position where the right column starts, or None. Uses where fragments START after a gap (works with narrow
    gutters, where the two columns' text would otherwise be glued into one line), and refuses tables (several start
    positions, or short cells)."""
    text_lines = [ln for ln in lines if ln.kind == "text" and ln.frags]
    if len(text_lines) < 8 or width <= 0:
        return None
    lo, hi = 0.28 * width, 0.72 * width
    bins: Counter = Counter()
    for ln in text_lines:
        fr = ln.frags
        size = ln.size or 10.0
        for i in range(1, len(fr)):
            gap = fr[i].x - (fr[i - 1].x + fr[i - 1].width)
            if gap >= max(0.6 * size, 7.0) and lo <= fr[i].x <= hi:
                bins[round(fr[i].x / 4.0)] += 1
    if not bins:
        return None
    scored = {b: bins[b - 1] + bins[b] + bins[b + 1] for b in bins}
    best = max(scored, key=scored.get)
    if scored[best] < 0.25 * len(text_lines):
        return None
    for b, s in scored.items():  # a second strong start position in the middle band: a table with 3+ columns
        if abs(b - best) > 3 and s >= 0.2 * len(text_lines):
            return None
    xr = best * 4.0
    left_len, right_len = [], []
    for ln in text_lines:
        l = [f for f in ln.frags if f.x < xr - 3]
        r = [f for f in ln.frags if f.x >= xr - 3]
        if l and r:
            left_len.append(sum(len(f.text) for f in l))
            right_len.append(sum(len(f.text) for f in r))
    if len(left_len) < 0.25 * len(text_lines):
        return None
    if statistics.mean(left_len) < 22 or statistics.mean(right_len) < 22:
        return None  # short cells: a table, not columns of text
    return xr


def _split_columns(lines: list, xr: float) -> list:
    """Reading order for a two-column page: blocks between full-width lines are read left column, then right."""
    out, left, right = [], [], []
    body = _median([ln.size for ln in lines if ln.kind == "text" and ln.size], 10.0)

    def flush():
        out.extend(left)
        out.extend(right)
        left.clear()
        right.clear()

    for ln in lines:
        if ln.kind == "image":
            flush()
            out.append(ln)
            continue
        l = [f for f in ln.frags if f.x < xr - 3]
        r = [f for f in ln.frags if f.x >= xr - 3]
        gaps = [ln.frags[i].x - (ln.frags[i - 1].x + ln.frags[i - 1].width) for i in range(1, len(ln.frags))]
        if l and r and ((gaps and max(gaps) < max(8.0, 0.9 * (ln.size or 10.0))) or ln.size >= 1.2 * body):  # a heading over both columns: text that runs on across the gutter, or larger than the body
            flush()
            out.append(ln)
        elif l and r:
            left.append(_line_from_fragments(l, ln.y))
            right.append(_line_from_fragments(r, ln.y))
        elif r:
            right.append(ln)
        else:
            last = l[-1]
            if last.x + last.width > xr + 20:  # runs across the gutter: a heading over both columns
                flush()
                out.append(ln)
            else:
                left.append(ln)
    flush()
    return out


# ---------------------------------------------------------------- headings

class Context:
    def __init__(self, body_size: float):
        self.body_size = body_size or 10.0
        self.size_levels: list = []

    def set_heading_sizes(self, sizes):
        self.size_levels = sorted({round(s) for s in sizes}, reverse=True)

    def is_heading(self, ln: Line) -> bool:
        if ln.kind != "text":
            return False
        t = ln.text.strip()
        if not t or len(t) > 150 or len(ln.segs) > 1:
            return False
        # not headings: table-of-contents entries, bullet items and "Label:" lines (found on a real document)
        if TOC_LEADER.search(t) or BULLET_START.match(t) or t.endswith(":"):
            return False
        big = ln.size >= 1.2 * self.body_size
        if big and not (t.endswith(".") and len(t) > 80):
            return True
        if ln.bold and len(t) <= 100 and not t.endswith("."):
            return True
        if HEADING_NUMBERING.match(t) and len(t) <= 100 and (ln.bold or ln.size >= self.body_size) and not t.endswith("."):
            return True
        letters = [c for c in t if c.isalpha()]
        if len(letters) >= 4 and t.isupper() and len(t) <= 80 and ln.size >= self.body_size:
            return True
        return False

    def level(self, ln: Line) -> int:
        t = ln.text.strip()
        m = re.match(r"^(\d+(?:\.\d+){0,3})\.?\s", t)
        if m:
            return m.group(1).count(".") + 1
        if self.size_levels:
            r = round(ln.size)
            if r in self.size_levels and ln.size >= 1.2 * self.body_size:
                return self.size_levels.index(r) + 1
        return max(2, len(self.size_levels) + 1)


# ---------------------------------------------------------------- paragraphs

def _join(a: str, b: str, page: int, page_result: PageResult) -> str:
    if a.endswith("­") and b:
        page_result.hyphens_removed["­"] += 1
        page_result.hyphen_joins.append({"pagina": page, "esquerda": a[-12:], "direita": b[:12], "resultado": (a[:-1] + b)[-24:]})
        return a[:-1] + b
    if a.endswith("-") and len(a) >= 2 and a[-2].isalpha() and b and b[0].isalpha():
        if b[0].islower():
            page_result.hyphens_removed["-"] += 1
            la = a.split(" ")[-1]
            lb = b.split(" ")[0]
            page_result.hyphen_joins.append({"pagina": page, "esquerda": la, "direita": lb, "resultado": la[:-1] + lb})
            return a[:-1] + b
        return a + b
    return a + " " + b


def _paragraphs(lines: list, ctx: Context, page: int, pr: PageResult) -> list:
    blocks: list = []
    cur = None
    prev = None
    sizes = [ln.size for ln in lines if ln.kind == "text"]
    pitches = [lines[i].y - lines[i + 1].y for i in range(len(lines) - 1) if lines[i].kind == "text" and lines[i + 1].kind == "text"]
    size = _median(sizes, 10.0)
    pitch = _median([p for p in pitches if 0 < p < 3 * size], 1.25 * size)
    left = min((ln.x0 for ln in lines if ln.kind == "text"), default=0.0)
    right = max((ln.x1 for ln in lines if ln.kind == "text"), default=0.0)
    width = max(right - left, 1.0)

    def flush():
        nonlocal cur
        if cur is not None:
            blocks.append(Block("para", cur, page))
            cur = None

    for ln in lines:
        if ln.kind == "image":
            flush()
            blocks.append(Block("image_small" if ln.small else "image", "", page, ref=ln.ref))
            prev = None
            continue
        text = ln.text.strip()
        if ctx.is_heading(ln):
            flush()
            if (
                blocks
                and blocks[-1].type == "heading"
                and prev is not None
                and prev.y - ln.y < 1.8 * ln.size
                and abs(prev.size - ln.size) < 0.6
            ):
                blocks[-1].text = _join(blocks[-1].text, text, page, pr)
            else:
                blocks.append(Block("heading", text, page, ctx.level(ln)))
            prev = ln
            continue
        new_para = cur is None or prev is None
        if not new_para:
            gap = prev.y - ln.y
            if gap > 1.5 * pitch:
                new_para = True
            elif LIST_START.match(text):
                new_para = True
            elif ln.x0 > left + 1.2 * ln.size and prev.x0 <= ln.x0 - 1.2 * ln.size + 0.5 and prev.x0 < ln.x0:
                new_para = True
            elif prev.text.rstrip().endswith((".", ":", ";", "!", "?")) and prev.x1 < left + 0.8 * width:
                new_para = True
        if new_para:
            flush()
            cur = text
        else:
            cur = _join(cur, text, page, pr)
        prev = ln
    flush()
    return blocks


def _table_regions(lines: list) -> list:
    """Indexes (start, end_exclusive) of runs of >= 3 consecutive text lines having 2+ segments."""
    runs, start = [], None
    for i, ln in enumerate(lines + [Line(0, [Seg(0, 0, "x", 1, False)])]):
        multi = ln.kind == "text" and len(ln.segs) >= 2
        if multi and start is None:
            start = i
        elif not multi and start is not None:
            if i - start >= 3:
                runs.append((start, i))
            start = None
    return runs


# ---------------------------------------------------------------- page / document

def organize_page(raw: RawPage, lines: list, header_keys: set, footer_keys: set, ctx: Context, decorative: frozenset = frozenset()) -> PageResult:
    pr = PageResult(number=raw.number)
    for f in raw.fragments:
        pr.raw_chars.update(non_space_counter(f.text))
        pr.garbled += sum(1 for ch in f.text if is_garbled_char(ch))
    pr.chars = sum(pr.raw_chars.values())
    visible = [im for im in raw.images if im.sig not in decorative]
    pr.images = len(visible)
    pr.images_small = sum(1 for im in visible if _is_small(im, raw))
    pr.images_decorative = len(raw.images) - len(visible)
    pr.ligatures = dict(raw.ligatures)
    pr.vector_ops = raw.paint_ops
    pr.widths_estimated = any(not f.exact_width for f in raw.fragments)
    if raw.rotate:
        pr.flags.append(FLAG_ROTATED)

    header, footer, number, body = split_running(lines, raw.height, header_keys, footer_keys)
    pr.header, pr.footer, pr.printed_number = header, footer, number
    pr.lines = len(body)

    if not raw.fragments and not visible:
        pr.flags.append(FLAG_NOTEXT)
        pr.blocks.append(Block("notext", "", raw.number))
        return pr
    if not raw.fragments:
        pr.flags.append(FLAG_NOTEXT)

    text_body = [ln for ln in body if ln.kind == "text"]
    xr = _detect_columns(body, raw.width)
    if xr is not None:
        pr.flags.append(FLAG_COLUMNS)
        ordered = _split_columns(body, xr)
        pr.blocks = _paragraphs(ordered, ctx, raw.number, pr)
    else:
        regions = _table_regions(body)
        if regions:
            pr.flags.append(FLAG_TABLE)
        elif sum(1 for ln in text_body if len(ln.segs) >= 2) >= 3:
            pr.flags.append(FLAG_UNCERTAIN)
        pos = 0
        for (a, b) in regions:
            if a > pos:
                pr.blocks.extend(_paragraphs(body[pos:a], ctx, raw.number, pr))
            pr.blocks.append(Block("table_start", "", raw.number))
            for ln in body[a:b]:
                pr.blocks.append(Block("table_row", "    ".join(s.text for s in ln.segs), raw.number))
            pr.blocks.append(Block("table_end", "", raw.number))
            pos = b
        if pos < len(body):
            pr.blocks.extend(_paragraphs(body[pos:], ctx, raw.number, pr))

    large = pr.images - pr.images_small
    if large:  # small icons and repeated decoration are marked/counted but do not flag the page
        pr.flags.append(FLAG_IMAGE)
        if pr.chars < 200:
            pr.flags.append(FLAG_IMAGE_ONLY)
    if pr.chars and pr.garbled / pr.chars > 0.05:
        pr.flags.append(FLAG_GARBLED)
    if raw.paint_ops >= VECTOR_OPS_THRESHOLD:
        pr.flags.append(FLAG_VECTOR)
    return pr


def _recurring_images(raw_pages: list) -> frozenset:
    """The same picture on >= 50 % of the pages (min 3) is decoration (header/footer bands, logos): not flagged."""
    n = len(raw_pages)
    if n < 3:
        return frozenset()
    pages_with = Counter()
    for rp in raw_pages:
        pages_with.update({im.sig for im in rp.images if im.sig})
    return frozenset(sig for sig, c in pages_with.items() if c >= max(3, RUNNING_SHARE * n))


def body_font_size(raw_pages: list) -> float:
    weights = Counter()
    for rp in raw_pages:
        for f in rp.fragments:
            weights[round(f.size * 2) / 2] += len(f.text.strip())
    return weights.most_common(1)[0][0] if weights else 10.0


def organize_document(raw_pages: list) -> tuple:
    """Returns (page_results, doc_info). doc_info holds the running-header/footer patterns."""
    decorative = _recurring_images(raw_pages)
    all_lines = [build_lines(rp, decorative) for rp in raw_pages]
    header_keys, footer_keys = find_running(all_lines, [rp.height for rp in raw_pages])
    ctx = Context(body_font_size(raw_pages))
    # heading sizes: distinct sizes of lines that look like headings by size alone
    big = [ln.size for lines in all_lines for ln in lines if ln.kind == "text" and ln.size >= 1.2 * ctx.body_size and len(ln.text) <= 150]
    ctx.set_heading_sizes(big)
    results = [organize_page(rp, lines, header_keys, footer_keys, ctx, decorative) for rp, lines in zip(raw_pages, all_lines)]
    info = {
        "body_size": ctx.body_size,
        "header_patterns": sorted(header_keys),
        "footer_patterns": sorted(footer_keys),
        "decorative_images": {f"{s[0]}x{s[1]}" if s and s[0] != "inline" else "inline": sum(1 for rp in raw_pages if any(im.sig == s for im in rp.images)) for s in sorted(decorative, key=str)},
    }
    return results, info
