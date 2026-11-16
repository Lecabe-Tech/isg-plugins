"""Valida e prepara lotes do Claude para a Base Central de Qualidade (sem escrita remota)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from quality_templates import resolver_inicio, template_info
from quality_structured import (WRITE_ABAS, assemble_responses, check_record,
                                check_response, extract_structured_output, schema_for)

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



ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".docx", ".doc", ".xls", ".png", ".jpg", ".jpeg"}


def _checked_directory(path: str | None, variable: str) -> Path:
    if not path:
        raise ValueError(f"{variable}: indique uma pasta local/sincronizada absoluta.")
    if path.lower().startswith(("http://", "https://")):
        raise ValueError(f"{variable}: URL não pode ser lida sem conector SharePoint. Use pasta sincronizada.")
    candidate = Path(path).expanduser()
    if not candidate.is_absolute() and not re.match(r"^[A-Za-z]:[\\/]", path):
        raise ValueError(f"{variable}: caminho de pasta deve ser absoluto.")
    if not candidate.is_dir():
        raise ValueError(f"{variable}: pasta não encontrada ou inacessível: {path}")
    return candidate.resolve()


def _reference_entry(root: Path, entry: object, label: str) -> dict:
    if not isinstance(entry, dict):
        raise ValueError(f"{label}: faltam arquivo e aba no manifesto ICE.")
    filename, sheet = entry.get("arquivo"), entry.get("aba")
    if not isinstance(filename, str) or not isinstance(sheet, str) or not filename or not sheet:
        raise ValueError(f"{label}: arquivo e aba são obrigatórios.")
    target = (root / filename).resolve()
    if not target.is_relative_to(root) or not target.is_file() or target.suffix.lower() != ".xlsx":
        raise ValueError(f"{label}: arquivo XLSX inválido ou fora da pasta referencial.")
    with zipfile.ZipFile(target) as z:
        if "xl/workbook.xml" not in z.namelist():
            raise ValueError(f"{label}: workbook sem metadados de abas.")
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        available = {s.get("name") for s in wb.iter(NS + "sheet")}
    if sheet not in available:
        raise ValueError(f"{label}: aba '{sheet}' ausente no Excel de referência.")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    expected = entry.get("sha256")
    if expected is not None and (not isinstance(expected, str) or digest.lower() != expected.lower()):
        raise ValueError(f"{label}: SHA-256 não corresponde ao manifesto.")
    return {"arquivo": filename, "aba": sheet, "sha256": digest, "hash_conferido": expected is not None}


def fontes_info(docs: str | None, ice: str | None, uf: str, ano: int, modelo: str) -> dict:
    """Verifica a disponibilidade técnica das fontes; não faz julgamento pedagógico."""
    if not re.fullmatch(r"[A-Z]{2}", uf) or ano < 2024 or ano > 2100 or modelo not in ("7h", "9h"):
        raise ValueError("Informe --uf (duas letras), --ano (2024..2100) e --modelo (7h/9h).")
    state_root = _checked_directory(docs, "ISG_QUALITY_STATE_DOCS")
    state_path = state_root / uf / str(ano)
    if not state_path.is_dir():
        raise ValueError(f"Documentos estaduais: subpasta {uf}/{ano} não encontrada.")
    documents = sorted(str(p.relative_to(state_path)) for p in state_path.rglob("*")
                       if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS)
    if not documents:
        raise ValueError(f"Documentos estaduais: nenhum PDF/Excel/Word/imagem em {uf}/{ano}.")
    ice_root = _checked_directory(ice, "ISG_QUALITY_ICE_REFERENCE")
    manifest = ice_root / "manifesto_ice.json"
    if not manifest.is_file():
        raise ValueError("Referencial ICE: falta manifesto_ice.json.")
    cfg = json.loads(manifest.read_text(encoding="utf-8-sig"))
    if not isinstance(cfg, dict) or not isinstance(cfg.get("versao"), str) or not cfg["versao"].strip():
        raise ValueError("Referencial ICE: informe versão no manifesto.")
    if cfg.get("aprovado") is not True or not cfg.get("aprovado_por"):
        raise ValueError("Referencial ICE: falta declaração de aprovação da Qualidade.")
    refs = cfg.get("referencias", {})
    if not isinstance(refs, dict) or not isinstance(refs.get("matrizes"), dict):
        raise ValueError("Referencial ICE: falta mapa de matrizes por modelo.")
    if modelo not in refs["matrizes"]:
        raise ValueError(f"Referencial ICE: gabarito {modelo} ausente; não substituir pelo outro modelo.")
    result = {"matriz": _reference_entry(ice_root, refs["matrizes"][modelo], modelo)}
    for key in ("orientacoes_pedagogicas", "orientacoes_gestao", "criterios"):
        result[key] = _reference_entry(ice_root, refs.get(key), key)
    return {"pronto_para_analisar": True, "uf": uf, "ano": ano, "modelo": modelo,
            "documentos": documents, "versao_referencial": cfg["versao"], "referencias": result,
            "aviso": "Pré-checagem técnica; aprovação declarada no manifesto não autentica a governança. Nenhuma planilha foi alterada."}


def parse_bundle(path: Path) -> dict:
    o = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(o, dict):
        raise ValueError("Lote JSON deve ser objeto.")
    if "structured_output" in o:
        checked = check_response(o)
        if not checked["valido"]:
            raise ValueError("Resposta Claude Code invalida: " + " | ".join(checked["erros"]))
        o = extract_structured_output(o)
    if "abas" in o:
        abas = o["abas"]
    elif "aba" in o and "linhas" in o:
        checked = check_response(o)
        if not checked["valido"]:
            raise ValueError("Resposta por aba invalida: " + " | ".join(checked["erros"]))
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
            for err in check_record(tab, row):
                erros.append(label + ": " + err)
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
    parser.add_argument("comando", choices=["status", "fontes", "resolver", "template", "esquema", "validar-resposta", "agrupar", "validar", "preparar"])
    parser.add_argument("arquivo", nargs="?")
    parser.add_argument("--base", default=os.getenv("ISG_QUALITY_BASE"))
    parser.add_argument("--saida")
    parser.add_argument("--docs", default=os.getenv("ISG_QUALITY_STATE_DOCS"))
    parser.add_argument("--templates", default=os.getenv("ISG_QUALITY_TEMPLATES_DIR"))
    parser.add_argument("--orientacao")
    parser.add_argument("--referencial", default=os.getenv("ISG_QUALITY_ICE_REFERENCE"))
    parser.add_argument("--uf")
    parser.add_argument("--ano", type=int)
    parser.add_argument("--modelo")
    parser.add_argument("--aba")
    parser.add_argument("--versao")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.comando == "status":
            result = base_info(args.base)
            result["documentos_configurados"] = bool(args.docs)
            result["referencial_configurado"] = bool(args.referencial)
            result["templates_configurados"] = bool(args.templates)
        elif args.comando == "fontes":
            result = fontes_info(args.docs, args.referencial, args.uf or "", args.ano or 0, args.modelo or "")
        elif args.comando == "resolver":
            result = resolver_inicio(args.docs, args.templates, args.ano or 0,
                                     args.orientacao, args.uf)
        elif args.comando == "template":
            result = template_info(args.templates, args.uf or "", args.ano or 0)
        elif args.comando == "esquema":
            if not args.aba:
                raise ValueError("Informe --aba.")
            print(json.dumps(schema_for(args.aba), ensure_ascii=False, separators=(",", ":")))
            return 0
        elif args.comando == "validar-resposta":
            if not args.arquivo:
                raise ValueError("Informe arquivo de resposta do Claude.")
            raw = json.loads(Path(args.arquivo).read_text(encoding="utf-8-sig"))
            result = check_response(raw)
        elif args.comando == "agrupar":
            if not args.arquivo or not args.saida:
                raise ValueError("Informe pasta de respostas e --saida para o lote.")
            if not args.versao:
                raise ValueError("Informe --versao.")
            bundle = assemble_responses(Path(args.arquivo), args.uf or "", args.ano or 0,
                                        args.modelo or "", args.versao)
            result = validate(bundle)
            if result["valido"]:
                output = Path(args.saida)
                if output.exists():
                    raise ValueError("Saida existente: nao sobrescrever lote.")
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                result["arquivo"] = str(output)
                result["estado"] = "LOTE_ESTRUTURADO_VALIDADO_NAO_IMPORTADO"
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
    for _stream in (sys.stdout, sys.stderr):  # PT-BR accents must come out as UTF-8 on every platform (same as cfp.py/eqv.py)
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    sys.exit(main())
