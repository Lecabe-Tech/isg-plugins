"""SPEC-017 G0/G1: four-class input manifest and source resolution (local files, file:// and public https URLs).

Never bypasses access control: https requests carry no credentials and a redirect to a sign-in page counts as
ACESSO_NEGADO. The real type comes from the bytes, not from the extension. Original bytes are copied to the run folder
so the same run can be reproduced and every quote checked again.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import unicodedata
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import schema_check
from quality_templates import is_uf

CLASSES = ("orientacoes_estaduais", "matriz_estadual", "template_cluster", "referencial_ice")
CLASS_LABEL = {
    "orientacoes_estaduais": "orientações estaduais",
    "matriz_estadual": "matriz estadual",
    "template_cluster": "template do cluster",
    "referencial_ice": "referencial ICE",
}
MAX_BYTES = 200 * 1024 * 1024
SUPPORTED = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "text/html": ".html",
}
EXT_TYPES = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsm": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".txt": "text/plain", ".md": "text/plain",
             ".csv": "text/csv", ".htm": "text/html", ".html": "text/html"}
LOGIN_HOSTS = re.compile(r"(^|\.)(login\.microsoftonline\.com|login\.live\.com|accounts\.google\.com)$", re.I)


class ManifestError(Exception):
    def __init__(self, code: str, message: str, errors: list | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.errors = errors or []


def _fold(text) -> str:
    t = unicodedata.normalize("NFKD", str(text or ""))
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in t if not unicodedata.combining(c)).lower())


def normalize_scope(manifest: dict) -> dict:
    """Accepts '9h'/'9 h'/'9 horas' and 'propedeutico'/'propedêutico'; anything else is out of scope."""
    m = dict(manifest)
    modelo = _fold(m.get("modelo"))
    modalidade = _fold(m.get("modalidade"))
    if modelo in ("9h", "9horas"):
        m["modelo"] = "9h"
    if modalidade == "propedeutico":
        m["modalidade"] = "propedeutico"
    return m


def validate_manifest(manifest) -> dict:
    """Returns the normalized manifest or raises ManifestError (MODELO_FORA_ESCOPO, UF_INVALIDA, MANIFESTO_INVALIDO)."""
    if not isinstance(manifest, dict):
        raise ManifestError("MANIFESTO_INVALIDO", "O manifesto precisa ser um objeto JSON.")
    m = normalize_scope(manifest)
    if m.get("modelo") != "9h" or m.get("modalidade") != "propedeutico":
        raise ManifestError("MODELO_FORA_ESCOPO", "Esta entrega analisa só o Ensino Médio Integral propedêutico de 9h "
                            f"(recebido: modelo {manifest.get('modelo')!r}, modalidade {manifest.get('modalidade')!r}). Outros modelos ficam para depois.")
    errors = schema_check.validate("manifesto", m)
    if errors:
        missing = [c for c in CLASSES if not (m.get("entradas") or {}).get(c)]
        if missing:
            raise ManifestError("CLASSE_AUSENTE", "Faltam classes de entrada obrigatórias: " + ", ".join(CLASS_LABEL[c] for c in missing) + ".", errors)
        raise ManifestError("MANIFESTO_INVALIDO", "O manifesto não segue o contrato v1: " + "; ".join(errors[:6]), errors)
    if not is_uf(m["uf"]):
        raise ManifestError("UF_INVALIDA", f"UF inválida: {m['uf']}. Use a sigla oficial de um estado ou do DF.")
    for cls in CLASSES:
        for e in m["entradas"][cls]:
            scheme = urlparse(e["uri"]).scheme.lower()
            if scheme not in ("", "file", "https") and not re.fullmatch(r"[a-z]", scheme):
                raise ManifestError("URI_NAO_PERMITIDA", f"Endereço não permitido em {CLASS_LABEL[cls]}: {e['uri']}. Use um arquivo local, um endereço file ou um endereço https público.")
    return m


def sniff(head: bytes, name: str = "", zip_names: list | None = None) -> str | None:
    """Media type from the bytes. Returns None for formats this delivery cannot read."""
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"PK\x03\x04"):
        names = zip_names or []
        if "word/document.xml" in names:
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if "xl/workbook.xml" in names:
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return None
    if head.startswith(b"\xd0\xcf\x11\xe0") or head[:4] in (b"GIF8", b"II*\x00", b"MM\x00*") or head[:4] == b"RIFF":
        return None  # legacy DOC/XLS (OLE), GIF, TIFF, WEBP: need a controlled conversion
    if b"\x00" in head[:4096]:
        return None
    text = head[:4096].decode("utf-8", errors="ignore").lstrip("﻿").lstrip().lower()
    if text.startswith("<!doctype html") or text.startswith("<html"):
        return "text/html"
    return "text/csv" if Path(name).suffix.lower() == ".csv" else "text/plain"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _local_path(uri: str, base: Path) -> Path:
    p = urlparse(uri)
    if p.scheme == "file":
        raw = unquote(p.path)
        if re.match(r"^/[A-Za-z]:", raw):
            raw = raw[1:]
        if p.netloc:
            raw = "//" + p.netloc + raw
        return Path(raw)
    path = Path(uri)
    return path if path.is_absolute() else (base / path)


def _download(uri: str, dest: Path, opener=None) -> dict:
    """Public https only, no credentials. {'ok', 'codigo', 'detalhe', 'nome'}."""
    req = urllib.request.Request(uri, headers={"User-Agent": "isg-model-alignment-quality/1"})
    open_ = opener or urllib.request.urlopen
    try:
        with open_(req, timeout=60) as resp:
            final = urlparse(resp.geturl() if hasattr(resp, "geturl") else uri)
            if LOGIN_HOSTS.search(final.hostname or "") or "/_forms/" in final.path.lower() or "authenticate" in final.path.lower():
                return {"ok": False, "codigo": "ACESSO_NEGADO", "detalhe": "O endereço pede login. Use uma cópia legítima do arquivo ou um acesso autorizado."}
            total = 0
            with open(dest, "wb") as out:
                while True:
                    block = resp.read(1 << 20)
                    if not block:
                        break
                    total += len(block)
                    if total > MAX_BYTES:
                        out.close()
                        dest.unlink(missing_ok=True)
                        return {"ok": False, "codigo": "LEITURA_FALHOU", "detalhe": "Arquivo maior que 200 MB."}
                    out.write(block)
            name = Path(unquote(final.path)).name or "download"
            return {"ok": True, "nome": name}
    except urllib.error.HTTPError as e:
        code = "ACESSO_NEGADO" if e.code in (401, 403) else "FONTE_AUSENTE"
        return {"ok": False, "codigo": code, "detalhe": f"O servidor respondeu {e.code}."}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"ok": False, "codigo": "FONTE_AUSENTE", "detalhe": "Não foi possível acessar o endereço (%s)." % re.sub(r"\s+", " ", str(getattr(e, "reason", e)))[:120]}


def resolve_sources(manifest: dict, base_dir: Path, run_dir: Path, opener=None) -> list:
    """One record per physical document (same bytes declared twice = one document with several classes).

    Record: id, classes, entradas (the manifest entries), nome, uri, caminho (copy in the run folder or None),
    sha256, tamanho_bytes, media_type, pendencias [{codigo, detalhe}]."""
    originals = run_dir / "originais"
    originals.mkdir(parents=True, exist_ok=True)
    docs: list = []
    by_hash: dict = {}
    seq = 0
    for cls in CLASSES:
        for entry in manifest["entradas"][cls]:
            uri = entry["uri"]
            pend: list = []
            tmp = originals / f".download-{seq + 1}"
            path, name = None, None
            if urlparse(uri).scheme == "https":
                r = _download(uri, tmp, opener)
                if r["ok"]:
                    path, name = tmp, r["nome"]
                else:
                    pend.append({"codigo": r["codigo"], "detalhe": r["detalhe"]})
            else:
                src = _local_path(uri, base_dir)
                name = src.name
                if not src.is_file():
                    pend.append({"codigo": "FONTE_AUSENTE", "detalhe": f"Arquivo não encontrado: {src}"})
                elif src.stat().st_size > MAX_BYTES:
                    pend.append({"codigo": "LEITURA_FALHOU", "detalhe": "Arquivo maior que 200 MB."})
                else:
                    try:
                        with open(src, "rb"):
                            pass
                        path = src
                    except OSError as e:
                        pend.append({"codigo": "ACESSO_NEGADO", "detalhe": f"Sem permissão para ler o arquivo ({e.strerror})."})
            digest = sha256_file(path) if path else None
            if digest and digest in by_hash:
                doc = by_hash[digest]
                if cls in doc["classes"]:
                    doc["pendencias"].append({"codigo": "FONTE_DUPLICADA", "detalhe": f"O mesmo arquivo foi informado duas vezes em {CLASS_LABEL[cls]} ({uri})."})
                else:
                    doc["classes"].append(cls)
                doc["entradas"].append({"classe": cls, **entry})
                if path == tmp:
                    tmp.unlink(missing_ok=True)
                continue
            seq += 1
            doc = {"id": f"DOC-{seq}", "classes": [cls], "entradas": [{"classe": cls, **entry}], "nome": name or uri, "uri": uri,
                   "caminho": None, "sha256": digest, "tamanho_bytes": None, "media_type": None, "pendencias": pend}
            if path:
                with open(path, "rb") as f:
                    head = f.read(8192)
                zip_names = None
                if head.startswith(b"PK\x03\x04"):
                    try:
                        with zipfile.ZipFile(path) as z:
                            zip_names = z.namelist()
                    except zipfile.BadZipFile:
                        zip_names = []
                media = sniff(head, name or "", zip_names)
                declared = EXT_TYPES.get(Path(name or "").suffix.lower())
                if media is None:
                    doc["pendencias"].append({"codigo": "FORMATO_NAO_SUPORTADO", "detalhe": f"Formato não suportado nesta entrega ({Path(name or '').suffix or 'sem extensão'}). Converta para PDF, DOCX, XLSX, PNG/JPEG, TXT/CSV ou HTML."})
                elif declared and declared != media and not (declared == "text/plain" and media in ("text/csv", "text/html")):
                    doc["pendencias"].append({"codigo": "TIPO_DIVERGENTE", "detalhe": f"A extensão indica {declared}, mas o conteúdo é {media}; foi usado o tipo do conteúdo."})
                doc["media_type"] = media
                doc["tamanho_bytes"] = path.stat().st_size
                copy = originals / f"{doc['id']}{SUPPORTED.get(media, Path(name or '').suffix.lower() or '.bin')}"
                if path == tmp:
                    tmp.replace(copy)
                else:
                    shutil.copyfile(path, copy)
                doc["caminho"] = str(copy)
                by_hash[digest] = doc
            docs.append(doc)
    return docs


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(path)


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
