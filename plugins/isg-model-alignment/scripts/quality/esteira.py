"""The analysis pipeline ("esteira") of one run: which stage is done and which command comes next.

A lay analyst should not have to run the steps one by one (lesson of the CE 2026 pilot). The skill `analisar` drives the
whole pipeline by asking this module, after each step, what the next one is, until the result and the review queue
exist. Everything is read from the run folder, so an interrupted analysis resumes where it stopped.

Stages, in order:
  1 entradas     manifest validated and the four input classes read (inventario.json)
  2 imagens      every passage in an image read (or copied from the same picture)
  3 matriz       9h propedêutico matrix selected and transcribed (matriz.json)
  4 orientacoes  every applicable ICE orientation evaluated: Sim, Não or pending with a reason
  5 cruzamento   typed claims compared with the matrix (consistencia.json newer than both fronts)
  6 resultado    resultado_qualidade.v1.json + resumo.md + review queue, newer than everything above
  7 template     filled COPY of the cluster template (one line per orientation with Sim/Não, the UF matrix tab), newer
                 than the result: the deliverable the analyst reviews (lesson of the CE 2026 pilot)
The AI steps (reading images, transcribing, evaluating) are done by Claude; the program checks and records them.
"""
from __future__ import annotations

from pathlib import Path

import quality_run as RUN

TITLES = {
    "entradas": "Ler as entradas (estado, template, ICE)",
    "imagens": "Ler os trechos em imagem",
    "matriz": "Transcrever e classificar a matriz de 9h",
    "orientacoes": "Avaliar as orientações do ICE",
    "cruzamento": "Cruzar matriz e orientações",
    "resultado": "Gerar o resultado e a fila de revisão",
    "template": "Preencher a cópia do template do cluster",
}
NEXT = {
    "entradas": "manifesto-montar → iniciar",
    "imagens": "imagens → ler cada imagem diferente (em lotes, com subagentes) → imagem-registrar",
    "matriz": "matriz-candidatas → tabela-pdf (se for PDF) → matriz-registrar",
    "orientacoes": "orientacoes-codigos → orientacoes-lotes → subagentes por lote → orientacoes-conferir → orientacoes-registrar",
    "cruzamento": "afirmacoes-registrar (se algum documento afirmar carga ou oferta) → cruzar",
    "resultado": "resultado → revisao-fila",
    "template": "template-preencher",
}


def _mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


