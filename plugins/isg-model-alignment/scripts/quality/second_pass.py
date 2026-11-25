"""Second, limited and resumable analysis pass of the Quality flow ("reanálise").

Between the first evaluation (matrix + orientations) and the cross-check, the items still in doubt get ONE more
independent look, by subagents, with only the criterion text and the state documents (no template history, no earlier
human answers and, to avoid anchoring, not even the first proposal):
  * orientations `pendente` or `decidido_revisar` (never an analyst decision);
  * matrix components marked for review because of cells read from an image, in a range or not verified: a second
    reading of the same pages, compared cell by cell with the first. Two AI readings that agree are still NOT a
    verification: the cells stay `nao_verificado`; a divergence is written in the component and kept in review.
The program decides what the second proposal may change:
  * it replaces the first decision only when it is strictly better (pending -> decided, review -> decided) with verified
    evidence and the same answer (or the first was pending);
  * a contradiction (Sim x Não) never resolves silently: the first decision stays, marked for review with both answers;
  * a worse proposal changes nothing; analyst decisions are never touched.
Everything is recorded in `reanalise.json` (start, end, items, outcome and reasons). The round is tied to the version
of the inputs (sources, units, references): one round per version; changed inputs open a new one. A missing source is
requested once (`documentos_solicitados`), with every affected field; nothing is searched or downloaded outside the
closed set of sources.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import document_normalizer as DN
import matrix_analysis as MA
import orientation_analysis as OA
import quality_run as RUN
import source_resolver as SR

FILE = "reanalise.json"
RANK = {"pendente": 0, "nao_avaliado": 0, "decidido_revisar": 1, "decidido": 2}

RULES = """
## Segunda passagem (reanálise)

Este lote tem só as orientações que ficaram em dúvida na primeira análise. Você NÃO recebe a resposta anterior: avalie
do zero, com o texto da orientação e os documentos do estado.
- Procure sinônimos, equivalências e trechos complementares em outras partes dos documentos (outra seção, anexo, quadro).
- Confira se o trecho vale para o Ensino Médio Integral PROPEDÊUTICO de 9h (não para o EMTI Profissional, EPT ou 7h).
- Prefira um trecho que AFIRME a orientação; relação só Indireta continua em revisão.
- Se ainda faltar prova, deixe presenca null e diga, na justificativa, qual documento ou trecho resolveria. Não pesquise
  na internet nem use conhecimento próprio sobre o estado.
