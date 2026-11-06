"""Storage and logic of a comparison run (SPEC-005 4.1): `<appdata>/eqv/<UF>/<year>/`. Nothing here calls the AI.

Everything the AI produces comes in through `register_inventory` and `register_cell`, where CODE verifies the quotes and applies
the rules; an analyst's decision (`decide`) always wins and is never overwritten by a re-run (REQ-CRS-07).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from . import EQV_VERSION
from . import evidence as E
from . import rules as R
from . import template as T

NEARBY = 3  # a quote found up to 3 pages from the cited one still counts; the REAL page is reported (decision of 2026-11-06)
UNRELIABLE_FLAGS = ("tabela", "duas colunas", "ordem de leitura incerta", "texto possivelmente corrompido", "página sem texto")
MARK = "(pré-preenchido por IA)"


class EqvError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def run_dir(appdata: Path, uf: str, year: int) -> Path:
    return Path(appdata) / "eqv" / uf.upper() / str(year)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def read_json(path: Path, default=None):
    if not Path(path).exists():
        if default is not None:
            return default
        raise EqvError("EXECUCAO_NAO_INICIADA", "Esta comparação ainda não foi iniciada. Rode `eqv iniciar` primeiro.")
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- start of a run

def parse_doc_arg(value: str) -> tuple:
    label, sep, folder = value.partition("=")
    if not sep or not label.strip() or not folder.strip():
        raise EqvError("DOCUMENTO_INVALIDO", f"Use --doc \"Rótulo=pasta do documento\" (recebi: {value}).")
    return label.strip(), folder.strip()


def start_run(appdata: Path, template_path, uf: str, year: int, docs: list, cfp_root: Path) -> dict:
    uf = uf.upper()
    t = T.read_template(template_path)
    key = f"{uf}-{year}"
    tabs = {tab: a for tab, a in t["abas"].items() if key in a["colunas"]}
    if not tabs:
        raise EqvError("SEM_COLUNAS", f"A planilha não tem colunas para {uf} {year} nas abas 1.1 e 1.2.")
    documents = {}
    for label, folder in docs:
        d = Path(folder)
        if not d.is_dir():
            d = Path(cfp_root) / folder
        if not (d / "index.json").is_file() or not (d / "chunks").is_dir():
            raise EqvError("DOCUMENTO_NAO_ENCONTRADO", f"Não encontrei o documento processado pelo CFP: {folder}.")
        idx = json.loads((d / "index.json").read_text(encoding="utf-8"))
        if idx.get("situacao") == "Reprovado":
            raise EqvError("DOCUMENTO_REPROVADO", f"O documento '{label}' está Reprovado na qualidade do CFP; reprocesse ou use outra versão.")
        chars = sum(c.get("caracteres", 0) for c in idx.get("chunks", []))
        documents[label] = {"pasta": str(d), "sha256": idx.get("sha256"), "titulo": idx.get("titulo"), "chunks": len(idx.get("chunks", [])), "caracteres": chars,
                            "situacao": idx.get("situacao"), "versao_cfp": idx.get("versoes", {}).get("cfp")}
    if not documents:
        raise EqvError("SEM_DOCUMENTOS", "Informe pelo menos um documento com --doc \"Rótulo=pasta\".")
    rd = run_dir(appdata, uf, year)
    previous = read_json(rd / "execucao.json", default={})
    if previous and previous.get("planilha_sha256") != t["sha256"]:
        raise EqvError("PLANILHA_DIFERENTE", "Já existe uma comparação deste estado e ano com outra versão da planilha. Use outra pasta de dados ou apague a execução antiga.")
    orient = {tab: a["orientacoes"] for tab, a in tabs.items()}
    write_json(rd / "orientacoes.json", {"sha256": t["sha256"], "orientacoes": orient, "colunas": {tab: a["colunas"][key] for tab, a in tabs.items()}})
    write_json(rd / "gabarito.json", {k: v for k, v in t["gabarito"].items() if k.split("|")[2] == uf and k.split("|")[3] == str(year)})
    write_json(rd / "documentos.json", documents)
    run = {"uf": uf, "ano": year, "planilha_sha256": t["sha256"], "abas": sorted(tabs), "iniciado_em": previous.get("iniciado_em") or now(), "versao_eqv": EQV_VERSION}
    write_json(rd / "execucao.json", run)
    chars = sum(d["caracteres"] for d in documents.values())
    return {"pasta": str(rd), "abas": {tab: len(o) for tab, o in orient.items()}, "documentos": documents, "caracteres": chars,
            "tokens_min": round(chars / 4), "tokens_max": round(chars / 3), "avisos": t["avisos"]}


# ---------------------------------------------------------------- documents and pages

def load_documents(rd: Path) -> dict:
    return read_json(rd / "documentos.json")


_PAGE_CACHE: dict = {}


def doc_pages(documents: dict, label: str, enriched: bool = False) -> dict:
    if label not in documents:
        raise EqvError("DOCUMENTO_DESCONHECIDO", f"Documento '{label}' não faz parte desta comparação. Rótulos: {', '.join(documents)}.")
    key = (documents[label]["pasta"], enriched)
    if key not in _PAGE_CACHE:
        if enriched and (Path(documents[label]["pasta"]) / "chunks_com_imagens").is_dir():
            _PAGE_CACHE[key] = E.load_pages(documents[label]["pasta"], "chunks_com_imagens")
        else:
            _PAGE_CACHE[key] = E.load_pages(documents[label]["pasta"])
    return _PAGE_CACHE[key]


def unreliable_pages(doc_folder: str) -> set:
    q = read_json(Path(doc_folder) / "qualidade.json", default={})
    out = set()
    for p in q.get("paginas", []):
        if any(any(f in a for f in UNRELIABLE_FLAGS) for a in p.get("avisos", [])):
            out.add(p["pagina"])
    return out


def locate_quote(quote: str, pages: dict, cited: int) -> dict:
    """Verifies a quote on the cited page, then on pages up to NEARBY away; returns the REAL page (REQ-CRS-03, decision Q-8)."""
    order = [cited] + [cited + d * s for d in range(1, NEARBY + 1) for s in (1, -1)]
    last = {"ok": False, "motivo": "página inexistente no documento"}
    for p in order:
        if p in pages:
            r = E.verify(quote, pages[p])
            if r["ok"]:
                return {"ok": True, "pagina": p, "motivo": "" if p == cited else f"encontrada na página {p} (a IA citou a {cited})"}
            last = r
    return {"ok": False, "pagina": cited, "motivo": last["motivo"]}


# ---------------------------------------------------------------- inventory (phase A)

def inventory_path(rd: Path, label: str) -> Path:
    return rd / "inventarios" / (re.sub(r"[^A-Za-z0-9._-]+", "_", label) + ".json")


def register_inventory(rd: Path, label: str, items: list, chunks_covered: list | None = None) -> dict:
    documents = load_documents(rd)
    pages = doc_pages(documents, label)
    inv = read_json(inventory_path(rd, label), default={"rotulo": label, "itens": [], "chunks_cobertos": [], "paginas_inspecionadas": []})
    accepted, rejected = [], []
    for it in items:
        quote, cited = str(it.get("trecho", "")), it.get("pagina")
        if not isinstance(cited, int):
            rejected.append({"item": it.get("titulo"), "motivo": "página ausente ou inválida"})
            continue
        r = locate_quote(quote, pages, cited)
        if not r["ok"]:
            rejected.append({"item": it.get("titulo"), "pagina": cited, "motivo": r["motivo"]})
            continue
        entry = {"grupo": it.get("grupo", ""), "titulo": it.get("titulo", ""), "descricao": it.get("descricao", ""), "pagina": r["pagina"],
                 "chunk": it.get("chunk"), "trecho": quote, "verificado_em": now()}
        if r["motivo"]:
            entry["nota"] = r["motivo"]
        accepted.append(entry)
    inv["itens"] += accepted
    inv["chunks_cobertos"] = sorted(set(inv["chunks_cobertos"]) | set(chunks_covered or []))
    inv["paginas_inspecionadas"] = sorted(set(inv["paginas_inspecionadas"]) | {a["pagina"] for a in accepted})
    inv["atualizado_em"] = now()
    write_json(inventory_path(rd, label), inv)
    return {"aceitos": len(accepted), "rejeitados": rejected, "total_itens": len(inv["itens"]), "chunks_cobertos": len(inv["chunks_cobertos"]),
            "chunks_do_documento": documents[label]["chunks"]}


def inventory_status(rd: Path) -> dict:
    documents = load_documents(rd)
    out = {}
    for label, d in documents.items():
        inv = read_json(inventory_path(rd, label), default={"itens": [], "chunks_cobertos": []})
        out[label] = {"itens": len(inv["itens"]), "chunks_cobertos": len(inv["chunks_cobertos"]), "chunks": d["chunks"],
                      "completo": len(inv["chunks_cobertos"]) >= d["chunks"] > 0}
    return out


# ---------------------------------------------------------------- cells (phase B -> C)

def cell_path(rd: Path, tab: str, code: str) -> Path:
    return rd / "celulas" / f"{tab}-{code}.json"


def known_orientation(rd: Path, tab: str, code: str) -> dict:
    for o in read_json(rd / "orientacoes.json")["orientacoes"].get(tab, []):
        if o["codigo"] == code:
            return o
    raise EqvError("ORIENTACAO_INEXISTENTE", f"A orientação {code} não existe na aba {tab} desta comparação.")


def build_comment(valor: str, evidencias: list, ausencia: dict | None, confirmed_only: bool = True) -> str:
    if valor == "Sim":
        by_doc: dict = {}
        for e in evidencias:
            if e.get("verificada"):
                by_doc.setdefault(e["documento"], []).append(e)
        parts = []
        for doc, es in by_doc.items():
            es = sorted(es, key=lambda e: e["pagina"])  # pages and quotes in the same order
            pgs = sorted({e["pagina"] for e in es})
            head = ("Págs. " + " e ".join(str(p) for p in pgs)) if len(pgs) > 1 else f"Pág. {pgs[0]}"
            quotes = " / ".join('"' + re.sub(r"\s+", " ", e["trecho"]).strip()[:300] + '"' for e in es[:2])
            parts.append(f"{head} ({doc}): {quotes}")
        body = " | ".join(parts) if parts else ""
    else:
        body = (ausencia or {}).get("resumo") or "Não encontrado nos documentos informados."
    return (body + " " + MARK).strip()


def register_cell(rd: Path, proposal: dict, minimo: int = R.DEFAULT_MINIMUM) -> dict:
    tab, code = proposal.get("aba"), proposal.get("codigo")
    o = known_orientation(rd, tab, code)
    previous = read_json(cell_path(rd, tab, code), default={})
    if previous.get("decidido_por") == "analista":  # an analyst's decision is never overwritten by a re-run (REQ-CRS-07)
        return {"aba": tab, "codigo": code, "mantida": True, "motivo": "decisão do analista preservada", "valor": previous["valor"]}
    documents = load_documents(rd)
    evidencias, rejected = [], []
    for ev in proposal.get("evidencias", []):
        label, cited = ev.get("documento"), ev.get("pagina")
        image = ev.get("origem", "texto") != "texto"
        pages = doc_pages(documents, label, enriched=image)
        r = locate_quote(str(ev.get("trecho", "")), pages, cited) if isinstance(cited, int) else {"ok": False, "pagina": cited, "motivo": "página ausente"}
        unreliable = r["ok"] and r["pagina"] in unreliable_pages(documents[label]["pasta"])
        item = {"documento": label, "chunk": ev.get("chunk"), "pagina": r["pagina"], "relacao": ev.get("relacao", "Equivalente"), "origem": ev.get("origem", "texto"),
                "trecho": ev.get("trecho", ""), "item": ev.get("item", ""), "verificada": r["ok"], "pagina_nao_confiavel": bool(unreliable)}
        if r["ok"] and r["motivo"]:
            item["nota"] = r["motivo"]
        if not r["ok"]:
            item["motivo_rejeicao"] = r["motivo"]
            rejected.append({"documento": label, "pagina": cited, "motivo": r["motivo"]})
        evidencias.append(item)
    inv = {l: read_json(inventory_path(rd, l), default={"chunks_cobertos": []}) for l in documents}
    complete = all(len(inv[l]["chunks_cobertos"]) >= documents[l]["chunks"] for l in documents)
    risk = any(unreliable_pages(d["pasta"]) for d in documents.values()) or any(_pending_images(d["pasta"]) for d in documents.values())
    ctx = {"cobertura_completa": complete, "risco_de_ocultar": risk, "memoria_em_conflito": bool(proposal.get("memoria_em_conflito")),
           "documento_reprovado": any(d["situacao"] == "Reprovado" for d in documents.values())}
    verdict = R.decide(proposal, evidencias, minimo, ctx)
    cell = {"aba": tab, "codigo": code, "uf": run_uf(rd), "ano": run_year(rd), "orientacao": o["orientacao"], "valor": verdict["valor"],
            "valor_planilha": R.tab_capitalization(verdict["valor"], tab), "revisar": verdict["revisar"], "confianca": verdict["confianca"],
            "motivos": verdict["motivos"], "valor_proposto": proposal.get("valor"), "confianca_proposta": proposal.get("confianca"),
            "explicacao": str(proposal.get("explicacao", "")).strip(), "evidencias": evidencias, "ausencia": proposal.get("ausencia"),
            "memoria": proposal.get("memoria", []), "comentario": build_comment(verdict["valor"], evidencias, proposal.get("ausencia")),
            "decidido_por": "IA", "registrado_em": now(), "versao_eqv": EQV_VERSION}
    write_json(cell_path(rd, tab, code), cell)
    return {"aba": tab, "codigo": code, "valor": cell["valor"], "revisar": cell["revisar"], "confianca": cell["confianca"], "motivos": cell["motivos"], "rejeitadas": rejected}


def _pending_images(doc_folder: str) -> int:
    idx = Path(doc_folder) / "imagens" / "index.json"
    if not idx.exists():
        return 0
    return sum(1 for e in json.loads(idx.read_text(encoding="utf-8"))["imagens"] if e.get("estado") == "pendente")


def run_uf(rd: Path) -> str:
    return read_json(rd / "execucao.json")["uf"]


def run_year(rd: Path) -> int:
    return read_json(rd / "execucao.json")["ano"]


def decide(rd: Path, tab: str, code: str, value: str, reason: str = "", author: str = "") -> dict:
    """The analyst's decision: overrides the AI value, clears the flag, counts as 95% (REQ-CFB-01)."""
    v = R.normalize_value(value)
    if v is None:
        raise EqvError("VALOR_INVALIDO", "O valor deve ser Sim ou Não.")
    o = known_orientation(rd, tab, code)
    cell = read_json(cell_path(rd, tab, code), default={"aba": tab, "codigo": code, "uf": run_uf(rd), "ano": run_year(rd), "orientacao": o["orientacao"],
                                                         "evidencias": [], "ausencia": None, "memoria": [], "explicacao": "", "motivos": []})
    cell.update({"valor": v, "valor_planilha": R.tab_capitalization(v, tab), "revisar": False, "confianca": R.ANALYST_CONFIDENCE, "decidido_por": "analista",
                 "autor": author, "motivo_do_analista": reason, "decidido_em": now()})
    if not cell.get("comentario"):
        cell["comentario"] = (reason + " " if reason else "") + "(decidido pelo analista)"
    write_json(cell_path(rd, tab, code), cell)
    document_words = "; ".join(sorted({e.get("item", "") for e in cell.get("evidencias", []) if e.get("item")}))
    return {"aba": tab, "codigo": code, "valor": v, "memoria_sugerida": {"assunto": "EQV", "tipo": "Fato" if v == "Sim" else "Rejeição", "componente_isg": f"{code} — {o['orientacao']}",
            "termo_externo": document_words, "enunciado": f"{code} em {run_uf(rd)} {run_year(rd)}: {v}", "justificativa": reason, "uf": run_uf(rd), "ano": run_year(rd), "confianca": R.ANALYST_CONFIDENCE}}


def load_cells(rd: Path) -> dict:
    out = {}
    d = rd / "celulas"
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            c = json.loads(p.read_text(encoding="utf-8"))
            out[(c["aba"], c["codigo"])] = c
    return out


def status(rd: Path) -> dict:
    orient = read_json(rd / "orientacoes.json")["orientacoes"]
    cells = load_cells(rd)
    tabs = {}
    for tab, rows in orient.items():
        done = [cells[(tab, o["codigo"])] for o in rows if (tab, o["codigo"]) in cells]
        tabs[tab] = {"orientacoes": len(rows), "comparadas": len(done), "sim": sum(c["valor"] == "Sim" for c in done), "nao": sum(c["valor"] == "Não" for c in done),
                     "revisar": sum(bool(c["revisar"]) for c in done), "por_analista": sum(c.get("decidido_por") == "analista" for c in done)}
    return {"abas": tabs, "inventarios": inventory_status(rd)}
