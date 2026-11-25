"""The analysis output in Notion: the ONLY place the results are delivered (0.1.8).

Since 0.1.8 the result JSON, `resumo.md`, the evidence ZIP and the 'Resultado JSON' link are no longer deliverables. The
JSON stays as the engine's internal working state (it binds the filled template and every Notion row to the same
content hash); what people read is in Notion:

  Solicitações              the request: input files, Status, 'Template Preenchido' (the XLSX, see notion_publish.py)
  Resultados — Execuções    one row per run (counts, observations) and, in the page body, what `resumo.md` had
  Resultados — Orientações  one row per orientation code
  Resultados — Matriz (componentes)  one row per component of the state matrix
  Resultados — Matriz (elementos)    the template's 16 totals, only when the template rule is approved
  Resultados — Fila de revisão       one row per task of the GROUPED review queue

Like the rest of the engine, this module never talks to Notion: it builds the rows (`desired_rows`), plans the writes
against the rows the connector read (`plan`: create / update / keep, never delete), and checks the rows read again
after the writes (`confirm`). The state of each base is kept in `notion_saida.json`, so an interrupted publication resumes
without duplicates. Every row key carries the run (UF-ano-<execução>-item, e.g. CE-2026-QUA13r1-AC1): two runs of the
same UF and year never collide (QUA-12 x QUA-13). Human fields are never written: 'Decisão humana', 'Classificação
humana', 'Comentário analista', 'Validação humana' (only its initial value) and, in the queue, 'Status' and 'Decisão
registrada'; a queue task the analyst already moved out of 'Aberta' is not touched.
"""
from __future__ import annotations

import re
from pathlib import Path

import notion_publish as NP
import quality_result as QR
import quality_run as RUN
import source_resolver as SR

FILE = "notion_saida.json"
BASES = ("execucao", "orientacoes", "componentes", "elementos", "fila")
DATA_SOURCES = {
    "solicitacoes": NP.DATA_SOURCE_ID,
    "execucao": NP.EXECUTIONS_DATA_SOURCE_ID,
    "orientacoes": "4223eb42-d128-815a-8326-000b67ed8ea4",
    "componentes": "4223eb42-d128-81aa-b28d-000b401ab464",
    "elementos": "4223eb42-d128-817c-8ea1-000b7c746d43",
    "fila": "4223eb42-d128-81c3-aa1d-000b87020c35",
}
BASE_TITLES = {"execucao": "Resultados — Execuções", "orientacoes": "Resultados — Orientações", "componentes": "Resultados — Matriz (componentes)",
               "elementos": "Resultados — Matriz (elementos)", "fila": "Resultados — Fila de revisão"}
KEY_PROP = {"execucao": "Execução", "orientacoes": "Chave", "componentes": "Chave", "elementos": "Chave", "fila": "Referência"}
HUMAN = {  # never sent by Claude
    "execucao": {"Validação humana"},
    "orientacoes": {"Decisão humana", "Comentário analista", "Valor final", "Solicitação"},
    "componentes": {"Classificação humana", "Comentário analista", "Classificação final", "Solicitação"},
    "elementos": {"Solicitação"},
    "fila": {"Status", "Decisão registrada", "Solicitação"},
}
QUEUE_OPEN = "Aberta"
TEXT_LIMIT = 1900  # a Notion text property holds 2000 characters per text object
ELEMENT_RULE = {"matriz completa": "TOTAL", "projeto de vida + pos-medio": "PVPOS", "itinerarios formativos": "ITIN", "parte diversificada": "PD"}


class NotionOutputError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------- helpers ----------------

def _fold(text) -> str:
    import unicodedata

    t = unicodedata.normalize("NFKD", str(text or ""))
    return re.sub(r"\s+", " ", "".join(c for c in t if not unicodedata.combining(c)).lower()).strip()


def _text(value, limit: int = TEXT_LIMIT):
    s = re.sub(r"[ \t]+", " ", str(value or "")).strip()
    if not s:
        return None
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def execution_token(result: dict) -> str:
    e = result["execucao"]
    return re.sub(r"[^A-Za-z0-9]", "", str(e["solicitacao_id"])) + f"r{e['revisao']}"


def row_key(result: dict, item: str) -> str:
    e = result["execucao"]
    return f"{e['uf']}-{e['ano']}-{execution_token(result)}-{item}"


