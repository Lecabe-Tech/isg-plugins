"""SPEC-017 G4: typed cross-check between the matrix and the orientations fronts.

Compares claims of the SAME type for the SAME cycle (UF + year + propedêutico 9h) and the same component; never edits
either front (it only reads matriz.json/orientacoes.json and writes consistencia.json). Typed assertions come from
Claude, each with a quote verified by the program:
  oferta / nao_oferta (a state document says the component is or is not offered),
  carga_semanal (a state document gives weekly lessons per grade),
  exigencia_normativa (the ICE reference says the component should exist: "should" is not "is").
The absence of a specific orientation is never a contradiction with a positive weekly load.
"""
from __future__ import annotations

from pathlib import Path

import document_normalizer as DN
import evidence_check as EC
import matrix_analysis as MA
import quality_run as RUN
import source_resolver as SR

TYPES = ("oferta", "nao_oferta", "carga_semanal", "exigencia_normativa")
STATE = ("orientacoes_estaduais", "matriz_estadual")
SERIES = MA.SERIES


class CrossCheckError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def register(run_dir: Path, items) -> dict:
    inv = RUN.load_inventory(run_dir)
    index = RUN.unit_index(run_dir)
    classes = {f["id"]: f["classes"] for f in inv["fontes"]}
    items = items if isinstance(items, list) else items.get("afirmacoes", [items])
    stored = []
    for i, a in enumerate(items, start=1):
        tipo = a.get("tipo")
        if tipo not in TYPES:
            raise CrossCheckError("AFIRMACAO_INVALIDA", f"Afirmação {i}: tipo '{tipo}' desconhecido (use {', '.join(TYPES)}).")
        comp = str(a.get("componente") or "").strip()
        if not comp:
            raise CrossCheckError("AFIRMACAO_INVALIDA", f"Afirmação {i}: informe o componente.")
        allowed = ("referencial_ice",) if tipo == "exigencia_normativa" else STATE
        motivos, evs, ok = [], [], True
        valores = {s: (a.get("valores") or {}).get(s) for s in SERIES} if tipo == "carga_semanal" else None
        cells = a.get("celulas") or {}
        if tipo == "carga_semanal" and cells:
            for s in SERIES:
                if valores[s] is None:
                    continue
                r = EC.check({"unidade": cells.get(s)}, index, classes, allowed, min_len=3, number=valores[s])
                evs += [r["evidencia"]] if r["evidencia"] else []
                if not r["ok"]:
                    ok = False
                    motivos.append(f"{s}: {r['motivo']}")
        else:
            r = EC.check(a, index, classes, allowed, min_len=4)
            evs += [r["evidencia"]] if r["evidencia"] else []
            if not r["ok"]:
                ok = False
                motivos.append(r["motivo"])
            elif tipo == "carga_semanal":
                missing = [s for s in SERIES if valores[s] is not None and not EC.number_in(a.get("trecho_literal", ""), valores[s])]
                if missing:
                    ok = False
                    motivos.append("valores que não aparecem no trecho: " + ", ".join(missing))
            if ok and tipo != "carga_semanal" and DN.squash(comp) not in DN.squash(a.get("trecho_literal", "")):
                ok = False
                motivos.append("o componente não aparece no trecho citado")
        ciclo = a.get("ciclo") or {}
        stored.append({"id": "A%03d" % i, "tipo": tipo, "componente": comp, "componente_matriz": a.get("componente_matriz"), "valores": valores,
                       "ciclo": {"uf": ciclo.get("uf"), "ano": ciclo.get("ano"), "modelo": ciclo.get("modelo")}, "evidencias": evs,
                       "verificada": ok, "motivos": motivos})
    SR.write_json(run_dir / "afirmacoes.json", stored)
    return {"afirmacoes": len(stored), "verificadas": sum(s["verificada"] for s in stored),
            "rejeitadas": [{"id": s["id"], "motivos": s["motivos"]} for s in stored if not s["verificada"]]}


