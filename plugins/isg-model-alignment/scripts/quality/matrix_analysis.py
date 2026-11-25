"""SPEC-017 G2: curricular matrix front (selection, literal transcription, classification, controlled consolidation).

Claude reads the sources and proposes; this module verifies every value against the cited unit and decides:
  * only a propedêutico 9h offer can be selected, and only inside the selected region are values accepted;
  * 0 (explicit zero), null 'ausente_na_fonte' (blank or dash in the source) and null 'nao_verificado' never mix;
  * values read from images stay unverified (kept as `valor_proposto`);
  * classifications must be in the template list and be justified by educational function, not by the name;
  * element totals only with the template rule whose fingerprint was approved by Quality (no 40-week factor,
    no hours: the 2026 template has none);
  * a value printed as a RANGE in the source ("3 ou 4h/a", lesson of the CE 2026 pilot) is kept as a range, never
    resolved to one number: status 'faixa', pending VALOR_EM_FAIXA, plus a check that the totals printed in the source
    fit inside the sums of the ranges, and the official document cited for the exact values (if any).
"""
from __future__ import annotations

import re
from pathlib import Path

import document_normalizer as DN
import evidence_check as EC
import quality_policy as QP
import quality_run as RUN
import source_resolver as SR
import template_rules as TR

SERIES = ("serie1", "serie2", "serie3")
NULL_REASONS = ("ausente_na_fonte", "nao_verificado")
MIN_CLASS_CONFIDENCE = QP.QUALITY_MIN_CONFIDENCE  # a valid category and a justification by function are still required
SIGNALS = {
    "9h": r"\b9 ?h\b|\b9 horas\b|nove horas|45 aulas|tempo integral|\bintegral\b",
    "propedeutico": r"propedeut",
    "tecnico": r"tecnic|profissional|eptnm",
    "7h": r"\b7 ?h\b|\b7 horas\b|sete horas|35 aulas",
    "outra_oferta": r"\bnoturn|\beja\b|jovens e adultos|parcial",
    "matriz": r"matriz curricular|matriz de referencia|organizacao curricular|carga horaria",
}


class MatrixError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def signals(text: str) -> list:
    t = DN.fold(text)
    return [k for k, rx in SIGNALS.items() if re.search(rx, t)]


def _region_of(unit: dict) -> str:
    uid = unit["id"]
    if unit["tipo"] == "sheet_cell":
        return uid.split("!")[0]
    if unit["tipo"] == "row" and "tabela" in unit["localizacao"]:
        return uid.rsplit("-l", 1)[0]
    return uid


def candidates(run_dir: Path) -> list:
    """Deterministic hint for Claude: regions of the state-matrix sources with offer signals and numbers."""
    inv = RUN.load_inventory(run_dir)
    units = RUN.load_units(run_dir)
    out = []
    for f in RUN.docs_of_class(inv, "matriz_estadual"):
        regions: dict = {}
        for u in units.get(f["id"], []):
            r = regions.setdefault(_region_of(u), {"regiao": _region_of(u), "fonte_id": f["id"], "unidades": 0, "numeros": 0, "texto": [], "status": set()})
            r["unidades"] += 1
            r["status"].add(u["status"])
            if isinstance(u.get("valor"), (int, float)) and not isinstance(u.get("valor"), bool):
                r["numeros"] += 1
            else:
                r["numeros"] += len(re.findall(r"(?<!\d)\d{1,2}(?!\d)", u.get("texto", "")))
            r["texto"].append(u.get("texto", "") + " " + (u.get("interpretacao_ia") or ""))
        for r in regions.values():
            sig = signals(" ".join(r["texto"]))
            if "matriz" in sig or ("9h" in sig and r["numeros"] >= 6) or r["status"] & {"requer_interpretacao"}:
                out.append({"regiao": r["regiao"], "fonte_id": r["fonte_id"], "sinais": sig, "unidades": r["unidades"], "numeros": r["numeros"],
                            "em_imagem": bool(r["status"] & {"requer_interpretacao", "interpretada_ia"}),
                            "inicio": DN.fold(" ".join(r["texto"]))[:160]})
    return out


COLUMN_UNCHECKED = "COLUNA_NAO_CONFERIDA"