def execution_title(result: dict) -> str:
    e = result["execucao"]
    return f"{e['uf']} {e['ano']} — {e['id']}"


def _load(run_dir: Path) -> dict | None:
    return SR.read_json(Path(run_dir) / FILE)


def _save(run_dir: Path, state: dict) -> None:
    SR.write_json(Path(run_dir) / FILE, state)


def _state(run_dir: Path) -> dict:
    st = _load(run_dir)
    if not st:
        raise NotionOutputError("SAIDA_NAO_INICIADA", "Rode notion-iniciar com a página da solicitação antes de gravar no Notion.")
    result = NP._result(Path(run_dir))
    if st["resultado_sha256"] != result["execucao"]["conteudo_sha256"]:
        raise NotionOutputError("RESULTADO_MUDOU", "O resultado mudou depois de notion-iniciar: rode notion-iniciar de novo para gravar o resultado atual.")
    return st


# ---------------- 1. start: the request page, checked before any write ----------------

def start(run_dir: Path, page: dict) -> dict:
    """`page`: the request read through the connector ({page_id, id_solicitacao, uf, ano, status}). Same checks as the
    template publication: page id, business id, UF and year, or nothing is written. Re-running after the result changed
    keeps the run row (same execution) and marks every base to be synchronized again."""
    run_dir = Path(run_dir)
    result = NP._result(run_dir)
    e = result["execucao"]
    pid = NP.normalize_page_id(page.get("page_id"))
    if not pid:
        raise NotionOutputError("SOLICITACAO_SEM_ID", "A página da solicitação veio sem page_id. Nunca se escolhe a solicitação mais recente: a entrega fica local.")
    problems = []
    if page.get("id_solicitacao") is not None and NP._norm_business_id(page["id_solicitacao"]) != NP._norm_business_id(e["solicitacao_id"]):
        problems.append(f"ID da solicitação {page['id_solicitacao']} ≠ {e['solicitacao_id']}")
    if NP._ufs(page.get("uf")) != [e["uf"]]:
        problems.append(f"UF {page.get('uf')} ≠ {e['uf']}")
    try:
        if int(page.get("ano")) != int(e["ano"]):
            problems.append(f"ano {page.get('ano')} ≠ {e['ano']}")
    except (TypeError, ValueError):
        problems.append(f"ano {page.get('ano')} ≠ {e['ano']}")
    if problems:
        raise NotionOutputError("SOLICITACAO_DIVERGENTE", "A página não é a solicitação desta execução (" + "; ".join(problems) + "). Nada foi gravado no Notion.")
    old = _load(run_dir)
    if old and old["page_id"] != pid:
        raise NotionOutputError("PAGINA_DIFERENTE", f"Esta execução já foi gravada em outra solicitação ({old['page_id']}); confira o page_id.")
    same = bool(old) and old["resultado_sha256"] == e["conteudo_sha256"]
    state = {"page_id": pid, "solicitacao_id": e["solicitacao_id"], "execucao_id": e["id"], "uf": e["uf"], "ano": e["ano"],
             "resultado_sha256": e["conteudo_sha256"], "versao_plugin": QR.plugin_version(), "status_solicitacao_lido": page.get("status"),
             "execucao_page_id": (old or {}).get("execucao_page_id"), "iniciada_em": (old or {}).get("iniciada_em") or RUN.now(),
             "bases": (old or {}).get("bases") if same else {b: {"status": "pendente", "linhas": None, "conferida_em": None, "erro": None} for b in BASES}}
    _save(run_dir, state)
    return state


# ---------------- 2. rows: what each base must contain for this run ----------------

def _units(evs: list) -> str | None:
    seen = []
    for ev in evs:
        u = ev.get("unidade")
        if u and u not in seen:
            seen.append(u)
    return _text("; ".join(seen))


