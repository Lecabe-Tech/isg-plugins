"""SPEC-017 G5: final JSON, semantic checks, PT-BR review summary and parity report.

`resultado_qualidade.v1.json` is the only deliverable: both fronts, cross-check, coverage, pending items and status
(completo / parcial / bloqueado). It is validated against the versioned schema AND against semantic rules (a `Sim`
without a verified quote, a `Não` without full coverage, a total without an approved rule... are errors). The
content hash ignores only the generation time, so the same inputs and decisions give the same hash (AC-017-14).
Nothing is written outside the run folder: no SG_* rows, spreadsheet, SharePoint or BI (AC-017-17).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cross_check as CC
import document_normalizer as DN
import matrix_analysis as MA
import orientation_analysis as OA
import quality_run as RUN
import schema_check
import source_resolver as SR
import template_rules as TR

ENGINE_VERSION = "spec017-1.2.0"
RESULT_SCHEMA_VERSION = "1.2"  # 1.1: evidence method celula_layout_conferida; 1.2: values in range (faixa), source totals, cited official document
SERIES = MA.SERIES
NON_BLOCKING = {"TIPO_DIVERGENTE", "FONTE_DUPLICADA"}
RESULT_FILE = "resultado_qualidade.v1.json"
SUMMARY_FILE = "resumo.md"


def content_hash(result: dict) -> str:
    clone = json.loads(json.dumps(result, ensure_ascii=False))
    clone["execucao"]["gerado_em"] = ""
    clone["execucao"]["conteudo_sha256"] = ""
    return hashlib.sha256(json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _dedupe(items: list) -> list:
    seen, out = set(), []
    for p in items:
        key = (p["codigo"], p["frente"], p["fonte_id"], p["detalhe"])
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def build(run_dir: Path) -> dict:
    inv = RUN.load_inventory(run_dir)
    manifest = RUN.load_manifest(run_dir)
    refs = TR.load_references(run_dir)
    matrix, mpend = MA.section(run_dir)
    orient, opend = OA.section(run_dir)
    consist = CC.run(run_dir)
    pend = []
    for f in inv["fontes"]:
        for p in f["pendencias"]:
            pend.append({"codigo": p["codigo"], "frente": "entradas", "detalhe": f"{f['nome']}: {p['detalhe']}", "fonte_id": f["id"], "bloqueia_completude": p["codigo"] not in NON_BLOCKING})
    for p in inv["pendencias"]:
        pend.append({"codigo": p["codigo"], "frente": "geral", "detalhe": p["detalhe"], "fonte_id": None, "bloqueia_completude": True})
    pend += mpend + opend
    open_conflicts = [c for c in consist["conflitos"] if c["resolucao_pendente"]]
    by_code: dict = {}
    for c in open_conflicts:
        by_code.setdefault(c["codigo"], []).append(c["entidade"])
    for code, ents in sorted(by_code.items()):
        pend.append({"codigo": "CONFLITO_PENDENTE", "frente": "consistencia", "detalhe": f"{code}: {len(ents)} caso(s) para decisão humana ({', '.join(ents[:8])}).", "fonte_id": None,
                     "bloqueia_completude": True})
    pend = _dedupe(pend)
    t = refs["template"]
    regra = (t.get("matriz") or {}).get("regra")
    hom_ice = manifest.get("homologacao_ice")
    state_docs = [f for f in inv["fontes"] if set(f["classes"]) & {"orientacoes_estaduais", "matriz_estadual"}]
    cells_total = (matrix["completude"]["total_linhas_fonte"] * 3) if matrix["completude"]["total_linhas_fonte"] is not None else None
    applicable = [orient["completude"][k]["codigos_aplicaveis"] for k in OA.TYPES]
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "execucao": {"id": f"{manifest['solicitacao_id']}-r{manifest.get('revisao', 1)}", "solicitacao_id": manifest["solicitacao_id"], "revisao": manifest.get("revisao", 1),
                     "uf": manifest["uf"], "ano": manifest["ano"], "modalidade": "propedeutico", "modelo": "9h", "versao_referencia_ice": refs["ice"]["versao"],
                     "motor_versao": ENGINE_VERSION, "gerado_em": RUN.now(), "status": "parcial", "conteudo_sha256": "0" * 64},
        "fontes": [{"id": f["id"], "classes": f["classes"], "nome": f["nome"], "uri": f["uri"], "sha256": f["sha256"], "media_type": f["media_type"],
                    "tamanho_bytes": f["tamanho_bytes"], "extrator": f["extrator"], "status_leitura": f["status_leitura"], "cobertura": f["cobertura"],
                    "metadados": f["metadados"], "pendencias": sorted({p["codigo"] for p in f["pendencias"]})} for f in inv["fontes"]],
        "referencias": {
            "template": {"fonte_id": t["fonte_id"], "aba_matriz": t["aba_matriz"], "classificacoes": t["classificacoes"],
                         "codigos": {k: len(t["codigos"][k]) for k in OA.TYPES},
                         "regra": ({"regra_id": regra["regra_id"], "formula_sha256": regra["formula_sha256"], "status": regra["status"],
                                    "homologacao": TR.rule_approval(refs, manifest)} if regra else None)},
            "ice": {"fonte_ids": refs["ice"]["fonte_ids"], "versao": refs["ice"]["versao"],
                    "homologacao": {"status": "declarada_no_manifesto" if hom_ice else "ausente", "aprovado_por": (hom_ice or {}).get("aprovado_por"), "data": (hom_ice or {}).get("data")},
                    "codigos": {k: len(refs["ice"]["codigos"][k]) for k in OA.TYPES}}},
        "matriz": matrix,
        "orientacoes": orient,
        "consistencia": consist,
        "pendencias": pend,
        "revisao_humana": {"necessaria": True, "status": "aguardando",
                           "itens": sum(c["revisar"] for c in matrix["componentes"]) + int(matrix["selecao"]["revisar"]) + len(open_conflicts)
                                    + sum(o["revisar"] for k in OA.TYPES for o in orient[k])},
        "metricas": {
            "cobertura_documental": {"numerador": sum(f["cobertura"]["unidades_lidas"] for f in state_docs), "denominador": sum(f["cobertura"]["unidades_total"] for f in state_docs),
                                     "descricao": "Unidades lidas (páginas, células, parágrafos, linhas, imagens) sobre as identificadas nas fontes estaduais."},
            "cobertura_matriz": {"numerador": matrix["completude"]["celulas_verificadas"] + matrix["completude"]["celulas_ausentes_na_fonte"], "denominador": cells_total,
                                 "descricao": "Células de aulas semanais verificadas ou comprovadamente em branco sobre linhas da fonte × 3 séries (vazio se o total de linhas não foi informado)."},
            "cobertura_orientacoes": {"numerador": sum(orient["completude"][k]["codigos_avaliados"] for k in OA.TYPES),
                                      "denominador": None if None in applicable else sum(applicable),
                                      "descricao": "Orientações com Sim ou Não defensável sobre códigos aplicáveis reconciliados (vazio se os códigos não foram reconciliados)."},
            "observacao": "Contagens medidas nesta execução. Não são percentual de automação do trabalho do analista nem concordância com ele; a concordância vem do relatório de paridade."},
        "gravacoes_externas": [],
    }
    matrix_blocked = not any(f["status_leitura"] != "nao_lida" for f in RUN.docs_of_class(inv, "matriz_estadual"))
    orient_blocked = not any(f["status_leitura"] != "nao_lida" for f in RUN.docs_of_class(inv, "orientacoes_estaduais")) or orient["codigos"]["status"] == "sem_codigos"
    complete = (not any(p["bloqueia_completude"] for p in pend) and matrix["completude"]["status"] == "completa"
                and all(orient["completude"][k]["status"] == "completa" for k in OA.TYPES) and not open_conflicts and hom_ice)
    result["execucao"]["status"] = "bloqueado" if (matrix_blocked and orient_blocked) else ("completo" if complete else "parcial")
    result["execucao"]["conteudo_sha256"] = content_hash(result)
    return result


def semantic_errors(result: dict) -> list:
    errors = []
    ids = {f["id"] for f in result.get("fontes", [])}
    orient_docs = {f["id"] for f in result["fontes"] if "orientacoes_estaduais" in f["classes"]}

    def evs_of(obj):
        if isinstance(obj, dict):
            if "fonte_id" in obj and "verificacao" in obj and "metodo" in obj:
                yield obj
            for v in obj.values():
                yield from evs_of(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from evs_of(v)
    for e in evs_of({"m": result["matriz"], "o": result["orientacoes"], "c": result["consistencia"]}):
        if e["fonte_id"] not in ids:
            errors.append(f"evidência cita fonte inexistente: {e['fonte_id']}")
        if e["metodo"] == "interpretacao_ia" and e["verificacao"] == "conferida":
            errors.append(f"leitura de imagem marcada como conferida: {e['unidade']}")
    for c in result["matriz"]["componentes"]:
        for s in SERIES:
            v = c["aulas_semanais"][s]
            if v["status"] == "verificado" and (v["valor"] is None or not v["evidencia"] or v["evidencia"]["verificacao"] != "conferida"):
                errors.append(f"{c['id']} {s}: verificado sem evidência conferida")
            if v["status"] != "verificado" and v["valor"] is not None:
                errors.append(f"{c['id']} {s}: valor sem verificação")
            if v["status"] == "faixa" and not (v.get("faixa") and v["evidencia"] and v["evidencia"]["verificacao"] == "conferida"):
                errors.append(f"{c['id']} {s}: faixa sem evidência conferida")
    resumo = result["matriz"]["resumo_por_elemento"]
    regra = result["referencias"]["template"]["regra"]
    if any(e["status"] == "calculado" for e in resumo["elementos"]) and not (regra and regra["homologacao"] and regra["formula_sha256"] == resumo["formula_version"]):
        errors.append("resumo por elemento calculado sem regra homologada")
    for k in OA.TYPES:
        rows = result["orientacoes"][k]
        comp = result["orientacoes"]["completude"][k]
        for o in rows:
            if o["presenca"] == "Sim" and o["origem"] != "analista" and not any(e["verificacao"] == "conferida" for e in o["evidencias"]):
                errors.append(f"{o['codigo']}: Sim sem citação conferida")
            if o["presenca"] == "Não" and o["origem"] != "analista" and not orient_docs <= set(o["fontes_verificadas"]):
                errors.append(f"{o['codigo']}: Não sem todas as fontes de orientação verificadas")
            if o["presenca"] is None and o["status"] not in ("pendente", "nao_avaliado"):
                errors.append(f"{o['codigo']}: sem decisão, mas com status {o['status']}")
        if comp["sim"] + comp["nao"] != comp["codigos_avaliados"] or comp["sim"] != sum(o["presenca"] == "Sim" for o in rows) or comp["nao"] != sum(o["presenca"] == "Não" for o in rows):
            errors.append(f"completude de {k} não confere com a lista")
    if result["execucao"]["status"] == "completo":
        if any(p["bloqueia_completude"] for p in result["pendencias"]) or any(c["resolucao_pendente"] for c in result["consistencia"]["conflitos"]):
            errors.append("status completo com pendências ou conflitos abertos")
        if result["referencias"]["ice"]["homologacao"]["status"] != "declarada_no_manifesto":
            errors.append("status completo sem homologação do ICE")
    if result["execucao"]["conteudo_sha256"] != content_hash(result):
        errors.append("conteudo_sha256 não confere com o conteúdo")
    return errors


def validate(result) -> dict:
    schema = schema_check.validate("resultado", result)
    semantic = semantic_errors(result) if not schema else []
    return {"valido": not schema and not semantic, "erros_schema": schema, "erros_semanticos": semantic}


def write(run_dir: Path, out: Path | None = None) -> dict:
    result = build(run_dir)
    check = validate(result)
    if not check["valido"]:
        return {"ok": False, "validacao": check, "resultado": result}
    out = out or (run_dir / RESULT_FILE)
    SR.write_json(out, result)
    (out.parent / SUMMARY_FILE).write_text(summary_md(result), encoding="utf-8", newline="\n")
    return {"ok": True, "validacao": check, "arquivo": str(out), "resumo": str(out.parent / SUMMARY_FILE), "resultado": result}


STATUS_TEXT = {"completo": "Completo (aguarda revisão da coordenação)", "parcial": "Parcial — não é um ciclo concluído", "bloqueado": "Bloqueado — faltam fontes legíveis"}


def _fmt(v):
    return "—" if v is None else (str(int(v)) if isinstance(v, float) and v.is_integer() else str(v))


def _cell(v: dict) -> str:
    if v.get("faixa"):
        return f"{_fmt(v['faixa']['min'])}–{_fmt(v['faixa']['max'])}" + ("*" if v["status"] == "nao_verificado" else "")
    if v["status"] == "nao_verificado" and v.get("valor_proposto") is not None:  # value read but not verified (for example from an image)
        return _fmt(v["valor_proposto"]) + "*"
    return _fmt(v["valor"]) + ("*" if v["status"] == "nao_verificado" else "")


def summary_md(r: dict) -> str:
    """PT-BR review summary built ONLY from the result object (for Jhon and the Quality coordinator)."""
    e, m, o = r["execucao"], r["matriz"], r["orientacoes"]
    L = [f"# Resultado da Qualidade — {e['uf']} {e['ano']} (propedêutico 9h)", "",
         f"**Situação:** {STATUS_TEXT[e['status']]}. Execução `{e['id']}`, referencial ICE {e['versao_referencia_ice'] or 'sem versão'}, gerado em {e['gerado_em']}.",
         "Este resumo vem do arquivo `resultado_qualidade.v1.json`; JSON válido não significa análise aprovada. Revisão humana: **aguardando** "
         f"({r['revisao_humana']['itens']} item(ns) marcado(s) para revisão).", "", "## Fontes", "",
         "| Fonte | Papel | Arquivo | Leitura | Unidades lidas | Pendências |", "|---|---|---|---|---|---|"]
    for f in r["fontes"]:
        L.append(f"| {f['id']} | {', '.join(f['classes'])} | {f['nome']} | {f['status_leitura']} | {f['cobertura']['unidades_lidas']}/{f['cobertura']['unidades_total']} | {', '.join(f['pendencias']) or '—'} |")
    s = m["selecao"]
    L += ["", "## Matriz curricular", ""]
    if s["status"] == "nao_registrada":
        L.append("Matriz ainda não selecionada nem transcrita.")
    else:
        conf = f"confirmada por {s['confirmacao']['autor']}" if s["confirmada_por_analista"] else "**não confirmada pelo analista**"
        L.append(f"Matriz selecionada em {s['fonte_id']} ({', '.join(s['unidades'])}), vigência {s['vigencia'] or '—'}, {conf}."
                 + (" Seleção marcada para revisão: " + "; ".join(s["motivos"]) + "." if s["revisar"] else ""))
        c = m["completude"]
        L.append(f"Componentes transcritos: {c['linhas_extraidas']} (linhas na fonte: {_fmt(c['total_linhas_fonte'])}). Células: {c['celulas_verificadas']} verificadas, "
                 f"{c['celulas_ausentes_na_fonte']} em branco na fonte, {c['celulas_nao_verificadas']} não verificadas, {c.get('celulas_em_faixa', 0)} em faixa. Hora-aula: {_fmt(m['minutos_aula']['valor'])} min.")
        L += ["", "| Componente (como na fonte) | 1ª | 2ª | 3ª | Classificação | Revisar |", "|---|---|---|---|---|---|"]
        for comp in m["componentes"]:
            cells = [_cell(comp["aulas_semanais"][x]) for x in SERIES]
            cls = comp["classificacao"] or "pendente"
            L.append(f"| {comp['nome_original']} | {' | '.join(cells)} | {cls}{' (pendente)' if comp['classificacao_status'] != 'aceita' and comp['classificacao'] else ''} | {'sim' if comp['revisar'] else '—'} |")
        L.append("")
        L.append("`4*` = valor lido mas não verificado na fonte (por exemplo, lido de imagem); `3–4` = faixa impressa na fonte, sem valor exato; `—` = vazio (em branco na fonte ou não verificado).")
        for t in m.get("totais_fonte") or []:
            L.append(f"- Total impresso na fonte — {t['rotulo']}, {t['serie']}ª série: {_fmt(t['valor'])}; soma dos componentes {_fmt(t['soma_min'])} a {_fmt(t['soma_max'])} → "
                     + {"cabe": "cabe", "nao_cabe": "**não cabe**", "indeterminado": "indeterminado"}[t["estado"]] + (f" ({t['motivo']})" if t["motivo"] else "") + ".")
        doc = m.get("documento_oficial_citado")
        if doc:
            L.append(f"- Documento oficial citado pela fonte para os valores exatos: {doc['titulo'] or '—'}" + ("" if doc["conferido"] else " (citação não conferida)") + ".")
        rs = m["resumo_por_elemento"]
        L += ["", f"**Resumo por elemento:** {rs['status'].replace('_', ' ')}. {rs['motivo'] or ''}"]
        if rs["elementos"]:
            L += ["", "| Elemento | 1ª | 2ª | 3ª |", "|---|---|---|---|"] + [f"| {x['elemento']} | {_fmt(x['serie1'])} | {_fmt(x['serie2'])} | {_fmt(x['serie3'])} |" for x in rs["elementos"]]
    L += ["", "## Orientações", "", f"Códigos: {o['codigos']['status'].replace('_', ' ')}" + (f" ({o['codigos']['autoridade']})" if o["codigos"]["autoridade"] else "") + "."]
    if o["codigos"]["somente_template"] or o["codigos"]["somente_ice"]:
        L.append(f"Só no template: {', '.join(o['codigos']['somente_template']) or 'nenhum'}. Só no ICE: {', '.join(o['codigos']['somente_ice']) or 'nenhum'}.")
    L += ["", "| Bloco | Aplicáveis | Sim | Não | Pendentes | Não avaliadas | Revisar |", "|---|---|---|---|---|---|---|"]
    for k, label in (("pedagogicas", "Pedagógicas"), ("gestao", "Gestão")):
        c = o["completude"][k]
        L.append(f"| {label} | {_fmt(c['codigos_aplicaveis'])} | {c['sim']} | {c['nao']} | {c['pendentes']} | {c['nao_avaliados']} | {c['revisar']} |")
    flagged = [x for k in OA.TYPES for x in o[k] if x["revisar"] and x["status"] != "nao_avaliado"]
    if flagged:
        L += ["", "Orientações para conferir:", ""]
        for x in flagged[:40]:
            where = "; ".join(f"{ev['fonte_id']} {_loc(ev['localizacao'])}" for ev in x["evidencias"][:2]) or "sem evidência conferida"
            L.append(f"- **{x['codigo']}** ({x['presenca'] or 'pendente'}): {x['justificativa'] or '—'} — {where}. {'; '.join(x['motivos'][:2])}")
    L += ["", "## Cruzamento entre matriz e orientações", ""]
    if r["consistencia"]["conflitos"]:
        L += [f"- [{c['gravidade']}] **{c['codigo']}** — {c['entidade']}: {c['detalhe']}" for c in r["consistencia"]["conflitos"]]
    else:
        L.append("Nenhum conflito encontrado.")
    queue = review_queue(r)
    L += ["", "## Fila de revisão", "", f"{len(queue)} decisão(ões) para o analista, da mais importante para a menos importante. "
          "Cada item diz o que decidir e onde está a evidência; nada aqui foi aprovado.", ""]
    for q in queue[:40]:
        L.append(f"{q['ordem']}. **{q['referencia']}** ({q['tipo']}) — {q['decisao']}" + (f" Evidência: {'; '.join(q['onde'][:3])}." if q["onde"] else "")
                 + (f" Motivo: {'; '.join(q['motivos'][:2])}." if q["motivos"] else ""))
    if len(queue) > 40:
        L.append(f"… e mais {len(queue) - 40} item(ns) no comando `revisao-fila`.")
    L += ["", "## Pendências", ""]
    L += [f"- {'**' if p['bloqueia_completude'] else ''}{p['codigo']}{'**' if p['bloqueia_completude'] else ''} ({p['frente']}): {p['detalhe']}" for p in r["pendencias"]] or ["Nenhuma."]
    mt = r["metricas"]
    L += ["", "## Medidas desta execução", ""]
    for key, label in (("cobertura_documental", "Cobertura documental"), ("cobertura_matriz", "Cobertura da matriz"), ("cobertura_orientacoes", "Cobertura das orientações")):
        L.append(f"- {label}: {mt[key]['numerador']} de {_fmt(mt[key]['denominador'])} — {mt[key]['descricao']}")
    L += [f"- {mt['observacao']}", "", "Nada foi gravado no Excel, no SharePoint, na base central nem no painel."]
    return "\n".join(L) + "\n"


DECISION_PENDING = {
    "MATRIZ_NAO_CONFIRMADA": "Confirmar se a matriz selecionada é a propedêutica de 9h vigente (comando matriz-confirmar).",
    "REGRA_NAO_HOMOLOGADA": "A Qualidade decide se aprova a regra de consolidação do template (registrar a impressão digital em regras_homologadas).",
    "REGRA_DESCONHECIDA": "A Qualidade decide como tratar fórmulas do template fora do padrão conhecido.",
    "REFERENCIAL_NAO_HOMOLOGADO": "A Qualidade registra a homologação do referencial ICE usado (versão, quem aprovou, data).",
    "CODIGOS_NAO_RECONCILIADOS": "A Qualidade define os códigos de orientação aplicáveis (aplicabilidade_codigos).",
    "FONTE_AUSENTE": "Enviar o documento que falta ou confirmar que ele não existe.",
    "ACESSO_NEGADO": "Enviar uma cópia legível do documento.",
    "FORMATO_NAO_SUPORTADO": "Converter o documento para PDF, DOCX, XLSX ou imagem e enviar de novo.",
    "VALOR_EM_FAIXA": "Enviar o documento oficial com o valor exato por série (o detalhe diz qual a fonte cita) ou registrar a decisão sobre o valor.",
    "TOTAL_FONTE_NAO_CABE": "Conferir a transcrição: o total impresso na fonte não fecha com a soma dos componentes.",
}


def _where(evs: list) -> list:
    return [f"{e['fonte_id']} {_loc(e['localizacao'])}" + (" (leitura de IA)" if e["metodo"] == "interpretacao_ia" else "") for e in evs]


def review_queue(r: dict) -> list:
    """Decisions the analyst has to make, most important first, each with the data that supports it:
    high conflicts, process decisions, medium conflicts, pending orientations, flagged components and selection,
    flagged orientations (lowest confidence first), low conflicts. Derived from the result only."""
    items = []

    def add(prio, tipo, ref, decisao, onde=(), motivos=()):
        items.append({"prioridade": prio, "tipo": tipo, "referencia": ref, "decisao": decisao, "onde": list(onde), "motivos": list(motivos)})
    sev = {"alta": 1, "media": 3, "baixa": 7}
    for c in r["consistencia"]["conflitos"]:
        if c["resolucao_pendente"]:
            vals = "; ".join(f"{v['origem']} {v['unidade'] or v['fonte_id'] or ''}: {v['valor']}" for v in c["valores"])
            add(sev[c["gravidade"]], "conflito", f"{c['codigo']} — {c['entidade']}", f"Decidir qual valor vale ou registrar a explicação ({vals}).",
                [v["unidade"] for v in c["valores"] if v["unidade"]], [c["detalhe"]])
    seen = set()
    for p in r["pendencias"]:
        if p["codigo"] in DECISION_PENDING and (p["codigo"], p["fonte_id"]) not in seen:
            seen.add((p["codigo"], p["fonte_id"]))
            add(2, "decisao", p["codigo"] + (f" ({p['fonte_id']})" if p["fonte_id"] else ""), DECISION_PENDING[p["codigo"]], (), [p["detalhe"]])
    sel = r["matriz"]["selecao"]
    if sel["revisar"] and not sel["confirmada_por_analista"]:
        add(5, "matriz", "Seleção da matriz", "Conferir a escolha da matriz.", _where(sel["evidencias"]), sel["motivos"])
    for c in r["matriz"]["componentes"]:
        if c["revisar"]:
            evs = [c["aulas_semanais"][s]["evidencia"] for s in SERIES if c["aulas_semanais"][s]["evidencia"]]
            add(5, "componente", f"{c['id']} {c['nome_original']}", "Conferir as aulas e a classificação deste componente.", _where(evs[:1]), c["motivos"])
    oris = [o for k in ("pedagogicas", "gestao") for o in r["orientacoes"][k]]
    for o in oris:
        if o["status"] == "pendente":
            add(4, "orientacao", o["codigo"], "Decidir Sim ou Não: a evidência registrada não basta.", _where(o["evidencias"]), [o["justificativa"]] + o["motivos"][:1])
    for o in sorted((o for o in oris if o["status"] == "decidido_revisar"), key=lambda o: (o["confianca"] if o["confianca"] is not None else 0)):
        add(6, "orientacao", o["codigo"], f"Confirmar {o['presenca']} (confiança {o['confianca']}%).", _where(o["evidencias"]), [o["justificativa"]])
    items.sort(key=lambda i: i["prioridade"])
    for n, i in enumerate(items, start=1):
        i["ordem"] = n
    return items


def _loc(loc: dict) -> str:
    t = loc.get("tipo")
    if t == "pdf_page":
        return f"pág. {loc['pagina']}"
    if t == "image_region" and loc.get("pagina"):
        return f"pág. {loc['pagina']}, imagem {loc.get('imagem', 1)}"
    if t == "sheet_cell":
        return f"{loc['aba']}!{loc['celula']}"
    if t == "paragraph":
        return f"parágrafo {loc['paragrafo']}"
    if t == "row":
        return f"tabela {loc.get('tabela', '')} linha {loc['linha']}".replace("  ", " ")
    return t or ""


# ---------------- parity with the analysts' fill ----------------

def key_from_template(path: Path, uf: str, ano: int) -> dict:
    """Answer key from a cluster template filled by the analysts (local copy, never committed)."""
    wb = DN.read_workbook(path)
    out = {"origem": path.name, "matriz": [], "elementos": [], "orientacoes": {}}
    tab = TR.matrix_tab(wb, uf)
    if tab:
        rule = TR.matrix_rule(tab, TR.classification_list(wb)[0])
        out["matriz"] = [{"nome": r["nome"], "serie1": r["serie1"], "serie2": r["serie2"], "serie3": r["serie3"], "classificacao": r["classificacao"]} for r in rule["preenchimento"]]
        out["elementos"] = rule["elementos_preenchidos"]
    T = TR._eqv()
    try:
        g = T.read_template(path)["gabarito"]
        out["orientacoes"] = {k.split("|")[1]: v["valor"] for k, v in g.items() if k.split("|")[2] == uf and k.split("|")[3] == str(ano) and v["valor"]}
    except T.TemplateError:
        pass
    return out


def parity(result: dict, key: dict) -> dict:
    comps = {DN.squash(c["nome_original"]): c for c in result["matriz"]["componentes"]}
    keyrows = {DN.squash(r["nome"]): r for r in key.get("matriz", [])}
    diffs, fields = [], {"comparados": 0, "iguais": 0, "diferentes": 0, "sem_valor_no_plugin": 0}
    for k, kr in keyrows.items():
        c = comps.get(k)
        if not c:
            continue
        for s in SERIES:
            kv, pv = kr.get(s), c["aulas_semanais"][s]
            if kv is None and pv["status"] != "verificado":
                continue
            if pv["status"] in ("nao_verificado", "faixa"):
                fields["sem_valor_no_plugin"] += 1
                continue
            fields["comparados"] += 1
            if (pv["valor"] or 0) == (kv or 0) and not (pv["valor"] is None and kv not in (None, 0)):
                fields["iguais"] += 1
            else:
                fields["diferentes"] += 1
                diffs.append({"componente": c["nome_original"], "campo": s, "plugin": pv["valor"], "gabarito": kv, "evidencia": pv["evidencia"]})
        if kr.get("classificacao"):
            if c["classificacao_status"] != "aceita":
                fields["sem_valor_no_plugin"] += 1
            else:
                fields["comparados"] += 1
                if DN.fold(c["classificacao"]) == DN.fold(kr["classificacao"]):
                    fields["iguais"] += 1
                else:
                    fields["diferentes"] += 1
                    diffs.append({"componente": c["nome_original"], "campo": "classificacao", "plugin": c["classificacao"], "gabarito": kr["classificacao"], "evidencia": None})
    orient = {o["codigo"]: o for k in OA.TYPES for o in result["orientacoes"][k]}
    ores = {"comparadas": 0, "iguais": 0, "diferentes": 0, "sem_decisao_no_plugin": 0, "so_no_gabarito": [], "diferencas": []}
    for code, val in sorted(key.get("orientacoes", {}).items()):
        kv = {"sim": "Sim", "nao": "Não", "não": "Não"}.get(str(val).strip().lower())
        if kv is None:
            continue
        o = orient.get(code)
        if not o:
            ores["so_no_gabarito"].append(code)
            continue
        if o["presenca"] is None:
            ores["sem_decisao_no_plugin"] += 1
            continue
        ores["comparadas"] += 1
        if o["presenca"] == kv:
            ores["iguais"] += 1
        else:
            ores["diferentes"] += 1
            ores["diferencas"].append({"codigo": code, "plugin": o["presenca"], "gabarito": kv, "revisar": o["revisar"], "justificativa": o["justificativa"],
                                       "evidencias": [{"fonte_id": e["fonte_id"], "unidade": e["unidade"]} for e in o["evidencias"][:3]]})
    return {"gabarito": key.get("origem", "JSON informado"),
            "matriz": {"linhas_gabarito": len(keyrows), "linhas_resultado": len(comps), "pareadas": len(set(keyrows) & set(comps)),
                       "so_no_gabarito": sorted(keyrows[k]["nome"] for k in set(keyrows) - set(comps)),
                       "so_no_resultado": sorted(comps[k]["nome_original"] for k in set(comps) - set(keyrows)), "campos": fields, "diferencas": diffs},
            "orientacoes": ores,
            "observacao": "Comparação campo a campo com o preenchimento dos analistas. Cada diferença precisa de explicação (fonte, edição, decisão) antes de qualquer conclusão; "
                          "itens sem decisão do plugin não contam como acerto nem erro."}