def _layout(rec: dict, index: dict, run_dir: Path | None, comp: str | None, serie: int | None, value) -> None:
    """For a value quoted from a PDF page, confirm the grade COLUMN from the text positions (pdf_layout). The quote proves
    the number is in the row; the layout proves it is under the right grade. Divergence = not verified; an unreadable
    layout keeps the quote but says the column was not confirmed."""
    ev = rec.get("evidencia")
    if not (run_dir and comp and serie and ev and ev["unidade"] in index):
        return
    doc_id, unit = index[ev["unidade"]]
    if unit["tipo"] != "pdf_page":
        return
    pdf = next(iter(sorted((run_dir / "originais").glob(doc_id + ".pdf"))), None)
    if pdf is None:
        return
    import pdf_layout as PL

    r = PL.check_cell(pdf, unit["localizacao"]["pagina"], comp, serie, value)
    if r["estado"] == "confere":
        ev["metodo"] = "celula_layout_conferida"
    elif r["estado"] == "diverge":
        rec.update(valor=None, status="nao_verificado", motivo=f"{comp}, {serie}ª série: o trecho confere, mas pela posição na tabela {r['motivo']}")
        ev["verificacao"] = "nao_conferida"
    else:
        rec["motivo"] = f"{COLUMN_UNCHECKED}: {comp}, {serie}ª série: o número está na linha citada, mas a coluna não foi conferida ({r['motivo']})"


RANGE_PENDING = "VALOR_EM_FAIXA"
IMAGE_ABSENCE = "Ausência lida em imagem"


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x >= 0


def _range_value(raw: dict, index, classes, region, label: str) -> dict:
    """A cell printed as a range ('3 ou 4h/a'): both ends must be in the quote. The record keeps valor None and the range
    in 'faixa'; status 'faixa' when the quote was checked, 'nao_verificado' when read from an image or not found."""
    f = raw.get("faixa")
    rec = {"valor": None, "status": "nao_verificado", "valor_proposto": None, "evidencia": None, "motivo": None, "faixa": None}
    if not (isinstance(f, (list, tuple)) and len(f) == 2 and _num(f[0]) and _num(f[1]) and f[0] < f[1]):
        rec["motivo"] = f"{label}: faixa inválida ({f!r}); use [mínimo, máximo] com mínimo menor que máximo"
        return rec
    lo, hi = f[0], f[1]
    rec["faixa"] = {"min": lo, "max": hi, "texto": str(raw.get("trecho_literal") or "").strip() or None}
    r = EC.check(raw, index, classes, ("matriz_estadual",), min_len=3, number=lo, region=region)
    rec["evidencia"] = r["evidencia"]
    if r["ok"] and not EC.number_in(raw.get("trecho_literal") or "", hi):
        r = {"ok": False, "motivo": f"o número {hi} não aparece no trecho citado"}
        rec["evidencia"]["verificacao"] = "nao_conferida"
    if r["ok"]:
        rec["status"] = "faixa"
        rec["motivo"] = f"{RANGE_PENDING}: {label}: a fonte traz uma faixa ({rec['faixa']['texto'] or f'{lo} a {hi}'}), não um valor por série"
    elif rec["evidencia"] and rec["evidencia"]["verificacao"] == "nao_verificavel":
        rec["motivo"] = f"{RANGE_PENDING}: {label}: faixa {lo} a {hi} lida em imagem (leitura de IA, precisa de conferência)"
    else:
        rec["motivo"] = f"{label}: {r['motivo']}"
    return rec


def bounds(cell: dict):
    """(min, max) weekly lessons of one cell, or None when unknown. Verified value v -> (v, v); range -> its ends (also
    when read from an image); blank in the source -> (0, 0)."""
    if cell["status"] == "verificado":
        return (cell["valor"], cell["valor"])
    if cell["status"] == "ausente_na_fonte":
        return (0, 0)
    if cell.get("faixa"):
        return (cell["faixa"]["min"], cell["faixa"]["max"])
    if cell["status"] == "nao_verificado" and (cell.get("motivo") or "").startswith(IMAGE_ABSENCE):
        return (0, 0)
    if cell["status"] == "nao_verificado" and _num(cell.get("valor_proposto")):
        return (cell["valor_proposto"], cell["valor_proposto"])
    return None


def offered(cell: dict) -> bool:
    """The source gives this cell a positive load: a value, a range whose minimum is positive or a value read from an
    image (not verified, but the matrix does show the component: lesson of the CE 2026 pilot, where image-only matrices
    produced false 'required by ICE x no lessons' conflicts)."""
    return ((cell["valor"] or 0) > 0 or bool(cell.get("faixa") and cell["faixa"]["min"] > 0)
            or (cell["status"] == "nao_verificado" and _num(cell.get("valor_proposto")) and cell["valor_proposto"] > 0))


