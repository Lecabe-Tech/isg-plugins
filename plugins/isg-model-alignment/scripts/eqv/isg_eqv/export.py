"""Output files (SPEC-005 REQ-CRS-04..08): a SEPARATE .xlsx and .csv per tab, a readable summary and the full JSON. Standard library only.

The analysts' template is never touched. The result keeps the template's row order so its columns can be pasted back.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from . import EQV_VERSION
from . import store as S

HEADERS = ["Código", "Bloco", "Sub-bloco", "Orientação", "Classificação", "Valor", "Comentário", "Confiança (%)", "Revisar", "Explicação", "Evidências", "Decidido por"]
WIDTHS = [10, 22, 22, 60, 16, 8, 70, 12, 9, 60, 80, 14]
OTHER_DOC = re.compile(r"caderno|\bEO\b|instru[cç][aã]o|portaria|resolu[cç][aã]o|nota t[eé]cnica|decreto|\blei\b|parecer", re.I)


def evidence_text(cell: dict) -> str:
    parts = []
    for e in cell.get("evidencias", []):
        flag = "" if e.get("verificada") else " [NÃO VERIFICADA]"
        src = "" if e.get("origem", "texto") == "texto" else " [interpretação de imagem, IA]"
        parts.append(f"Pág. {e.get('pagina')} ({e.get('documento')}) [{e.get('relacao', '')}]{src}{flag}: \"{re.sub(chr(32) + '+', ' ', str(e.get('trecho', ''))).strip()}\"")
    a = cell.get("ausencia")
    if a:
        parts.append("Ausência: " + "; ".join(str(x) for x in a.get("itens_considerados", [])) + " | Onde se procurou: " + str(a.get("onde_procurou", "")))
    return "\n".join(parts)


def rows_for_tab(rd: Path, tab: str, orient: list, cells: dict) -> list:
    rows = []
    for o in orient:
        c = cells.get((tab, o["codigo"]))
        base = [o["codigo"], o["grupo"], o["subgrupo"], o["orientacao"], o["classificacao"]]
        if c is None:
            rows.append(base + ["", "", "", "Sim", "Ainda não comparada.", "", ""])
            continue
        why = c.get("explicacao", "")
        if c.get("revisar") and c.get("motivos"):
            why = (why + "\nRevisar: " + "; ".join(c["motivos"])).strip()
        rows.append(base + [c["valor_planilha"], c.get("comentario", ""), c["confianca"], "Sim" if c.get("revisar") else "Não", why, evidence_text(c),
                            "Analista" if c.get("decidido_por") == "analista" else "IA"])
    return rows


# ---------------------------------------------------------------- xlsx (minimal, standard library)

def col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path: Path, headers: list, rows: list, widths: list, flag_col: int | None = None) -> None:
    def cell(ref, value, style):
        if value == "" or value is None:
            return f'<c r="{ref}" s="{style}"/>'
        if isinstance(value, int) and not isinstance(value, bool):
            return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
        return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'

    sheet_rows = ['<row r="1">' + "".join(cell(f"{col_letter(i + 1)}1", h, 1) for i, h in enumerate(headers)) + "</row>"]
    for r, row in enumerate(rows, start=2):
        flagged = flag_col is not None and str(row[flag_col]) == "Sim"
        cells = []
        for i, v in enumerate(row):
            style = 2 if (flagged and i in (flag_col, flag_col - 3)) else 3
            cells.append(cell(f"{col_letter(i + 1)}{r}", v, style))
        sheet_rows.append(f'<row r="{r}">' + "".join(cells) + "</row>")
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths))
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    sheet = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
             f'<cols>{cols}</cols><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>')
    styles = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="{ns}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
              '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/></patternFill></fill></fills>'
              '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
              '<xf numFmtId="0" fontId="0" fillId="2" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
              '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs></styleSheet>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   '<sheets><sheet name="Resultado" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                   '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/worksheets/sheet1.xml", sheet)


def write_csv(path: Path, headers: list, rows: list) -> None:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")  # ';' and BOM: opens correctly in Excel with Brazilian settings
    w.writerow(headers)
    w.writerows(rows)
    path.write_text("﻿" + buf.getvalue(), encoding="utf-8", newline="")


# ---------------------------------------------------------------- summary, completeness, measurement

def completeness(rd: Path, documents: dict, orient: dict, cells: dict) -> dict:
    reasons = []
    missing = sum(1 for tab, rows in orient.items() for o in rows if (tab, o["codigo"]) not in cells)
    if missing:
        reasons.append(f"{missing} orientação(ões) ainda não comparada(s)")
    if any(d["situacao"] == "Reprovado" for d in documents.values()):
        reasons.append("há documento Reprovado no CFP")
    pending = sum(S._pending_images(d["pasta"]) for d in documents.values())
    if pending:
        reasons.append(f"{pending} imagem(ns) dos documentos ainda não interpretada(s) pelo SIP")
    return {"completo": not reasons, "motivos": reasons}


def export(rd: Path) -> dict:
    run = S.read_json(rd / "execucao.json")
    orient_all = S.read_json(rd / "orientacoes.json")
    orient = orient_all["orientacoes"]
    documents = S.load_documents(rd)
    cells = S.load_cells(rd)
    written, summary_tabs = [], {}
    for tab, rows_o in orient.items():
        rows = rows_for_tab(rd, tab, rows_o, cells)
        write_xlsx(rd / f"resultado_{tab}.xlsx", HEADERS, rows, WIDTHS, flag_col=8)
        write_csv(rd / f"resultado_{tab}.csv", HEADERS, rows)
        written += [f"resultado_{tab}.xlsx", f"resultado_{tab}.csv"]
        done = [cells[(tab, o["codigo"])] for o in rows_o if (tab, o["codigo"]) in cells]
        summary_tabs[tab] = {"orientacoes": len(rows_o), "comparadas": len(done), "sim": sum(c["valor"] == "Sim" for c in done), "nao": sum(c["valor"] == "Não" for c in done),
                             "revisar": sum(bool(c["revisar"]) for c in done), "por_analista": sum(c.get("decidido_por") == "analista" for c in done),
                             "abaixo_do_minimo": sum(1 for c in done if any("abaixo do mínimo" in m for m in c.get("motivos", [])))}
    comp = completeness(rd, documents, orient, cells)
    result = {"uf": run["uf"], "ano": run["ano"], "planilha_sha256": run["planilha_sha256"], "versao_eqv": EQV_VERSION, "gerado_em": S.now(),
              "documentos": {k: {"sha256": v["sha256"], "titulo": v["titulo"], "versao_cfp": v["versao_cfp"], "situacao": v["situacao"]} for k, v in documents.items()},
              "abas": summary_tabs, "comparacao_completa": comp, "celulas": [cells[k] for k in sorted(cells)]}
    S.write_json(rd / "resultado.json", result)
    (rd / "resultado.md").write_text(render_md(run, documents, summary_tabs, comp), encoding="utf-8", newline="\n")
    written += ["resultado.md", "resultado.json"]
    return {"arquivos": written, "pasta": str(rd), "abas": summary_tabs, "comparacao_completa": comp}


def render_md(run: dict, documents: dict, tabs: dict, comp: dict) -> str:
    l = [f"# Comparação EQV — {run['uf']} {run['ano']}", "", f"**Comparação completa: {'sim' if comp['completo'] else 'não'}**", ""]
    if comp["motivos"]:
        l += ["Falta:"] + [f"- {m}" for m in comp["motivos"]] + [""]
    l += ["| Aba | Orientações | Comparadas | Sim | Não | Revisar | Decididas por analista |", "|---|---|---|---|---|---|---|"]
    for tab, s in sorted(tabs.items()):
        l.append(f"| {tab} | {s['orientacoes']} | {s['comparadas']} | {s['sim']} | {s['nao']} | {s['revisar']} | {s['por_analista']} |")
    l += ["", "## Documentos usados", ""] + [f"- **{k}** — {v['titulo']} (situação no CFP: {v['situacao']})" for k, v in documents.items()]
    l += ["", "Comparação feita com **apenas** estes documentos; se os analistas usam outros, as respostas podem divergir.",
          "Os valores e comentários marcados *(pré-preenchido por IA)* são **propostas**: confira no PDF as células com **Revisar = Sim**.", ""]
    return "\n".join(l)


def measure(rd: Path) -> dict:
    """Agreement with the analysts' answers (REQ-CQL-05, 6.2). Cells whose analyst comment cites a document we do not have are counted apart."""
    key = S.read_json(rd / "gabarito.json")
    cells = S.load_cells(rd)
    documents = S.load_documents(rd)
    labels = [l.lower() for l in documents]
    m = {"comparadas": 0, "sem_resposta_do_analista": 0, "excluidas_outros_documentos": 0, "avaliadas": 0, "concordam": 0, "falso_sim": 0, "falso_nao": 0, "revisar": 0,
         "paginas_citadas_pelo_analista_encontradas": 0, "paginas_comparaveis": 0}
    detail = []
    for (tab, code), c in sorted(cells.items()):
        m["comparadas"] += 1
        m["revisar"] += bool(c["revisar"])
        k = key.get(f"{tab}|{code}|{c['uf']}|{c['ano']}")
        val = S.R.normalize_value(k["valor"]) if k else None
        if val is None:
            m["sem_resposta_do_analista"] += 1
            continue
        comment = k.get("comentario", "")
        if OTHER_DOC.search(comment) and not any(l in comment.lower() for l in labels):
            m["excluidas_outros_documentos"] += 1
            continue
        m["avaliadas"] += 1
        if val == c["valor"]:
            m["concordam"] += 1
        elif c["valor"] == "Sim":
            m["falso_sim"] += 1
            detail.append({"cod": code, "tab": tab, "ia": "Sim", "analista": "Não"})
        else:
            m["falso_nao"] += 1
            detail.append({"cod": code, "tab": tab, "ia": "Não", "analista": "Sim"})
        cited = {int(n) for mm in re.finditer(r"P[áa]?gs?\.?\s*:?\s*([\d][\d\s,e.\-]*)", comment, re.I) for n in re.findall(r"\d+", mm.group(1))}
        if cited and c["valor"] == "Sim":
            m["paginas_comparaveis"] += 1
            m["paginas_citadas_pelo_analista_encontradas"] += bool(cited & {e["pagina"] for e in c["evidencias"] if e.get("verificada")})
    m["concordancia_pct"] = round(100 * m["concordam"] / m["avaliadas"], 1) if m["avaliadas"] else None
    m["divergencias"] = detail
    return m
