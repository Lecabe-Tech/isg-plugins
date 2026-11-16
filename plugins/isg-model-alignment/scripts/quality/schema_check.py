"""Draft-07 JSON Schema subset validator for the SPEC-017 contracts (standard library only).

The SG_* validator in `quality_structured.py` covers flat tab rows and stays as it is. The SPEC-017 manifest and result
are nested, so this validator adds `$ref` to `#/definitions/...`, `minimum`/`maximum`, `minLength`, `uniqueItems`
and `anyOf`. Messages are PT-BR because they reach the analyst.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
SCHEMAS = {
    "manifesto": "manifesto_qualidade.v1.schema.json",
    "resultado": "resultado_qualidade.v1.schema.json",
}


def load_schema(kind: str) -> dict:
    if kind not in SCHEMAS:
        raise ValueError(f"Schema desconhecido: {kind}")
    return json.loads((SCHEMA_DIR / SCHEMAS[kind]).read_text(encoding="utf-8"))


def _type_ok(value, kind: str) -> bool:
    if kind == "null":
        return value is None
    if kind == "boolean":
        return type(value) is bool
    if kind == "integer":
        return type(value) is int
    if kind == "number":
        return type(value) in (int, float) and (type(value) is int or math.isfinite(value))
    if kind == "string":
        return isinstance(value, str)
    if kind == "object":
        return isinstance(value, dict)
    if kind == "array":
        return isinstance(value, list)
    return False


def _resolve(root: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise ValueError(f"Referência não suportada: {ref}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _same(a, b) -> bool:
    return type(a) is type(b) and a == b


def _node(root: dict, schema: dict, value, loc: str, errors: list) -> None:
    if "$ref" in schema:
        _node(root, _resolve(root, schema["$ref"]), value, loc, errors)
        return
    if "anyOf" in schema:
        if not any(not _collect(root, alt, value, loc) for alt in schema["anyOf"]):
            errors.append(f"{loc}: não corresponde a nenhuma das formas permitidas.")
        return
    kind = schema.get("type")
    if kind is not None:
        kinds = kind if isinstance(kind, list) else [kind]
        if not any(_type_ok(value, k) for k in kinds):
            errors.append(f"{loc}: tipo inválido, esperado {kinds}.")
            return
    if "const" in schema and not _same(value, schema["const"]):
        errors.append(f"{loc}: valor fixo diferente do contrato.")
    if "enum" in schema and not any(_same(value, v) for v in schema["enum"]):
        errors.append(f"{loc}: fora dos valores permitidos {schema['enum']}.")
    if isinstance(value, str):
        if "minLength" in schema and len(value.strip()) < schema["minLength"]:
            errors.append(f"{loc}: texto curto demais (mínimo {schema['minLength']}).")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            errors.append(f"{loc}: formato inválido.")
    if type(value) in (int, float) and type(value) is not bool:
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{loc}: menor que {schema['minimum']}.")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{loc}: maior que {schema['maximum']}.")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in sorted(set(schema.get("required", [])) - set(value)):
            errors.append(f"{loc}.{key}: campo obrigatório ausente.")
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(props)):
                errors.append(f"{loc}.{key}: campo não permitido.")
        elif isinstance(schema.get("additionalProperties"), dict):
            for key in sorted(set(value) - set(props)):
                _node(root, schema["additionalProperties"], value[key], f"{loc}.{key}", errors)
        for key, sub in props.items():
            if key in value:
                _node(root, sub, value[key], f"{loc}.{key}", errors)
    elif isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{loc}: precisa de pelo menos {schema['minItems']} item(ns).")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{loc}: excede {schema['maxItems']} item(ns).")
        if schema.get("uniqueItems"):
            seen = [json.dumps(v, sort_keys=True, ensure_ascii=False) for v in value]
            if len(seen) != len(set(seen)):
                errors.append(f"{loc}: itens repetidos.")
        if isinstance(schema.get("items"), dict):
            for i, item in enumerate(value):
                _node(root, schema["items"], item, f"{loc}[{i}]", errors)


def _collect(root: dict, schema: dict, value, loc: str) -> list:
    errs: list = []
    _node(root, schema, value, loc, errs)
    return errs


def validate(kind: str, value) -> list:
    """List of PT-BR errors (empty = valid against the versioned schema)."""
    root = load_schema(kind)
    return _collect(root, root, value, "$")
