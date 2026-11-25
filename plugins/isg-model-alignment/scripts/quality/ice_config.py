"""Configured ICE reference (decision of 2026-11-17, after the CE 2026 pilot).

The ICE reference is the same for every state, so it is configured ONCE: the folder of the plugin option
`quality_ice_reference` (or the environment variable ISG_QUALITY_ICE_REFERENCE, which wins), with a
`manifesto_ice.json` that declares the version, the approval and the files. A SharePoint link to that folder is
accepted and read from the OneDrive copy (sharepoint_link.py).

A run whose manifest leaves `referencial_ice` empty uses this configured reference. The program never picks a file on
its own: without a configured and approved reference, the run does not start and says what to do. A reference marked as
a test copy or not approved is refused as default. Standard library only.

Approved rules (0.1.8). Besides the files, an APPROVED manifesto_ice.json may carry data the Quality team decided once for
every run, recorded in the run manifest as `configuracao_ice` (never filled by the plugin itself):
  * `codigos`: {"pedagogicas": [{"codigo": "EL1", "texto": "..."}], "gestao": [...]} — the ICE orientation codes, so an ICE
    in PDF no longer leaves the codes unidentified;
  * `carga_minima`: [{"classificacao": "Estudo Orientado e Avaliação Semanal", "minimo_por_serie": {"serie1": 2, ...},
    "minimo_total": 6, "ideal_total": 6}] — the minimum weekly load of each diversified component (ICE table 1), compared
    with the matrix in the cross-check (CARGA_ABAIXO_MINIMO);
  * `equivalencias_componentes`: [{"uf": "CE", "nome": "NTPPS", "classificacao": "Projeto de Vida"}] — approved name
    equivalences, used as the classification basis "equivalencia_aprovada" (values read from images stay unverified).
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


SERIES = ("serie1", "serie2", "serie3")
CODE = re.compile(r"^[A-Z]{1,4}\d+$")


def approved_rules(cfg: dict) -> dict:
    """The approved rules of a manifesto_ice.json (already checked as approved), validated; {} when there is none."""
    out = {}
    codes = cfg.get("codigos")
    if codes is not None:
        if not isinstance(codes, dict):
            raise IceConfigError("ICE_CONFIG_INVALIDA", "'codigos' do manifesto_ice.json deve ser {pedagogicas: [...], gestao: [...]}.")
        clean = {}
        for k in ("pedagogicas", "gestao"):
            rows = []
            for c in codes.get(k) or []:
                code = str((c or {}).get("codigo") if isinstance(c, dict) else c).strip().upper()
                if not CODE.match(code):
                    raise IceConfigError("ICE_CONFIG_INVALIDA", f"Código de orientação inválido no manifesto_ice.json ({k}): {code!r}.")
                rows.append({"codigo": code, "texto": str(c.get("texto") or "").strip() if isinstance(c, dict) else ""})
            clean[k] = rows
        out["codigos"] = clean
    minimum = cfg.get("carga_minima")
    if minimum is not None:
        rows = []
        for m in minimum if isinstance(minimum, list) else [None]:
            if not isinstance(m, dict) or not str(m.get("classificacao") or "").strip():
                raise IceConfigError("ICE_CONFIG_INVALIDA", "Cada item de 'carga_minima' precisa da 'classificacao' (como no template).")
            per = m.get("minimo_por_serie") or {}
            if not isinstance(per, dict) or any(not isinstance(per.get(s, 0), (int, float)) for s in SERIES):
                raise IceConfigError("ICE_CONFIG_INVALIDA", f"'minimo_por_serie' inválido em carga_minima ({m['classificacao']}).")
            tot = m.get("minimo_total")
            if tot is not None and not isinstance(tot, (int, float)):
                raise IceConfigError("ICE_CONFIG_INVALIDA", f"'minimo_total' inválido em carga_minima ({m['classificacao']}).")
            if not per and tot is None:
                raise IceConfigError("ICE_CONFIG_INVALIDA", f"carga_minima de {m['classificacao']} sem 'minimo_por_serie' nem 'minimo_total'.")
            rows.append({"classificacao": str(m["classificacao"]).strip(), "minimo_por_serie": {s: per[s] for s in SERIES if s in per} or None,
                         "minimo_total": tot, "ideal_total": m.get("ideal_total"), "observacao": m.get("observacao")})
        out["carga_minima"] = rows
    eqs = cfg.get("equivalencias_componentes")
    if eqs is not None:
        rows = []
        for e in eqs if isinstance(eqs, list) else [None]:
            if not isinstance(e, dict) or not str(e.get("nome") or "").strip() or not str(e.get("classificacao") or "").strip():
                raise IceConfigError("ICE_CONFIG_INVALIDA", "Cada item de 'equivalencias_componentes' precisa de 'nome' e 'classificacao'.")
            uf = str(e.get("uf") or "").strip().upper() or None
            rows.append({"uf": uf, "nome": str(e["nome"]).strip(), "classificacao": str(e["classificacao"]).strip(), "observacao": e.get("observacao")})
        out["equivalencias_componentes"] = rows
    return out


def rules_record(cfg: dict) -> dict | None:
    """`configuracao_ice` for the run manifest: who approved, when, and the approved rules; None without rules."""
    rules = cfg.get("regras") or {}
    if not rules:
        return None
    return {"versao": cfg["versao"], "aprovado_por": cfg["aprovado_por"], "data": cfg.get("data"), **rules}


def read_rules_file(path: str) -> dict:
    """A manifesto_ice.json given directly (for example kept in the plugin repository for the cloud flow): it must be
    approved; returns the `configuracao_ice` record."""
    p = Path(path)
    if p.is_dir():
        p = p / MANIFEST
    try:
        cfg = json.loads(p.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise IceConfigError("ICE_CONFIG_INVALIDA", f"Arquivo de configuração do ICE não encontrado: {p}.")
    except json.JSONDecodeError:
        raise IceConfigError("ICE_CONFIG_INVALIDA", f"{p} não é um JSON válido.")
    versao = str(cfg.get("versao") or "").strip()
    if not versao or TEST_MARK.search(versao):
        raise IceConfigError("ICE_DE_TESTE" if versao else "ICE_CONFIG_INVALIDA", f"A configuração do ICE em {p} não tem versão oficial ('{versao}').")
    if cfg.get("aprovado") is not True or not str(cfg.get("aprovado_por") or "").strip():
        raise IceConfigError("ICE_NAO_APROVADO", f"A configuração do ICE em {p} não declara a aprovação da Qualidade (aprovado: true e aprovado_por).")
    rec = rules_record({"versao": versao, "aprovado_por": str(cfg["aprovado_por"]).strip(), "data": str(cfg.get("data") or "").strip() or None,
                        "regras": approved_rules(cfg)})
    if not rec:
        raise IceConfigError("ICE_SEM_REGRAS", f"{p} não traz codigos, carga_minima nem equivalencias_componentes.")
    return rec


def configured(arg: str | None) -> bool:
    raw = (os.environ.get(ENV) or "").strip() or (arg or "").strip()
    return bool(raw) and not raw.startswith("${")


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
            "arquivos": files, "homologacao": homol, "regras": approved_rules(cfg)}


def fill_manifest(manifest: dict, arg: str | None) -> dict:
    """Manifest with `referencial_ice` filled from the configured reference when the requester left it empty.
    The homologation record comes from manifesto_ice.json (with date) unless the manifest already has one. The approved
    rules of the configured reference (codes, minimum load, equivalences) go to `configuracao_ice` even when the ICE file
    itself was sent with the request, unless the manifest already brings its own record."""
    m = json.loads(json.dumps(manifest))
    if m["entradas"].get("referencial_ice"):
        if m.get("configuracao_ice") or not configured(arg):
            return m
        try:
            cfg = load(arg)
        except IceConfigError:
            return m  # the sent ICE file is used; without a usable configured reference there are no approved rules
    else:
        cfg = load(arg)
        m["entradas"]["referencial_ice"] = [{"uri": str(f), "papel": "referencial", "versao": cfg["versao"],
                                             "observacao": f"referencial ICE configurado no plugin ({cfg['pasta']})"} for f in cfg["arquivos"]]
        if not m.get("homologacao_ice") and cfg["homologacao"]:
            m["homologacao_ice"] = cfg["homologacao"]
    if not m.get("configuracao_ice"):
        rec = rules_record(cfg)
        if rec:
            m["configuracao_ice"] = rec
    return m
