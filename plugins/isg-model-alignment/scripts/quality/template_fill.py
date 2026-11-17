"""Filled copy of the cluster template from the validated result (lesson of the CE 2026 pilot).

The analysts work in the cluster template: one line per orientation with Sim or Não and an observation, and the matrix
tab of the UF. Counts in a summary do not replace that view. This module writes a COPY of the template the analyst sent
(the bytes kept in the run folder), changing only:
  * tabs 1.1 and 1.2: the value and observation columns of the UF and year (found from the headers, never from fixed
    letters): Sim / Não / Pendente per line, observation 'Pág. X (documento): "trecho"', '[Revisar: confiança X%]';
  * the UF matrix tab: the component table (name, 1ª-3ª série, classification, observation), the class-hour minutes and
    the validity year. A range stays as text ('3 ou 4'); lines with the same name and classification are added up, the
    way the analysts fill the template; a value read from an image is written and said in the observation;
  * cells that need a human decision are highlighted in yellow; formulas are recalculated when Excel opens the file.
Everything else (other UFs, styles, lists, drawings, formulas) is copied byte for byte. Standard library only: the
workbook is a zip of XML and only the touched parts are rewritten. Nothing is written to the central base or SharePoint.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import document_normalizer as DN
import quality_result as QR
import source_resolver as SR
import template_rules as TR

YELLOW = "FFFFE699"
MIN_CONF = 85


class FillError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------- workbook parts ----------------

def _sheet_paths(z: zipfile.ZipFile) -> dict:
    """{sheet name: part path inside the zip}."""
    wb = z.read("xl/workbook.xml").decode("utf-8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    targets = {m.group(1): m.group(2) for m in re.finditer(r'<Relationship\b[^>]*?Id="([^"]+)"[^>]*?Target="([^"]+)"', rels)}
    targets.update({m.group(2): m.group(1) for m in re.finditer(r'<Relationship\b[^>]*?Target="([^"]+)"[^>]*?Id="([^"]+)"', rels)})
    out = {}
    for m in re.finditer(r"<sheet\b([^>]*)/?>", wb):
        attrs = m.group(1)
        name = re.search(r'name="([^"]*)"', attrs)
        rid = re.search(r'r:id="([^"]*)"', attrs) or re.search(r'\bid="([^"]*)"', attrs)
        if not (name and rid and rid.group(1) in targets):
            continue
        t = targets[rid.group(1)]
        path = t.lstrip("/") if t.startswith("/") else "xl/" + t
        out[_unescape(name.group(1))] = path
    return out


def _unescape(s: str) -> str:
    return s.replace("&quot;", '"').replace("&apos;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


class Styles:
    """Adds a yellow copy of a cell style when a cell needs a decision."""

    def __init__(self, xml: str | None):
        self.xml = xml
        self.new: list = []
        self.cache: dict = {}
        fills = re.search(r'<fills count="(\d+)">(.*?)</fills>', xml or "", re.S)
        xfs = re.search(r'<cellXfs count="(\d+)">(.*?)</cellXfs>', xml or "", re.S)
        self.enabled = bool(fills and xfs)
        if not self.enabled:  # a workbook without a style sheet: the values are written, without the yellow mark
            return
        self.fill_id = int(fills.group(1))
        self.xml = xml.replace(fills.group(0), f'<fills count="{self.fill_id + 1}">{fills.group(2)}'
                               f'<fill><patternFill patternType="solid"><fgColor rgb="{YELLOW}"/><bgColor indexed="64"/></patternFill></fill></fills>')
        xfs = re.search(r'<cellXfs count="(\d+)">(.*?)</cellXfs>', self.xml, re.S)
        self.xfs = re.findall(r"<xf\b[^>]*/>|<xf\b[^>]*>.*?</xf>", xfs.group(2), re.S)
        self.new: list = []
        self.cache: dict = {}

    def yellow(self, s: str | None) -> str | None:
        if not self.enabled or not self.xfs:
            return s
        k = int(s or 0)
        if k not in self.cache:
            x = self.xfs[k] if k < len(self.xfs) else self.xfs[0]
            x = re.sub(r'fillId="\d+"', f'fillId="{self.fill_id}"', x) if "fillId=" in x else x.replace("<xf ", f'<xf fillId="{self.fill_id}" ', 1)
            x = re.sub(r'applyFill="\d"', 'applyFill="1"', x) if "applyFill=" in x else x.replace("<xf ", '<xf applyFill="1" ', 1)
            self.new.append(x)
            self.cache[k] = str(len(self.xfs) + len(self.new) - 1)
        return self.cache[k]

    def output(self) -> str | None:
        if not self.enabled or not self.new:
            return self.xml
        xfs = re.search(r'<cellXfs count="(\d+)">(.*?)</cellXfs>', self.xml, re.S)
        return self.xml.replace(xfs.group(0), f'<cellXfs count="{len(self.xfs) + len(self.new)}">{xfs.group(2)}{"".join(self.new)}</cellXfs>')


class Sheet:
    """Minimal cell editor on the worksheet XML (keeps every other cell and attribute)."""

    def __init__(self, xml: str, styles: Styles):
        self.xml = xml
        self.styles = styles
        self.touched: set = set()

    @staticmethod
    def _cell_re(ref: str):
        return re.compile(r'<c r="%s"(?:\s[^>]*?)?(?:/>|>.*?</c>)' % ref, re.S)

    def style(self, ref: str) -> str | None:
        m = self._cell_re(ref).search(self.xml)
        s = re.search(r'\ss="(\d+)"', m.group(0)) if m else None
        return s.group(1) if s else None

    def set(self, ref: str, value, yellow: bool = False, style_from: str | None = None) -> None:
        self.touched.add(ref)
        m = self._cell_re(ref).search(self.xml)
        s = self.style(ref) or (self.style(style_from) if style_from else None)
        if yellow:
            s = self.styles.yellow(s)
        sa = f' s="{s}"' if s is not None else ""
        if value is None or value == "":
            new = f'<c r="{ref}"{sa}/>'
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            new = f'<c r="{ref}"{sa}><v>{int(value) if float(value).is_integer() else value}</v></c>'
        else:
            new = f'<c r="{ref}"{sa} t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'
        if m:
            self.xml = self.xml[:m.start()] + new + self.xml[m.end():]
            return
        col, row = re.match(r"([A-Z]+)(\d+)", ref).groups()
        rm = re.search(r'<row r="%s"(?:\s[^>]*?)?(?:/>|>(.*?)</row>)' % row, self.xml, re.S)
        if rm is None:
            self._add_row(int(row), new)
            return
        if rm.group(0).endswith("/>") and rm.group(1) is None:
            self.xml = self.xml[:rm.start()] + rm.group(0)[:-2] + ">" + new + "</row>" + self.xml[rm.end():]
            return
        inner = rm.group(1)
        pos = len(inner)
        for c in re.finditer(r'<c r="([A-Z]+)\d+"', inner):
            if DN.col_to_num(c.group(1)) > DN.col_to_num(col):
                pos = c.start()
                break
        self.xml = self.xml[:rm.start(1)] + inner[:pos] + new + inner[pos:] + self.xml[rm.end(1):]

    def _add_row(self, row: int, cell: str) -> None:
        new = f'<row r="{row}">{cell}</row>'
        for m in re.finditer(r'<row r="(\d+)"', self.xml):
            if int(m.group(1)) > row:
                self.xml = self.xml[:m.start()] + new + self.xml[m.start():]
                return
        if "<sheetData/>" in self.xml:
            self.xml = self.xml.replace("<sheetData/>", f"<sheetData>{new}</sheetData>", 1)
        else:
            self.xml = self.xml.replace("</sheetData>", new + "</sheetData>", 1)

    def finish(self, drop_formula_cache: bool = False) -> str:
        """Removes hyperlinks on the touched cells and, for the matrix tab, the cached formula results."""
        def keep(m):
            ref = re.search(r'ref="([A-Z]+\d+)"', m.group(0))
            return "" if ref and ref.group(1) in self.touched else m.group(0)
        x = re.sub(r"<hyperlink\b[^>]*/>", keep, self.xml)
        x = re.sub(r"<hyperlinks>\s*</hyperlinks>", "", x)
        if drop_formula_cache:
            # numeric formula cells only: a text formula (t="str") without its cached value makes Excel repair the file
            x = re.sub(r'(<c\b(?![^>]*\bt=)[^>]*>(?:<f\b[^>]*/>|<f\b[^>]*>.*?</f>))<v>.*?</v>', r"\1", x, flags=re.S)
        return x


# ---------------- what goes into the cells ----------------

def _where(ev: dict, names: dict) -> str:
    loc = ev.get("localizacao") or {}
    doc = names.get(ev.get("fonte_id"), ev.get("fonte_id") or "")
    if loc.get("tipo") in ("pdf_page", "image_region"):
        place = f"Pág. {loc.get('pagina')}" + (" (imagem)" if loc.get("tipo") == "image_region" else "")
    elif loc.get("tipo") == "sheet_cell":
        place = f"{loc.get('aba')}!{loc.get('celula')}"
    elif loc.get("tipo") == "paragraph":
        place = f"Parágrafo {loc.get('paragrafo')}"
    else:
        place = ev.get("unidade") or ""
    return f"{place} ({doc})"


def orientation_cells(o: dict, names: dict) -> tuple:
    """(value, observation, needs_decision) of one orientation line."""
    conf = o.get("confianca")
    low = isinstance(conf, (int, float)) and conf < MIN_CONF
    tail = f" [Revisar: confiança {conf}%]" if (o.get("revisar") and conf is not None) else (" [Revisar]" if o.get("revisar") else "")
    if o["presenca"] == "Sim":
        evs = [e for e in o["evidencias"] if e.get("verificacao") == "conferida"] or o["evidencias"]
        txt = " | ".join(f'{_where(e, names)}: "{e.get("trecho_literal", "").strip()}"' for e in evs[:3])
        return "Sim", (txt or (o.get("justificativa") or "")) + tail, bool(o.get("revisar") or low)
    if o["presenca"] == "Não":
        docs = ", ".join(names.get(d, d) for d in o.get("fontes_verificadas") or [])
        return "Não", f"{(o.get('justificativa') or '').strip()} [Ausência verificada em: {docs}]".strip() + tail, bool(o.get("revisar") or low)
    why = (o.get("justificativa") or "") or "; ".join(o.get("motivos") or [])
    return "Pendente", f"PENDENTE (sem prova suficiente para Sim ou Não): {why}".strip(), True


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def matrix_lines(comps: list) -> list:
    """Template lines: components with the same name and classification added up, per grade:
    {'nome', 'classificacao', 'valores': [v1, v2, v3], 'amarelo': [b1, b2, b3], 'amarelo_classe', 'obs'}."""
    groups: dict = {}
    order = []
    for c in comps:
        key = (DN.squash(c["nome_original"]), c["classificacao"] or "")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(c)
    lines = []
    for key in order:
        cs = groups[key]
        vals, yel, notes = [], [], []
        for s in QR.SERIES:
            lo = hi = 0
            text_range, unknown, image = False, False, False
            for c in cs:
                cell = c["aulas_semanais"][s]
                if cell["status"] == "verificado":
                    lo += cell["valor"]
                    hi += cell["valor"]
                elif cell.get("faixa"):
                    lo += cell["faixa"]["min"]
                    hi += cell["faixa"]["max"]
                    text_range = True
                elif cell["status"] == "ausente_na_fonte" or (cell.get("motivo") or "").startswith("Ausência lida em imagem"):
                    pass
                elif _num(cell.get("valor_proposto")):
                    lo += cell["valor_proposto"]
                    hi += cell["valor_proposto"]
                    image = True
                else:
                    unknown = True
            if unknown:
                vals.append(None)
                yel.append(True)
            elif text_range:
                vals.append(f"{_fmt(lo)} ou {_fmt(hi)}" if len(cs) == 1 else f"{_fmt(lo)} a {_fmt(hi)}")
                yel.append(True)
            else:
                vals.append(lo)
                yel.append(False)
            if image:
                notes.append("valores lidos de imagem (IA)")
        c0 = cs[0]
        obs = []
        if len(cs) > 1:
            obs.append(f"Soma de {len(cs)} linhas da fonte com este nome")
        if any(y and isinstance(v, str) for v, y in zip(vals, yel)):
            obs.append("faixa na fonte: valor exato pendente")
        if any(v is None for v in vals):
            obs.append("valor não verificado: conferir na fonte")
        if notes:
            obs.append(notes[0])
        cls_pend = any(c["classificacao_status"] != "aceita" for c in cs)
        conf = next((m for c in cs for m in c["motivos"] if m.startswith("confiança da classificação")), None)
        if cls_pend:
            obs.append("classificação pendente")
        elif conf:
            obs.append("revisar " + conf)
        pages = sorted({c["aulas_semanais"][s]["evidencia"]["localizacao"].get("pagina") for c in cs for s in QR.SERIES
                        if c["aulas_semanais"][s]["evidencia"] and c["aulas_semanais"][s]["status"] != "ausente_na_fonte"
                        and not (c["aulas_semanais"][s].get("motivo") or "").startswith("Ausência lida em imagem")} - {None})
        if pages:
            obs.append("fonte: pág. " + ", ".join(str(p) for p in pages))
        text = "; ".join(obs)
        lines.append({"nome": c0["nome_original"], "classificacao": c0["classificacao"], "valores": vals, "amarelo": yel,
                      "amarelo_classe": cls_pend or bool(conf), "obs": (text[:1].upper() + text[1:]) if text else None})
    return lines


def _fmt(v):
    return int(v) if _num(v) and float(v).is_integer() else v


# ---------------- the whole fill ----------------

def default_path(run_dir: Path) -> Path | None:
    """Where the filled copy goes by default: next to the run folder, named after the template. None = no XLSX template."""
    run_dir = Path(run_dir)
    refs = SR.read_json(run_dir / "referencias.json") or {}
    inv = SR.read_json(run_dir / "inventario.json") or {}
    tid = (refs.get("template") or {}).get("fonte_id")
    f = next((x for x in inv.get("fontes", []) if x["id"] == tid), None)
    if not f or not (f.get("media_type") or "").endswith("spreadsheetml.sheet"):
        return None
    return run_dir.parent / f"{Path(f['nome']).stem} - preenchido {inv['uf']} {inv['ano']} (resultado do plugin).xlsx"


def fill(run_dir: Path, out: Path | None = None) -> dict:
    run_dir = Path(run_dir)
    res_path = run_dir / QR.RESULT_FILE
    if not res_path.exists():
        raise FillError("RESULTADO_AUSENTE", "Gere o resultado antes de preencher o template (comando resultado).")
    result = json.loads(res_path.read_text(encoding="utf-8"))
    if not QR.validate(result)["valido"]:
        raise FillError("RESULTADO_INVALIDO", "O resultado não passa na validação; corrija antes de preencher o template.")
    refs = TR.load_references(run_dir)
    tid = refs["template"]["fonte_id"]
    src = next(iter(sorted((run_dir / "originais").glob(f"{tid}.xlsx"))), None) if tid else None
    if src is None:
        raise FillError("TEMPLATE_AUSENTE", "A execução não tem o template do cluster em XLSX.")
    uf, ano = result["execucao"]["uf"], result["execucao"]["ano"]
    names = {f["id"]: Path(f["nome"]).stem for f in result["fontes"]}
    tname = next(f["nome"] for f in result["fontes"] if f["id"] == tid)
    out = Path(out) if out else (default_path(run_dir) or run_dir.parent / f"{Path(tname).stem} - preenchido {uf} {ano} (resultado do plugin).xlsx")
    T = TR._eqv()
    avisos, counts = [], {"pedagogicas": {"Sim": 0, "Não": 0, "Pendente": 0}, "gestao": {"Sim": 0, "Não": 0, "Pendente": 0}}
    try:
        tpl = T.read_template(src)
    except T.TemplateError as e:
        tpl = None
        avisos.append("Abas de orientações não preenchidas: " + e.message)
    wb = DN.read_workbook(src)
    mtab = TR.matrix_tab(wb, uf)
    rule = TR.matrix_rule(mtab, refs["template"]["classificacoes"]) if mtab else None
    with zipfile.ZipFile(src) as z:
        parts = {i.filename: z.read(i.filename) for i in z.infolist()}
        infos = z.infolist()
        paths = _sheet_paths(z)
    styles = Styles(parts["xl/styles.xml"].decode("utf-8") if "xl/styles.xml" in parts else None)
    changed: dict = {}

    if tpl:
        for tab, kind in (("1.1", "pedagogicas"), ("1.2", "gestao")):
            a = tpl["abas"][tab]
            col = a["colunas"].get(f"{uf}-{ano}")
            if not col:
                avisos.append(f"A aba {a['nome']} não tem a coluna de {uf} {ano}; as orientações dessa aba não foram preenchidas.")
                continue
            sh = Sheet(parts[paths[a["nome"]]].decode("utf-8"), styles)
            by = {o["codigo"]: o for o in result["orientacoes"][kind]}
            for row in a["orientacoes"]:
                o = by.get(row["codigo"])
                if o is None or o["status"] == "nao_avaliado":
                    continue
                val, obs, decide = orientation_cells(o, names)
                counts[kind][val] += 1
                sh.set(f"{col['valor']}{row['linha']}", val, yellow=decide)
                if col["comentario"]:
                    sh.set(f"{col['comentario']}{row['linha']}", obs)
            changed[paths[a["nome"]]] = sh.finish()

    matrix_rows = 0
    if rule and rule.get("layout"):
        lay = rule["layout"]
        cells = TR._cells(mtab)
        hrow = lay["linha_cabecalho"]
        obs_col = next((DN.num_to_col(c) for (c, r), v in sorted(cells.items()) if r == hrow and DN.fold(TR._text(v)).startswith("observac")), None)
        name_col, cls_col = lay["coluna_nome"], lay["coluna_classificacao"]
        scols = [lay["colunas_series"][s] for s in QR.SERIES]
        sh = Sheet(parts[paths[mtab["nome"]]].decode("utf-8"), styles)
        lines = matrix_lines(result["matriz"]["componentes"])
        first = hrow + 1
        old_end = first + len(rule["preenchimento"])
        model = f"{name_col}{first}"
        for i, ln in enumerate(lines):
            r = first + i
            sh.set(f"{name_col}{r}", ln["nome"], style_from=model)
            for col, v, y in zip(scols, ln["valores"], ln["amarelo"]):
                sh.set(f"{col}{r}", v, yellow=y, style_from=f"{col}{first}")
            sh.set(f"{cls_col}{r}", ln["classificacao"], yellow=ln["amarelo_classe"], style_from=f"{cls_col}{first}")
            if obs_col:
                sh.set(f"{obs_col}{r}", ln["obs"], style_from=f"{obs_col}{first}")
        for r in range(first + len(lines), old_end):  # analysts' lines beyond ours: emptied, never mixed with the result
            for col in [name_col, *scols, cls_col] + ([obs_col] if obs_col else []):
                sh.set(f"{col}{r}", None)
        matrix_rows = len(lines)
        minutes = result["matriz"]["minutos_aula"]
        mval = minutes["valor"] if minutes["status"] == "verificado" else minutes.get("valor_proposto")
        pos = TR.find_label(cells, "tempo", "hora-aula") or TR.find_label(cells, "hora aula")
        if pos:
            sh.set(f"{DN.num_to_col(pos[0] + 1)}{pos[1]}", mval, yellow=mval is None or minutes["status"] != "verificado")
        pos = TR.find_label(cells, "ano", "vigencia")
        if pos and result["matriz"]["selecao"].get("vigencia"):
            v = result["matriz"]["selecao"]["vigencia"]
            sh.set(f"{DN.num_to_col(pos[0] + 1)}{pos[1]}", int(v) if str(v).isdigit() else v)
        changed[paths[mtab["nome"]]] = sh.finish(drop_formula_cache=True)
    else:
        avisos.append(f"O template não tem a aba de matriz de {uf} com o layout esperado; a matriz não foi preenchida.")

    if not changed:
        raise FillError("NADA_PREENCHIDO", "Nada pôde ser preenchido no template: " + " ".join(avisos))
    if styles.output() is not None:
        changed["xl/styles.xml"] = styles.output()
    wbx = parts["xl/workbook.xml"].decode("utf-8")
    if "<calcPr" in wbx:
        wbx = re.sub(r"<calcPr\b([^>]*?)/>", lambda m: "<calcPr" + re.sub(r'\s*fullCalcOnLoad="\w+"', "", m.group(1)) + ' fullCalcOnLoad="1"/>', wbx)
    else:  # calcPr comes right after sheets/definedNames in the workbook schema
        anchor = "</definedNames>" if "</definedNames>" in wbx else "</sheets>"
        wbx = wbx.replace(anchor, anchor + '<calcPr fullCalcOnLoad="1"/>', 1)
    changed["xl/workbook.xml"] = wbx
    # calcChain.xml lists every formula cell; a filled cell that held a formula would make Excel repair the file.
    # Without it Excel rebuilds the chain when it opens the workbook.
    drop = {"xl/calcChain.xml"}
    changed["xl/_rels/workbook.xml.rels"] = re.sub(r'<Relationship\b[^>]*calcChain[^>]*/>', "", parts["xl/_rels/workbook.xml.rels"].decode("utf-8"))
    changed["[Content_Types].xml"] = re.sub(r'<Override\b[^>]*calcChain[^>]*/>', "", parts["[Content_Types].xml"].decode("utf-8"))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w") as zo:
        for info in infos:
            if info.filename in drop:
                continue
            data = changed[info.filename].encode("utf-8") if info.filename in changed else parts[info.filename]
            zo.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
    tmp.replace(out)
    return {"arquivo": str(out), "uf": uf, "ano": ano, "orientacoes": counts, "linhas_matriz": matrix_rows, "avisos": avisos,
            "resultado_sha256": result["execucao"]["conteudo_sha256"]}
