"""SPEC-017 G1: multi-format extraction into located units (standard library + the CFP's vendored pypdf).

Unit: {id, tipo, localizacao, texto, status, avisos, [valor, formula, mesclada, oculta]}.
  tipo: pdf_page | image_region | sheet_cell | paragraph | row | text_block
  status: lida | vazia | requer_interpretacao | interpretada_ia | sem_valor | erro_leitura | ignorada
Nothing is dropped in silence: what cannot be read becomes a unit with a pending status and a warning. Sources are
treated as data: formulas are read as text, macros are never run, HTML scripts are discarded.
"""
from __future__ import annotations

import csv
import html
import io
import re
import struct
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFP_DIR = HERE.parent / "cfp"
EXTRACTOR_VERSION = "q17-normalizer-1"
READ_OK = ("lida", "vazia", "interpretada_ia", "ignorada")
PENDING = ("requer_interpretacao", "sem_valor", "erro_leitura")

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "{%s}" % NS_MAIN
W = "{%s}" % NS_W
MIN_TEXT = 20  # letters/digits on a PDF page below which it is treated as image-only
BIG_IMAGE = 0.15  # an image covering 15% of a text page may hold a table or chart: it needs SIP


def squash(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text or ""))
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in t if not unicodedata.combining(c)).lower())


def fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text or ""))
    return re.sub(r"\s+", " ", "".join(c for c in t if not unicodedata.combining(c)).lower()).strip()


def _unit(doc_id, suffix, tipo, loc, texto="", status="lida", avisos=None, **extra) -> dict:
    u = {"id": f"{doc_id}:{suffix}", "tipo": tipo, "localizacao": {"tipo": tipo, **loc}, "texto": texto, "status": status, "avisos": avisos or []}
    u.update(extra)
    return u


# ---------------- PDF (reuses the CFP reader) ----------------

def _pdf_units(doc_id: str, path: Path) -> tuple:
    for p in (str(CFP_DIR / "vendor"), str(CFP_DIR)):
        if p not in sys.path:
            sys.path.insert(0, p)
    from isg_cfp.extract import extract_page, normalize_text, open_reader
    from isg_cfp.organize import _recurring_images

    reader, err = open_reader(path)
    if err == "PDF_PROTEGIDO":
        return [], [{"codigo": "ACESSO_NEGADO", "detalhe": "O PDF está protegido por senha; envie uma cópia sem proteção."}]
    if err:
        return [], [{"codigo": "LEITURA_FALHOU", "detalhe": "O PDF está corrompido ou não pôde ser aberto."}]
    units, raws = [], []
    for i in range(len(reader.pages)):
        try:
            raws.append(extract_page(reader, i))
        except Exception:
            raws.append(None)
    decorative = _recurring_images([r for r in raws if r is not None])
    for i, raw in enumerate(raws):
        n = i + 1
        try:
            text = normalize_text(reader.pages[i].extract_text() or "")
        except Exception:
            units.append(_unit(doc_id, f"p{n}", "pdf_page", {"pagina": n}, status="erro_leitura", avisos=["Não foi possível extrair o texto desta página."]))
            continue
        images = [im for im in (raw.images if raw else []) if im.sig not in decorative]
        if len(squash(text)) < MIN_TEXT and images:
            units.append(_unit(doc_id, f"p{n}", "pdf_page", {"pagina": n}, text, "requer_interpretacao",
                               ["Página só com imagem (digitalizada ou tabela em figura): precisa de leitura de imagem (SIP) e revisão."]))
            continue
        status = "lida" if squash(text) else "vazia"
        units.append(_unit(doc_id, f"p{n}", "pdf_page", {"pagina": n}, text, status))
        area = (raw.width * raw.height) if raw else 0
        for k, im in enumerate(images, start=1):
            if area and (im.w * im.h) / area >= BIG_IMAGE:
                units.append(_unit(doc_id, f"p{n}-img{k}", "image_region", {"pagina": n, "imagem": k}, "", "requer_interpretacao",
                                   ["Imagem grande na página: pode conter tabela ou gráfico; precisa de leitura de imagem (SIP)."]))
    return units, []


# ---------------- DOCX ----------------

def _w_text(el) -> str:
    out = []
    for node in el.iter():
        if node.tag == W + "t" and node.text:
            out.append(node.text)
        elif node.tag == W + "tab":
            out.append("\t")
        elif node.tag in (W + "br", W + "cr"):
            out.append("\n")
    return "".join(out)