def _value(raw, index, classes, region, label: str, run_dir: Path | None = None, comp: str | None = None, serie: int | None = None) -> dict:
    """One weekly-lesson or minutes cell from the proposal -> verified value record."""
    raw = raw if isinstance(raw, dict) else {"valor": raw}
    if raw.get("faixa") is not None:
        return _range_value(raw, index, classes, region, label)
    valor, motivo_nulo = raw.get("valor"), raw.get("motivo")
    rec = {"valor": None, "status": "nao_verificado", "valor_proposto": None, "evidencia": None, "motivo": None}
    if valor is None:
        if motivo_nulo not in NULL_REASONS:
            rec["motivo"] = f"{label}: valor vazio sem motivo (use 'ausente_na_fonte' ou 'nao_verificado')"
            return rec
        if motivo_nulo == "ausente_na_fonte":
            rec["status"] = "ausente_na_fonte"
            rec["motivo"] = raw.get("detalhe") or "Em branco ou com traço na fonte (não é zero)."
            uid = str(raw.get("unidade") or "")
            blank_cell = re.fullmatch(r"(DOC-\d+):(.+)!([A-Z]{1,3}\d+)", uid)
            if blank_cell and EC.in_region(uid, region) and (uid not in index or index[uid][1]["texto"].strip() in ("-", "–", "—", "")):
                doc, aba, cel = blank_cell.groups()
                rec["evidencia"] = {"fonte_id": doc, "unidade": uid, "localizacao": {"tipo": "sheet_cell", "aba": aba, "celula": cel},
                                    "trecho_literal": index[uid][1]["texto"] if uid in index else "", "metodo": "celula_conferida", "verificacao": "conferida", "relacao": None}
            elif uid:
                r = EC.check(raw, index, classes, ("matriz_estadual",), min_len=3, region=region)
                rec["evidencia"] = r["evidencia"]
                if r["evidencia"] and r["evidencia"]["verificacao"] == "nao_verificavel":
                    rec["status"], rec["motivo"] = "nao_verificado", IMAGE_ABSENCE + ": precisa de conferência."
                elif not r["ok"]:
                    rec["status"], rec["motivo"] = "nao_verificado", f"{label}: {r['motivo']}"
                else:
                    _layout(rec, index, run_dir, comp, serie, None)
            else:
                rec["status"], rec["motivo"] = "nao_verificado", f"{label}: ausência declarada sem localização na fonte."
        else:
            rec["motivo"] = raw.get("detalhe") or f"{label}: não verificado."
        return rec
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor < 0:
        rec["motivo"] = f"{label}: valor inválido ({valor!r})"
        return rec
    rec["valor_proposto"] = valor
    r = EC.check(raw, index, classes, ("matriz_estadual",), min_len=3, number=valor, region=region)
    rec["evidencia"] = r["evidencia"]
    if r["ok"]:
        rec.update(valor=valor, status="verificado")
        _layout(rec, index, run_dir, comp, serie, valor)
    else:
        rec["motivo"] = f"{label}: {r['motivo']}"
    return rec