def _same_cycle(a: dict, manifest: dict) -> str | None:
    c = a["ciclo"]
    if c["uf"] is None or c["ano"] is None or c["modelo"] is None:
        return "ciclo da afirmação não identificado (UF, ano e modelo)"
    if str(c["uf"]).upper() != manifest["uf"] or int(c["ano"]) != manifest["ano"] or SR.normalize_scope({"modelo": c["modelo"]}).get("modelo") != "9h":
        return f"afirmação de outro ciclo ({c['uf']} {c['ano']} {c['modelo']})"
    return None


def _match(a: dict, comps: list) -> dict | None:
    if a.get("componente_matriz"):
        return next((c for c in comps if c["nome_original"] == a["componente_matriz"]), None)
    key = DN.squash(a["componente"])
    return next((c for c in comps if DN.squash(c["nome_original"]) == key), None)


def _val(origin, ev, value):
    return {"origem": origin, "fonte_id": ev["fonte_id"] if ev else None, "unidade": ev["unidade"] if ev else None, "valor": value}


def _upper(cell: dict):
    """Largest weekly load a cell can have: the verified value, the top of a range or the value read but not verified."""
    if cell.get("faixa"):
        return cell["faixa"]["max"], False
    if cell["status"] == "verificado":
        return cell["valor"] or 0, True
    if cell.get("valor_proposto") is not None:
        return cell["valor_proposto"], False
    return 0, cell["status"] == "ausente_na_fonte"


def _minimum_load(rule: dict, comps: list, matrix: dict, conflicts: list, chk) -> None:
    """ICE table 1 (approved in manifesto_ice.json): the load of a diversified element, summed over the components with
    that accepted class, against the minimum. Compares with the LARGEST possible value (top of a range, value read from an
    image), so a conflict means 'below the minimum even in the best case'; unverified values are said in the detail."""
    cls = DN.fold(rule["classificacao"])
    pending = [c["id"] for c in comps if c["classificacao_status"] != "aceita"]
    members = [c for c in comps if c["classificacao_status"] == "aceita" and DN.fold(c["classificacao"] or "") == cls]
    if pending and not members:
        chk("carga_minima", "nao_aplicavel", f"{rule['classificacao']}: há classificação pendente ({', '.join(pending[:6])}); comparação adiada")
        return
    per, sure = {}, True
    for s in SERIES:
        vals = [_upper(c["aulas_semanais"][s]) for c in members]
        per[s] = sum(v for v, _ in vals)
        sure = sure and all(ok for _, ok in vals)
    below = []
    for s, need in (rule.get("minimo_por_serie") or {}).items():
        if per[s] < need:
            below.append(f"{s[-1]}ª série {QRfmt(per[s])} < {QRfmt(need)}")
    if rule.get("minimo_total") is not None and sum(per.values()) < rule["minimo_total"]:
        below.append(f"total {QRfmt(sum(per.values()))} < {QRfmt(rule['minimo_total'])}")
    if not below:
        chk("carga_minima", "sem_conflito", f"{rule['classificacao']}: carga da matriz atinge o mínimo aprovado do ICE")
        return
    ev = next((c["aulas_semanais"][s]["evidencia"] for c in members for s in SERIES if c["aulas_semanais"][s].get("evidencia")), None)
    conflicts.append({"codigo": "CARGA_ABAIXO_MINIMO", "gravidade": "media", "predicado": "carga mínima do componente (ICE)", "entidade": rule["classificacao"],
                      "valores": [{"origem": "referencial_ice", "fonte_id": None, "unidade": None, "valor": {"minimo_por_serie": rule.get("minimo_por_serie"),
                                                                                                              "minimo_total": rule.get("minimo_total")}},
                                  _val("matriz", ev, per)],
                      "fontes": [matrix["selecao"]["fonte_id"]] if matrix["selecao"]["fonte_id"] else [], "resolucao_pendente": True,
                      "detalhe": f"{rule['classificacao']} abaixo do mínimo aprovado do ICE: " + "; ".join(below)
                                 + (f" (componentes: {', '.join(c['nome_original'] for c in members) or 'nenhum'})"
                                    + ("" if sure else "; comparação com o maior valor possível, há valores em faixa ou não verificados") + ".")})