"""


class SecondPassError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def inputs_version(run_dir: Path) -> str:
    """SHA-256 of what the analysis reads: source hashes, located units (with image readings) and the references."""
    h = hashlib.sha256()
    inv = RUN.load_inventory(run_dir)
    for f in sorted(inv["fontes"], key=lambda x: x["id"]):
        h.update((f["id"] + ":" + str(f["sha256"])).encode("utf-8"))
    for p in sorted((run_dir / "fontes").glob("DOC-*.json")):
        h.update(hashlib.sha256(p.read_bytes()).digest())
    ref = run_dir / "referencias.json"
    if ref.exists():
        h.update(hashlib.sha256(ref.read_bytes()).digest())
    return h.hexdigest()


def _load(run_dir: Path) -> dict | None:
    return SR.read_json(run_dir / FILE)


def _candidates(run_dir: Path) -> dict:
    sec, _ = OA.section(run_dir) if (run_dir / "orientacoes.json").exists() else ({"pedagogicas": [], "gestao": []}, [])
    rows = [o for k in OA.TYPES for o in sec[k]]
    not_eval = [o["codigo"] for o in rows if o["status"] == "nao_avaliado"]
    codes = [o["codigo"] for o in rows if o["status"] in ("pendente", "decidido_revisar") and o["origem"] != "analista"]
    data = SR.read_json(run_dir / "matriz.json") or {}
    comps = []
    for c in data.get("componentes") or []:
        cells = [c["aulas_semanais"][s] for s in MA.SERIES]
        doubtful = any(x["status"] == "nao_verificado" or x.get("faixa") or (x.get("evidencia") or {}).get("metodo") == "interpretacao_ia" for x in cells)
        if c["revisar"] and doubtful:
            comps.append(c["id"])
    units = (data.get("selecao") or {}).get("unidades") or []
    return {"orientacoes": codes, "nao_avaliadas": not_eval, "componentes": comps, "unidades_matriz": units}


def status(run_dir: Path) -> dict:
    """{'estado': feita | em_andamento | pendente, 'detalhe'} for the pipeline."""
    run_dir = Path(run_dir)
    rec = _load(run_dir)
    version = inputs_version(run_dir)
    if rec and rec["versao_entradas"] == version and rec["status"] == "concluida":
        r = rec["resumo"]
        return {"estado": "feita", "detalhe": f"Segunda passagem concluída: {r['substituidas']} decisão(ões) melhorada(s), {r['divergentes']} divergente(s) em revisão, "
                                              f"{r['mantidas']} mantida(s); {r['componentes_relidos']} componente(s) relido(s)."}
    cand = _candidates(run_dir)
    if not cand["orientacoes"] and not cand["componentes"]:
        return {"estado": "feita", "detalhe": "Nada em dúvida para reanalisar."}
    if rec and rec["versao_entradas"] == version and rec["status"] == "em_andamento":
        done = len(rec["orientacoes"]["resultado"])
        return {"estado": "em_andamento", "detalhe": f"Segunda passagem em andamento: {done} de {len(rec['orientacoes']['selecionadas'])} orientação(ões) reavaliada(s); "
                                                    f"matriz {'relida' if rec['matriz']['comparacao'] is not None else 'não relida'}."}
    return {"estado": "pendente", "detalhe": f"{len(cand['orientacoes'])} orientação(ões) e {len(cand['componentes'])} componente(s) em dúvida para a segunda passagem."}


def plan(run_dir: Path, out_dir: Path, size: int = 35) -> dict:
    """Starts (or resumes) the round for the current inputs and writes the work packages. A round already concluded for
    the same inputs is not repeated."""
    run_dir, out_dir = Path(run_dir), Path(out_dir)
    version = inputs_version(run_dir)
    rec = _load(run_dir)
    if rec and rec["versao_entradas"] == version and rec["status"] == "concluida":
        return {"ja_concluida": True, "registro": rec}
    cand = _candidates(run_dir)
    if cand["nao_avaliadas"]:
        raise SecondPassError("PRIMEIRA_PASSAGEM_INCOMPLETA", f"{len(cand['nao_avaliadas'])} orientação(ões) ainda sem a primeira avaliação; termine a etapa de orientações antes.")
    resumed = bool(rec and rec["versao_entradas"] == version and rec["status"] == "em_andamento")
    if not resumed:
        rec = {"versao_entradas": version, "rodada": 1, "status": "em_andamento", "iniciada_em": RUN.now(), "concluida_em": None,
               "orientacoes": {"selecionadas": cand["orientacoes"], "resultado": []},
               "matriz": {"componentes": cand["componentes"], "unidades": cand["unidades_matriz"], "comparacao": None},
               "documentos_solicitados": (rec or {}).get("documentos_solicitados", []) if rec and rec["versao_entradas"] == version else [],
               "resumo": None}
        SR.write_json(run_dir / FILE, rec)
    batches = {"lotes": []}
    if rec["orientacoes"]["selecionadas"]:
        batches = OA.export_batches(run_dir, out_dir, size, only=set(rec["orientacoes"]["selecionadas"]), extra_rules=RULES)
    data = SR.read_json(run_dir / "matriz.json") or {}
    names = {c["id"]: c["nome_original"] for c in data.get("componentes") or []}
    if rec["matriz"]["componentes"]:
        out_dir.mkdir(parents=True, exist_ok=True)
        lines = ["# Segunda leitura da matriz (reanálise)", "",
                 "Releia, por série, as páginas abaixo e transcreva de novo SÓ os componentes listados, sem consultar a transcrição anterior.",
                 "Copie os números como aparecem; uma faixa ('3 ou 4') entra como faixa; em branco ou traço = null. Confira os totais impressos.",
                 "Grave `matriz_segunda_leitura.json` no formato:",
                 '{"componentes": [{"nome_original": "...", "aulas_semanais": {"serie1": 2, "serie2": {"faixa": [3, 4]}, "serie3": null}}],',
                 ' "totais_fonte": [{"rotulo": "...", "serie": 1, "valor": 45}]}', "", "Páginas (unidades): " + ", ".join(rec["matriz"]["unidades"]), "",
                 "Componentes:"] + [f"- {names.get(i, i)}" for i in rec["matriz"]["componentes"]]
        (out_dir / "MATRIZ_SEGUNDA_LEITURA.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return {"ja_concluida": False, "retomada": resumed, "pasta": str(out_dir), "orientacoes": len(rec["orientacoes"]["selecionadas"]),
            "lotes": batches["lotes"], "componentes": len(rec["matriz"]["componentes"]), "unidades_matriz": rec["matriz"]["unidades"]}


def _open_round(run_dir: Path) -> dict:
    rec = _load(run_dir)
    if not rec or rec["status"] != "em_andamento":
        raise SecondPassError("REANALISE_NAO_PLANEJADA", "Não há segunda passagem em andamento; rode reanalise-planejar antes.")
    if rec["versao_entradas"] != inputs_version(run_dir):
        raise SecondPassError("ENTRADAS_MUDARAM", "As entradas mudaram depois do planejamento da segunda passagem; planeje de novo.")
    return rec


def _brief(d: dict) -> dict:
    return {"presenca": d.get("presenca"), "status": d.get("status"), "confianca": d.get("confianca")}


def register_orientations(run_dir: Path, proposals) -> dict:
    run_dir = Path(run_dir)
    rec = _open_round(run_dir)
    items = proposals if isinstance(proposals, list) else proposals.get("orientacoes", [proposals])
    inv = RUN.load_inventory(run_dir)
    index = RUN.unit_index(run_dir)
    classes = {f["id"]: f["classes"] for f in inv["fontes"]}
    ctx = OA._context(inv)
    store = SR.read_json(run_dir / "orientacoes.json", {}) or {}
    selected = set(rec["orientacoes"]["selecionadas"])
    seen = {r["codigo"] for r in rec["orientacoes"]["resultado"]}
    out = {"substituidas": [], "divergentes": [], "mantidas": [], "preservadas_do_analista": [], "fora_da_selecao": [], "ja_reavaliadas": []}
    for p in items:
        code = str(p.get("codigo") or "").strip()
        if code not in selected:
            out["fora_da_selecao"].append(code)
            continue
        if code in seen:  # one second look per item and per round
            out["ja_reavaliadas"].append(code)
            continue
        first = store.get(code) or {}
        before = _brief(first)
        if first.get("origem") == "analista":
            out["preservadas_do_analista"].append(code)
            rec["orientacoes"]["resultado"].append({"codigo": code, "decisao": "preservada_do_analista", "antes": _brief(first), "proposta": None, "depois": _brief(first)})
            continue
        second = OA.decide(p, index, classes, ctx)
        prop = {"presenca": second["presenca"], "status": second["status"], "confianca": second["confianca"], "justificativa": second["justificativa"],
                "evidencias": [e["unidade"] for e in second["evidencias"]], "motivos": second["motivos"]}
        p1, p2 = first.get("presenca"), second["presenca"]
        if p1 and p2 and p1 != p2:
            first = dict(first)
            first.update(status="decidido_revisar", revisar=True,
                         motivos=list(dict.fromkeys(first.get("motivos", []) + [f"segunda passagem divergente: propôs {p2} ({second['confianca']}%) com outra evidência; decisão humana"])))
            store[code] = first
            kind = "divergente"
        elif second["presenca"] is not None and RANK[second["status"]] > RANK.get(first.get("status"), 0) and p1 in (None, p2):
            second["motivos"] = list(dict.fromkeys(second["motivos"] + [f"resolvida na segunda passagem (antes: {first.get('status', 'nao_avaliado')})"]))
            store[code] = second
            kind = "substituida"
        else:
            first = dict(first)
            first["motivos"] = list(dict.fromkeys(first.get("motivos", []) + ["segunda passagem sem evidência melhor"]))
            store[code] = first
            kind = "mantida"
        out[kind + "s"].append(code)
        rec["orientacoes"]["resultado"].append({"codigo": code, "decisao": kind, "antes": before, "proposta": prop, "depois": _brief(store[code])})
        seen.add(code)
    SR.write_json(run_dir / "orientacoes.json", store)
    SR.write_json(run_dir / FILE, rec)
    out["faltam"] = sorted(selected - seen)
    return out


def _reading(raw):
    """A second-reading cell -> comparable value: number, ('faixa', lo, hi) or None (blank)."""
    if isinstance(raw, dict) and raw.get("faixa") is not None:
        f = raw["faixa"]
        return ("faixa", f[0], f[1]) if isinstance(f, (list, tuple)) and len(f) == 2 else ("invalida",)
    if isinstance(raw, dict):
        raw = raw.get("valor")
    return raw if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None


def _first(cell: dict):
    if cell.get("faixa"):
        return ("faixa", cell["faixa"]["min"], cell["faixa"]["max"])
    if cell["status"] == "verificado":
        return cell["valor"]
    return cell.get("valor_proposto")


def register_matrix(run_dir: Path, reading: dict) -> dict:
    """Compares the second reading with the first, cell by cell, for the components selected in the plan. Values and
    statuses never change: agreement is written as a note (still not verified), divergence keeps the component in review."""
    run_dir = Path(run_dir)
    rec = _open_round(run_dir)
    data = SR.read_json(run_dir / "matriz.json")
    if not data:
        raise SecondPassError("MATRIZ_NAO_REGISTRADA", "Registre a matriz antes da segunda leitura.")
    by_name = {DN.squash(str(c.get("nome_original") or "")): c for c in reading.get("componentes") or []}
    comparison = []
    for c in data["componentes"]:
        if c["id"] not in rec["matriz"]["componentes"]:
            continue
        r2 = by_name.get(DN.squash(c["nome_original"]))
        if r2 is None:
            comparison.append({"id": c["id"], "nome": c["nome_original"], "resultado": "nao_relido", "series": {}})
            continue
        series, diverge = {}, []
        for s in MA.SERIES:
            a, b = _first(c["aulas_semanais"][s]), _reading((r2.get("aulas_semanais") or {}).get(s))
            series[s] = {"primeira": a, "segunda": b, "confere": a == b}
            if a != b:
                diverge.append(f"{s[-1]}ª série: {a} × {b}")
        if diverge:
            note = "duas leituras divergem (" + "; ".join(diverge) + "): conferir na fonte"
            c["revisar"] = True
        else:
            note = "segunda leitura confere com a primeira; continua não verificada pelo programa" if any(
                c["aulas_semanais"][s]["status"] != "verificado" for s in MA.SERIES) else "segunda leitura confere com a primeira"
        c["motivos"] = list(dict.fromkeys([m for m in c["motivos"] if not m.startswith(("duas leituras divergem", "segunda leitura confere"))] + [note]))
        comparison.append({"id": c["id"], "nome": c["nome_original"], "resultado": "diverge" if diverge else "confere", "series": series})
    SR.write_json(run_dir / "matriz.json", data)
    rec["matriz"]["comparacao"] = comparison
    rec["matriz"]["totais_segunda_leitura"] = reading.get("totais_fonte") or []
    SR.write_json(run_dir / FILE, rec)
    return {"comparados": len(comparison), "conferem": sum(x["resultado"] == "confere" for x in comparison),
            "divergem": [x["nome"] for x in comparison if x["resultado"] == "diverge"], "nao_relidos": [x["nome"] for x in comparison if x["resultado"] == "nao_relido"]}


def request_document(run_dir: Path, titulo: str, motivo: str, campos: list) -> dict:
    """Records ONE request for a missing source, with every affected field (deduplicated by title)."""
    run_dir = Path(run_dir)
    rec = _open_round(run_dir)
    titulo = (titulo or "").strip()
    if len(titulo) < 3 or not campos:
        raise SecondPassError("ENTRADA_INVALIDA", "Informe o título do documento e ao menos um campo afetado.")
    docs = rec.setdefault("documentos_solicitados", [])
    cur = next((d for d in docs if DN.squash(d["titulo"]) == DN.squash(titulo)), None)
    if cur is None:
        cur = {"titulo": titulo, "motivo": (motivo or "").strip() or None, "campos": []}
        docs.append(cur)
    cur["campos"] = sorted(set(cur["campos"]) | {str(c).strip() for c in campos if str(c).strip()})
    SR.write_json(run_dir / FILE, rec)
    return cur


def finish(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    rec = _open_round(run_dir)
    res = rec["orientacoes"]["resultado"]
    done = {r["codigo"] for r in res}
    comp = rec["matriz"]["comparacao"]
    rec["resumo"] = {"selecionadas": len(rec["orientacoes"]["selecionadas"]), "reavaliadas": len(done),
                     "nao_reavaliadas": sorted(set(rec["orientacoes"]["selecionadas"]) - done),
                     "substituidas": sum(r["decisao"] == "substituida" for r in res), "divergentes": sum(r["decisao"] == "divergente" for r in res),
                     "mantidas": sum(r["decisao"] == "mantida" for r in res), "componentes_selecionados": len(rec["matriz"]["componentes"]),
                     "componentes_relidos": sum(1 for x in comp or [] if x["resultado"] != "nao_relido"),
                     "matriz_relida": comp is not None, "documentos_solicitados": len(rec.get("documentos_solicitados") or [])}
    rec.update(status="concluida", concluida_em=RUN.now())
    SR.write_json(run_dir / FILE, rec)
    return rec["resumo"]


def requested_documents(run_dir: Path) -> list:
    rec = _load(Path(run_dir))
    return (rec or {}).get("documentos_solicitados") or []