def register(run_dir: Path, proposal: dict) -> dict:
    inv = RUN.load_inventory(run_dir)
    refs = TR.load_references(run_dir)
    index = RUN.unit_index(run_dir)
    classes = {f["id"]: f["classes"] for f in inv["fontes"]}
    sel_in = proposal.get("selecao") or {}
    oferta = sel_in.get("oferta") or {}
    if SR.normalize_scope({"modelo": oferta.get("modelo"), "modalidade": oferta.get("modalidade")}) != {"modelo": "9h", "modalidade": "propedeutico"}:
        raise MatrixError("MODELO_FORA_ESCOPO", "Só uma oferta propedêutica de 9h pode ser selecionada (recebido: %s / %s)." % (oferta.get("modelo"), oferta.get("modalidade")))
    fonte = sel_in.get("fonte_id")
    if fonte not in classes or "matriz_estadual" not in classes[fonte]:
        raise MatrixError("FONTE_INVALIDA", f"A matriz precisa vir de um documento informado como matriz estadual (recebido: {fonte}).")
    region = [str(u) for u in sel_in.get("unidades") or []]
    if not region or any(not any(EC.in_region(k, [r]) for k in index) or not r.startswith(fonte + ":") for r in region):
        raise MatrixError("SELECAO_INVALIDA", "Informe as unidades (páginas, abas ou tabelas) da matriz selecionada, todas do mesmo documento.")
    motivos, evs = [], []
    for e in sel_in.get("evidencias") or []:
        # the title or the text that names the offer may sit outside the table (CE 2026: the matrix is an image and the
        # "45 horas semanais ... jornada diária de 9h/a" text is on the page before): any unit of the SAME document counts
        if not str(e.get("unidade") or "").startswith(fonte + ":"):
            motivos.append(f"evidência da seleção: {e.get('unidade')} não é do documento da matriz ({fonte})")
            continue
        r = EC.check(e, index, classes, ("matriz_estadual",), min_len=10)
        if r["evidencia"]:
            evs.append(r["evidencia"])
        if not r["ok"]:
            motivos.append("evidência da seleção: " + r["motivo"])
    region_text = " ".join(u.get("texto", "") for uid, (d, u) in index.items() if EC.in_region(uid, region))
    quoted = " ".join(e["trecho_literal"] for e in evs if e["verificacao"] == "conferida")
    sig_quote, sig_region = signals(quoted), signals(region_text)
    revisar = False
    if not any(e["verificacao"] == "conferida" for e in evs):
        motivos.append("nenhuma citação da seleção foi conferida")
        revisar = True
    if "9h" not in sig_quote and "9h" not in sig_region:
        motivos.append("OFERTA_9H_NAO_EVIDENCIADA: o trecho selecionado não menciona 9 horas ou tempo integral")
        revisar = True
    if "tecnico" in sig_region or "7h" in sig_region:
        motivos.append("a região selecionada também menciona outra oferta (técnica ou 7h): confira a escolha")
        revisar = True
    previous = SR.read_json(run_dir / "matriz.json", {}) or {}
    same = previous.get("selecao", {}).get("fonte_id") == fonte and previous.get("selecao", {}).get("unidades") == region
    selecao = {"status": "registrada", "fonte_id": fonte, "unidades": region, "oferta": {"modalidade": "propedeutico", "modelo": "9h", "etapa": oferta.get("etapa")},
               "vigencia": sel_in.get("vigencia"), "evidencias": evs, "confirmada_por_analista": False, "confirmacao": None,
               "candidatas_descartadas": [{"unidades": [str(x) for x in c.get("unidades", [])], "motivo": str(c.get("motivo", "")).strip() or "sem motivo"}
                                          for c in sel_in.get("candidatas_descartadas") or []],
               "revisar": revisar, "motivos": motivos}
    if same and previous["selecao"].get("confirmada_por_analista"):
        selecao.update(status="confirmada", confirmada_por_analista=True, confirmacao=previous["selecao"]["confirmacao"])
    if proposal.get("minutos_aula") is None:  # not given at all (CE 2026 pilot): say so, never inherit a previous value
        minutos = {"valor": None, "status": "nao_verificado", "valor_proposto": None, "evidencia": None,
                   "motivo": "duração da hora-aula: não informada na proposta (a fonte selecionada não traz o valor ou ele não foi localizado)"}
    else:
        minutos = _value(proposal.get("minutos_aula"), index, classes, region, "duração da hora-aula")
    allowed = refs["template"]["classificacoes"]
    by_fold = {DN.fold(c): c for c in allowed}
    approved = RUN.load_manifest(run_dir).get("configuracao_ice") or {}
    uf = RUN.load_manifest(run_dir)["uf"]
    equiv = {DN.fold(e["nome"]): e for e in approved.get("equivalencias_componentes") or [] if e.get("uf") in (None, uf)}
    comps = []
    for i, c in enumerate(proposal.get("componentes") or [], start=1):
        name = str(c.get("nome_original") or "").strip()
        if not name:
            raise MatrixError("COMPONENTE_INVALIDO", f"O componente {i} está sem o nome original.")
        cm = []
        aulas = {s: _value((c.get("aulas_semanais") or {}).get(s), index, classes, region, f"{name}, {s[-1]}ª série", run_dir, name, i_s)
                 for i_s, s in enumerate(SERIES, start=1)}
        for s in SERIES:
            if aulas[s]["status"] in ("nao_verificado", "faixa"):
                cm.append(aulas[s]["motivo"] or f"{s} não verificado")
            elif (aulas[s]["motivo"] or "").startswith(COLUMN_UNCHECKED):
                cm.append(aulas[s]["motivo"].split(": ", 1)[1])
        evs_name = []
        if c.get("nome_evidencia"):
            r = EC.check(c["nome_evidencia"], index, classes, ("matriz_estadual",), min_len=3, region=region)
            if r["evidencia"]:
                evs_name.append(r["evidencia"])
            ok_name = r["ok"] and DN.squash(name) in DN.squash(r["evidencia"]["trecho_literal"])
            if not ok_name:
                cm.append("nome: " + (r["motivo"] or "o nome original não aparece no trecho citado"))
        else:
            cm.append("nome sem evidência na fonte")
        cls_raw = str(c.get("classificacao") or "").strip()
        cls = by_fold.get(DN.fold(cls_raw))
        just = str(c.get("justificativa_classificacao") or "").strip()
        base = c.get("base_classificacao") if c.get("base_classificacao") in ("funcao_educacional", "nome") else "nao_informada"
        eq = equiv.get(DN.fold(name))
        eq_cls = by_fold.get(DN.fold(eq["classificacao"])) if eq else None
        if eq_cls and (not cls_raw or DN.fold(cls_raw) == DN.fold(eq_cls)):  # an approved equivalence decides the class
            cls, base = eq_cls, "equivalencia_aprovada"
            just = (f"Equivalência aprovada pela Qualidade ({approved.get('aprovado_por')}, {approved.get('data') or 'sem data'}): "
                    f"{eq['nome']} = {eq_cls}. " + just).strip()
        elif eq_cls:
            cm.append(f"classificação proposta '{cls_raw}' difere da equivalência aprovada ({eq['nome']} = {eq_cls})")
        status = "aceita"
        if not allowed:
            status = "pendente"
            cm.append("CLASSIFICACAO_PENDENTE: o template não trouxe a lista de classificações")
        elif not cls:
            status = "pendente"
            cm.append(f"CLASSIFICACAO_PENDENTE: '{cls_raw or '(vazia)'}' não está na lista do template")
        elif base not in ("funcao_educacional", "equivalencia_aprovada") or len(just) < 15:
            status = "pendente"
            cm.append("CLASSIFICACAO_PENDENTE: a classificação precisa de justificativa pela função educacional do componente, não só pelo nome")
        conf = c.get("confianca_classificacao") if base != "equivalencia_aprovada" else None  # approved: no confidence guess
        revisar_c = status == "pendente" or (isinstance(conf, (int, float)) and conf < MIN_CLASS_CONFIDENCE) or any(a["status"] == "nao_verificado" for a in aulas.values()) \
            or any(a["evidencia"] and a["evidencia"]["metodo"] == "interpretacao_ia" for a in aulas.values()) or bool(cm)
        if isinstance(conf, (int, float)) and conf < MIN_CLASS_CONFIDENCE:
            cm.append(f"confiança da classificação {conf}% abaixo de {MIN_CLASS_CONFIDENCE}%")
        comps.append({"id": "C%03d" % i, "nome_original": name, "aulas_semanais": aulas, "classificacao": cls if status == "aceita" else (cls or None),
                      "classificacao_status": status, "justificativa_classificacao": just, "base_classificacao": base,
                      "evidencias": evs_name, "revisar": bool(revisar_c), "motivos": cm})
    total = proposal.get("total_linhas_fonte")
    total = total if isinstance(total, int) and not isinstance(total, bool) and total >= 0 else None
    data = {"selecao": selecao, "minutos_aula": minutos, "componentes": comps, "total_linhas_fonte": total,
            "totais_fonte": _source_totals(proposal.get("totais_fonte") or [], comps, index, classes, region),
            "documento_oficial_citado": _cited_document(proposal.get("documento_oficial_citado"), index, classes)}
    SR.write_json(run_dir / "matriz.json", data)
    return summary(run_dir)