def _orientation_row(result: dict, o: dict, relation: list) -> dict:
    e = result["execucao"]
    presence = o["presenca"] if o["presenca"] in ("Sim", "Não") else "Pendente"
    status = o["status"] if o["status"] in ("decidido", "decidido_revisar") else "pendente"
    just = o["justificativa"] or ""
    if o["revisar"] and o["motivos"]:
        just = (just + " Revisar: " + "; ".join(m for m in o["motivos"] if m)).strip()
    sims = [ev for ev in o["evidencias"] if ev.get("verificacao") == "conferida"] if presence == "Sim" else []
    return {"Chave": row_key(result, o["codigo"]), "Código": o["codigo"], "Grupo": re.match(r"[A-Z]+", o["codigo"]).group(0),
            "Tipo": {"pedagogica": "pedagógica", "gestao": "gestão"}[o["tipo"]], "Orientação (referência)": _text(o["texto_referencia"]),
            "Presença (Claude)": presence, "Status Claude": status, "Confiança": o["confianca"] if presence != "Pendente" else None,
            "Revisar": bool(o["revisar"] or presence == "Pendente"), "Evidência (doc:pág)": _units(sims),
            "Trecho": _text(" | ".join(ev["trecho_literal"] for ev in sims if ev.get("trecho_literal"))), "Justificativa": _text(just),
            "UF": e["uf"], "Ano": e["ano"], "Execução": relation}


def _cell_value(cell: dict):
    """The number shown in Notion: the verified value, or the value read but not verified (an image read by AI, said
    in the justification). A range and an absent cell stay EMPTY: never zero, never a value chosen inside the range."""
    if cell.get("faixa"):
        return None
    if cell["status"] == "verificado":
        return cell["valor"]
    if cell["status"] == "nao_verificado" and cell.get("valor_proposto") is not None:
        return cell["valor_proposto"]
    return None


def _component_row(result: dict, c: dict, classes: list, relation: list) -> dict:
    e = result["execucao"]
    cells = c["aulas_semanais"]
    notes = []
    ranges = [f"{s[-1]}ª série: {QR._fmt(cells[s]['faixa']['min'])} ou {QR._fmt(cells[s]['faixa']['max'])} (faixa na fonte, sem valor escolhido)"
              for s in QR.SERIES if cells[s].get("faixa")]
    if ranges:
        notes.append("Faixas: " + "; ".join(ranges) + ".")
    if any((cells[s].get("evidencia") or {}).get("metodo") == "interpretacao_ia" for s in QR.SERIES):
        notes.append("Aulas lidas de imagem por IA, não verificadas pelo programa.")
    absent = [f"{s[-1]}ª" for s in QR.SERIES if cells[s]["status"] == "ausente_na_fonte"]
    if absent:
        notes.append("Não aparece na fonte em: " + ", ".join(absent) + " série.")
    other = [m for m in c["motivos"] if m]
    just = " ".join([c.get("justificativa_classificacao") or ""] + notes + (["Revisar: " + "; ".join(other)] if c["revisar"] and other else []))
    evs = [cells[s]["evidencia"] for s in QR.SERIES if cells[s].get("evidencia")]
    cls = c["classificacao"] if c["classificacao"] in classes else None
    return {"Chave": row_key(result, c["id"]), "ID componente": c["id"], "Componente": _text(c["nome_original"]),
            "Aulas 1ª série": _cell_value(cells["serie1"]), "Aulas 2ª série": _cell_value(cells["serie2"]), "Aulas 3ª série": _cell_value(cells["serie3"]),
            "Classificação (Claude)": cls, "Status classificação": "revisar" if (c["revisar"] or c["classificacao_status"] != "aceita") else "aceita",
            "Revisar": bool(c["revisar"] or c["classificacao_status"] != "aceita"), "Evidência (doc:pág)": _units(evs), "Justificativa": _text(just),
            "UF": e["uf"], "Ano": e["ano"], "Execução": relation}


def _element_rows(result: dict, relation: list) -> list:
    """The template's totals, only when the approved rule calculated them all. Without the approved rule the base stays
    empty for this run and the reason goes to the run row (no hand calculation)."""
    rs = result["matriz"]["resumo_por_elemento"]
    if rs["status"] != "calculado":
        return []
    e = result["execucao"]
    mins = result["matriz"]["minutos_aula"]
    classes = {_fold(x) for x in result["referencias"]["template"]["classificacoes"]}
    rows = []
    for n, el in enumerate(rs["elementos"], start=1):
        rule = ELEMENT_RULE.get(_fold(el["elemento"])) or ("CLASSE" if _fold(el["elemento"]) in classes else None)
        rows.append({"Chave": row_key(result, f"E{n:02d}"), "Elemento": el["elemento"], "Ordem": n, "Regra": rule,
                     "Aulas 1ª série": el["serie1"], "Aulas 2ª série": el["serie2"], "Aulas 3ª série": el["serie3"],
                     "Base de cálculo": "plugin (sem decisão humana)", "Modelo do Integral": "Propedêutico 9h",
                     "Hora-aula (min)": mins["valor"] if mins["status"] == "verificado" else None,
                     "Observações": _text(rs["motivo"]), "UF": e["uf"], "Ano": e["ano"], "Execução": relation})
    return rows


