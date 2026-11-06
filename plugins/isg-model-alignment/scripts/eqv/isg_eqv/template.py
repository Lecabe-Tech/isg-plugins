"""Reader of the analysts' template workbook (SPEC-005 REQ-CIN): tabs `1.1` and `1.2`, standard library only.

An .xlsx is a zip of XML. The reader never writes to the workbook, never needs images/formulas/styles and finds every
column from the HEADERS (never from fixed letters), so a moved column is found and a changed layout is reported.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
M = "{%s}" % NS_MAIN

CODE_RE = re.compile(r"^[A-Z]{1,4}\d+$")
UF_RE = re.compile(r"^[A-Z]{2}$")
YEAR_RE = re.compile(r"^(20\d{2})$")
TABS = {"1.1": "pedagógicas", "1.2": "gestão"}


class TemplateError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text))
    return re.sub(r"\s+", " ", "".join(c for c in t if not unicodedata.combining(c)).lower()).strip()


def col_to_num(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def num_to_col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def split_ref(ref: str) -> tuple:
    m = re.match(r"([A-Z]+)(\d+)$", ref)
    return col_to_num(m.group(1)), int(m.group(2))


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _text_of(el) -> str:
    return "".join(t.text or "" for t in el.iter(M + "t"))


def read_sheets(path) -> dict:
    """{sheet name: {(col_num, row): value as text}} for every visible sheet. Formulas: their cached value."""
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise TemplateError("ARQUIVO_INVALIDO", "O arquivo não parece ser uma planilha .xlsx válida.")
    with z:
        try:
            wb = ET.fromstring(z.read("xl/workbook.xml"))
            rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        except KeyError:
            raise TemplateError("ARQUIVO_INVALIDO", "O arquivo não parece ser uma planilha .xlsx válida (faltam partes internas).")
        targets = {r.get("Id"): r.get("Target") for r in rels}
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            shared = [_text_of(si) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(M + "si")]
        out = {}
        for s in wb.find(M + "sheets"):
            if s.get("state") in ("hidden", "veryHidden"):
                continue
            tgt = targets.get(s.get("{%s}id" % NS_REL))
            if not tgt:
                continue
            name = ("xl/" + tgt.lstrip("/").replace("xl/", "", 1)) if not tgt.startswith("/") else tgt.lstrip("/")
            if name not in z.namelist():
                continue
            cells = {}
            for c in ET.fromstring(z.read(name)).iter(M + "c"):
                t = c.get("t")
                v = c.find(M + "v")
                if t == "inlineStr":
                    val = _text_of(c.find(M + "is")) if c.find(M + "is") is not None else ""
                elif v is None or v.text is None:
                    continue
                elif t == "s":
                    val = shared[int(v.text)]
                elif t == "b":
                    val = "TRUE" if v.text == "1" else "FALSE"
                else:
                    val = v.text
                    if t in (None, "n") and re.fullmatch(r"-?\d+\.0+", val):
                        val = val.split(".")[0]
                cells[split_ref(c.get("r"))] = val
            out[s.get("name")] = cells
        return out


def find_tabs(sheets: dict) -> dict:
    """Tabs '1.1 …' and '1.2 …' by their numeric prefix, ignoring accents and case."""
    found = {}
    for name in sheets:
        m = re.match(r"\s*(1\.[12])\b", fold(name))
        if m and "orient" in fold(name):
            found[m.group(1)] = name
    return found


def parse_tab(tab: str, name: str, cells: dict) -> dict:
    """One tab -> {'aba', 'nome', 'orientacoes': [...], 'colunas': {(uf, ano): (valor, comentario)}, 'avisos': [...]}"""
    problems = []
    header_row = None
    for (c, r), v in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if fold(v).startswith("codigo da orientacao"):
            header_row, code_col = r, c
            break
    if header_row is None:
        raise TemplateError("LAYOUT_DESCONHECIDO", f"Na aba '{name}' não encontrei a coluna 'Código da orientação'. O layout mudou? Nada foi lido.")
    cols_in_header = {c: v for (c, r), v in cells.items() if r == header_row}

    def col_of(prefix: str, default=None):
        for c, v in sorted(cols_in_header.items()):
            if fold(v).startswith(prefix):
                return c
        return default

    text_col = col_of("orientacao")
    class_col = col_of("classificacao")
    group_col = col_of("componente e/ou pratica educativa (1") or col_of("bloco")
    sub_col = col_of("componente e/ou pratica educativa (2") or col_of("sub bloco")
    if text_col is None:
        raise TemplateError("LAYOUT_DESCONHECIDO", f"Na aba '{name}' não encontrei a coluna 'Orientação'. Nada foi lido.")
    # the UF row is the closest row above the header with 2-letter upper-case labels
    uf_row = None
    for r in range(header_row - 1, max(0, header_row - 5), -1):
        labels = [(c, v.strip()) for (c, rr), v in cells.items() if rr == r and UF_RE.match(v.strip())]
        if labels:
            uf_row, uf_labels = r, sorted(labels)
            break
    if uf_row is None:
        raise TemplateError("LAYOUT_DESCONHECIDO", f"Na aba '{name}' não encontrei os estados (UF) acima do cabeçalho. Nada foi lido.")
    year_cols = sorted((c, YEAR_RE.match(v.strip()).group(1)) for c, v in cols_in_header.items() if YEAR_RE.match(v.strip()))
    if not year_cols:
        raise TemplateError("LAYOUT_DESCONHECIDO", f"Na aba '{name}' não encontrei as colunas de ano no cabeçalho. Nada foi lido.")
    columns = {}
    for c, year in year_cols:
        uf = None
        for lc, label in uf_labels:
            if lc <= c:
                uf = label
        if uf is None:
            problems.append(f"coluna {num_to_col(c)} (ano {year}) sem estado")
            continue
        comment_col = c + 1 if "observac" in fold(cols_in_header.get(c + 1, "")) else None
        if comment_col is None:
            problems.append(f"{uf} {year}: coluna de comentários não encontrada ao lado de {num_to_col(c)}")
        columns[(uf, int(year))] = (c, comment_col)

    rows, group, sub, seen = [], "", "", set()
    last_row = max(r for (_, r) in cells)
    for r in range(header_row + 1, last_row + 1):
        if group_col and cells.get((group_col, r), "").strip():
            group = cells[(group_col, r)].strip()
        if sub_col and cells.get((sub_col, r), "").strip():
            sub = cells[(sub_col, r)].strip()
        code = cells.get((code_col, r), "").strip()
        if not code:
            continue
        if not CODE_RE.match(code):
            problems.append(f"linha {r}: código '{code}' ignorado (formato inesperado)")
            continue
        if code in seen:
            problems.append(f"linha {r}: código {code} repetido")
        seen.add(code)
        text = cells.get((text_col, r), "").strip()
        if not text:
            problems.append(f"linha {r}: {code} sem texto de orientação")
        rows.append({"aba": tab, "codigo": code, "linha": r, "grupo": group, "subgrupo": "" if sub in ("-", "") else sub, "orientacao": text,
                     "classificacao": cells.get((class_col, r), "").strip() if class_col else ""})
    return {"aba": tab, "nome": name, "linha_cabecalho": header_row, "orientacoes": rows, "colunas": columns, "avisos": problems}


def read_template(path) -> dict:
    """The whole template: orientations of tabs 1.1 and 1.2, the column map and the analysts' answers (answer key)."""
    sheets = read_sheets(path)
    tabs = find_tabs(sheets)
    missing = [t for t in TABS if t not in tabs]
    if missing:
        raise TemplateError("ABA_AUSENTE", "Não encontrei na planilha a(s) aba(s): " + ", ".join(f"{t} (orientações {TABS[t]})" for t in missing) + ".")
    result = {"sha256": sha256_file(path), "abas": {}, "gabarito": {}, "avisos": []}
    for tab in sorted(tabs):
        cells = sheets[tabs[tab]]
        parsed = parse_tab(tab, tabs[tab], cells)
        result["abas"][tab] = {k: v for k, v in parsed.items() if k != "colunas"}
        result["abas"][tab]["colunas"] = {f"{uf}-{year}": {"valor": num_to_col(vc), "comentario": num_to_col(cc) if cc else None} for (uf, year), (vc, cc) in sorted(parsed["colunas"].items())}
        result["avisos"] += [f"aba {tab}: {a}" for a in parsed["avisos"]]
        for o in parsed["orientacoes"]:
            for (uf, year), (vc, cc) in parsed["colunas"].items():
                val = cells.get((vc, o["linha"]), "").strip()
                com = cells.get((cc, o["linha"]), "").strip() if cc else ""
                if val or com:
                    result["gabarito"].setdefault(f"{tab}|{o['codigo']}|{uf}|{year}", {"valor": val, "comentario": com})
    return result


def summarize(t: dict) -> str:
    parts = []
    for tab, a in sorted(t["abas"].items()):
        ufs = sorted({k.split("-")[0] for k in a["colunas"]})
        years = sorted({k.split("-")[1] for k in a["colunas"]})
        parts.append(f"aba {tab}: {len(a['orientacoes'])} orientações; estados {', '.join(ufs)}; anos {', '.join(years)}")
    return "; ".join(parts) + f". Respostas dos analistas encontradas: {len(t['gabarito'])}."
