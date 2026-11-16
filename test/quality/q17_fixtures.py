"""Synthetic fixtures for SPEC-017 tests: no real Instituto or state data, every value is invented.

Writers for PDF (via test.cfp.pdfgen), DOCX, XLSX (numbers, formulas with or without cached value, shared formulas,
merged cells, hidden sheets), PNG and JPEG, plus a complete synthetic four-class source set.
"""
from __future__ import annotations

import json
import re
import struct
import zipfile
import zlib
from pathlib import Path
from xml.sax.saxutils import escape

from test.cfp import pdfgen

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class F:
    """A formula cell: F("SUM(B2:B3)", cached=7) or F("SUM(B2:B3)") (no cached value), shared=(si, ref) for masters."""

    def __init__(self, text, cached=None, si=None, ref=None):
        self.text, self.cached, self.si, self.ref = text, cached, si, ref


def _cell_xml(ref: str, v) -> str:
    if isinstance(v, F):
        attrs = ""
        if v.si is not None:
            attrs = ' t="shared" si="%d"' % v.si + (' ref="%s"' % v.ref if v.ref else "")
        f = "<f%s>%s</f>" % (attrs, escape(v.text)) if v.text else "<f%s/>" % attrs
        val = "" if v.cached is None else "<v>%s</v>" % v.cached
        typ = ' t="str"' if isinstance(v.cached, str) else ""
        return '<c r="%s"%s>%s%s</c>' % (ref, typ, f, val)
    if isinstance(v, bool):
        return '<c r="%s" t="b"><v>%d</v></c>' % (ref, int(v))
    if isinstance(v, (int, float)):
        return '<c r="%s"><v>%s</v></c>' % (ref, v)
    return '<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (ref, escape(str(v)))


def make_xlsx(path: Path, sheets: dict, hidden: tuple = (), merges: dict | None = None) -> Path:
    """sheets: {name: {"B12": value}}; value = str | int | float | F."""
    merges = merges or {}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        names = list(sheets)
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>')
        z.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="%s" xmlns:r="%s"><sheets>%s</sheets></workbook>' % (
            NS_MAIN, NS_REL, "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"%s/>' % (escape(n), i + 1, i + 1, ' state="hidden"' if n in hidden else "") for i, n in enumerate(names))))
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="%s">%s</Relationships>' % (
            NS_PKG, "".join('<Relationship Id="rId%d" Target="worksheets/sheet%d.xml"/>' % (i + 1, i + 1) for i in range(len(names)))))
        for i, n in enumerate(names):
            rows: dict = {}
            for ref, v in sheets[n].items():
                rows.setdefault(int(re.sub(r"[A-Z]+", "", ref)), []).append((ref, v))

            def colnum(ref):
                n_ = 0
                for ch in re.match(r"[A-Z]+", ref).group():
                    n_ = n_ * 26 + ord(ch) - 64
                return n_
            body = "".join('<row r="%d">%s</row>' % (r, "".join(_cell_xml(ref, v) for ref, v in sorted(rows[r], key=lambda x: colnum(x[0])))) for r in sorted(rows))
            mc = merges.get(n, [])
            mxml = ('<mergeCells count="%d">%s</mergeCells>' % (len(mc), "".join('<mergeCell ref="%s"/>' % m for m in mc))) if mc else ""
            z.writestr("xl/worksheets/sheet%d.xml" % (i + 1), '<?xml version="1.0"?><worksheet xmlns="%s"><sheetData>%s</sheetData>%s</worksheet>' % (NS_MAIN, body, mxml))
    return path


def make_docx(path: Path, blocks: list) -> Path:
    """blocks: ("p", text) | ("table", [[cell, ...], ...]) | ("img", alt)."""
    def para(text):
        return '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % escape(text)
    body = ""
    for kind, value in blocks:
        if kind == "p":
            body += para(value)
        elif kind == "table":
            body += "<w:tbl>%s</w:tbl>" % "".join("<w:tr>%s</w:tr>" % "".join("<w:tc>%s</w:tc>" % para(str(c)) for c in row) for row in value)
        elif kind == "img":
            body += '<w:p><w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"><wp:docPr id="1" name="%s" descr="%s"/></wp:inline></w:drawing></w:r></w:p>' % (escape(value), escape(value))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>')
        z.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="%s"><w:body>%s</w:body></w:document>' % (NS_W, body))
    return path


