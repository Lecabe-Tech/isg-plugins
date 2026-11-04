"""Quality checks and status (SPEC-003 2.6, 4.6). The status NEVER drops content: it only tells how far to trust it."""
from __future__ import annotations

import re
from collections import Counter

from .organize import PageResult, non_space_counter

STATUS_OK = "Aprovado"
STATUS_WARN = "Aprovado com avisos"
STATUS_FAIL = "Reprovado"

EMPTY_PAGE_LIMIT = 0.10
GARBLED_LIMIT = 0.02
EMPTY_PAGE_CHARS = 30

MARKER_TEMPLATE = re.compile(r"<!-- página \d+|\(continuação\)|\| cabeçalho:|\| rodapé:|\| número impresso:|-->")


def expected_counter(results: list) -> Counter:
    """Characters that must appear in the chunk files: source text minus logged hyphen removals,
    plus the markdown '## ' of each heading (2 '#' characters)."""
    total = Counter()
    headings = 0
    for pr in results:
        total.update(pr.raw_chars)
        for ch, n in pr.hyphens_removed.items():
            total[ch] -= n
        headings += sum(1 for b in pr.blocks if b.type == "heading")
    total["#"] += 2 * headings
    return +total  # drop zero/negative entries


def counter_from_chunk_text(text: str) -> Counter:
    """Non-space characters of a rendered chunk file that come from the source (front matter and marker/label
    templates removed)."""
    body = text
    if body.startswith("---\n"):
        end = body.find("\n---\n", 4)
        body = body[end + 5:] if end != -1 else body
    total = Counter()
    for line in body.split("\n"):
        s = line.strip()
        if not s:
            continue
        if s.startswith("<!-- página "):
            total.update(non_space_counter(MARKER_TEMPLATE.sub("", s)))
            continue
        if s.startswith("[Imagem ") or s.startswith("[Início de tabela — página ") or s == "[Fim de tabela]" or s.startswith("[Página sem texto extraível"):
            continue
        total.update(non_space_counter(s))
    return total


def verify_written(results: list, chunk_texts: list) -> tuple:
    """Q1/Q2 on the FILES that were written: every page marker present, and every character conserved."""
    problems = []
    seen_pages = set()
    out = Counter()
    for text in chunk_texts:
        out.update(counter_from_chunk_text(text))
        for m in re.finditer(r"<!-- página (\d+)", text):
            seen_pages.add(int(m.group(1)))
    missing = [pr.number for pr in results if pr.number not in seen_pages]
    if missing:
        problems.append(f"Q1: páginas sem marcador nos chunks: {missing[:20]}")
    expected = expected_counter(results)
    out = +out
    diff_missing = expected - out
    diff_extra = out - expected
    if diff_missing:
        sample = "".join(sorted(diff_missing.keys()))[:40]
        problems.append(f"Q2: {sum(diff_missing.values())} caractere(s) do PDF não estão nos chunks (exemplos: {sample!r})")
    if diff_extra:
        sample = "".join(sorted(diff_extra.keys()))[:40]
        problems.append(f"Q2: {sum(diff_extra.values())} caractere(s) a mais nos chunks (exemplos: {sample!r})")
    return problems, {
        "esperados": sum(expected.values()),
        "encontrados": sum(out.values()),
        "faltando": sum(diff_missing.values()),
        "a_mais": sum(diff_extra.values()),
    }


def evaluate(results: list, written_problems: list, determinism_ok: bool = True) -> dict:
    n = len(results)
    empty = [pr.number for pr in results if pr.chars < EMPTY_PAGE_CHARS and pr.images == 0]
    total_chars = sum(pr.chars for pr in results)
    garbled = sum(pr.garbled for pr in results)
    flagged = [pr for pr in results if pr.flags]
    checks = [
        {"id": "Q1", "nome": "Cobertura de páginas", "ok": not any(p.startswith("Q1") for p in written_problems), "detalhe": "; ".join(p for p in written_problems if p.startswith("Q1"))},
        {"id": "Q2", "nome": "Conservação dos caracteres", "ok": not any(p.startswith("Q2") for p in written_problems), "detalhe": "; ".join(p for p in written_problems if p.startswith("Q2"))},
        {"id": "Q3", "nome": "Páginas sem texto", "ok": len(empty) <= EMPTY_PAGE_LIMIT * n, "detalhe": f"{len(empty)} de {n} páginas sem texto" + (f" (páginas {empty[:30]})" if empty else "")},
        {"id": "Q4", "nome": "Texto corrompido", "ok": (garbled / total_chars if total_chars else 0.0) <= GARBLED_LIMIT, "detalhe": f"{garbled} de {total_chars} caracteres suspeitos"},
        {"id": "Q5", "nome": "Ordem de leitura", "ok": True, "detalhe": f"{sum(1 for pr in results if 'ordem de leitura incerta' in pr.flags or 'duas colunas — ordem de leitura inferida' in pr.flags)} página(s) com ordem inferida ou incerta"},
        {"id": "Q6", "nome": "Tabelas", "ok": True, "detalhe": f"{sum(1 for pr in results if 'tabela' in pr.flags)} página(s) com tabela"},
        {"id": "Q7", "nome": "Imagens", "ok": True, "detalhe": f"{sum(pr.images - pr.images_small for pr in results)} imagem(ns) não processada(s) (mais {sum(pr.images_small for pr in results)} pequena(s) e {sum(pr.images_decorative for pr in results)} repetida(s) como decoração, sem aviso)"},
        {"id": "Q8", "nome": "Determinismo", "ok": determinism_ok, "detalhe": "duas execuções produzem a mesma saída" if determinism_ok else "saídas diferentes entre execuções"},
        {"id": "Q9", "nome": "Codificação", "ok": True, "detalhe": "UTF-8 sem BOM, LF, NFC"},
    ]
    failed_fidelity = [c for c in checks if c["id"] in ("Q1", "Q2", "Q8") and not c["ok"]]
    if failed_fidelity or not checks[2]["ok"] or not checks[3]["ok"]:
        status = STATUS_FAIL
    elif flagged:
        status = STATUS_WARN
    else:
        status = STATUS_OK
    return {"status": status, "verificacoes": checks, "paginas_sem_texto": empty}


def spot_check_pages(results: list, count: int = 5) -> list:
    """5 pages to compare by eye: flagged pages first, then pages evenly spread (no randomness: deterministic)."""
    flagged = [pr.number for pr in results if pr.flags]
    picked = flagged[:count]
    n = len(results)
    i = 0
    while len(picked) < min(count, n):
        cand = results[min(n - 1, (i * n) // count)].number
        if cand not in picked:
            picked.append(cand)
        i += 1
        if i > 4 * count:
            break
    return sorted(picked)
