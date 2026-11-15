"""Valida e prepara lotes do Claude para a Base Central de Qualidade (sem escrita remota)."""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

SCHEMA = {
    "SG_Ciclos": "CicloID UF Ano Modelo Cluster SituacaoOrigem StatusValidacao Publicado ResponsavelAprovacao ArquivoOrigem",
    "SG_Componentes": "RegistroID CicloID UF Ano Modelo ComponenteOriginal Classificacao Serie1 Serie2 Serie3 MinutosAula Evidencia CelulaOrigem StatusValidacao Publicado",
    "SG_ResumoMatriz": "ResumoID CicloID UF Ano Modelo MinutosAula Elemento Serie1 Serie2 Serie3 HorasTotais AulasTotais CelulaOrigem StatusValidacao Publicado",
    "SG_Avaliacoes": "RegistroID CicloID UF Ano Modelo Tipo Codigo PresencaOriginal Presenca JustificativaEvidencia Origem CelulaOrigem StatusValidacao Publicado Aprovador DocumentoID",
    "SG_Documentos": "DocumentoID UF Ano NomeArquivo Tipo URLSharePoint Paginas StatusDocumento Observacao HashArquivo",
}
SCHEMA = {k: v.split() for k, v in SCHEMA.items()}
IDS = {"SG_Ciclos": "CicloID", "SG_Componentes": "RegistroID", "SG_ResumoMatriz": "ResumoID", "SG_Avaliacoes": "RegistroID", "SG_Documentos": "DocumentoID"}
CHILDREN = {"SG_Componentes", "SG_ResumoMatriz", "SG_Avaliacoes"}
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def base_info(value: str | None) -> dict:
    if not value or not value.strip():
        return {"configurada": False, "tipo": "ausente", "verificada": False}
    value = value.strip()
    if value.startswith(("https://", "http://")):
        u = urlparse(value)
        if u.scheme != "https" or not u.hostname or not u.path.lower().endswith(".xlsx"):
            raise ValueError("Base remota exige URL HTTPS direta de arquivo .xlsx.")
        return {"configurada": True, "tipo": "url_sharepoint", "referencia": value, "verificada": False,
                "aviso": "URL sozinha não concede autenticação nem grava no SharePoint."}
    if not value.lower().endswith(".xlsx"):
        raise ValueError("A base local precisa apontar para um arquivo .xlsx.")
    if not (Path(value).is_absolute() or re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("\\\\")):
        raise ValueError("Use um caminho absoluto, não relativo.")
    p = Path(value)
    if not p.is_file():
        return {"configurada": True, "tipo": "arquivo_local", "referencia": value, "verificada": False,
                "aviso": "Caminho configurado, mas arquivo não acessível neste ambiente."}
    with zipfile.ZipFile(p) as z:
        tabs = {}
        for name in z.namelist():
            if not re.fullmatch(r"xl/tables/table\d+\.xml", name):
                continue
            t = ET.fromstring(z.read(name))
            cols = [c.attrib["name"] for c in t.find(NS + "tableColumns")]
            tabs[t.attrib["name"]] = cols
    faltantes = [name for name, fields in SCHEMA.items() if tabs.get(name) != fields]
    return {"configurada": True, "tipo": "arquivo_local", "referencia": value,
            "verificada": len(faltantes) == 0, "tabelas_encontradas": sorted(tabs),
            "tabelas_incompativeis": faltantes, "gravacao_executada": False}


def parse_bundle(path: Path) -> dict:
    o = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(o, dict):
        raise ValueError("Lote JSON deve ser objeto.")
    if "abas" in o:
        abas = o["abas"]
    elif "aba" in o and "linhas" in o:
        abas = {o["aba"]: o["linhas"]}
    else:
        raise ValueError("JSON precisa de 'abas' ou de 'aba' + 'linhas'.")
    if not isinstance(abas, dict) or not abas:
        raise ValueError("'abas' deve ser objeto não vazio.")
    return {"lote": o.get("lote", {}), "abas": abas, "pendencias": o.get("pendencias", []),
            "evidencias_eqv": o.get("evidencias_eqv")}