def _queue_type(gid: str) -> str:
    if gid.startswith("G-CONFLITO"):
        return "conflito"
    if gid.startswith(("G-COMPONENTE", "G-CLASSIFICACAO")):
        return "componente"
    if gid.startswith(("G-ORIENTACAO", "G-ORIENTACOES")):
        return "orientacao"
    return "decisao"


def _queue_rows(result: dict, relation: list) -> list:
    e = result["execucao"]
    grouped = QR.grouped_review_queue(result)
    rows = []
    for g in grouped["grupos"]:
        action = g["acao"] + (f" Documento a pedir: {g['documento_solicitado']}." if g.get("documento_solicitado") else "")
        items = "; ".join(i["referencia"] for i in g["itens"][:40]) + ("; …" if len(g["itens"]) > 40 else "")
        where = g["referencias"] + (["Células: " + "; ".join(g["celulas"])] if g["celulas"] else [])
        rows.append({"Item": _text(f"{g['ordem']:02d} · {g['titulo']}", 200), "Referência": row_key(result, g["id"]), "Ordem": g["ordem"],
                     "Prioridade": g["prioridade"], "Tipo": _queue_type(g["id"]), "O que decidir": _text(action),
                     "Motivos": _text(f"{g['causa']} Itens detalhados ({len(g['itens'])}): {items}." + ("" if g["confirmacao_individual"] else
                                      " Decisão única por requisito de negócio.") + " Confirmar a tarefa não confirma cada valor dela."),
                     "Onde (evidência)": _text("; ".join(where)), "UF": e["uf"], "Ano": e["ano"], "Execução": relation})
    return rows


def _execution_row(result: dict, state: dict) -> dict:
    e = result["execucao"]
    o = result["orientacoes"]["completude"]
    mins = result["matriz"]["minutos_aula"]
    grouped = QR.grouped_review_queue(result)
    blocking = sorted({p["codigo"] for p in result["pendencias"] if p["bloqueia_completude"]})
    rs = result["matriz"]["resumo_por_elemento"]
    obs = [f"Fila: {grouped['total_grupos']} tarefa(s) agrupada(s), {grouped['total_itens_detalhados']} item(ns) detalhado(s)."]
    if rs["status"] != "calculado":
        obs.append(f"Matriz (elementos) sem linhas nesta execução: {(rs['motivo'] or rs['status']).rstrip('.')}.")
    if blocking:
        obs.append("Pendências que impedem o status completo: " + ", ".join(blocking) + ".")
    return {"Execução": execution_title(result), "UF": e["uf"], "Ano": e["ano"], "Revisão": e["revisao"], "Modalidade": "propedêutico 9h",
            "Motor": f"{e['motor_versao']} · plugin {state.get('versao_plugin') or QR.plugin_version()}",
            "Status Claude": e["status"] if e["status"] in ("parcial", "completo") else "erro",
            "Sim (Claude)": sum(o[k]["sim"] for k in ("pedagogicas", "gestao")), "Não (Claude)": sum(o[k]["nao"] for k in ("pedagogicas", "gestao")),
            "Pendentes (Claude)": sum(o[k]["pendentes"] + o[k]["nao_avaliados"] for k in ("pedagogicas", "gestao")),
            "Itens na fila": grouped["total_grupos"], "Hora-aula (min)": mins["valor"] if mins["status"] == "verificado" else None,
            "SHA-256 conteúdo": e["conteudo_sha256"], "date:Gerado em:start": e["gerado_em"], "date:Gerado em:is_datetime": 1,
            "Observações": _text(" ".join(obs)), "Solicitação": [state["page_id"]]}