def png_bytes(w: int = 4, h: int = 3) -> bytes:
    raw = b"".join(b"\x00" + bytes((x * 40) % 256 for x in range(w * 3)) for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def jpeg_bytes(w: int = 640, h: int = 480) -> bytes:
    """Header-only JPEG (SOI, APP0, SOF0, EOI): enough for type sniffing and size; pixels are not decoded."""
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof0 = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, h, w, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + sof0 + b"\xff\xd9"


def make_pdf(path: Path, pages: list, image_pages: tuple = ()) -> Path:
    """pages: list of lists of text lines; page numbers in image_pages get only a picture (no text layer)."""
    doc = pdfgen.PdfDoc(title="Documento sintético")
    for i, lines in enumerate(pages, start=1):
        if i in image_pages:
            doc.add_page([pdfgen.PdfDoc.image(60, 300, 400, 300)])
        else:
            doc.add_page([pdfgen.PdfDoc.text(60, 780 - 18 * k, line) for k, line in enumerate(lines)])
    doc.save(path)
    return path


# ---- a complete synthetic source set (state "MG", year 2026: values are invented) ----

ORIENT_P1 = "As eletivas devem ter relação direta com a Base Nacional Comum Curricular e com os itinerários."
ORIENT_P2 = "O acolhimento dos estudantes acontece na primeira semana letiva com participação dos jovens protagonistas."
GESTAO_P1 = "O plano de ação da escola é elaborado pela equipe gestora e revisado a cada bimestre com indicadores."
ICE_PED = [("EL1", "Relação direta com a BNCC", "Eletivas de Base"), ("EL2", "Uso de metodologias ativas", "Eletivas de Base"),
           ("AC1", "Acolhimento inicial dos estudantes", "Acolhimento")]
ICE_GES = [("PA1", "Plano de ação elaborado pela equipe gestora", "Plano de Ação"), ("PA2", "Monitoramento bimestral de indicadores", "Plano de Ação")]
CLASSES = ["Formação Geral Básica", "Aprofundamento", "Eletivas de Base", "Projeto de Vida", "Estudo Orientado e Avaliação Semanal",
           "Tutoria", "Práticas Experimentais", "Pós-Médio", "Projeto de Corresponsabilidade Social", "Protagonismo", "Recomposição",
           "Outros componentes da Parte Diversificada"]
MATRIX_ROWS = [("Língua Portuguesa", 5, 5, 5), ("Matemática", 5, 5, 5), ("Projeto de Vida", 2, 2, 0), ("Eletiva", 2, 2, 2),
               ("Estudo Orientado", 4, 4, 4), ("Robótica", 0, 2, 2)]


def ice_xlsx(path: Path, extra_ped: list | None = None) -> Path:
    ped = {"A1": "Elemento", "B1": "Elemento (2º nível)", "C1": "Código da orientação", "D1": "Orientação", "E1": "Classificação"}
    for i, (code, text, elem) in enumerate(ICE_PED + (extra_ped or []), start=2):
        ped.update({f"A{i}": elem, f"C{i}": code, f"D{i}": text, f"E{i}": "Imprescindível"})
    ges = {"A1": "Elemento", "B1": "Elemento (2º nível)", "C1": "Código da orientação", "D1": "Orientação", "E1": "Classificação"}
    for i, (code, text, elem) in enumerate(ICE_GES, start=2):
        ges.update({f"A{i}": elem, f"C{i}": code, f"D{i}": text, f"E{i}": "Imprescindível"})
    mat = {"A1": "Elemento", "B1": "Aulas semanais - 1ª série", "C1": "Aulas semanais - 2ª série", "D1": "Aulas semanais - 3ª série",
           "A2": "Língua Portuguesa", "B2": 4, "C2": 4, "D2": 4, "A3": "Química", "B3": 1, "C3": 1, "D3": 1}
    return make_xlsx(path, {"orientações_referenciais_ICE": ped, "orientações_modelo_gestão": ges, "matriz_referencial_ICE": mat})


def template_xlsx(path: Path, uf: str = "MG", filled: bool = True, rule_variant: str = "padrao") -> Path:
    """Cluster template: tabs 1.1/1.2 (codes), '2.1 Revisão Matriz <UF>' (matrix + formulas), hidden 'classificacoes'."""
    t11 = {"B9": "Componente e/ou prática educativa (1º nível)", "C9": "Componente e/ou prática educativa (2º nível)", "D9": "Código da orientação",
           "E9": "Orientação", "F9": "Classificação", "G8": uf, "G9": "2026", "H9": "Observações/comentários"}
    for k, (code, text, elem) in enumerate(ICE_PED):
        t11.update({f"B{10 + k}": elem, f"C{10 + k}": "-", f"D{10 + k}": code, f"E{10 + k}": text, f"F{10 + k}": "Imprescindível"})
        if filled:
            t11[f"G{10 + k}"] = "Sim" if code != "EL2" else "Não"
    t12 = {"B9": "Componente e/ou prática educativa (1º nível)", "C9": "Componente e/ou prática educativa (2º nível)", "D9": "Código da orientação",
           "E9": "Orientação", "F9": "Classificação", "G8": uf, "G9": "2026", "H9": "Observações/comentários"}
    for k, (code, text, elem) in enumerate(ICE_GES):
        t12.update({f"B{10 + k}": elem, f"C{10 + k}": "-", f"D{10 + k}": code, f"E{10 + k}": text, f"F{10 + k}": "Imprescindível"})
        if filled:
            t12[f"G{10 + k}"] = "SIM"
    m = {"B4": "Estado (sigla UF)", "C4": uf, "B6": "Tempo de hora-aula (minutos)", "C6": 50, "B8": "Ano de vigência da matriz", "C8": 2026,
         "C10": "Aulas semanais", "B11": "Componente Curricular", "C11": "1ª série", "D11": "2ª série", "E11": "3ª série", "F11": "Classificação",
         "J11": "Elemento", "K11": "Aulas semanais - 1ª série", "L11": "Aulas semanais - 2ª série", "M11": "Aulas semanais - 3ª série"}
    analyst = {"Língua Portuguesa": "Formação Geral Básica", "Matemática": "Formação Geral Básica", "Projeto de Vida": "Projeto de Vida",
               "Eletiva": "Eletivas de Base", "Estudo Orientado": "Estudo Orientado e Avaliação Semanal", "Robótica": "Aprofundamento"}
    if filled:
        for k, (name, a, b, c) in enumerate(MATRIX_ROWS):
            m.update({f"B{12 + k}": name, f"C{12 + k}": a, f"D{12 + k}": b, f"E{12 + k}": c, f"F{12 + k}": analyst[name]})
    m["J12"] = "Matriz completa"
    for col in "KLM":
        m[f"{col}12"] = F(f"SUM({col}13:{col}24)", si=None)
    for k, cls in enumerate(CLASSES):
        r = 13 + k
        m[f"J{r}"] = cls
        for si, (col, src) in enumerate(zip("KLM", "CDE")):
            m[f"{col}{r}"] = F(f"SUMIFS(${src}:${src},$F:$F,$J{r})", si=si, ref=f"{col}13:{col}24") if k == 0 else F("", si=si)
    m["J25"], m["J26"], m["J27"] = "Projeto de Vida + Pós-Médio", "Itinerários Formativos", "Parte Diversificada"
    m["K25"], m["L25"], m["M25"] = F("K16+K20"), F("L16+L20", si=3, ref="L25:M25"), F("", si=3)
    m["K26"], m["L26"], m["M26"] = F("K12-K13"), F("L12-L13"), F("M12-M13")
    m["K27"], m["L27"], m["M27"] = F("K26-K14"), F("L26-L14"), F("M26-M14")
    if rule_variant == "alterada":
        m["K27"] = F("K26-K14-K15")
    cls_sheet = {"B9": "Classificações", **{f"B{10 + i}": c for i, c in enumerate(CLASSES)}}
    return make_xlsx(path, {"1.1 Base orient. pedagógicas": t11, "1.2 Base orient. gestão": t12, f"2.1 Revisão Matriz {uf}": m, "classificacoes": cls_sheet},
                     hidden=("classificacoes",), merges={f"2.1 Revisão Matriz {uf}": ["C10:E10"]})


def matrix_xlsx(path: Path, with_technical: bool = True, missing_cache: bool = False) -> Path:
    """State matrix workbook: 9h propedêutico sheet (+ a technical offer sheet as a trap)."""
    s = {"A1": "MATRIZ CURRICULAR - ENSINO MÉDIO EM TEMPO INTEGRAL 9 HORAS - PROPEDÊUTICO - VIGÊNCIA 2026",
         "A2": "Duração da hora-aula: 50 minutos", "A3": "Componente", "B3": "1ª série", "C3": "2ª série", "D3": "3ª série", "E3": "Total"}
    for i, (name, a, b, c) in enumerate(MATRIX_ROWS, start=4):
        s.update({f"A{i}": name, f"B{i}": a, f"C{i}": b, f"D{i}": c, f"E{i}": F(f"SUM(B{i}:D{i})", None if missing_cache else a + b + c)})
    last = 3 + len(MATRIX_ROWS)
    s[f"A{last + 1}"] = "Total semanal"
    s[f"B{last + 1}"] = F(f"SUM(B4:B{last})", None if missing_cache else sum(r[1] for r in MATRIX_ROWS))
    sheets = {"Integral 9h": s}
    if with_technical:
        sheets["Técnico"] = {"A1": "MATRIZ CURRICULAR - ENSINO MÉDIO INTEGRADO À EDUCAÇÃO PROFISSIONAL TÉCNICA", "A3": "Componente", "B3": "1ª série",
                             "A4": "Matemática", "B4": 3}
    return make_xlsx(path, sheets, merges={"Integral 9h": ["A1:E1"]})


def orientations_pdf(path: Path, with_image_page: bool = False, conflicting_eo: bool = False) -> Path:
    pages = [["Diretrizes pedagógicas da rede estadual 2026", ORIENT_P1, ORIENT_P2],
             ["Organização curricular", "Estudo Orientado: 4 aulas na 1ª série, 4 na 2ª e " + ("5" if conflicting_eo else "4") + " na 3ª série."]]
    if with_image_page:
        pages.append(["(página digitalizada)"])
    return make_pdf(path, pages, image_pages=(3,) if with_image_page else ())


def management_docx(path: Path) -> Path:
    return make_docx(path, [("p", "Caderno de gestão escolar 2026"), ("p", GESTAO_P1),
                            ("table", [["Instrumento", "Periodicidade"], ["Plano de ação", "Anual"], ["Monitoramento", "Bimestral"]]),
                            ("img", "Organograma da escola")])


def source_set(folder: Path, **kw) -> Path:
    """Writes the four classes + a manifest; returns the manifest path. kw: image_page, conflicting_eo, missing_cache, homologado."""
    folder.mkdir(parents=True, exist_ok=True)
    orientations_pdf(folder / "diretrizes.pdf", kw.get("image_page", False), kw.get("conflicting_eo", False))
    management_docx(folder / "gestao.docx")
    matrix_xlsx(folder / "matriz.xlsx", missing_cache=kw.get("missing_cache", False))
    template_xlsx(folder / "template.xlsx", rule_variant=kw.get("rule_variant", "padrao"))
    ice_xlsx(folder / "ice.xlsx", extra_ped=kw.get("ice_extra"))
    manifest = {
        "schema_version": "1.0", "solicitacao_id": "SINTETICO-001", "revisao": 1, "uf": "MG", "ano": 2026, "modelo": "9h", "modalidade": "propedeutico",
        "entradas": {"orientacoes_estaduais": [{"uri": "diretrizes.pdf", "papel": "orientacao"}, {"uri": "gestao.docx", "papel": "orientacao"}],
                     "matriz_estadual": [{"uri": "matriz.xlsx", "papel": "matriz", "vigencia": "2026"}],
                     "template_cluster": [{"uri": "template.xlsx", "papel": "template"}],
                     "referencial_ice": [{"uri": "ice.xlsx", "papel": "referencial", "versao": "SINTETICA-1"}]},
        "homologacao_ice": {"versao": "SINTETICA-1", "aprovado_por": "Coordenação (sintético)", "data": "2026-11-16"} if kw.get("homologado", True) else None,
        "regras_homologadas": [], "aplicabilidade_codigos": None}
    extra = kw.get("extra_entries") or {}
    for cls, entries in extra.items():
        manifest["entradas"][cls] += entries
    path = folder / "manifesto.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