def status(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    stages = []

    def add(key, state, detail):
        stages.append({"etapa": key, "titulo": TITLES[key], "estado": state, "detalhe": detail, "proximo": None if state == "feita" else NEXT[key]})
    inv_path = run_dir / "inventario.json"
    if not inv_path.exists():
        add("entradas", "pendente", "Execução ainda não iniciada nesta pasta.")
        for k in ("imagens", "matriz", "orientacoes", "cruzamento", "resultado", "template"):
            add(k, "pendente", "Depende das entradas.")
        return _close(stages)
    inv = RUN.load_inventory(run_dir)
    pend_in = sum(len(f["pendencias"]) for f in inv["fontes"]) + len(inv["pendencias"])
    add("entradas", "feita", f"{len(inv['fontes'])} documento(s) lido(s); {pend_in} pendência(s) de entrada (vão para a fila de revisão).")

    imgs = RUN.pending_images(run_dir)
    unique = sum(1 for p in imgs if not p["mesma_imagem_que"])
    add("imagens", "feita" if not imgs else "em_andamento",
        "Todos os trechos em imagem foram lidos." if not imgs else f"{len(imgs)} trecho(s) em imagem sem leitura ({unique} imagem(ns) diferente(s)).")

    import matrix_analysis as MA
    import orientation_analysis as OA

    if (run_dir / "matriz.json").exists():
        s = MA.summary(run_dir)
        add("matriz", "feita", f"{s['componentes']} componente(s); {s['verificadas']} célula(s) verificada(s), {s['nao_verificadas']} não verificada(s), "
            f"{s.get('em_faixa', 0)} em faixa; {len(s['pendencias'])} pendência(s) para a fila.")
    else:
        add("matriz", "pendente", "Matriz ainda não registrada.")

    if (run_dir / "orientacoes.json").exists():
        sec, _ = OA.section(run_dir)
        c = sec["completude"]
        not_eval = sum(c[k]["nao_avaliados"] for k in OA.TYPES)
        done = sum(c[k]["codigos_avaliados"] for k in OA.TYPES)
        pend = sum(c[k]["pendentes"] for k in OA.TYPES)
        add("orientacoes", "feita" if not not_eval else "em_andamento",
            f"{done} com Sim ou Não, {pend} pendente(s) com motivo, {not_eval} ainda não avaliada(s).")
    else:
        add("orientacoes", "pendente", "Nenhuma orientação registrada.")

    fronts = max(_mtime(run_dir / "matriz.json"), _mtime(run_dir / "orientacoes.json"), _mtime(run_dir / "afirmacoes.json"))
    cons = run_dir / "consistencia.json"
    add("cruzamento", "feita" if cons.exists() and _mtime(cons) >= fronts else "pendente",
        "Cruzamento feito depois da última mudança nas frentes." if cons.exists() and _mtime(cons) >= fronts else
        ("Matriz ou orientações mudaram depois do último cruzamento." if cons.exists() else "Cruzamento ainda não executado."))

    res = run_dir / "resultado_qualidade.v1.json"
    latest = max(_mtime(inv_path), fronts, _mtime(cons), max((_mtime(p) for p in (run_dir / "fontes").glob("DOC-*.json")), default=0.0))
    fresh = res.exists() and _mtime(res) >= latest
    add("resultado", "feita" if fresh else "pendente",
        "Resultado gerado depois da última mudança; a fila de revisão está no resumo.md." if fresh else
        ("Algo mudou depois do último resultado: gere de novo." if res.exists() else "Resultado ainda não gerado."))

    import template_fill as TF

    tpl = TF.default_path(run_dir)
    if tpl is None:
        add("template", "feita", "Sem template do cluster em XLSX nesta execução: nada a preencher.")
    else:
        done = tpl.exists() and fresh and _mtime(tpl) >= _mtime(res)
        add("template", "feita" if done else "pendente", f"Cópia preenchida: {tpl}" if done else
            ("O resultado mudou depois do último preenchimento: preencha de novo." if tpl.exists() else "Cópia do template ainda não preenchida."))
    return _close(stages)


def _close(stages: list) -> dict:
    open_before = False  # the cross-check and the result depend on every earlier stage: they are redone after it
    for s in stages:
        if s["etapa"] in ("cruzamento", "resultado", "template") and open_before and s["estado"] == "feita":
            s.update(estado="pendente", detalhe="Refazer depois de concluir as etapas anteriores.", proximo=NEXT[s["etapa"]])
        open_before = open_before or s["estado"] != "feita"
    nxt = next((s for s in stages if s["estado"] != "feita"), None)
    return {"etapas": stages, "proxima": nxt["etapa"] if nxt else None, "proximo_passo": nxt["proximo"] if nxt else None,
            "concluida": nxt is None}


def manifest(uf: str, ano: int, estado: list, template: list, ice: list, matriz: list | None = None, solicitacao: str | None = None) -> dict:
    """Manifest from the files the analyst sent, already split by the skill: state documents count both as orientations
    and as the matrix source (the program finds the matrix inside them); `matriz` = state files that only hold the
    matrix; an empty ICE list = the configured reference. Files, folders and SharePoint links are all accepted."""
    matriz = matriz or []
    return {"schema_version": "1.0", "solicitacao_id": solicitacao or f"{uf.upper()}-{ano}-01", "revisao": 1, "uf": uf.upper(), "ano": int(ano),
            "modelo": "9h", "modalidade": "propedeutico",
            "entradas": {"orientacoes_estaduais": [{"uri": u, "papel": "orientacao"} for u in estado],
                         "matriz_estadual": [{"uri": u, "papel": "matriz"} for u in estado + matriz],
                         "template_cluster": [{"uri": u, "papel": "template"} for u in template],
                         "referencial_ice": [{"uri": u, "papel": "referencial"} for u in ice]},
            "homologacao_ice": None, "regras_homologadas": [], "aplicabilidade_codigos": None}
