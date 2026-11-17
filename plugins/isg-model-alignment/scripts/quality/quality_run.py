"""SPEC-017 run folder: manifest -> resolved sources -> located units -> inventory (G0/G1), shared by the later gates.

Run folder layout (everything the run needs, nothing outside it):
  manifesto.json, inventario.json, referencias.json, originais/DOC-n.*, fontes/DOC-n.json,
  matriz.json, orientacoes.json, afirmacoes.json, consistencia.json, resultado_qualidade.v1.json, resumo.md
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from pathlib import Path

import document_normalizer as DN
import source_resolver as SR


class RunError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _status(units: list, pend: list) -> str:
    if not units:
        return "nao_lida"
    blocking = {"ACESSO_NEGADO", "FONTE_AUSENTE", "FORMATO_NAO_SUPORTADO", "LEITURA_FALHOU", "IMAGEM_PENDENTE", "FORMULA_SEM_VALOR_EM_CACHE", "CONTEUDO_NAO_LIDO"}
    if any(p["codigo"] in blocking for p in pend) or any(u["status"] in DN.PENDING for u in units):
        return "lida_com_pendencias"
    return "lida"


def export_images(run_dir: Path, units: list) -> None:
    """Writes the pictures of every pending image unit to imagens/ and links them to the unit (`arquivos_imagem`), so the
    SIP reading is done on the exact picture and the link is recorded; a picture that cannot be exported keeps its reason."""
    for u in units:
        items = u.pop("_imagens", None)
        if items is None:
            continue
        files, reasons = [], []
        for k, it in enumerate(items, start=1):
            if "data" in it:
                name = re.sub(r"[^A-Za-z0-9._-]", "_", u["id"].replace(":", "_")) + (f"-{k}" if len(items) > 1 else "") + "." + it["ext"]
                (run_dir / "imagens").mkdir(parents=True, exist_ok=True)
                (run_dir / "imagens" / name).write_bytes(it["data"])
                files.append("imagens/" + name)
            else:
                reasons.append(it["motivo"])
        u["arquivos_imagem"] = files
        if reasons:
            u["avisos"] = u["avisos"] + ["Imagem não exportada: " + r for r in reasons]


def image_key(run_dir: Path, unit: dict) -> str | None:
    """SHA-256 of the exported picture(s) of an image unit; the same key = the same picture (lesson of the CE 2026
    pilot: one 112-page PDF had the same figure on five pages, each waiting for its own reading)."""
    files = unit.get("arquivos_imagem") or []
    if not files:
        return None
    h = hashlib.sha256()
    for f in files:
        p = run_dir / f
        if not p.is_file():
            return None
        h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def pending_images(run_dir: Path) -> list:
    """Image units still waiting for a SIP reading, with the exported files. A unit whose picture is identical to an
    earlier pending one says so in `mesma_imagem_que`: read only the first; the reading is copied to the others."""
    out, first = [], {}
    for doc_id, units in load_units(run_dir).items():
        for u in units:
            if u["status"] == "requer_interpretacao":
                key = image_key(run_dir, u)
                same = first.get(key) if key else None
                if key and not same:
                    first[key] = u["id"]
                out.append({"unidade": u["id"], "localizacao": u["localizacao"], "arquivos": [str(run_dir / f) for f in u.get("arquivos_imagem", [])],
                            "avisos": u["avisos"], "mesma_imagem_que": same})
    return out


def template_ufs(path: Path) -> list:
    """UFs of the '2.x Revisão Matriz <UF>' tabs of a cluster template."""
    wb = DN.read_workbook(path)
    out = []
    for s in wb["abas"]:
        name = DN.fold(s["nome"])
        if re.match(r"^\s*2\.\d+\s+revisao\s+(da\s+)?matriz\b", name):
            out.append(name.split()[-1].upper())
    return out


def _check_template_uf(docs: list, uf: str) -> None:
    """Fail fast (lesson of the CE 2026 pilot): a cluster template that does not cover the UF stops the run before the
    long reading, saying which UFs the template covers. A missing or unreadable template stays a pending item."""
    found = {}
    for d in docs:
        if "template_cluster" in d["classes"] and d["caminho"] and (d["media_type"] or "").endswith("spreadsheetml.sheet"):
            try:
                found[d["nome"]] = template_ufs(Path(d["caminho"]))
            except Exception:  # noqa: BLE001  (unreadable workbook: reported later by the normalizer)
                continue
    if any(found.values()) and not any(uf.upper() in ufs for ufs in found.values()):  # a template of OTHER UFs (no matrix tab at all = only a warning later)
        detail = "; ".join(f"{n}: {', '.join(u) or 'nenhuma aba de matriz'}" for n, u in found.items())
        raise RunError("TEMPLATE_SEM_UF", f"O template enviado não tem a aba de matriz de {uf.upper()} ({detail}). Envie o template do cluster que contém {uf.upper()}; "
                       "nada foi analisado.")


def start_run(manifest_path: Path, run_dir: Path, references=None, ice_dir: str | None = None) -> dict:
    """G0 + G1. `references(run_dir, manifest, inventory)` is called at the end when given (template/ICE analysis).
    An empty `referencial_ice` is filled from the configured ICE reference (`ice_dir` or ISG_QUALITY_ICE_REFERENCE)."""
    try:
        raw = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise SR.ManifestError("MANIFESTO_INVALIDO", "O manifesto não é um JSON válido.")
    manifest = SR.validate_manifest(raw)
    import ice_config as ICE

    manifest = ICE.fill_manifest(manifest, ice_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if (run_dir / "inventario.json").exists():
        old = SR.read_json(run_dir / "manifesto.json", {})
        if old and (old.get("solicitacao_id"), old.get("uf"), old.get("ano")) != (manifest["solicitacao_id"], manifest["uf"], manifest["ano"]):
            raise RunError("PASTA_EM_USO", "A pasta já contém outra execução (outra solicitação, UF ou ano). Use uma pasta nova.")
    SR.write_json(run_dir / "manifesto.json", manifest)
    docs = SR.resolve_sources(manifest, Path(manifest_path).resolve().parent, run_dir)
    _check_template_uf(docs, manifest["uf"])
    inventory = []
    for d in docs:
        result = DN.normalize(d)
        units = result["unidades"]
        export_images(run_dir, units)
        pend = d["pendencias"] + result["pendencias"]
        for e in d["entradas"]:
            vig = (e.get("vigencia") or "").strip()
            if vig and str(manifest["ano"]) not in vig:
                pend.append({"codigo": "VERSAO_DIVERGENTE", "detalhe": f"Vigência declarada '{vig}' não corresponde ao ano {manifest['ano']}."})
        record = {"id": d["id"], "classes": d["classes"], "nome": d["nome"], "uri": d["uri"], "sha256": d["sha256"], "media_type": d["media_type"],
                  "tamanho_bytes": d["tamanho_bytes"], "extrator": result["extrator"], "status_leitura": _status(units, pend),
                  "cobertura": DN.coverage(units),
                  "metadados": {k: next((e.get(k) for e in d["entradas"] if e.get(k)), None) for k in ("titulo", "emissor", "versao", "vigencia")} |
                               {"papeis": sorted({e.get("papel") or e["classe"] for e in d["entradas"]})},
                  "pendencias": pend}
        SR.write_json(run_dir / "fontes" / f"{d['id']}.json", {"documento": record, "unidades": units})
        inventory.append(record)
    general = []
    if not manifest.get("homologacao_ice"):
        general.append({"codigo": "REFERENCIAL_NAO_HOMOLOGADO", "detalhe": "O manifesto não traz o registro de homologação do referencial ICE (versão, quem aprovou e data)."})
    inv = {"uf": manifest["uf"], "ano": manifest["ano"], "modelo": manifest["modelo"], "modalidade": manifest["modalidade"],
           "solicitacao_id": manifest["solicitacao_id"], "revisao": manifest.get("revisao", 1), "iniciada_em": now(), "fontes": inventory, "pendencias": general}
    SR.write_json(run_dir / "inventario.json", inv)
    if references is None:
        import template_rules

        references = template_rules.build_references
    if references:
        references(run_dir, manifest, inv)
    return inv


def load_inventory(run_dir: Path) -> dict:
    inv = SR.read_json(run_dir / "inventario.json")
    if inv is None:
        raise RunError("EXECUCAO_INEXISTENTE", f"Não há execução iniciada em {run_dir}. Rode o comando iniciar primeiro.")
    return inv


def load_manifest(run_dir: Path) -> dict:
    return SR.read_json(run_dir / "manifesto.json", {})


def load_units(run_dir: Path, doc_id: str | None = None) -> dict:
    """{doc_id: [units]} for one or all documents of the run."""
    out = {}
    for f in sorted((run_dir / "fontes").glob("DOC-*.json"), key=lambda p: int(p.stem.split("-")[1])):
        if doc_id and f.stem != doc_id:
            continue
        out[f.stem] = SR.read_json(f)["unidades"]
    return out


def unit_index(run_dir: Path) -> dict:
    """{unit id: (doc_id, unit)}."""
    return {u["id"]: (d, u) for d, units in load_units(run_dir).items() for u in units}


def docs_of_class(inv: dict, cls: str) -> list:
    return [f for f in inv["fontes"] if cls in f["classes"]]


def register_image_reading(run_dir: Path, unit_id: str, text: str, author: str = "SIP") -> dict:
    """Attaches an AI image reading (SIP) to an image unit. It stays flagged as AI-made and is never 'verified'.
    Pending units with exactly the same picture (same bytes) receive the same reading, marked as a copy."""
    if not text.strip():
        raise RunError("ENTRADA_INVALIDA", "A leitura da imagem está vazia.")
    files = {f.stem: f for f in (run_dir / "fontes").glob("DOC-*.json")}
    doc_id = unit_id.split(":", 1)[0]
    if doc_id not in files:
        raise RunError("UNIDADE_INEXISTENTE", f"Unidade desconhecida: {unit_id}")
    datas = {d: SR.read_json(p) for d, p in files.items()}
    target = next((u for u in datas[doc_id]["unidades"] if u["id"] == unit_id), None)
    if target is None:
        raise RunError("UNIDADE_INEXISTENTE", f"Unidade desconhecida: {unit_id}")
    if target["status"] not in ("requer_interpretacao", "interpretada_ia"):
        raise RunError("UNIDADE_NAO_E_IMAGEM", f"A unidade {unit_id} tem texto próprio; a leitura de imagem só vale para trechos em imagem.")
    key = image_key(run_dir, target)
    changed, copies = {doc_id}, []

    def mark(u, body, note):
        u["interpretacao_ia"] = body
        u["status"] = "interpretada_ia"
        u["avisos"] = [a for a in u["avisos"] if "precisa de leitura" not in a] + [note]
    mark(target, text.strip(), f"Conteúdo lido por IA ({author}); precisa de conferência humana.")
    if key:
        for d, data in datas.items():
            for u in data["unidades"]:
                if u is not target and u["status"] == "requer_interpretacao" and image_key(run_dir, u) == key:
                    mark(u, f"(Mesma imagem de {unit_id}.)\n" + text.strip(), f"Mesma imagem de {unit_id}: leitura de IA copiada ({author}); precisa de conferência humana.")
                    copies.append(u["id"])
                    changed.add(d)
    inv = load_inventory(run_dir)
    for d in changed:
        data = datas[d]
        data["documento"]["cobertura"] = DN.coverage(data["unidades"])
        if not any(x["status"] == "requer_interpretacao" for x in data["unidades"]):
            data["documento"]["pendencias"] = [p for p in data["documento"]["pendencias"] if p["codigo"] != "IMAGEM_PENDENTE"]
        else:
            n = sum(x["status"] == "requer_interpretacao" for x in data["unidades"])
            data["documento"]["pendencias"] = [({**p, "detalhe": f"{n} trecho(s) em imagem precisam de leitura de imagem (SIP) e revisão."} if p["codigo"] == "IMAGEM_PENDENTE" else p)
                                               for p in data["documento"]["pendencias"]]
        data["documento"]["status_leitura"] = _status(data["unidades"], data["documento"]["pendencias"])
        SR.write_json(files[d], data)
        inv["fontes"] = [data["documento"] if f["id"] == d else f for f in inv["fontes"]]
    SR.write_json(run_dir / "inventario.json", inv)
    return {"unidade": unit_id, "status": target["status"], "copiada_para": copies}