def _source_totals(items: list, comps: list, index, classes, region) -> list:
    """Totals printed in the source (for example 'Formação Geral Básica 24h/a' per grade). Each one is checked against
    the sum of the transcribed components of that classification (ranges as min..max): 'cabe', 'nao_cabe' or
    'indeterminado' (a component without value or classification). A total read from an image keeps its value as
    proposed and says so; the check still runs, because it only compares what the source itself prints."""
    out = []
    for i, t in enumerate(items, start=1):
        label = str(t.get("rotulo") or "").strip() or f"total {i}"
        serie = t.get("serie")
        valor = t.get("valor")
        rec = {"rotulo": label, "classificacao": None, "serie": serie if serie in (1, 2, 3) else None, "valor": valor if _num(valor) else None,
               "evidencia": None, "soma_min": None, "soma_max": None, "estado": "indeterminado", "motivo": None}
        if rec["serie"] is None or rec["valor"] is None:
            rec["motivo"] = "informe serie (1, 2 ou 3) e valor numérico"
            out.append(rec)
            continue
        r = EC.check(t, index, classes, ("matriz_estadual",), min_len=2, number=valor, region=region)
        rec["evidencia"] = r["evidencia"]
        if not r["ok"] and not (r["evidencia"] and r["evidencia"]["verificacao"] == "nao_verificavel"):
            rec["motivo"] = "total sem citação conferida: " + r["motivo"]
            out.append(rec)
            continue
        cls = str(t.get("classificacao") or "").strip()
        members = [c for c in comps if not cls or (c["classificacao"] and DN.fold(c["classificacao"]) == DN.fold(cls))]
        rec["classificacao"] = cls or None
        if cls and any(c["classificacao_status"] != "aceita" for c in comps):
            rec["motivo"] = "há componente com classificação pendente; a soma desta classificação pode mudar"
        b = [bounds(c["aulas_semanais"]["serie%d" % rec["serie"]]) for c in members]
        if not members or any(x is None for x in b):
            rec["motivo"] = rec["motivo"] or ("nenhum componente com esta classificação" if not members else "há componente sem valor nesta série")
        else:
            rec["soma_min"], rec["soma_max"] = sum(x[0] for x in b), sum(x[1] for x in b)
            fits = rec["soma_min"] <= valor <= rec["soma_max"]
            rec["estado"] = "cabe" if fits else "nao_cabe"
            rec["motivo"] = rec["motivo"] or (None if fits else f"a soma dos componentes vai de {rec['soma_min']} a {rec['soma_max']}, e a fonte imprime {valor}")
        if r["evidencia"] and r["evidencia"]["verificacao"] == "nao_verificavel":
            rec["motivo"] = ((rec["motivo"] + "; ") if rec["motivo"] else "") + "total lido em imagem (leitura de IA)"
        out.append(rec)
    return out