def desired_rows(run_dir: Path, base: str) -> list:
    if base not in BASES:
        raise NotionOutputError("BASE_DESCONHECIDA", f"Base desconhecida: {base}. Use: {', '.join(BASES)}.")
    run_dir = Path(run_dir)
    state = _state(run_dir)
    result = NP._result(run_dir)
    if base == "execucao":
        return [_execution_row(result, state)]
    if not state.get("execucao_page_id"):
        raise NotionOutputError("EXECUCAO_NAO_GRAVADA", "Grave e confira primeiro a linha da execução (notion-conferir --base execucao): as outras bases se ligam a ela.")
    relation = [state["execucao_page_id"]]
    if base == "orientacoes":
        return [_orientation_row(result, o, relation) for k in ("pedagogicas", "gestao") for o in result["orientacoes"][k]]
    if base == "componentes":
        classes = result["referencias"]["template"]["classificacoes"]
        return [_component_row(result, c, classes, relation) for c in result["matriz"]["componentes"]]
    if base == "elementos":
        return _element_rows(result, relation)
    return _queue_rows(result, relation)


def execution_body(result: dict) -> str:
    """Body of the run page in Notion: what `resumo.md` had (sources DOC-n, matrix, decisions, conflicts, coverage), so the
    reader can resolve 'Evidência (doc:pág)' without any file."""
    e, m = result["execucao"], result["matriz"]
    L = [f"Situação: **{QR.STATUS_TEXT[e['status']]}**. Execução `{e['id']}`, referencial ICE {e['versao_referencia_ice'] or 'sem versão'}, gerado em {e['gerado_em']}. "
         "Proposta do Claude à espera de validação humana: nada aqui foi aprovado.", "", "## Fontes (DOC-n)", ""]
    for f in result["fontes"]:
        L.append(f"- **{f['id']}** — {f['nome']} ({', '.join(f['classes'])}); leitura {f['status_leitura']}, "
                 f"{f['cobertura']['unidades_lidas']}/{f['cobertura']['unidades_total']} unidades" + (f"; pendências: {', '.join(f['pendencias'])}" if f["pendencias"] else ""))
    s = m["selecao"]
    L += ["", "## Matriz", ""]
    if s["status"] == "nao_registrada":
        L.append("Matriz ainda não selecionada nem transcrita.")
    else:
        c = m["completude"]
        L.append(f"Matriz em {s['fonte_id']} ({', '.join(s['unidades'])}), vigência {s['vigencia'] or '—'}, "
                 + ("confirmada pelo analista." if s["confirmada_por_analista"] else "**não confirmada pelo analista**."))
        L.append(f"{c['linhas_extraidas']} componente(s); células: {c['celulas_verificadas']} verificadas, {c['celulas_nao_verificadas']} não verificadas, "
                 f"{c.get('celulas_em_faixa', 0)} em faixa, {c['celulas_ausentes_na_fonte']} em branco na fonte. Hora-aula: {QR._fmt(m['minutos_aula']['valor'])} min.")
        for t in m.get("totais_fonte") or []:
            L.append(f"- Total impresso — {t['rotulo']}, {t['serie']}ª série: {QR._fmt(t['valor'])} (soma {QR._fmt(t['soma_min'])} a {QR._fmt(t['soma_max'])}: {t['estado']}).")
        doc = m.get("documento_oficial_citado")
        if doc:
            L.append(f"- Documento oficial citado para os valores exatos: {doc['titulo'] or '—'}.")
        rs = m["resumo_por_elemento"]
        L.append(f"- Resumo por elemento: {rs['status'].replace('_', ' ')}. {rs['motivo'] or ''}".rstrip())
    grouped = QR.grouped_review_queue(result)
    L += ["", "## Decisões gerais (antes de validar)", ""]
    general = [g for g in grouped["grupos"] if _queue_type(g["id"]) == "decisao"]
    L += [f"- [ ] **{g['titulo']}** — {g['acao']}" for g in general] or ["Nenhuma."]
    L += ["", "## Conflitos do cruzamento", ""]
    conflicts = result["consistencia"]["conflitos"]
    L += [f"- [{c['gravidade']}] {c['codigo']} — {c['entidade']}: {c['detalhe']}" for c in conflicts] or ["Nenhum conflito."]
    mt = result["metricas"]
    L += ["", "## Cobertura", ""]
    for key, label in (("cobertura_documental", "Documental"), ("cobertura_matriz", "Matriz"), ("cobertura_orientacoes", "Orientações")):
        L.append(f"- {label}: {mt[key]['numerador']} de {QR._fmt(mt[key]['denominador'])}.")
    L += ["", f"Fila de revisão: {grouped['total_grupos']} tarefa(s) na base 'Resultados — Fila de revisão' ({grouped['total_itens_detalhados']} item(ns) detalhado(s)). "
          "Confirmar uma tarefa não confirma cada valor dela."]
    return "\n".join(L) + "\n"