def QRfmt(v):
    return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)


def run(run_dir: Path) -> dict:
    """Recomputes consistencia.json from the current fronts. Deterministic; read-only on both fronts."""
    manifest = RUN.load_manifest(run_dir)
    inv = RUN.load_inventory(run_dir)
    matrix, _ = MA.section(run_dir)
    comps = matrix["componentes"]
    assertions = SR.read_json(run_dir / "afirmacoes.json", []) or []
    conflicts, checks = [], []

    def chk(rule, result, detail):
        checks.append({"regra": rule, "resultado": result, "detalhe": detail})
    usable = []
    for a in assertions:
        if not a["verificada"]:
            chk(a["tipo"], "ignorada", f"{a['id']} ({a['componente']}): citação não conferida — " + "; ".join(a["motivos"]))
            continue
        why = _same_cycle(a, manifest)
        if why:
            chk(a["tipo"], "ignorada", f"{a['id']} ({a['componente']}): {why}; não é comparável")
            continue
        usable.append(a)
    for a in usable:
        comp = _match(a, comps)
        ev = a["evidencias"][0] if a["evidencias"] else None
        if a["tipo"] == "nao_oferta":
            positive = comp and any((comp["aulas_semanais"][s]["valor"] or 0) > 0 for s in SERIES if comp["aulas_semanais"][s]["status"] == "verificado")
            if positive:
                conflicts.append({"codigo": "CONTRADICAO_OFERTA_CARGA", "gravidade": "alta", "predicado": "oferta do componente no ciclo", "entidade": comp["nome_original"],
                                  "valores": [_val("matriz", comp["aulas_semanais"]["serie1"]["evidencia"], {s: comp["aulas_semanais"][s]["valor"] for s in SERIES}),
                                              _val("documento", ev, "não oferecido")],
                                  "fontes": sorted({x for x in (ev and ev["fonte_id"], matrix["selecao"]["fonte_id"]) if x}), "resolucao_pendente": True,
                                  "detalhe": f"A matriz confirmada tem aulas de {comp['nome_original']}, mas {a['id']} afirma que o componente não é oferecido no mesmo ciclo."})
            else:
                chk("nao_oferta", "sem_conflito", f"{a['id']}: {a['componente']} sem carga positiva verificada na matriz")
        elif a["tipo"] == "carga_semanal":
            if not comp:
                chk("carga_semanal", "nao_aplicavel", f"{a['id']}: {a['componente']} não está na matriz transcrita")
                continue
            diff = [s for s in SERIES if a["valores"][s] is not None and comp["aulas_semanais"][s]["status"] == "verificado" and comp["aulas_semanais"][s]["valor"] != a["valores"][s]]
            if diff:
                conflicts.append({"codigo": "CONFLITO_ENTRE_FONTES", "gravidade": "media", "predicado": "aulas semanais por série", "entidade": comp["nome_original"],
                                  "valores": [_val("matriz", comp["aulas_semanais"][diff[0]]["evidencia"], {s: comp["aulas_semanais"][s]["valor"] for s in SERIES}),
                                              _val("documento", ev, a["valores"])],
                                  "fontes": sorted({x for x in (ev and ev["fonte_id"], matrix["selecao"]["fonte_id"]) if x}), "resolucao_pendente": True,
                                  "detalhe": f"{comp['nome_original']}: a matriz e {a['id']} divergem em {', '.join(s[-1] + 'ª série' for s in diff)}; os dois valores foram mantidos, sem escolha automática."})
            else:
                chk("carga_semanal", "sem_conflito", f"{a['id']}: {comp['nome_original']} com as mesmas aulas da matriz")
        elif a["tipo"] == "exigencia_normativa":
            offered = comp and any(MA.offered(comp["aulas_semanais"][s]) for s in SERIES)  # a range "1 ou 2" is an offer
            if not offered:
                conflicts.append({"codigo": "NORMATIVO_VS_OFERTA", "gravidade": "media", "predicado": "componente exigido pelo ICE x oferta real", "entidade": a["componente"],
                                  "valores": [_val("referencial_ice", ev, "exigido"), _val("matriz", None, "ausente" if not comp else "sem aulas")],
                                  "fontes": [ev["fonte_id"]] if ev else [], "resolucao_pendente": True,
                                  "detalhe": f"O ICE prevê {a['componente']}, mas a matriz estadual não o oferece. É diferença entre norma e oferta: nenhuma aula foi inventada."})
            else:
                chk("exigencia_normativa", "sem_conflito", f"{a['id']}: {a['componente']} previsto no ICE e oferecido na matriz")
        else:
            chk("oferta", "sem_conflito" if comp else "nao_aplicavel", f"{a['id']}: {a['componente']} " + ("na matriz" if comp else "não está na matriz transcrita"))
    carga = [a for a in usable if a["tipo"] == "carga_semanal"]
    for i, a in enumerate(carga):
        for b in carga[i + 1:]:
            if DN.squash(a["componente_matriz"] or a["componente"]) != DN.squash(b["componente_matriz"] or b["componente"]):
                continue
            diff = [s for s in SERIES if a["valores"][s] is not None and b["valores"][s] is not None and a["valores"][s] != b["valores"][s]]
            if diff:
                ea, eb = a["evidencias"][0], b["evidencias"][0]
                conflicts.append({"codigo": "CONFLITO_ENTRE_FONTES", "gravidade": "media", "predicado": "aulas semanais por série", "entidade": a["componente"],
                                  "valores": [_val("documento", ea, a["valores"]), _val("documento", eb, b["valores"])],
                                  "fontes": sorted({ea["fonte_id"], eb["fonte_id"]}), "resolucao_pendente": True,
                                  "detalhe": f"{a['id']} e {b['id']} divergem sobre {a['componente']}; o analista decide qual edição vale."})
    for c in comps:
        if c["classificacao_status"] != "aceita":
            conflicts.append({"codigo": "CLASSIFICACAO_PENDENTE", "gravidade": "baixa", "predicado": "classificação do componente", "entidade": c["nome_original"],
                              "valores": [_val("matriz", c["evidencias"][0] if c["evidencias"] else None, c["classificacao"])], "fontes": [matrix["selecao"]["fonte_id"]] if matrix["selecao"]["fonte_id"] else [],
                              "resolucao_pendente": True, "detalhe": "Aulas mantidas como estão na fonte; a classificação aguarda justificativa ou decisão."})
    for f in inv["fontes"]:
        if set(f["classes"]) & set(STATE) and f["status_leitura"] != "lida":
            conflicts.append({"codigo": "COBERTURA_DOCUMENTAL_INCOMPLETA", "gravidade": "media", "predicado": "leitura completa das fontes estaduais", "entidade": f["id"],
                              "valores": [{"origem": "inventario", "fonte_id": f["id"], "unidade": None, "valor": f["status_leitura"]}], "fontes": [f["id"]], "resolucao_pendente": True,
                              "detalhe": f"{f['nome']}: " + ("; ".join(p["detalhe"] for p in f["pendencias"]) or "leitura incompleta") + ". Nenhuma conclusão negativa é tirada só da ausência."})
    for rule in (manifest.get("configuracao_ice") or {}).get("carga_minima") or []:
        _minimum_load(rule, comps, matrix, conflicts, chk)
    offered = [c["nome_original"] for c in comps if any(MA.offered(c["aulas_semanais"][s]) for s in SERIES)]
    chk("oferta_x_orientacao", "sem_conflito", "Oferta de componente com carga positiva e ausência de orientação específica são avaliações diferentes: não geram conflito"
        + (f" ({len(offered)} componente(s) com carga)." if offered else "."))
    result = {"status": "executada", "conflitos": conflicts, "checagens": checks}
    SR.write_json(run_dir / "consistencia.json", result)
    return result