def _cited_document(ref, index, classes):
    """The official document the source cites for the exact values (for example 'Matrizes Curriculares para EEMTIs
    2026'). The quote must be checked in a state document: the plugin never looks for it, it only asks for it."""
    if not ref:
        return None
    title = str(ref.get("titulo") or "").strip()
    r = EC.check(ref, index, classes, ("matriz_estadual", "orientacoes_estaduais"), min_len=10)
    return {"titulo": title or None, "evidencia": r["evidencia"], "conferido": bool(r["ok"]), "motivo": None if r["ok"] else r["motivo"]}


def confirm(run_dir: Path, autor: str, motivo: str = "") -> dict:
    data = SR.read_json(run_dir / "matriz.json")
    if not data:
        raise MatrixError("MATRIZ_NAO_REGISTRADA", "Registre a matriz antes de confirmá-la.")
    if len((autor or "").strip()) < 2:
        raise MatrixError("AUTOR_OBRIGATORIO", "Informe quem confirmou a matriz (nome do analista).")
    data["selecao"].update(status="confirmada", confirmada_por_analista=True, confirmacao={"autor": autor.strip(), "data": RUN.now(), "motivo": motivo.strip() or None})
    SR.write_json(run_dir / "matriz.json", data)
    return data["selecao"]


def _consolidate(comps: list, refs: dict, manifest: dict) -> dict:
    mt = refs["template"].get("matriz") or {}
    regra = mt.get("regra")
    base = {"status": "pendente_regra_homologada", "regra_id": None, "formula_version": None, "motivo": None, "elementos": []}
    if not regra:
        base["motivo"] = "O template não trouxe um bloco de consolidação legível."
        return base
    base.update(regra_id=regra["regra_id"], formula_version=regra["formula_sha256"])
    if regra["status"] != "reconhecida":
        base["motivo"] = "REGRA_DESCONHECIDA: fórmulas do template fora do padrão conhecido (%s)." % ", ".join(regra["desconhecidos"])
        return base
    if not TR.rule_approval(refs, manifest):
        base["motivo"] = "REGRA_NAO_HOMOLOGADA: a Qualidade ainda não aprovou esta versão da regra (formula_sha256 %s)." % regra["formula_sha256"][:12]
        return base
    pending_cls = [c for c in comps if c["classificacao_status"] != "aceita"]
    values: dict = {}
    elements = []
    by_name = {e["elemento"]: e for e in regra["elementos"]}

    def calc(name, stack=()):
        if name in values:
            return values[name]
        node = by_name.get(name)
        res = {"elemento": name, "serie1": None, "serie2": None, "serie3": None, "status": "pendente", "entradas_contribuintes": [], "motivo": None}
        if node is None or name in stack:
            res["motivo"] = "elemento desconhecido na regra"
        elif node["tipo"] == "soma_classificacao":
            members = [c for c in comps if c["classificacao"] == node["classificacao"] and c["classificacao_status"] == "aceita"]
            res["entradas_contribuintes"] = [c["id"] for c in members]
            if pending_cls:
                res["motivo"] = "há componente com classificação pendente: " + ", ".join(c["id"] for c in pending_cls)
            elif any(c["aulas_semanais"][s]["status"] == "faixa" for c in members for s in SERIES):
                res["motivo"] = "há aulas em faixa nos componentes desta classificação (valor exato pendente)"
            elif any(c["aulas_semanais"][s]["status"] == "nao_verificado" for c in members for s in SERIES):
                res["motivo"] = "há aulas não verificadas nos componentes desta classificação"
            else:
                for s in SERIES:  # a blank cell adds nothing, exactly like SUMIFS in the template
                    res[s] = sum(c["aulas_semanais"][s]["valor"] or 0 for c in members)
                res["status"] = "calculado"
        else:
            parts = [(t, n) for n in node["de"] for t in ("+",)] if node["tipo"] == "soma_elementos" else [tuple(t) for t in node["termos"]]
            subs = [(sign, calc(n, stack + (name,))) for sign, n in parts]
            res["entradas_contribuintes"] = [s["elemento"] for _, s in subs]
            if all(s["status"] == "calculado" for _, s in subs):
                for k in SERIES:
                    res[k] = sum((s[k] if sign == "+" else -s[k]) for sign, s in subs)
                res["status"] = "calculado"
            else:
                res["motivo"] = "depende de elemento pendente"
        values[name] = res
        return res
    for e in regra["elementos"]:
        elements.append(calc(e["elemento"]))
    done = sum(e["status"] == "calculado" for e in elements)
    base["elementos"] = elements
    base["status"] = "calculado" if done == len(elements) else ("parcial" if done else "pendente_dados")
    homol = TR.rule_approval(refs, manifest)
    base["motivo"] = f"Regra homologada por {homol['aprovado_por']} em {homol['data']}." if base["status"] == "calculado" else "Há elementos pendentes."
    return base