def validate(bundle: dict) -> dict:
    abas = bundle["abas"]
    erros = []
    counts = {}
    ciclo_ids = set()
    for tab, rows in abas.items():
        if tab not in SCHEMA:
            erros.append(f"{tab}: tabela não permitida para gravação pelo Claude.")
            continue
        if not isinstance(rows, list):
            erros.append(f"{tab}: linhas devem ser lista.")
            continue
        counts[tab] = len(rows)
        seen = set()
        for i, row in enumerate(rows, 1):
            label = f"{tab}[{i}]"
            if not isinstance(row, dict):
                erros.append(label + ": linha não é objeto.")
                continue
            unexpected = set(row) - set(SCHEMA[tab])
            if unexpected:
                erros.append(label + ": colunas inesperadas " + ",".join(sorted(unexpected)))
            idfield = IDS[tab]
            record_id = row.get(idfield)
            if not isinstance(record_id, str) or not record_id.strip():
                erros.append(label + f": {idfield} obrigatório.")
            elif record_id in seen:
                erros.append(label + f": ID duplicado {record_id}.")
            else:
                seen.add(record_id)
            if tab == "SG_Ciclos" and isinstance(record_id, str):
                ciclo_ids.add(record_id)
            if tab != "SG_Documentos":
                if row.get("Publicado") != "Não":
                    erros.append(label + ": Publicado deve ser 'Não'.")
                target = "Pendente revisão" if tab == "SG_Ciclos" else "Importado - revisar"
                if row.get("StatusValidacao") != target:
                    erros.append(label + f": StatusValidacao deve ser {target}.")
            if tab == "SG_Avaliacoes":
                if row.get("Aprovador") not in (None, ""):
                    erros.append(label + ": Aprovador deve estar vazio.")
                if row.get("Tipo") not in ("Pedagógica", "Gestão"):
                    erros.append(label + ": Tipo inválido.")
                if row.get("Presenca") not in ("Sim", "Não", None, ""):
                    erros.append(label + ": Presenca inválida.")
            if tab == "SG_Ciclos" and row.get("ResponsavelAprovacao") not in (None, ""):
                erros.append(label + ": ResponsavelAprovacao deve estar vazio.")
    lote = bundle.get("lote") or {}
    if lote:
        if not isinstance(lote, dict):
            erros.append("lote precisa ser objeto.")
            lote = {}
        for tab, rows in abas.items():
            if tab not in SCHEMA or not isinstance(rows, list):
                continue
            for i, row in enumerate(rows, 1):
                if not isinstance(row, dict):
                    continue
                for k in ("UF", "Ano"):
                    if k in lote and row.get(k) != lote[k]:
                        erros.append(f"{tab}[{i}]: {k} não coincide com lote.")
                if "Modelo" in lote and "Modelo" in row and row.get("Modelo") != lote["Modelo"]:
                    erros.append(f"{tab}[{i}]: Modelo não coincide com lote.")
    for tab in CHILDREN:
        for i, row in enumerate(abas.get(tab, []), 1):
            if isinstance(row, dict) and row.get("CicloID") not in ciclo_ids:
                erros.append(f"{tab}[{i}]: CicloID precisa constar no mesmo pacote.")
    return {"valido": not erros, "erros": erros, "contagens": counts,
            "total": sum(counts.values()), "publicado": False}


def write_staging(bundle: dict, destination: Path) -> list:
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Diretório de saída já contém arquivos; use um diretório novo.")
    destination.mkdir(parents=True, exist_ok=True)
    created = []
    canonical = destination / "lote-validado.json"
    canonical.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    created.append(canonical.name)
    for tab, rows in bundle["abas"].items():
        path = destination / (tab + ".csv")
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=SCHEMA[tab], delimiter=";", extrasaction="raise")
            w.writeheader()
            for row in rows:
                w.writerow({col: ("" if row.get(col) is None else row[col]) for col in SCHEMA[tab]})
        created.append(path.name)
    return created


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepara lotes Claude sem editar a base central.")
    parser.add_argument("comando", choices=["status", "validar", "preparar"])
    parser.add_argument("arquivo", nargs="?")
    parser.add_argument("--base", default=os.getenv("ISG_QUALITY_BASE"))
    parser.add_argument("--saida")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.comando == "status":
            result = base_info(args.base)
        else:
            if not args.arquivo:
                raise ValueError("Informe o caminho do lote JSON.")
            bundle = parse_bundle(Path(args.arquivo))
            result = validate(bundle)
            if result["valido"] and args.comando == "preparar":
                if not args.saida:
                    raise ValueError("Informe --saida.")
                result["arquivos"] = write_staging(bundle, Path(args.saida))
                result["estado"] = "PACOTE_PREPARADO_NAO_GRAVADO"
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.json else None))
        return 0 if result.get("valido", True) else 2
    except (ValueError, OSError, json.JSONDecodeError, zipfile.BadZipFile) as e:
        print(json.dumps({"valido": False, "erro": str(e)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