# ---------------- 3. plan: create / update / keep, against what is already there ----------------

def _norm(v):
    if v is None or v == "" or v == []:
        return None
    if isinstance(v, bool):
        return v
    if v in ("__YES__", "__NO__"):
        return v == "__YES__"
    if isinstance(v, (int, float)):
        return round(float(v), 4)
    if isinstance(v, list):
        out = []
        for x in v:
            pid = NP.normalize_page_id(x) if isinstance(x, str) and re.search(r"[0-9a-fA-F]{32}|[0-9a-fA-F-]{36}", x) else None
            out.append(pid or str(x))
        return sorted(out)
    if isinstance(v, str):
        try:
            return round(float(v), 4) if re.fullmatch(r"-?\d+(\.\d+)?", v.strip()) else re.sub(r"\s+", " ", v).strip()
        except ValueError:
            return re.sub(r"\s+", " ", v).strip()
    return v


def _flat(row: dict) -> dict:
    """A row read by the connector, either {page_id, propriedades: {...}} or flat {page_id/url, prop: value}."""
    props = dict(row.get("propriedades") or {k: v for k, v in row.items() if k not in ("page_id", "url", "propriedades")})
    pid = NP.normalize_page_id(row.get("page_id") or row.get("url"))
    return {"page_id": pid, "props": props}


def _compared(base: str, props: dict) -> dict:
    return {k: v for k, v in props.items() if k not in HUMAN[base] and not k.startswith("date:")}


def plan(run_dir: Path, base: str, existing: list) -> dict:
    """`existing`: the rows of this base already linked to this run (read by the connector). Never deletes: a row of this
    run that is no longer produced is reported as obsolete for the analyst."""
    run_dir = Path(run_dir)
    state = _state(run_dir)
    desired = desired_rows(run_dir, base)
    kp = KEY_PROP[base]
    have: dict = {}
    for r in existing or []:
        f = _flat(r)
        key = str(f["props"].get(kp) or "").strip()
        if not key:
            continue
        if key in have:
            raise NotionOutputError("LINHA_DUPLICADA", f"Há mais de uma linha com a chave {key} em {BASE_TITLES[base]}; resolva a duplicata no Notion antes de continuar.")
        have[key] = f
    out = {"base": base, "data_source_id": DATA_SOURCES[base], "criar": [], "atualizar": [], "manter": [], "bloqueadas": [], "obsoletas": []}
    keys = set()
    for row in desired:
        key = str(row[kp])
        keys.add(key)
        cur = have.get(key)
        props = {k: v for k, v in row.items() if k not in HUMAN[base]}
        if cur is None:
            create = dict(props)
            if base == "execucao":
                create["Validação humana"] = "Aguardando"
            out["criar"].append({"chave": key, "propriedades": create})
            continue
        if base == "fila" and str(cur["props"].get("Status") or QUEUE_OPEN) != QUEUE_OPEN:
            out["bloqueadas"].append({"chave": key, "page_id": cur["page_id"], "motivo": f"tarefa em '{cur['props'].get('Status')}': o analista já a está tratando"})
            continue
        diff = {k: v for k, v in _compared(base, props).items() if _norm(v) != _norm(cur["props"].get(k))}
        if diff:
            out["atualizar"].append({"chave": key, "page_id": cur["page_id"], "propriedades": diff})
        else:
            out["manter"].append(key)
    out["obsoletas"] = sorted(k for k in have if k not in keys)
    b = state["bases"][base]
    b.update(status="planejada", linhas=len(desired), erro=None)
    _save(run_dir, state)
    out["total_desejado"] = len(desired)
    return out


# ---------------- 4. confirm: the rows read again after the writes ----------------

