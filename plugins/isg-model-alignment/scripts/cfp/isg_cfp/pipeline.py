"""Orchestration: validate -> extract -> organise -> chunk -> verify -> write (atomically) -> catalog."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import CFP_VERSION
from .chunk import DEFAULT_MAX_CHARS, DEFAULT_MIN_CHARS, make_chunks
from .extract import extract_page, open_reader, pdf_metadata
from .images import extract_document_images, write_index
from .organize import _recurring_images, organize_document
from .quality import evaluate, spot_check_pages, verify_written
from .render import render_chunk, render_index, render_quality

UF_CODES = ("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO").split()
BIG_BYTES = 200 * 1024 * 1024
BIG_PAGES = 1000
MAX_PATH = 200


class CfpError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def slugify(text: str, limit: int = 40) -> str:
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return (t[:limit].strip("-")) or "documento"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_inputs(pdf: Path, uf: str, ano) -> tuple:
    if not pdf.is_file():
        raise CfpError("ENTRADA_INVALIDA", f"Não encontrei o arquivo: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        raise CfpError("ENTRADA_INVALIDA", "Só é possível processar arquivos PDF (.pdf).")
    uf = (uf or "").strip().upper()
    if uf not in UF_CODES:
        raise CfpError("ENTRADA_INVALIDA", f"UF inválida: '{uf}'. Use a sigla de um estado (por exemplo SP, MG, BA).")
    try:
        year = int(str(ano).strip())
    except (TypeError, ValueError):
        raise CfpError("ENTRADA_INVALIDA", f"Ano inválido: '{ano}'. Informe 4 dígitos (por exemplo 2025).")
    if not (2000 <= year <= datetime.now().year + 1):
        raise CfpError("ENTRADA_INVALIDA", f"Ano fora do intervalo permitido (2000 a {datetime.now().year + 1}): {year}.")
    with open(pdf, "rb") as f:
        if f.read(5) != b"%PDF-":
            raise CfpError("PDF_INVALIDO", "O arquivo não parece ser um PDF válido (não começa com %PDF-).")
    return uf, year


def replace_with_retry(src: Path, dst: Path, attempts: int = 6) -> None:
    """os.replace that waits a moment when Windows refuses it because another program (antivirus,
    indexer, OneDrive) is briefly holding files that were just written. Other systems succeed at once."""
    import time
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.25 * (attempt + 1))


def _atomic_write_json(path: Path, data) -> None:
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    replace_with_retry(tmp, path)


def load_catalog(cfp_root: Path) -> list:
    p = cfp_root / "catalogo.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("documentos", [])
        except Exception:
            raise CfpError("CATALOGO_INVALIDO", "O arquivo catalogo.json está ilegível; nada foi alterado.")
    return []


def render_catalog_md(docs: list) -> str:
    l = ["# Catálogo de documentos processados", "", "| UF | Ano | Título | Páginas | Chunks | Situação | Pasta | Substituído por |", "|---|---|---|---|---|---|---|---|"]
    for d in sorted(docs, key=lambda d: (d["uf"], d["ano"], d["titulo"].lower(), d["pasta"])):
        l.append(f"| {d['uf']} | {d['ano']} | {d['titulo'].replace('|', '/')} | {d['paginas']} | {d['chunks']} | {d['status']} | `{d['pasta']}` | {d.get('substituido_por') or '—'} |")
    return "\n".join(l) + "\n"


def write_catalog(cfp_root: Path, docs: list) -> None:
    _atomic_write_json(cfp_root / "catalogo.json", {"documentos": docs})
    tmp = cfp_root / f"catalogo.md.tmp-{os.getpid()}"
    tmp.write_text(render_catalog_md(docs), encoding="utf-8", newline="\n")
    replace_with_retry(tmp, cfp_root / "catalogo.md")


def _render_all(results, info, chunks_cap, minimum, meta, ligatures):
    chunks = make_chunks(results, chunks_cap, minimum)
    pages = {pr.number: pr for pr in results}
    doc_key = meta["pasta_nome"]
    texts = [render_chunk(c, doc_key, meta["uf"], meta["ano"], pages, len(chunks)) for c in chunks]
    return chunks, pages, texts


def _output_hash(texts: list, index_md: str, qual_md: str) -> str:
    h = hashlib.sha256()
    for t in texts:
        h.update(t.encode("utf-8"))
    h.update(index_md.encode("utf-8"))
    h.update(qual_md.encode("utf-8"))
    return h.hexdigest()


def process_pdf(pdf, uf, ano, appdata: Path, titulo=None, force=False, max_chars=DEFAULT_MAX_CHARS, min_chars=DEFAULT_MIN_CHARS,
                confirm_large=False, progress=None, extract_images=True, include_small=False) -> dict:
    pdf = Path(pdf)
    uf, year = validate_inputs(pdf, uf, ano)
    size = pdf.stat().st_size
    sha = sha256_file(pdf)
    cfp_root = appdata / "cfp"
    cfp_root.mkdir(parents=True, exist_ok=True)

    catalog = load_catalog(cfp_root)
    if not force:
        for d in catalog:
            if d["sha256"] == sha and d.get("versao_cfp") == CFP_VERSION and not d.get("substituido_por"):
                return {"codigo": "JA_PROCESSADO", "pasta": d["pasta"], "caminho": str(cfp_root / d["pasta"]), "status": d["status"],
                        "paginas": d["paginas"], "chunks": d["chunks"]}

    reader, err = open_reader(pdf)
    if err == "PDF_PROTEGIDO":
        raise CfpError("PDF_PROTEGIDO", "O PDF é protegido por senha ou criptografado; não foi possível ler. Peça uma versão sem proteção.")
    if err:
        raise CfpError("PDF_INVALIDO", "Não consegui abrir o PDF (arquivo danificado ou sem páginas).")
    n_pages = len(reader.pages)
    if (size > BIG_BYTES or n_pages > BIG_PAGES) and not confirm_large:
        raise CfpError("CONFIRMACAO_NECESSARIA", f"Arquivo grande ({size // (1024 * 1024)} MB, {n_pages} páginas). Confirme com o analista e rode de novo com --confirmar-grande.")

    meta_pdf = pdf_metadata(reader)
    title = (titulo or "").strip() or meta_pdf.get("titulo") or pdf.stem
    slug = slugify(title)
    pasta_nome = f"{slug}-{sha[:8]}"
    rel = f"{uf}/{year}/{pasta_nome}"
    target = cfp_root / uf / str(year) / pasta_nome
    if len(str(target / "chunks" / "000.md")) > MAX_PATH:
        raise CfpError("CAMINHO_LONGO", "O caminho da pasta de dados é longo demais (limite de 200 caracteres no Windows). Escolha uma pasta de dados mais curta.")

    raw_pages = []
    for i in range(n_pages):
        raw_pages.append(extract_page(reader, i))
        if progress and (i + 1) % 25 == 0:
            progress(i + 1, n_pages)
    if progress:
        progress(n_pages, n_pages)

    ligatures = Counter()
    for rp in raw_pages:
        ligatures.update(rp.ligatures)

    meta = {"titulo": title, "uf": uf, "ano": year, "arquivo_original": pdf.name, "sha256": sha, "paginas": n_pages,
            "versao_cfp": CFP_VERSION, "versao_pypdf": _pypdf_version(), "versao_python": platform.python_version(), "pasta_nome": pasta_nome}

    results, info = organize_document(raw_pages)
    chunks, pages, texts = _render_all(results, info, max_chars, min_chars, meta, ligatures)

    # Q8: determinism (second pass over the same extracted pages)
    results2, info2 = organize_document(raw_pages)
    chunks2, pages2, texts2 = _render_all(results2, info2, max_chars, min_chars, meta, ligatures)
    determinism_ok = texts == texts2

    written_problems, conservation = verify_written(results, texts)
    quality = evaluate(results, written_problems, determinism_ok)
    spot = spot_check_pages(results)
    index_md = render_index(meta, chunks, pages, quality)
    qual_md = render_quality(meta, results, quality, info, spot, ligatures)
    out_hash = _output_hash(texts, index_md, qual_md)

    index_json = {
        "documento": pasta_nome, **{k: meta[k] for k in ("titulo", "uf", "ano", "arquivo_original", "sha256", "paginas")},
        "situacao": quality["status"], "metadados_pdf": meta_pdf,
        "versoes": {"cfp": CFP_VERSION, "pypdf": meta["versao_pypdf"], "python": meta["versao_python"]},
        "opcoes": {"max_caracteres": max_chars, "min_caracteres": min_chars},
        "chunks": [{"chunk": c.number, "arquivo": f"chunks/{c.number:03d}.md", "paginas": c.page_range, "secao": " > ".join(c.path) if c.path else "Início do documento",
                    "caracteres": c.text_size, "avisos": sorted({f"{f}" for p in c.pages for f in pages[p].flags} | c.flags)} for c in chunks],
        "paginas_com_avisos": {str(pr.number): pr.flags for pr in results if pr.flags},
    }
    quality_json = {"situacao": quality["status"], "verificacoes": quality["verificacoes"], "conservacao": conservation,
                    "paginas": [{"pagina": pr.number, "caracteres": pr.chars, "linhas": pr.lines, "imagens": pr.images - pr.images_small, "imagens_pequenas": pr.images_small, "imagens_decorativas": pr.images_decorative, "avisos": pr.flags,
                                 "cabecalho": pr.header, "rodape": pr.footer, "numero_impresso": pr.printed_number,
                                 "larguras_estimadas": pr.widths_estimated} for pr in results],
                    "imagens_decorativas_repetidas": info.get("decorative_images", {}), "cabecalhos_repetidos": info["header_patterns"], "rodapes_repetidos": info["footer_patterns"],
                    "hifenizacoes_unidas": [j for pr in results for j in pr.hyphen_joins],
                    "ligaduras_expandidas": dict(ligatures), "conferencia_por_amostra": spot}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log = {"processado_em": now, "saida_sha256": out_hash, "opcoes": index_json["opcoes"], "versoes": index_json["versoes"],
           "tamanho_bytes": size, "paginas": n_pages, "chunks": len(chunks)}

    # ---- write atomically: tmp folder, then rename (REQ-COU-10)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f"{pasta_nome}.tmp-{os.getpid()}"
    if tmp.exists():
        shutil.rmtree(tmp)  # only CFP's own temporary folder (REQ-COU-09 exception)
    (tmp / "chunks").mkdir(parents=True)
    for c, t in zip(chunks, texts):
        (tmp / "chunks" / f"{c.number:03d}.md").write_text(t, encoding="utf-8", newline="\n")
    (tmp / "index.md").write_text(index_md, encoding="utf-8", newline="\n")
    (tmp / "qualidade.md").write_text(qual_md, encoding="utf-8", newline="\n")
    _atomic_write_json(tmp / "index.json", index_json)
    _atomic_write_json(tmp / "qualidade.json", quality_json)
    _atomic_write_json(tmp / "log.json", log)
    shutil.copyfile(pdf, tmp / "original.pdf")
    image_entries = []
    if extract_images:  # SPEC-004: deterministic, no AI; the original chunks above are never touched by this step
        chunk_of_page = {}
        for c in chunks:
            for p in c.pages:
                chunk_of_page.setdefault(p, c.number)
        image_entries = extract_document_images(raw_pages, _recurring_images(raw_pages), tmp / "imagens", chunk_of_page, include_small)
        write_index(tmp / "imagens", image_entries)

    if target.exists():  # --force: keep the previous folder, never delete (REQ-COU-06)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        replace_with_retry(target, target.parent / f"{pasta_nome}-substituido-{stamp}")
        for d in catalog:
            if d["pasta"] == rel:
                d["pasta"] = f"{uf}/{year}/{pasta_nome}-substituido-{stamp}"
                d["substituido_por"] = rel
    replace_with_retry(tmp, target)

    # ---- catalog: new entry; older versions of the same title are marked superseded (REQ-COU-07)
    for d in catalog:
        if d["uf"] == uf and d["ano"] == year and d.get("slug") == slug and d["sha256"] != sha and not d.get("substituido_por"):
            d["substituido_por"] = rel
    catalog.append({"uf": uf, "ano": year, "titulo": title, "slug": slug, "pasta": rel, "sha256": sha, "paginas": n_pages, "chunks": len(chunks),
                    "status": quality["status"], "processado_em": now, "versao_cfp": CFP_VERSION, "saida_sha256": out_hash, "substituido_por": None})
    write_catalog(cfp_root, catalog)

    return {"codigo": "PROCESSADO", "pasta": rel, "caminho": str(target), "status": quality["status"], "paginas": n_pages, "chunks": len(chunks),
            "avisos": len([pr for pr in results if pr.flags]), "conservacao": conservation, "saida_sha256": out_hash,
            "imagens": _image_counts(image_entries)}


def _pypdf_version() -> str:
    try:
        import pypdf

        return pypdf.__version__
    except Exception:
        return "?"


def _image_counts(entries: list) -> dict:
    out: dict = {}
    for e in entries:
        out[e["estado"]] = out.get(e["estado"], 0) + 1
    out["total"] = len(entries)
    return out