def section(run_dir: Path) -> tuple:
    """(matrix section of the result, pendencias)."""
    data = SR.read_json(run_dir / "matriz.json")
    refs = TR.load_references(run_dir)
    manifest = RUN.load_manifest(run_dir)
    pend = []

    def p(code, detail, block=True):
        pend.append({"codigo": code, "frente": "matriz", "detalhe": detail, "fonte_id": None, "bloqueia_completude": block})
    empty_val = {"valor": None, "status": "nao_verificado", "valor_proposto": None, "evidencia": None, "motivo": "Matriz não registrada."}
    if not data:
        p("MATRIZ_NAO_REGISTRADA", "A matriz propedêutica de 9h ainda não foi selecionada nem transcrita.")
        sec = {"selecao": {"status": "nao_registrada", "fonte_id": None, "unidades": [], "oferta": None, "vigencia": None, "evidencias": [], "confirmada_por_analista": False,
                           "confirmacao": None, "candidatas_descartadas": [], "revisar": False, "motivos": []},
               "minutos_aula": empty_val, "componentes": [],
               "resumo_por_elemento": {"status": "pendente_dados", "regra_id": None, "formula_version": None, "motivo": "Matriz não registrada.", "elementos": []},
               "completude": {"status": "nao_iniciada", "total_linhas_fonte": None, "linhas_extraidas": 0, "celulas_verificadas": 0, "celulas_ausentes_na_fonte": 0,
                              "celulas_nao_verificadas": 0, "celulas_em_faixa": 0, "classificacoes_pendentes": 0, "motivos": ["Matriz não registrada."]},
               "totais_fonte": [], "documento_oficial_citado": None}
        _rule_pend(refs, manifest, p)
        return sec, pend
    comps = data["componentes"]
    resumo = _consolidate(comps, refs, manifest)
    cells = [c["aulas_semanais"][s] for c in comps for s in SERIES]
    ver = sum(x["status"] == "verificado" for x in cells)
    absent = sum(x["status"] == "ausente_na_fonte" for x in cells)
    nver = sum(x["status"] == "nao_verificado" for x in cells)
    in_range = sum(bool(x.get("faixa")) for x in cells)
    cls_pend = sum(c["classificacao_status"] != "aceita" for c in comps)
    motivos = []
    sel = data["selecao"]
    totals = data.get("totais_fonte") or []
    cited = data.get("documento_oficial_citado")
    if in_range:
        where = (f" Pedir o documento oficial citado pela fonte: {cited['titulo']} ({cited['evidencia']['fonte_id']} {cited['evidencia']['unidade']})."
                 if cited and cited["conferido"] and cited["titulo"] else " Pedir o documento oficial com os valores por série ou registrar a decisão.")
        p(RANGE_PENDING, f"{in_range} célula(s) de aulas semanais estão em faixa na fonte (por exemplo '3 ou 4h/a'); o valor exato por série não foi escolhido." + where)
        motivos.append(f"{in_range} célula(s) em faixa")
    bad = [t for t in totals if t["estado"] == "nao_cabe"]
    if bad:
        p("TOTAL_FONTE_NAO_CABE", "; ".join(f"{t['rotulo']} {t['serie']}ª série: {t['motivo']}" for t in bad) + ". Confira a transcrição ou a fonte.")
        motivos.append("total impresso na fonte não fecha com os componentes")
    if not sel["confirmada_por_analista"]:
        p("MATRIZ_NAO_CONFIRMADA", "O analista ainda não confirmou que esta é a matriz propedêutica de 9h vigente.")
        motivos.append("seleção não confirmada pelo analista")
    if any(m.startswith("OFERTA_9H") for m in sel["motivos"]):
        p("OFERTA_9H_NAO_EVIDENCIADA", "O trecho selecionado não menciona a oferta de 9 horas; confira a escolha da matriz.")
    if nver:
        p("VALOR_NAO_VERIFICADO", f"{nver} célula(s) de aulas semanais sem verificação na fonte (imagem, citação que não confere ou valor não encontrado).")
        motivos.append(f"{nver} célula(s) não verificada(s)")
    if data["minutos_aula"]["status"] != "verificado":
        p("VALOR_NAO_VERIFICADO", "A duração da hora-aula não foi verificada na fonte.")
        motivos.append("duração da hora-aula não verificada")
    if cls_pend:
        p("CLASSIFICACAO_PENDENTE", f"{cls_pend} componente(s) com classificação pendente.")
        motivos.append(f"{cls_pend} classificação(ões) pendente(s)")
    total = data.get("total_linhas_fonte")
    if total is None:
        p("TOTAL_LINHAS_DESCONHECIDO", "Não foi informado quantas linhas de componentes a matriz oficial tem; a cobertura não pode ser comprovada.")
        motivos.append("total de linhas da fonte desconhecido")
    elif total != len(comps):
        p("LINHAS_FALTANDO", f"A matriz oficial tem {total} linha(s) de componentes e foram transcritas {len(comps)}.")
        motivos.append("linhas transcritas diferentes do total da fonte")
    if resumo["status"] != "calculado":
        motivos.append("resumo por elemento não calculado")
    _rule_pend(refs, manifest, p)
    complete = not motivos and not sel["revisar"]
    sec = {"selecao": sel, "minutos_aula": data["minutos_aula"], "componentes": comps, "resumo_por_elemento": resumo,
           "completude": {"status": "completa" if complete else "incompleta", "total_linhas_fonte": total, "linhas_extraidas": len(comps), "celulas_verificadas": ver,
                          "celulas_ausentes_na_fonte": absent, "celulas_nao_verificadas": nver, "celulas_em_faixa": in_range, "classificacoes_pendentes": cls_pend,
                          "motivos": motivos + (["seleção marcada para revisão"] if sel["revisar"] else [])},
           "totais_fonte": totals, "documento_oficial_citado": cited}
    return sec, pend