def confirm(run_dir: Path, base: str, reread: list) -> dict:
    run_dir = Path(run_dir)
    state = _state(run_dir)
    desired = desired_rows(run_dir, base)
    kp = KEY_PROP[base]
    got: dict = {}
    for r in reread or []:
        f = _flat(r)
        key = str(f["props"].get(kp) or "").strip()
        if key:
            got.setdefault(key, []).append(f)
    missing, dup, diverge, locked = [], [], [], []
    for row in desired:
        key = str(row[kp])
        rows = got.get(key, [])
        if not rows:
            missing.append(key)
            continue
        if len(rows) > 1:
            dup.append(key)
            continue
        cur = rows[0]
        if base == "fila" and str(cur["props"].get("Status") or QUEUE_OPEN) != QUEUE_OPEN:
            locked.append(key)
            continue
        bad = [k for k, v in _compared(base, row).items() if _norm(v) != _norm(cur["props"].get(k))]
        if bad:
            diverge.append({"chave": key, "campos": bad})
    b = state["bases"][base]
    if missing or dup or diverge:
        b.update(status="falhou", erro={"faltando": missing[:50], "duplicadas": dup[:50], "divergentes": diverge[:50], "em": RUN.now()})
        _save(run_dir, state)
        raise NotionOutputError("NOTION_NAO_CONFERE", f"{BASE_TITLES[base]}: {len(missing)} linha(s) faltando, {len(dup)} duplicada(s), {len(diverge)} com valor diferente "
                                "na releitura. A gravação NÃO está confirmada; refaça notion-planejar com as linhas relidas.")
    if base == "execucao":
        state["execucao_page_id"] = got[str(desired[0][kp])][0]["page_id"]
        if not state["execucao_page_id"]:
            raise NotionOutputError("EXECUCAO_SEM_ID", "A linha da execução relida veio sem page_id.")
    b.update(status="confirmada", linhas=len(desired), conferida_em=RUN.now(), erro=None, bloqueadas_pelo_analista=locked)
    _save(run_dir, state)
    return {"base": base, "confirmada": True, "linhas": len(desired), "bloqueadas_pelo_analista": locked,
            "execucao_page_id": state.get("execucao_page_id")}


def fail(run_dir: Path, base: str, code: str, message: str) -> dict:
    state = _load(Path(run_dir))
    if not state:
        return {}
    if base in state["bases"]:
        state["bases"][base].update(status="falhou", erro={"codigo": code, "mensagem": message, "em": RUN.now()})
    _save(Path(run_dir), state)
    return state


# ---------------- 5. delivery: the request status moves only when everything is confirmed ----------------

def delivery(run_dir: Path, page_status: str | None = None) -> dict:
    run_dir = Path(run_dir)
    state = _state(run_dir)
    open_bases = [b for b in BASES if state["bases"][b]["status"] != "confirmada"]
    pub = SR.read_json(run_dir / NP.FILE) or {}
    xlsx_ok = pub.get("status") == "confirmada" and pub.get("resultado_sha256") == state["resultado_sha256"]
    current = page_status if page_status is not None else state.get("status_solicitacao_lido")
    ready = not open_bases and xlsx_ok
    new_status = NP.STATUS_DELIVERED if ready and current not in NP.STATUS_NO_REGRESS else None
    why = ("bases e template conferidos" if ready else
           "falta conferir: " + ", ".join([BASE_TITLES[b] for b in open_bases] + ([] if xlsx_ok else ["template preenchido na solicitação"])))
    if ready and new_status is None:
        why = f"a solicitação já está em '{current}'; não se regride o status"
    return {"pronta": ready, "novo_status": new_status, "motivo": why, "bases_pendentes": open_bases, "template_conferido": xlsx_ok,
            "page_id": state["page_id"], "execucao_page_id": state.get("execucao_page_id")}


def pipeline_state(run_dir: Path) -> dict | None:
    st = _load(Path(run_dir))
    if not st:
        return None
    try:
        d = delivery(run_dir)
    except NotionOutputError as e:
        return {"estado": "pendente", "detalhe": e.message}
    except NP.PublishError as e:
        return {"estado": "pendente", "detalhe": e.message}
    if d["pronta"]:
        return {"estado": "feita", "detalhe": "Execução, orientações, matriz, fila e template conferidos no Notion."}
    return {"estado": "em_andamento", "detalhe": "Saída no Notion: " + d["motivo"] + "."}
