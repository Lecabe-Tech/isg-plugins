"""SPEC-017 run folder: manifest -> resolved sources -> located units -> inventory (G0/G1), shared by the later gates.

Run folder layout (everything the run needs, nothing outside it):
  manifesto.json, inventario.json, referencias.json, originais/DOC-n.*, fontes/DOC-n.json,
  matriz.json, orientacoes.json, afirmacoes.json, consistencia.json, resultado_qualidade.v1.json, resumo.md
"""
from __future__ import annotations

import datetime as _dt
import json
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


def start_run(manifest_path: Path, run_dir: Path, opener=None, references=None) -> dict:
    """G0 + G1. `references(run_dir, manifest, inventory)` is called at the end when given (template/ICE analysis)."""
    try:
        raw = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise SR.ManifestError("MANIFESTO_INVALIDO", "O manifesto não é um JSON válido.")
    manifest = SR.validate_manifest(raw)
    run_dir.mkdir(parents=True, exist_ok=True)
    if (run_dir / "inventario.json").exists():
        old = SR.read_json(run_dir / "manifesto.json", {})
        if old and (old.get("solicitacao_id"), old.get("uf"), old.get("ano")) != (manifest["solicitacao_id"], manifest["uf"], manifest["ano"]):
            raise RunError("PASTA_EM_USO", "A pasta já contém outra execução (outra solicitação, UF ou ano). Use uma pasta nova.")
    SR.write_json(run_dir / "manifesto.json", manifest)
    docs = SR.resolve_sources(manifest, Path(manifest_path).resolve().parent, run_dir, opener)
    inventory = []
    for d in docs:
        result = DN.normalize(d)
        units = result["unidades"]
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
    """Attaches an AI image reading (SIP) to an image unit. It stays flagged as AI-made and is never 'verified'."""
    doc_id = unit_id.split(":", 1)[0]
    path = run_dir / "fontes" / f"{doc_id}.json"
    data = SR.read_json(path)
    if data is None:
        raise RunError("UNIDADE_INEXISTENTE", f"Unidade desconhecida: {unit_id}")
    for u in data["unidades"]:
        if u["id"] == unit_id:
            if u["status"] not in ("requer_interpretacao", "interpretada_ia"):
                raise RunError("UNIDADE_NAO_E_IMAGEM", f"A unidade {unit_id} tem texto próprio; a leitura de imagem só vale para trechos em imagem.")
            if not text.strip():
                raise RunError("ENTRADA_INVALIDA", "A leitura da imagem está vazia.")
            u["interpretacao_ia"] = text.strip()
            u["status"] = "interpretada_ia"
            u["avisos"] = [a for a in u["avisos"] if "precisa de leitura" not in a] + [f"Conteúdo lido por IA ({author}); precisa de conferência humana."]
            data["documento"]["cobertura"] = DN.coverage(data["unidades"])
            if not any(x["status"] == "requer_interpretacao" for x in data["unidades"]):
                data["documento"]["pendencias"] = [p for p in data["documento"]["pendencias"] if p["codigo"] != "IMAGEM_PENDENTE"]
            data["documento"]["status_leitura"] = _status(data["unidades"], data["documento"]["pendencias"])
            SR.write_json(path, data)
            inv = load_inventory(run_dir)
            inv["fontes"] = [data["documento"] if f["id"] == doc_id else f for f in inv["fontes"]]
            SR.write_json(run_dir / "inventario.json", inv)
            return {"unidade": unit_id, "status": u["status"]}
    raise RunError("UNIDADE_INEXISTENTE", f"Unidade desconhecida: {unit_id}")