def _rule_pend(refs, manifest, p):
    regra = (refs["template"].get("matriz") or {}).get("regra")
    if not regra:
        p("REGRA_DESCONHECIDA", "O template não trouxe um bloco de consolidação legível; o resumo por elemento fica pendente.")
    elif regra["status"] != "reconhecida":
        p("REGRA_DESCONHECIDA", "Fórmulas de consolidação fora do padrão conhecido: " + ", ".join(regra["desconhecidos"]) + ".")
    elif not TR.rule_approval(refs, manifest):
        p("REGRA_NAO_HOMOLOGADA", "Regra de consolidação do template (formula_sha256 %s) ainda não homologada pela Qualidade." % regra["formula_sha256"])


def summary(run_dir: Path) -> dict:
    sec, pend = section(run_dir)
    c = sec["completude"]
    return {"selecao": sec["selecao"]["status"], "componentes": c["linhas_extraidas"], "verificadas": c["celulas_verificadas"],
            "ausentes_na_fonte": c["celulas_ausentes_na_fonte"], "nao_verificadas": c["celulas_nao_verificadas"], "em_faixa": c["celulas_em_faixa"],
            "classificacoes_pendentes": c["classificacoes_pendentes"],
            "totais_fonte": [{k: t[k] for k in ("rotulo", "serie", "valor", "soma_min", "soma_max", "estado", "motivo")} for t in sec["totais_fonte"]],
            "resumo": sec["resumo_por_elemento"]["status"], "completude": c["status"], "pendencias": pend,
            "revisar": [{"id": x["id"], "nome": x["nome_original"], "motivos": x["motivos"]} for x in sec["componentes"] if x["revisar"]]}
