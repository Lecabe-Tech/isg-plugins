"""Contrato JSON estrito da Qualidade (subconjunto do JSON Schema; sem dependencias)."""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
WRITE_ABAS = ("SG_Documentos", "SG_Ciclos", "SG_Componentes", "SG_ResumoMatriz", "SG_Avaliacoes")
READ_ABAS = ("SG_Referenciais", "SG_Aprovacoes", "LEIA_ME", "VALIDACAO", "DICIONARIO", "CONTRATO_TH")
ALL_ABAS = WRITE_ABAS + READ_ABAS


def schema_for(aba: str) -> dict:
    if aba not in ALL_ABAS:
        raise ValueError(f"Aba desconhecida: {aba}")
    path = SCHEMA_DIR / f"{aba}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _matches_type(value: object, kind: str) -> bool:
    if kind == "null":
        return value is None
    if kind == "boolean":
        return type(value) is bool
    if kind == "integer":
        return type(value) is int
    if kind == "number":
        return type(value) in (int, float)
    if kind == "string":
        return isinstance(value, str)
    if kind == "object":
        return isinstance(value, dict)
    if kind == "array":
        return isinstance(value, list)
    return False


def _validate_node(schema: dict, value: object, loc: str, errors: list[str]) -> None:
    kind = schema.get("type")
    if kind is not None:
        candidates = kind if isinstance(kind, list) else [kind]
        if not any(_matches_type(value, k) for k in candidates):
            errors.append(f"{loc}: tipo inválido, esperado {candidates}.")
            return
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        errors.append(f"{loc}: valor fixo diferente do contrato.")
    if "enum" in schema and not any(type(value) is type(v) and value == v for v in schema["enum"]):
        errors.append(f"{loc}: fora dos valores permitidos.")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        missing = set(schema.get("required", [])) - set(value)
        for key in sorted(missing):
            errors.append(f"{loc}.{key}: campo obrigatório ausente.")
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(props)):
                errors.append(f"{loc}.{key}: campo não permitido.")
        for key, sub in props.items():
            if key in value:
                _validate_node(sub, value[key], f"{loc}.{key}", errors)
    elif isinstance(value, list):
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{loc}: excede o número de itens permitido.")
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{loc}: número insuficiente de itens.")
        if isinstance(schema.get("items"), dict):
            for i, item in enumerate(value):
                _validate_node(schema["items"], item, f"{loc}[{i}]", errors)


def check_record(aba: str, row: dict) -> list[str]:
    if aba not in WRITE_ABAS:
        return [f"{aba}: Claude não pode gerar linhas para esta aba."]
    schema = schema_for(aba)["properties"]["linhas"]["items"]
    errors: list[str] = []
    _validate_node(schema, row, aba, errors)
    if not isinstance(row, dict):
        return errors
    for key in ("CicloID", "RegistroID", "ResumoID", "DocumentoID", "UF", "Modelo",
                "ComponenteOriginal", "Elemento", "Codigo", "NomeArquivo"):
        if key in row and (not isinstance(row[key], str) or not row[key].strip()):
            errors.append(f"{aba}.{key}: identificador/texto obrigatório não pode ser vazio.")
    if "Ano" in row and type(row["Ano"]) is int and not (2024 <= row["Ano"] <= 2100):
        errors.append(f"{aba}.Ano: ano fora da faixa permitida.")
    for key in ("Serie1", "Serie2", "Serie3", "MinutosAula", "HorasTotais", "AulasTotais", "Paginas"):
        value = row.get(key)
        if type(value) in (int, float) and value < 0:
            errors.append(f"{aba}.{key}: não pode ser negativo.")
    if aba != "SG_Documentos" and all(isinstance(row.get(k), (str, int)) for k in ("UF", "Ano", "Modelo")):
        prefix = f"{row['UF']}|{row['Ano']}|{row['Modelo']}|"
        if isinstance(row.get("CicloID"), str) and not row["CicloID"].startswith(prefix):
            errors.append(f"{aba}.CicloID: não corresponde a UF, Ano e Modelo.")
    return errors


def extract_structured_output(obj: object) -> dict:
    """Aceita objeto puro ou envelope CLI com structured_output; não confia em markdown."""
    if not isinstance(obj, dict):
        raise ValueError("Resposta deve ser JSON objeto.")
    if "structured_output" in obj:
        inner = obj["structured_output"]
        if not isinstance(inner, dict):
            raise ValueError("Claude Code retornou structured_output inválido.")
        return inner
    if "result" in obj and "aba" not in obj:
        raise ValueError("Claude Code não retornou structured_output; a saída textual não é importável.")
    return obj


def check_response(obj: object) -> dict:
    try:
        data = extract_structured_output(obj)
        aba = data.get("aba")
        schema = schema_for(aba)
    except (ValueError, TypeError) as exc:
        return {"valido": False, "erros": [str(exc)], "aba": None}
    errors: list[str] = []
    _validate_node(schema, data, "$", errors)
    if aba in READ_ABAS and data.get("linhas") != []:
        errors.append(f"{aba}: somente leitura/governança; linhas devem ser [].")
    if aba in WRITE_ABAS and isinstance(data.get("linhas"), list):
        for i, row in enumerate(data["linhas"]):
            errors.extend(f"linhas[{i}]: {e}" for e in check_record(aba, row))
    return {"valido": not errors, "erros": errors, "aba": aba,
            "linhas": len(data.get("linhas", [])) if isinstance(data.get("linhas"), list) else 0}


def assemble_responses(folder: Path, uf: str, ano: int, modelo: str, versao: str) -> dict:
    """Exige os cinco JSONs de dados; valida TODOS antes de criar lote."""
    if not folder.is_dir():
        raise ValueError("Pasta de respostas inexistente.")
    if not isinstance(uf, str) or len(uf) != 2 or type(ano) is not int or modelo not in ("7h", "9h") or not versao:
        raise ValueError("Informe --uf, --ano, --modelo e --versao válidos.")
    abas = {}
    pendencias = []
    fontes = []
    for aba in WRITE_ABAS:
        path = folder / f"{aba}.json"
        if not path.is_file():
            raise ValueError(f"Falta resposta estruturada para {aba}: {path.name}")
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
        validation = check_response(obj)
        if not validation["valido"]:
            raise ValueError(f"{aba}: " + " | ".join(validation["erros"][:12]))
        content = extract_structured_output(obj)
        if content["aba"] != aba:
            raise ValueError(f"Arquivo {path.name} contém a aba errada.")
        abas[aba] = content["linhas"]
        pendencias.extend({"aba": aba, **v} for v in content["pendencias"])
        fontes.extend(content["fontes"])
    return {"lote": {"UF": uf, "Ano": ano, "Modelo": modelo, "Versao": versao},
            "abas": abas, "pendencias": pendencias, "fontes": fontes,
            "evidencias_eqv": None}
