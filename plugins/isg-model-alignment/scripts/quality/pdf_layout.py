"""Table rows of a PDF page from the position of its text (lesson of the MG 2026 pilot).

Official matrices are PDF tables. Their plain text loses the columns: an isolated "3 120 100:00:00" does not say which
grade it belongs to. The CFP reader keeps the position of every text fragment, so the columns can be rebuilt:
  * the reading direction follows the page rotation (landscape tables are stored rotated 90/270 degrees);
  * every numeric fragment defines a row, and the label fragments next to it (also labels broken in two lines) join it;
  * the starting positions of the numeric fragments are grouped into column anchors;
  * the size of one column group (for example A/S, A/A, H/A = 3 numbers) comes from the most complete row
    (numbers in that row / number of columns).
When the layout does not close (too many anchors, a group size that does not divide, a row matched twice), the rows are
marked `incerta` and nothing is confirmed from them. Standard library + the CFP's vendored pypdf only.
"""
from __future__ import annotations

import re
import statistics
from pathlib import Path

import document_normalizer as DN

NUM_TOKEN = re.compile(r"^\d+(?:[.,:]\d+)*$")


def _is_numeric(text: str) -> bool:
    toks = text.split()
    return bool(toks) and all(NUM_TOKEN.match(t) for t in toks)


def _cluster(values: list, tol: float) -> list:
    """Sorted cluster centres (first value of each cluster) of 1-D positions."""
    out = []
    for v in sorted(values):
        if not out or v - out[-1][-1] > tol:
            out.append([v])
        else:
            out[-1].append(v)
    return [c[0] for c in out]


_CACHE: dict = {}