def _has_image(el) -> bool:
    return any(n.tag.endswith("}drawing") or n.tag.endswith("}pict") for n in el.iter())


def _docx_units(doc_id: str, path: Path) -> tuple:
    try:
        with zipfile.ZipFile(path) as z:
            root = ET.fromstring(z.read("word/document.xml"))
            extra_parts = [n for n in z.namelist() if re.match(r"word/(header|footer)\d*\.xml$", n)]
    except (zipfile.BadZipFile, KeyError, ET.ParseError):
        return [], [{"codigo": "LEITURA_FALHOU", "detalhe": "O DOCX está corrompido ou incompleto."}]
    body = root.find(W + "body")
    units, p_idx, t_idx, img_idx = [], 0, 0, 0
    for el in list(body) if body is not None else []:
        if el.tag == W + "p":
            p_idx += 1
            text = _w_text(el).strip()
            if text:
                units.append(_unit(doc_id, f"par{p_idx}", "paragraph", {"paragrafo": p_idx}, text))
            if _has_image(el):
                img_idx += 1
                descr = " ".join(filter(None, (n.get("descr") or n.get("name") for n in el.iter() if n.tag.endswith("}docPr"))))
                units.append(_unit(doc_id, f"img{img_idx}", "image_region", {"paragrafo": p_idx, "imagem": img_idx}, "", "requer_interpretacao",
                                   ["Imagem no documento" + (f" ({descr})" if descr else "") + ": precisa de leitura de imagem (SIP)."]))
        elif el.tag == W + "tbl":
            t_idx += 1
            for r_idx, tr in enumerate(el.iter(W + "tr"), start=1):
                cells = [_w_text(tc).strip() for tc in tr.findall(W + "tc")]
                units.append(_unit(doc_id, f"tab{t_idx}-l{r_idx}", "row", {"tabela": t_idx, "linha": r_idx}, " | ".join(cells), celulas=cells))
            if _has_image(el):
                img_idx += 1
                units.append(_unit(doc_id, f"img{img_idx}", "image_region", {"tabela": t_idx, "imagem": img_idx}, "", "requer_interpretacao",
                                   ["Imagem dentro de tabela: precisa de leitura de imagem (SIP)."]))
    warnings = []
    if extra_parts:
        warnings.append({"codigo": "CONTEUDO_NAO_LIDO", "detalhe": "Cabeçalhos e rodapés do DOCX não foram lidos (costumam repetir título e paginação)."})
    return units, warnings


# ---------------- XLSX ----------------

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
    m = re.match(r"\$?([A-Z]+)\$?(\d+)$", ref)
    return col_to_num(m.group(1)), int(m.group(2))


def shift_formula(formula: str, dcol: int, drow: int) -> str:
    """Moves the relative references of a shared formula (A1 style; $ keeps a part fixed; whole columns stay)."""
    def rep(m):
        if m.group(0).startswith("_") or (m.start() > 0 and (formula[m.start() - 1].isalpha() or formula[m.start() - 1] in "_.")):
            return m.group(0)
        c_abs, col, r_abs, row = m.group(1), m.group(2), m.group(3), m.group(4)
        if not c_abs:
            col = num_to_col(col_to_num(col) + dcol)
        if not r_abs:
            row = str(int(row) + drow)
        return f"{c_abs}{col}{r_abs}{row}"
    return re.sub(r"(\$?)([A-Z]{1,3})(\$?)(\d+)", rep, formula)


