"""SPEC-017 G2: curricular matrix front (selection, literal transcription, classification, controlled consolidation).

Claude reads the sources and proposes; this module verifies every value against the cited unit and decides:
  * only a propedêutico 9h offer can be selected, and only inside the selected region are values accepted;
  * 0 (explicit zero), null 'ausente_na_fonte' (blank or dash in the source) and null 'nao_verificado' never mix;
  * values read from images stay unverified (kept as `valor_proposto`);
  * classifications must be in the template list and be justified by educational function, not by the name;
  * element totals only with the template rule whose fingerprint was approved by Quality (no 40-week factor,
    no hours: the 2026 template has none).
"""
from __future__ import annotations

import re
from pathlib import Path

import document_normalizer as DN
import evidence_check as EC
import quality_run as RUN
import source_resolver as SR
import template_rules as TR

SERIES = ("serie1", "serie2", "serie3")
NULL_REASONS = ("ausente_na_fonte", "nao_verificado")
MIN_CLASS_CONFIDENCE = 85
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


def _value(raw, index, classes, region, label: str) -> dict:
    """One weekly-lesson or minutes cell from the proposal -> verified value record."""
    raw = raw if isinstance(raw, dict) else {"valor": raw}
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
                    rec["status"], rec["motivo"] = "nao_verificado", "Ausência lida em imagem: precisa de conferência."
                elif not r["ok"]:
                    rec["status"], rec["motivo"] = "nao_verificado", f"{label}: {r['motivo']}"
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
        r = EC.check(e, index, classes, ("matriz_estadual",), min_len=10, region=region)
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
    minutos = _value(proposal.get("minutos_aula"), index, classes, region, "duração da hora-aula")
    allowed = refs["template"]["classificacoes"]
    by_fold = {DN.fold(c): c for c in allowed}
    comps = []
    for i, c in enumerate(proposal.get("componentes") or [], start=1):
        name = str(c.get("nome_original") or "").strip()
        if not name:
            raise MatrixError("COMPONENTE_INVALIDO", f"O componente {i} está sem o nome original.")
        cm = []
        aulas = {s: _value((c.get("aulas_semanais") or {}).get(s), index, classes, region, f"{name}, {s[-1]}ª série") for s in SERIES}
        for s in SERIES:
            if aulas[s]["status"] == "nao_verificado":
                cm.append(aulas[s]["motivo"] or f"{s} não verificado")
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
        status = "aceita"
        if not allowed:
            status = "pendente"
            cm.append("CLASSIFICACAO_PENDENTE: o template não trouxe a lista de classificações")
        elif not cls:
            status = "pendente"
            cm.append(f"CLASSIFICACAO_PENDENTE: '{cls_raw or '(vazia)'}' não está na lista do template")
        elif base != "funcao_educacional" or len(just) < 15:
            status = "pendente"
            cm.append("CLASSIFICACAO_PENDENTE: a classificação precisa de justificativa pela função educacional do componente, não só pelo nome")
        conf = c.get("confianca_classificacao")
        revisar_c = status == "pendente" or (isinstance(conf, (int, float)) and conf < MIN_CLASS_CONFIDENCE) or any(a["status"] == "nao_verificado" for a in aulas.values()) \
            or any(a["evidencia"] and a["evidencia"]["metodo"] == "interpretacao_ia" for a in aulas.values()) or bool(cm)
        if isinstance(conf, (int, float)) and conf < MIN_CLASS_CONFIDENCE:
            cm.append(f"confiança da classificação {conf}% abaixo de {MIN_CLASS_CONFIDENCE}%")
        comps.append({"id": "C%03d" % i, "nome_original": name, "aulas_semanais": aulas, "classificacao": cls if status == "aceita" else (cls or None),
                      "classificacao_status": status, "justificativa_classificacao": just, "base_classificacao": base,
                      "evidencias": evs_name, "revisar": bool(revisar_c), "motivos": cm})
    total = proposal.get("total_linhas_fonte")
    total = total if isinstance(total, int) and not isinstance(total, bool) and total >= 0 else None
    data = {"selecao": selecao, "minutos_aula": minutos, "componentes": comps, "total_linhas_fonte": total}
    SR.write_json(run_dir / "matriz.json", data)
    return summary(run_dir)


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
                              "celulas_nao_verificadas": 0, "classificacoes_pendentes": 0, "motivos": ["Matriz não registrada."]}}
        _rule_pend(refs, manifest, p)
        return sec, pend
    comps = data["componentes"]
    resumo = _consolidate(comps, refs, manifest)
    cells = [c["aulas_semanais"][s] for c in comps for s in SERIES]
    ver = sum(x["status"] == "verificado" for x in cells)
    absent = sum(x["status"] == "ausente_na_fonte" for x in cells)
    nver = sum(x["status"] == "nao_verificado" for x in cells)
    cls_pend = sum(c["classificacao_status"] != "aceita" for c in comps)
    motivos = []
    sel = data["selecao"]
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
                          "celulas_ausentes_na_fonte": absent, "celulas_nao_verificadas": nver, "classificacoes_pendentes": cls_pend,
                          "motivos": motivos + (["seleção marcada para revisão"] if sel["revisar"] else [])}}
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
            "ausentes_na_fonte": c["celulas_ausentes_na_fonte"], "nao_verificadas": c["celulas_nao_verificadas"], "classificacoes_pendentes": c["classificacoes_pendentes"],
            "resumo": sec["resumo_por_elemento"]["status"], "completude": c["status"], "pendencias": pend,
            "revisar": [{"id": x["id"], "nome": x["nome_original"], "motivos": x["motivos"]} for x in sec["componentes"] if x["revisar"]]}