def page_table(pdf_path: Path, page: int, columns: int = 3) -> dict:
    """{'orientacao', 'colunas', 'grupo', 'linhas': [{'rotulo', 'pos', 'grupos': [[tokens] | None] * columns, 'incerta'}], 'avisos'}."""
    key = (str(pdf_path), page, columns)
    if key in _CACHE:
        return _CACHE[key]
    DN._cfp_path()
    DN.quiet_pdf_library()
    from isg_cfp.extract import extract_page, open_reader

    out = {"orientacao": None, "colunas": [], "grupo": None, "linhas": [], "avisos": []}
    reader, err = open_reader(pdf_path)
    if err or page < 1 or page > len(reader.pages):
        out["avisos"].append("página não encontrada no PDF")
        _CACHE[key] = out
        return out
    raw = extract_page(reader, page - 1)
    rot = (raw.rotate or 0) % 360
    if rot == 90:
        rc = lambda f: (f.x, f.y)  # noqa: E731  (row coordinate, column coordinate)
    elif rot == 270:
        rc = lambda f: (-f.x, -f.y)  # noqa: E731
    else:
        rc = lambda f: (-f.y, f.x)  # noqa: E731
    out["orientacao"] = "paisagem" if rot in (90, 270) else "retrato"
    frags = [f for f in raw.fragments if f.text.strip()]
    if not frags:
        out["avisos"].append("página sem texto")
        _CACHE[key] = out
        return out
    size = statistics.median(f.size for f in frags) or 7.0
    nums = [f for f in frags if _is_numeric(f.text)]
    labels = [f for f in frags if not _is_numeric(f.text)]
    if not nums:
        out["avisos"].append("página sem números")
        _CACHE[key] = out
        return out
    anchors = _cluster([rc(f)[1] for f in nums], tol=2.0 * size)
    out["colunas"] = anchors
    longest = max(len(f.text.split()) for f in nums)
    group = longest // columns if longest % columns == 0 and longest >= columns else None
    out["grupo"] = group
    layout_ok = group is not None and len(anchors) <= columns
    if group is None:
        out["avisos"].append(f"a linha mais completa tem {longest} número(s), que não se dividem em {columns} coluna(s)")
    if len(anchors) > columns:
        out["avisos"].append(f"{len(anchors)} posições de coluna para {columns} série(s): layout não reconhecido")
    rows: dict = {}
    for f in nums:
        r, c = rc(f)
        row = next((k for k in rows if abs(k - r) <= 0.9 * size), None)
        if row is None:
            row = r
            rows[row] = {"pos": r, "num": [], "lab": []}
        rows[row]["num"].append((c, f.text.split()))
    for f in labels:
        r, c = rc(f)
        near = min(rows, key=lambda k: abs(k - r))
        if abs(near - r) <= 1.5 * size:
            rows[near]["lab"].append((r, c, f.text.strip()))
    for k in sorted(rows):
        row = rows[k]
        groups = [None] * columns
        incerta = not layout_ok
        for c, toks in sorted(row["num"]):
            if not layout_ok:
                continue
            start = min(range(len(anchors)), key=lambda i: abs(anchors[i] - c))
            if len(toks) % group:
                incerta = True
                continue
            for j in range(len(toks) // group):
                col = start + j
                if col >= columns:
                    incerta = True
                    break
                if groups[col] is not None:
                    incerta = True
                groups[col] = toks[j * group:(j + 1) * group]
        label = " ".join(t for _, _, t in sorted(row["lab"]))
        out["linhas"].append({"rotulo": re.sub(r"\s+", " ", label).strip(), "pos": round(k, 1), "grupos": groups, "incerta": incerta})
    _CACHE[key] = out
    return out


def _in_order(words: list, label: list) -> bool:
    """All words of the name appear in the label in the same order (other words may sit between them)."""
    it = iter(label)
    return bool(words) and all(any(w == x for x in it) for w in words)


def find_row(table: dict, name: str) -> dict | None:
    """The single row whose label contains the component name (accents, case and spacing ignored); None if absent or ambiguous."""
    key = DN.squash(name)
    if not key:
        return None
    hits = [r for r in table["linhas"] if key in DN.squash(r["rotulo"])]
    if not hits:  # a neighbouring label (e.g. the area name of a merged cell) may fall inside a label broken in two lines
        words = [DN.squash(w) for w in DN.fold(name).split() if DN.squash(w)]
        hits = [r for r in table["linhas"] if _in_order(words, [DN.squash(w) for w in DN.fold(r["rotulo"]).split()])]
    if len(hits) > 1:
        exact = [r for r in hits if DN.squash(r["rotulo"]).endswith(key)]
        hits = exact if len(exact) == 1 else hits
    return hits[0] if len(hits) == 1 else None


def check_cell(pdf_path: Path, page: int, name: str, serie: int, value, columns: int = 3) -> dict:
    """Confirms (or not) that `value` is the first number of the `serie` column in the row of `name`.
    value None = blank in the source. Returns {'estado': 'confere'|'diverge'|'indeterminado', 'motivo', 'achado'}."""
    t = page_table(pdf_path, page, columns)
    row = find_row(t, name)
    if row is None:
        return {"estado": "indeterminado", "motivo": "linha do componente não localizada no layout da página", "achado": None}
    if row["incerta"]:
        return {"estado": "indeterminado", "motivo": "layout da tabela incerto (" + "; ".join(t["avisos"]) + ")" if t["avisos"] else "layout da linha incerto", "achado": None}
    grp = row["grupos"][serie - 1]
    found = None if grp is None else grp[0]
    if value is None:
        return {"estado": "confere" if grp is None else "diverge", "motivo": "" if grp is None else f"a coluna da {serie}ª série tem {found}", "achado": found}
    if grp is None:
        filled = [i + 1 for i, g in enumerate(row["grupos"]) if g is not None]
        return {"estado": "diverge", "motivo": f"a coluna da {serie}ª série está em branco no layout" + (f"; há valor na(s) coluna(s) {filled}" if filled else ""), "achado": None}
    try:
        same = float(found.replace(",", ".")) == float(value)
    except ValueError:
        same = False
    return {"estado": "confere" if same else "diverge", "motivo": "" if same else f"a coluna da {serie}ª série tem {found}, não {value}", "achado": found}