def read_workbook(path: Path) -> dict:
    """{'abas': [{'nome', 'oculta', 'celulas': {ref: {'valor', 'texto', 'formula', 'tipo'}}, 'mescladas': [...]}], 'imagens': n}."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = ["".join(t.text or "" for t in si.iter(M + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(M + "si")]
        sheets = []
        for s in wb.find(M + "sheets"):
            target = rels.get(s.get("{%s}id" % NS_REL), "")
            part = target.lstrip("/") if target.startswith("/") else "xl/" + target
            if part not in names:
                continue
            root = ET.fromstring(z.read(part))
            cells, masters = {}, {}
            for c in root.iter(M + "c"):
                ref, t = c.get("r"), c.get("t")
                v, f = c.find(M + "v"), c.find(M + "f")
                formula = None
                if f is not None:
                    if f.text:
                        formula = f.text
                        if f.get("t") == "shared" and f.get("si") is not None:
                            masters[f.get("si")] = (ref, f.text)
                    elif f.get("t") == "shared" and f.get("si") in masters:
                        mref, mtext = masters[f.get("si")]
                        (mc, mr), (cc, cr) = split_ref(mref), split_ref(ref)
                        formula = shift_formula(mtext, cc - mc, cr - mr)
                    else:
                        formula = ""
                if t == "inlineStr":
                    is_ = c.find(M + "is")
                    value = "".join(x.text or "" for x in is_.iter(M + "t")) if is_ is not None else ""
                elif v is None or v.text is None:
                    value = None
                elif t == "s":
                    value = shared[int(v.text)]
                elif t == "b":
                    value = v.text == "1"
                elif t in ("str", "e"):
                    value = v.text
                else:
                    num = float(v.text)
                    value = int(num) if num.is_integer() else num
                if value is None and formula is None:
                    continue
                if isinstance(value, str) and not value.strip() and formula is None:
                    continue
                text = "" if value is None else ("VERDADEIRO" if value is True else "FALSO" if value is False else str(value))
                cells[ref] = {"valor": value, "texto": text, "formula": formula, "tipo": "erro" if t == "e" else None}
            mc = root.find(M + "mergeCells")
            sheets.append({"nome": s.get("name"), "oculta": s.get("state") in ("hidden", "veryHidden"), "celulas": cells,
                           "mescladas": [m.get("ref") for m in mc] if mc is not None else []})
        return {"abas": sheets, "imagens": len([n for n in names if n.startswith("xl/media/")])}


def _xlsx_units(doc_id: str, path: Path, evidence_class: bool) -> tuple:
    try:
        wb = read_workbook(path)
    except (zipfile.BadZipFile, KeyError, ET.ParseError, ValueError):
        return [], [{"codigo": "LEITURA_FALHOU", "detalhe": "O XLSX está corrompido ou incompleto."}]
    units, warnings = [], []
    no_cache = 0
    for sh in wb["abas"]:
        merged_anchor = {m.split(":")[0]: m for m in sh["mescladas"]}
        for ref in sorted(sh["celulas"], key=lambda r: (split_ref(r)[1], split_ref(r)[0])):
            c = sh["celulas"][ref]
            extra = {"valor": c["valor"], "formula": c["formula"], "oculta": sh["oculta"], "mesclada": merged_anchor.get(ref)}
            avisos = []
            status = "lida"
            if c["formula"] is not None and c["valor"] is None:
                avisos.append("Fórmula sem valor calculado salvo no arquivo: o valor não foi inventado.")
                if evidence_class:  # in the template/ICE the formula TEXT is the rule; its cached value is never used as data
                    status = "sem_valor"
                    no_cache += 1
            elif c["tipo"] == "erro":
                status = "sem_valor"
                avisos.append(f"A célula mostra erro do Excel ({c['texto']}).")
            units.append(_unit(doc_id, f"{sh['nome']}!{ref}", "sheet_cell", {"aba": sh["nome"], "celula": ref}, c["texto"], status, avisos, **extra))
    if no_cache:
        warnings.append({"codigo": "FORMULA_SEM_VALOR_EM_CACHE", "detalhe": f"{no_cache} fórmula(s) sem valor salvo; abra e salve no Excel para gravar os resultados, ou confirme os valores."})
    for k in range(1, wb["imagens"] + 1):
        if evidence_class:
            units.append(_unit(doc_id, f"img{k}", "image_region", {"imagem": k}, "", "requer_interpretacao", ["Imagem na planilha: precisa de leitura de imagem (SIP)."]))
        else:
            units.append(_unit(doc_id, f"img{k}", "image_region", {"imagem": k}, "", "ignorada", ["Imagem em planilha de referência: não é usada como evidência."]))
    return units, warnings


# ---------------- images, text, CSV, HTML ----------------

def image_size(data: bytes) -> tuple:
    if data.startswith(b"\x89PNG") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data.startswith(b"\xff\xd8"):
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg
    return None, None


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _text_units(doc_id: str, text: str) -> list:
    units, start, buf = [], None, []
    lines = text.splitlines()
    for i, line in enumerate(lines + [""], start=1):
        if line.strip():
            if start is None:
                start = i
            buf.append(line)
        elif buf:
            units.append(_unit(doc_id, f"l{start}-{i - 1}", "text_block", {"linha_inicio": start, "linha_fim": i - 1}, "\n".join(buf)))
            start, buf = None, []
    return units


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<!--.*?-->", " ", raw)
    raw = re.sub(r"(?i)<\s*(br|/p|/div|/li|/tr|/h\d|/table)\b[^>]*>", "\n", raw)
    raw = re.sub(r"(?i)<\s*(td|th)\b[^>]*>", " | ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = html.unescape(raw)
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines())


def _csv_units(doc_id: str, text: str) -> list:
    sample = text[:4096]
    delim = ";" if sample.count(";") > sample.count(",") else ","
    units = []
    for i, row in enumerate(csv.reader(io.StringIO(text), delimiter=delim), start=1):
        if any(c.strip() for c in row):
            units.append(_unit(doc_id, f"l{i}", "row", {"linha": i}, " | ".join(row), celulas=row))
    return units


def normalize(doc: dict) -> dict:
    """doc: record from source_resolver. Returns {'unidades': [...], 'pendencias': [...], 'extrator': str|None}."""
    path = Path(doc["caminho"]) if doc.get("caminho") else None
    media = doc.get("media_type")
    if not path or not media:
        return {"unidades": [], "pendencias": [], "extrator": None}
    doc_id = doc["id"]
    evidence_class = bool(set(doc["classes"]) & {"orientacoes_estaduais", "matriz_estadual"})
    if media == "application/pdf":
        units, pend = _pdf_units(doc_id, path)
        kind = "pdf"
    elif media.endswith("wordprocessingml.document"):
        units, pend = _docx_units(doc_id, path)
        kind = "docx"
    elif media.endswith("spreadsheetml.sheet"):
        units, pend = _xlsx_units(doc_id, path, evidence_class)
        kind = "xlsx"
    elif media in ("image/png", "image/jpeg"):
        data = path.read_bytes()
        w, h = image_size(data)
        units = [_unit(doc_id, "img1", "image_region", {"imagem": 1, "largura": w, "altura": h}, "", "requer_interpretacao",
                       ["Arquivo de imagem: o conteúdo precisa de leitura de imagem (SIP) e revisão; nenhum valor é dado como verificado."])]
        pend, kind = [], "imagem"
    elif media == "text/csv":
        units, pend, kind = _csv_units(doc_id, _decode(path.read_bytes())), [], "csv"
    elif media == "text/html":
        units, pend, kind = _text_units(doc_id, html_to_text(_decode(path.read_bytes()))), [], "html"
    else:
        units, pend, kind = _text_units(doc_id, _decode(path.read_bytes())), [], "texto"
    if any(u["status"] == "requer_interpretacao" for u in units):
        pend.append({"codigo": "IMAGEM_PENDENTE", "detalhe": "%d trecho(s) em imagem precisam de leitura de imagem (SIP) e revisão." % sum(u["status"] == "requer_interpretacao" for u in units)})
    if any(u["status"] == "erro_leitura" for u in units):
        pend.append({"codigo": "LEITURA_FALHOU", "detalhe": "%d página(s) não puderam ser lidas." % sum(u["status"] == "erro_leitura" for u in units)})
    if not units and not pend:
        pend.append({"codigo": "CONTEUDO_NAO_LIDO", "detalhe": "Nenhum conteúdo foi encontrado no arquivo."})
    return {"unidades": units, "pendencias": pend, "extrator": f"{EXTRACTOR_VERSION}/{kind}"}


def coverage(units: list) -> dict:
    return {"unidades_total": len(units), "unidades_lidas": sum(u["status"] in READ_OK for u in units),
            "unidades_pendentes": sum(u["status"] in PENDING for u in units)}


def search(units_by_doc: dict, query: str, limit: int = 30) -> list:
    """Every term (accent and case insensitive) must be in the unit. Returns [{unidade, fonte_id, localizacao, trecho}]."""
    terms = [fold(t) for t in re.findall(r'"[^"]+"|\S+', query)]
    terms = [t.strip('"') for t in terms if t.strip('"')]
    out = []
    for doc_id, units in units_by_doc.items():
        for u in units:
            text = fold(u.get("texto", "") + " " + (u.get("interpretacao_ia") or ""))
            if terms and all(t in text for t in terms):
                pos = text.find(terms[0])
                out.append({"unidade": u["id"], "fonte_id": doc_id, "localizacao": u["localizacao"], "status": u["status"],
                            "trecho": re.sub(r"\s+", " ", text[max(0, pos - 80):pos + 160]).strip()})
                if len(out) >= limit:
                    return out
    return out
