"""Configured ICE reference (decision of 2026-11-17, after the CE 2026 pilot).

The ICE reference is the same for every state, so it is configured ONCE: the folder of the plugin option
`quality_ice_reference` (or the environment variable ISG_QUALITY_ICE_REFERENCE, which wins), with a
`manifesto_ice.json` that declares the version, the approval and the files. A SharePoint link to that folder is
accepted and read from the OneDrive copy (sharepoint_link.py).

A run whose manifest leaves `referencial_ice` empty uses this configured reference. The program never picks a file on
its own: without a configured and approved reference, the run does not start and says what to do. A reference marked as
a test copy or not approved is refused as default. Standard library only.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import sharepoint_link as SP

ENV = "ISG_QUALITY_ICE_REFERENCE"
MANIFEST = "manifesto_ice.json"
TEST_MARK = re.compile(r"teste|test\b|confirmar|exemplo|rascunho", re.I)


class IceConfigError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _folder(arg: str | None) -> Path:
    raw = (os.environ.get(ENV) or "").strip() or (arg or "").strip()
    if not raw or raw.startswith("${"):  # an unset plugin option arrives literally as ${user_config...}
        raise IceConfigError("ICE_NAO_CONFIGURADO", "O referencial ICE não está configurado. Configure a pasta do referencial ICE no plugin (opção "
                             "'Pasta de referenciais ICE' ou variável ISG_QUALITY_ICE_REFERENCE), com o manifesto_ice.json aprovado pela Qualidade, "
                             "ou envie o arquivo do referencial junto com os outros. O plugin não escolhe um referencial por conta própria.")
    if SP.is_sharepoint(raw):
        found = SP.local_copy(raw)
        if found["caminho"] is None:
            raise IceConfigError("ICE_SEM_COPIA_LOCAL", SP.missing_message(raw, found["motivo"]))
        return found["caminho"]
    return Path(raw)


def load(arg: str | None = None) -> dict:
    """{'pasta', 'versao', 'aprovado_por', 'data', 'arquivos': [Path], 'homologacao': {...} | None}."""
    folder = _folder(arg)
    if not folder.is_dir():
        raise IceConfigError("ICE_NAO_CONFIGURADO", f"A pasta configurada do referencial ICE não existe neste computador: {folder}.")
    mpath = folder / MANIFEST
    if not mpath.is_file():
        raise IceConfigError("ICE_CONFIG_INVALIDA", f"Falta o {MANIFEST} na pasta do referencial ICE ({folder}).")
    try:
        cfg = json.loads(mpath.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        raise IceConfigError("ICE_CONFIG_INVALIDA", f"O {MANIFEST} não é um JSON válido.")
    versao = str(cfg.get("versao") or "").strip()
    if not versao:
        raise IceConfigError("ICE_CONFIG_INVALIDA", f"O {MANIFEST} não informa a versão do referencial.")
    if TEST_MARK.search(versao) or TEST_MARK.search(folder.name):
        raise IceConfigError("ICE_DE_TESTE", f"O referencial configurado parece uma cópia de teste (versão '{versao}', pasta '{folder.name}'). "
                             "Configure o referencial oficial ou envie o arquivo junto com os outros.")
    if cfg.get("aprovado") is not True or not str(cfg.get("aprovado_por") or "").strip():
        raise IceConfigError("ICE_NAO_APROVADO", f"O {MANIFEST} não declara a aprovação da Qualidade (aprovado: true e aprovado_por). "
                             "Sem isso ele não é usado como padrão.")
    names: list = []

    def collect(node):
        if isinstance(node, dict):
            if isinstance(node.get("arquivo"), str):
                names.append(node["arquivo"])
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for v in node:
                collect(v)
    collect(cfg.get("referencias") or {})
    names += [d for d in cfg.get("documentos") or [] if isinstance(d, str)]
    files, missing = [], []
    for n in dict.fromkeys(names):
        p = (folder / n).resolve()
        if not p.is_relative_to(folder.resolve()):
            raise IceConfigError("ICE_CONFIG_INVALIDA", f"O {MANIFEST} aponta para fora da pasta do referencial: {n}.")
        (files if p.is_file() else missing).append(p)
    if missing:
        raise IceConfigError("ICE_CONFIG_INVALIDA", "Arquivo(s) do referencial ICE não encontrado(s): " + ", ".join(str(m) for m in missing) + ".")
    if not files:
        raise IceConfigError("ICE_CONFIG_INVALIDA", f"O {MANIFEST} não declara nenhum arquivo do referencial.")
    if any(TEST_MARK.search(f.stem) for f in files):
        raise IceConfigError("ICE_DE_TESTE", "O referencial configurado tem arquivo de teste: " + ", ".join(f.name for f in files if TEST_MARK.search(f.stem)) + ".")
    data = str(cfg.get("data") or "").strip()
    homol = ({"versao": versao, "aprovado_por": str(cfg["aprovado_por"]).strip(), "data": data, "documento": str(mpath)}
             if re.fullmatch(r"\d{4}-\d{2}-\d{2}", data) else None)
    return {"pasta": str(folder), "versao": versao, "aprovado_por": str(cfg["aprovado_por"]).strip(), "data": data or None,
            "arquivos": files, "homologacao": homol}


def fill_manifest(manifest: dict, arg: str | None) -> dict:
    """Manifest with `referencial_ice` filled from the configured reference when the requester left it empty.
    The homologation record comes from manifesto_ice.json (with date) unless the manifest already has one."""
    if manifest["entradas"].get("referencial_ice"):
        return manifest
    cfg = load(arg)
    m = json.loads(json.dumps(manifest))
    m["entradas"]["referencial_ice"] = [{"uri": str(f), "papel": "referencial", "versao": cfg["versao"],
                                         "observacao": f"referencial ICE configurado no plugin ({cfg['pasta']})"} for f in cfg["arquivos"]]
    if not m.get("homologacao_ice") and cfg["homologacao"]:
        m["homologacao_ice"] = cfg["homologacao"]
    return m
