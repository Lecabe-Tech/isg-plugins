"""SIP integration (SPEC-004 S2-S4): register interpretations, estimate cost, build the enriched copy of the chunks.

Deterministic, no AI. The original chunks are NEVER modified (REQ-SIN-02); the enriched copy is rebuilt from them.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

SIP_TEMPLATE_VERSION = 1
SECTIONS = ["Tipo", "Texto na imagem (transcrição literal)", "Conteúdo estruturado", "Descrição", "Significado no contexto", "Confiança", "Dúvidas e partes ilegíveis"]
CONFIDENCE = ("alta", "média", "baixa")
STATES_DONE = ("interpretada", "corrigida")
TOKENS_STANDARD_CAP = 1568
TOKENS_HIGHRES_CAP = 4784
TOKENS_ANSWER = 1000

MARKER_RE = re.compile(r"^\[Imagem( pequena)? não processada — página (\d+) — id (p\d+-\d+)\]$", re.M)
BLOCK_RE = re.compile(r'<!-- SIP início id=(\S+) original="([^"]*)"[^\n]*-->\n.*?\n<!-- SIP fim id=\1 -->', re.S)
BANNER = "<!-- SIP banner: este arquivo tem interpretações de imagens feitas por IA; o que está fora dos blocos SIP é o texto original do PDF -->\n"


class SipError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------- front matter / template

def split_front_matter(text: str) -> tuple:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[4:end].split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, text[end + 5:].lstrip("\n")


def validate_interpretation(text: str) -> list:
    """Template lint (REQ-SIP-01, 06, SQL-01/03): the problems found, [] when the Markdown follows the template."""
    problems = []
    meta, body = split_front_matter(text)
    for key in ("id", "sha256", "confianca", "origem", "versao_modelo_sip", "estado"):
        if not meta.get(key):
            problems.append(f"campo ausente no cabeçalho: {key}")
    if meta.get("confianca") and meta["confianca"] not in CONFIDENCE:
        problems.append("confianca deve ser alta, média ou baixa")
    if meta.get("origem") and not meta["origem"].startswith("IA") and meta.get("estado") != "corrigida":
        problems.append("origem deve começar com 'IA'")
    pos = -1
    for s in SECTIONS:
        m = re.search(r"^### " + re.escape(s) + r"\s*$", body, re.M)
        if not m:
            problems.append(f"seção ausente: {s}")
        elif m.start() < pos:
            problems.append(f"seção fora de ordem: {s}")
        else:
            pos = m.start()
    return problems


# ---------------------------------------------------------------- index

def read_index(doc: Path) -> list:
    p = doc / "imagens" / "index.json"
    if not p.exists():
        raise SipError("SEM_IMAGENS", "Este documento ainda não tem imagens extraídas. Rode `cfp imagens` (ou processe de novo com --force).")
    return json.loads(p.read_text(encoding="utf-8"))["imagens"]


def write_index(doc: Path, entries: list) -> None:
    p = doc / "imagens" / "index.json"
    tmp = p.with_name(p.name + f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps({"imagens": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, p)


def _source_id(entry: dict) -> str:
    return entry.get("igual_a") or entry["id"]


def interpretation_path(doc: Path, entry: dict) -> Path:
    return doc / "imagens" / f"{_source_id(entry)}.md"


def effective_state(doc: Path, entry: dict) -> str:
    """The state an image really has: a written interpretation wins over the index (duplicates share their source's)."""
    p = interpretation_path(doc, entry)
    if p.exists():
        meta, _ = split_front_matter(p.read_text(encoding="utf-8"))
        if meta.get("estado") in STATES_DONE:
            return meta["estado"]
        return "interpretada"
    return entry["estado"]


def register(doc: Path, appdata: Path, image_id: str, md_file: Path, estado: str = "interpretada") -> dict:
    """Validates and stores an interpretation (REQ-SIP-09, REQ-SFB-02): document file, index, global cache."""
    if estado not in STATES_DONE:
        raise SipError("ESTADO_INVALIDO", "O estado deve ser interpretada ou corrigida.")
    entries = read_index(doc)
    by_id = {e["id"]: e for e in entries}
    if image_id not in by_id:
        raise SipError("IMAGEM_INEXISTENTE", f"Imagem {image_id} não existe neste documento.")
    entry = by_id[image_id]
    source = by_id.get(_source_id(entry), entry)
    if not source.get("sha256"):
        raise SipError("SEM_ARQUIVO", f"A imagem {image_id} não foi extraída; não há o que registrar.")
    text = Path(md_file).read_text(encoding="utf-8")
    meta, body = split_front_matter(text)
    meta.update({"id": source["id"], "sha256": source["sha256"], "pagina": str(source["pagina"]), "estado": estado,
                 "versao_modelo_sip": meta.get("versao_modelo_sip") or str(SIP_TEMPLATE_VERSION),
                 "gerado_em": meta.get("gerado_em") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    if estado == "interpretada":
        meta["origem"] = "IA (Claude)"
    else:
        meta.setdefault("origem", "IA (Claude), corrigida por analista")
    order = ["id", "sha256", "pagina", "confianca", "gerado_em", "origem", "versao_modelo_sip", "estado"]
    head = "\n".join(f"{k}: {meta[k]}" for k in order + [k for k in meta if k not in order] if k in meta)
    final = f"---\n{head}\n---\n\n{body.strip()}\n"
    problems = validate_interpretation(final)
    if problems:
        raise SipError("MODELO_INVALIDO", "A interpretação não segue o modelo: " + "; ".join(problems))
    target = doc / "imagens" / f"{source['id']}.md"
    if target.exists() and estado == "corrigida":  # keep the previous version (REQ-SFB-02)
        n = 1
        while (doc / "imagens" / f"{source['id']}.v{n}.md").exists():
            n += 1
        shutil.copyfile(target, doc / "imagens" / f"{source['id']}.v{n}.md")
    tmp = target.with_name(target.name + f".tmp-{os.getpid()}")
    tmp.write_text(final, encoding="utf-8", newline="\n")
    os.replace(tmp, target)
    cache = appdata / "sip" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(target, cache / f"{source['sha256']}.md")
    for e in entries:
        if _source_id(e) == source["id"]:
            e["estado"] = estado
            e["motivo"] = None
    write_index(doc, entries)
    return {"id": source["id"], "estado": estado, "arquivo": str(target), "sha256": source["sha256"]}


# ---------------------------------------------------------------- cost

def estimate_tokens(entry: dict) -> tuple:
    """(low, high) tokens for one image: image part min(ceil(w/28)*ceil(h/28), cap) + a typical answer (SPEC-004 4.4)."""
    w, h = entry.get("pixels") or [0, 0]
    raw = math.ceil(w / 28) * math.ceil(h / 28)
    return min(raw, TOKENS_STANDARD_CAP) + TOKENS_ANSWER, min(raw, TOKENS_HIGHRES_CAP) + TOKENS_ANSWER


def pending_report(doc: Path, appdata: Path, only_chunks: list | None = None, apply_cache: bool = True) -> dict:
    """Images still to interpret, after filling what the global cache already knows (no AI call, REQ-SIP-10)."""
    entries = read_index(doc)
    filled = []
    if apply_cache:
        cache = appdata / "sip" / "cache"
        for e in entries:
            if e["estado"] == "pendente" and not e.get("igual_a") and e.get("sha256") and not interpretation_path(doc, e).exists() and (cache / f"{e['sha256']}.md").exists():
                shutil.copyfile(cache / f"{e['sha256']}.md", interpretation_path(doc, e))
                for x in entries:
                    if _source_id(x) == e["id"]:
                        x["estado"] = "interpretada"
                filled.append(e["id"])
        if filled:
            write_index(doc, entries)
    pend = [e for e in entries if e["estado"] == "pendente" and not e.get("igual_a") and e.get("arquivo")
            and (only_chunks is None or e.get("chunk") in only_chunks)]
    low = sum(estimate_tokens(e)[0] for e in pend)
    high = sum(estimate_tokens(e)[1] for e in pend)
    return {"pendentes": [{"id": e["id"], "pagina": e["pagina"], "arquivo": e["arquivo"], "pixels": e["pixels"], "chunk": e.get("chunk"), "legenda": e.get("legenda", "")} for e in pend],
            "quantidade": len(pend), "tokens_min": low, "tokens_max": high, "preenchidas_do_cache": filled}


# ---------------------------------------------------------------- enriched copy

def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _block(entry: dict, state: str, md_text: str | None, original: str) -> str:
    iid, page = entry["id"], entry["pagina"]
    if md_text is not None:
        meta, body = split_front_matter(md_text)
        label = "corrigida por analista" if state == "corrigida" else "interpretação por IA"
        head = f'<!-- SIP início id={iid} original="{original}" sha256={meta.get("sha256", "")} confianca={meta.get("confianca", "")} estado={state} -->'
        lines = [f"> **Imagem p. {page} — {label}, conferir no PDF** (id {iid})", ">"] + [("> " + ln) if ln.strip() else ">" for ln in body.strip().split("\n")]
    else:
        why = {"pendente": "ainda não interpretada", "pequena": "ícone pequeno, não interpretado", "não extraível": "não foi possível extrair" + (f" ({entry['motivo']})" if entry.get("motivo") else ""),
               "grande demais": "grande demais para interpretar (acima de 8000 px ou 10 MB)"}.get(state, state)
        head = f'<!-- SIP início id={iid} original="{original}" estado={state} -->'
        lines = [f"> **Imagem p. {page} (id {iid}) — {why}.**"]
    return head + "\n" + "\n".join(lines) + f"\n<!-- SIP fim id={iid} -->"


def strip_blocks(text: str) -> str:
    """Round trip (Q10): enriched text -> original text."""
    out = BLOCK_RE.sub(lambda m: m.group(2), text)
    return out.replace(BANNER, "", 1)


def build_enriched(doc: Path) -> dict:
    entries = read_index(doc)
    by_id = {e["id"]: e for e in entries}
    chunks_dir = doc / "chunks"
    before = {p.name: _sha(p) for p in sorted(chunks_dir.glob("*.md"))}
    out_tmp = doc / f"chunks_com_imagens.tmp-{os.getpid()}"
    if out_tmp.exists():
        shutil.rmtree(out_tmp)  # CFP's own temporary folder only
    out_tmp.mkdir()
    problems, seen_ids = [], set()
    for src in sorted(chunks_dir.glob("*.md")):
        original = src.read_text(encoding="utf-8")

        def repl(m):
            iid = m.group(3)
            seen_ids.add(iid)
            e = by_id.get(iid)
            if e is None:
                problems.append(f"marcador {iid} sem entrada no índice de imagens (Q13)")
                return m.group(0)
            state = effective_state(doc, e)
            md = None
            if state in STATES_DONE:
                md = interpretation_path(doc, e).read_text(encoding="utf-8")
            return _block(e, state, md, m.group(0))

        body = MARKER_RE.sub(repl, original)
        meta_end = body.find("\n---\n", 4) + 5 if body.startswith("---\n") else 0
        enriched = body[:meta_end] + BANNER + body[meta_end:]
        if strip_blocks(enriched) != original:
            shutil.rmtree(out_tmp)
            raise SipError("IDA_E_VOLTA_FALHOU", f"Verificação de ida e volta falhou no trecho {src.stem}; nada foi escrito (Q10).")
        (out_tmp / src.name).write_text(enriched, encoding="utf-8", newline="\n")
    after = {p.name: _sha(p) for p in sorted(chunks_dir.glob("*.md"))}
    if before != after:
        shutil.rmtree(out_tmp)
        raise SipError("ORIGINAIS_ALTERADOS", "Os trechos originais mudaram durante a integração; nada foi escrito (Q11).")
    for e in entries:
        if e["id"] not in seen_ids and e["estado"] not in ("pequena",) and e.get("chunk") is not None:
            problems.append(f"imagem {e['id']} está no índice mas não tem marcador nos trechos (Q13)")
    target = doc / "chunks_com_imagens"
    if target.exists():  # the previous generated copy is renamed to a temporary name and removed; the sources (imagens/*.md, memory) are kept
        old_tmp = doc / f"chunks_com_imagens.tmp-old-{os.getpid()}"
        os.replace(target, old_tmp)
        shutil.rmtree(old_tmp)
    os.replace(out_tmp, target)
    cov = coverage(doc, entries)
    cov["problemas_indice"] = problems
    (doc / "cobertura.md").write_text(render_coverage(cov), encoding="utf-8", newline="\n")
    (doc / "cobertura.json").write_text(json.dumps(cov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (doc / "index_com_imagens.md").write_text(render_enriched_index(doc, cov), encoding="utf-8", newline="\n")
    return cov


def coverage(doc: Path, entries: list) -> dict:
    counts: dict = {}
    pages: dict = {}
    for e in entries:
        s = effective_state(doc, e)
        counts[s] = counts.get(s, 0) + 1
        d = pages.setdefault(str(e["pagina"]), {})
        d[s] = d.get(s, 0) + 1
    quality = json.loads((doc / "qualidade.json").read_text(encoding="utf-8"))
    vector_pages = [p["pagina"] for p in quality["paginas"] if any("gráfico vetorial" in a for a in p.get("avisos", []))]
    reasons = []
    if counts.get("pendente"):
        reasons.append(f"{counts['pendente']} imagem(ns) ainda não interpretada(s)")
    if counts.get("não extraível"):
        reasons.append(f"{counts['não extraível']} imagem(ns) não extraível(is)")
    if counts.get("grande demais"):
        reasons.append(f"{counts['grande demais']} imagem(ns) grande(s) demais")
    if vector_pages:
        reasons.append(f"{len(vector_pages)} página(s) com possível gráfico vetorial: {', '.join(map(str, vector_pages))}")
    if quality["situacao"] == "Reprovado":
        reasons.append("o documento está Reprovado na qualidade do CFP")
    return {"contagem": counts, "paginas": pages, "paginas_vetoriais": vector_pages, "completo": not reasons, "motivos": reasons,
            "situacao_cfp": quality["situacao"], "total": len(entries)}


def render_coverage(cov: dict) -> str:
    l = ["# Cobertura das imagens", "", f"**Conteúdo completo: {'sim' if cov['completo'] else 'não'}**", ""]
    if cov["motivos"]:
        l += ["Falta:"] + [f"- {m}" for m in cov["motivos"]] + [""]
    l += ["| Situação da imagem | Quantidade |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(cov["contagem"].items())]
    l += ["", f"Total de imagens no índice: {cov['total']}. Situação de qualidade do CFP: {cov['situacao_cfp']}.", ""]
    if cov["paginas_vetoriais"]:
        l += ["Páginas com possível gráfico vetorial (conferir no PDF): " + ", ".join(map(str, cov["paginas_vetoriais"])), ""]
    l += ["As interpretações são feitas por IA: confira no PDF antes de decidir com base nelas.", ""]
    return "\n".join(l)


def render_enriched_index(doc: Path, cov: dict) -> str:
    base = (doc / "index.md").read_text(encoding="utf-8") if (doc / "index.md").exists() else ""
    head = ["# Índice com imagens", "", f"Conteúdo completo: **{'sim' if cov['completo'] else 'não'}**. Os trechos com interpretações de imagens ficam em `chunks_com_imagens/`;",
            "os trechos originais (`chunks/`) não foram alterados.", "", "---", ""]
    return "\n".join(head) + base
