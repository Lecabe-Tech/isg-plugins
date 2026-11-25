"""SPEC-017: what the cluster template and the ICE reference contribute (structure and rules, never evidence of offer).

Template: the classification list (hidden sheet), the UF matrix tab ('2.x Revisão Matriz <UF>'), the consolidation
formulas read from the cells and turned into a rule with a SHA-256 fingerprint and the orientation codes of tabs 1.1/1.2
(EQV reader). The analysts' answers already in the template (Sim/Não, observations, matrix values, class-hour minutes,
validity year) are HISTORY, never evidence: `build_references` keeps only a structural projection in referencias.json
(how many answers there were, not their values). The template bytes stay in originais/ for the filled copy and for the
optional parity, which runs only after the independent result is written.
ICE: the orientation codes per type and the approval record declared in the manifest.
A formula the parser does not know makes the rule `desconhecida` (REGRA_DESCONHECIDA): nothing is guessed.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import document_normalizer as DN
import source_resolver as SR

HERE = Path(__file__).resolve().parent
CODE_RE = re.compile(r"^[A-Z]{1,4}\d+$")
SERIES = ("serie1", "serie2", "serie3")


def _eqv():
    p = str(HERE.parent / "eqv")
    if p not in sys.path:
        sys.path.insert(0, p)
    from isg_eqv import template as T
    return T


def _cells(sheet: dict) -> dict:
    """{(col, row): cell} of a sheet from document_normalizer.read_workbook."""
    return {DN.split_ref(ref): c for ref, c in sheet["celulas"].items()}


def _text(c) -> str:
    return "" if c is None or c.get("valor") is None else str(c["valor"]).strip()


def find_label(cells: dict, *needles) -> tuple | None:
    """Position of the first cell whose folded text contains every needle."""
    for (col, row), c in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        t = DN.fold(_text(c))
        if t and all(n in t for n in needles):
            return col, row
    return None


def value_right_of(cells: dict, pos: tuple | None):
    if not pos:
        return None
    col, row = pos
    for c in range(col + 1, col + 6):
        v = cells.get((c, row))
        if v is not None and v.get("valor") not in (None, ""):
            return v["valor"]
    return None


def classification_list(wb: dict) -> tuple:
    """(list, sheet name, warnings). Prefers the sheet named exactly 'classificacoes'."""
    candidates = [s for s in wb["abas"] if "classificac" in DN.fold(s["nome"])]
    candidates.sort(key=lambda s: (DN.fold(s["nome"]) != "classificacoes", s["nome"]))
    lists = []
    for s in candidates:
        cells = _cells(s)
        heads = [(c, r) for (c, r), v in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0]))
                 if DN.fold(_text(v)).startswith("classificac") and len(_text(v)) < 60]
        for col, row in heads:
            values = []
            r = row + 1
            while _text(cells.get((col, r))):
                values.append(_text(cells[(col, r)]))
                r += 1
            if values:
                lists.append((s["nome"], values))
                break
    if not lists:
        return [], None, ["O template não tem a lista de classificações (aba 'classificacoes')."]
    warnings = [f"A aba '{n}' tem uma lista diferente ({len(v)} itens); foi usada '{lists[0][0]}'." for n, v in lists[1:] if v != lists[0][1]]
    return lists[0][1], lists[0][0], warnings


def matrix_tab(wb: dict, uf: str) -> dict | None:
    for s in wb["abas"]:
        name = DN.fold(s["nome"])
        if re.match(r"^\s*2\.\d+\s+revisao\s+(da\s+)?matriz\b", name) and name.split()[-1] == uf.lower():
            return s
    return None


REF = r"\$?([A-Z]{1,3})\$?(\d+)"


def _parse_formula(f: str, element_rows: dict, comp_cols: dict, cls_col: int, serie: str) -> dict | None:
    """One element formula -> rule node (column letters removed) or None when unknown."""
    f = (f or "").strip().lstrip("=").replace(" ", "")
    m = re.fullmatch(r"SUM\(" + REF + ":" + REF + r"\)", f)
    if m:
        r1, r2 = int(m.group(2)), int(m.group(4))
        labels = [element_rows[r] for r in range(r1, r2 + 1) if r in element_rows]
        if len(labels) != r2 - r1 + 1:
            return None
        return {"tipo": "soma_elementos", "de": labels}
    m = re.fullmatch(r"SUMIFS\(\$?([A-Z]{1,3}):\$?([A-Z]{1,3}),\$?([A-Z]{1,3}):\$?([A-Z]{1,3}),\$?([A-Z]{1,3})\$?(\d+)\)", f)
    if m:
        sum_col, crit_col, label_row = DN.col_to_num(m.group(1)), DN.col_to_num(m.group(3)), int(m.group(6))
        if m.group(1) != m.group(2) or m.group(3) != m.group(4) or sum_col != comp_cols.get(serie) or crit_col != cls_col or label_row not in element_rows:
            return None
        return {"tipo": "soma_classificacao", "classificacao": element_rows[label_row]}
    m = re.fullmatch(r"([+-]?" + REF + r")(([+-]" + REF + r")*)", f)
    if m:
        terms = []
        for sign, _col, row in re.findall(r"([+-]?)\$?([A-Z]{1,3})\$?(\d+)", f):
            if int(row) not in element_rows:
                return None
            terms.append(["-" if sign == "-" else "+", element_rows[int(row)]])
        return {"tipo": "expressao", "termos": terms}
    return None


def matrix_rule(sheet: dict, classifications: list) -> dict:
    """Reads the matrix tab: metadata, component table layout, analysts' fill and the consolidation rule."""
    cells = _cells(sheet)
    out = {"aba": sheet["nome"], "metadados": {}, "layout": None, "preenchimento": [], "elementos_preenchidos": [], "regra": None, "avisos": []}
    out["metadados"] = {"uf": value_right_of(cells, find_label(cells, "estado", "uf")),
                        "minutos_aula": value_right_of(cells, find_label(cells, "tempo", "hora-aula")) or value_right_of(cells, find_label(cells, "hora aula")),
                        "ano": value_right_of(cells, find_label(cells, "ano", "vigencia"))}
    head = find_label(cells, "componente curricular")
    if not head:
        out["avisos"].append("A aba da matriz não tem o cabeçalho 'Componente Curricular'.")
        return out
    name_col, hrow = head
    comp_cols, cls_col, elem_col, elem_cols = {}, None, None, {}
    for (c, r), v in cells.items():
        if r != hrow:
            continue
        t = DN.fold(_text(v))
        for i, s in enumerate(SERIES, start=1):
            if re.fullmatch(rf"{i}a serie", t):
                comp_cols[s] = c
            elif re.fullmatch(rf"aulas semanais - {i}a serie", t):
                elem_cols[s] = c
        if t == "classificacao":
            cls_col = c
        elif t == "elemento":
            elem_col = c
    if len(comp_cols) != 3 or cls_col is None:
        out["avisos"].append("Não encontrei as colunas 1ª/2ª/3ª série e Classificação da tabela de componentes.")
        return out
    out["layout"] = {"linha_cabecalho": hrow, "coluna_nome": DN.num_to_col(name_col), "colunas_series": {k: DN.num_to_col(v) for k, v in comp_cols.items()},
                     "coluna_classificacao": DN.num_to_col(cls_col)}
    r = hrow + 1
    while _text(cells.get((name_col, r))):
        row = {"linha": r, "nome": _text(cells[(name_col, r)]), "classificacao": _text(cells.get((cls_col, r))) or None}
        for s, c in comp_cols.items():
            v = cells.get((c, r))
            row[s] = v["valor"] if v is not None and isinstance(v.get("valor"), (int, float)) and not isinstance(v.get("valor"), bool) else None
        out["preenchimento"].append(row)
        r += 1
    if elem_col is None or len(elem_cols) != 3:
        out["avisos"].append("A aba não tem o bloco 'Elemento' com as aulas semanais por série; sem regra de consolidação.")
        return out
    element_rows, r = {}, hrow + 1
    while _text(cells.get((elem_col, r))):
        element_rows[r] = _text(cells[(elem_col, r)])
        r += 1
    formulas, nodes, unknown = [], [], []
    for row, label in element_rows.items():
        raw = {s: (cells.get((c, row)) or {}).get("formula") for s, c in elem_cols.items()}
        parsed = {s: _parse_formula(raw[s] or "", element_rows, comp_cols, cls_col, s) for s in SERIES}
        formulas.append([label] + [raw[s] for s in SERIES])
        out["elementos_preenchidos"].append({"elemento": label, **{s: (cells.get((elem_cols[s], row)) or {}).get("valor") for s in SERIES}})
        if any(p is None for p in parsed.values()) or not (parsed["serie1"] == parsed["serie2"] == parsed["serie3"]):
            unknown.append(label)
            nodes.append({"elemento": label, "tipo": "desconhecida"})
            continue
        node = {"elemento": label, **parsed["serie1"]}
        if node["tipo"] == "soma_classificacao" and node["classificacao"] not in classifications:
            out["avisos"].append(f"O elemento '{label}' soma uma classificação que não está na lista do template.")
        nodes.append(node)
    canonical = json.dumps({"elementos": nodes, "formulas": formulas}, ensure_ascii=False, sort_keys=True)
    sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    out["regra"] = {"regra_id": "template-revisao-matriz:" + sha[:12], "formula_sha256": sha, "status": "desconhecida" if unknown else "reconhecida",
                    "elementos": nodes, "formulas": formulas, "desconhecidos": unknown}
    return out


HISTORY_KEYS = ("preenchimento", "elementos_preenchidos", "metadados")


def structural_projection(rule: dict) -> dict:
    """The matrix tab without the analysts' values: layout, consolidation rule and warnings only. What the analysts typed
    (components, weekly lessons, classifications, element totals, class-hour minutes, validity year) is left out, so no
    later step can read it as evidence."""
    return {k: v for k, v in rule.items() if k not in HISTORY_KEYS}


def ice_codes(wb: dict) -> dict:
    """{'pedagogicas': [...], 'gestao': [...]} from sheets with 'Código da orientação' + 'Orientação' headers."""
    out = {"pedagogicas": [], "gestao": []}
    for s in wb["abas"]:
        cells = _cells(s)
        code_pos = find_label(cells, "codigo", "orientac")
        if not code_pos:
            continue
        ccol, hrow = code_pos
        text_col = next((c for (c, r), v in cells.items() if r == hrow and DN.fold(_text(v)) in ("orientacao", "orientacoes")), None)
        elem_col = next((c for (c, r), v in cells.items() if r == hrow and DN.fold(_text(v)).startswith("elemento") and "2" not in _text(v)), None)
        kind = "gestao" if "gest" in DN.fold(s["nome"]) else "pedagogicas"
        for (c, r), v in sorted(cells.items(), key=lambda kv: kv[0][1]):
            code = _text(v)
            if c == ccol and r > hrow and CODE_RE.match(code):
                out[kind].append({"codigo": code, "texto": _text(cells.get((text_col, r))) if text_col else "",
                                  "elemento": _text(cells.get((elem_col, r))) if elem_col else "", "aba": s["nome"], "linha": r})
    return out


def build_references(run_dir: Path, manifest: dict, inv: dict) -> dict:
    refs = {"template": {"fonte_id": None, "aba_matriz": None, "classificacoes": [], "aba_classificacoes": None, "codigos": {"pedagogicas": [], "gestao": []},
                         "matriz": None, "historico_isolado": {"orientacoes_preenchidas": 0, "linhas_matriz_preenchidas": 0}, "avisos": []},
            "ice": {"fonte_ids": [], "versao": None, "homologacao": None, "codigos": {"pedagogicas": [], "gestao": []}, "avisos": []}}
    t = refs["template"]
    for f in inv["fontes"]:
        if "template_cluster" not in f["classes"] or not (f["media_type"] or "").endswith("spreadsheetml.sheet"):
            continue
        path = next((run_dir / "originais").glob(f["id"] + ".*"))
        wb = DN.read_workbook(path)
        tab = matrix_tab(wb, manifest["uf"])
        if t["fonte_id"] and not tab:
            continue
        t["fonte_id"] = f["id"]
        t["classificacoes"], t["aba_classificacoes"], warn = classification_list(wb)
        t["avisos"] += warn
        if tab:
            t["aba_matriz"] = tab["nome"]
            rule = matrix_rule(tab, t["classificacoes"])
            t["matriz"] = structural_projection(rule)
            t["historico_isolado"]["linhas_matriz_preenchidas"] = len(rule["preenchimento"])
            t["avisos"] += rule["avisos"]
        else:
            t["avisos"].append(f"O template não tem a aba '2.x Revisão Matriz {manifest['uf']}'.")
        T = _eqv()
        try:
            read = T.read_template(path)
            t["codigos"] = {"pedagogicas": [{"codigo": o["codigo"], "texto": o["orientacao"], "elemento": o.get("grupo", "")} for o in read["abas"].get("1.1", {}).get("orientacoes", [])],
                            "gestao": [{"codigo": o["codigo"], "texto": o["orientacao"], "elemento": o.get("grupo", "")} for o in read["abas"].get("1.2", {}).get("orientacoes", [])]}
            key = f"{manifest['uf']}|{manifest['ano']}"
            t["historico_isolado"]["orientacoes_preenchidas"] = sum(1 for k in read["gabarito"] if "|".join(k.split("|")[2:4]) == key)
        except T.TemplateError as e:
            t["avisos"].append("Abas de orientações do template: " + e.message)
        if tab:
            break
    if not t["fonte_id"]:
        t["avisos"].append("Nenhum template de cluster em XLSX foi lido.")
    ice = refs["ice"]
    for f in inv["fontes"]:
        if "referencial_ice" not in f["classes"]:
            continue
        ice["fonte_ids"].append(f["id"])
        if (f["media_type"] or "").endswith("spreadsheetml.sheet"):
            codes = ice_codes(DN.read_workbook(next((run_dir / "originais").glob(f["id"] + ".*"))))
            for k in codes:
                ice["codigos"][k] += codes[k]
        else:
            ice["avisos"].append(f"{f['id']} não é planilha: os códigos de orientação dele não são lidos automaticamente.")
    hom = manifest.get("homologacao_ice")
    ice["versao"] = (hom or {}).get("versao") or next((e.get("versao") for c in ("referencial_ice",) for e in manifest["entradas"][c] if e.get("versao")), None)
    ice["homologacao"] = hom
    SR.write_json(run_dir / "referencias.json", refs)
    return refs


def load_references(run_dir: Path) -> dict:
    refs = SR.read_json(run_dir / "referencias.json")
    if refs is None:
        raise ValueError("referencias.json ausente")
    return refs


def rule_approval(refs: dict, manifest: dict) -> dict | None:
    regra = ((refs["template"].get("matriz") or {}).get("regra"))
    if not regra:
        return None
    return next(({"aprovado_por": r["aprovado_por"], "data": r["data"]} for r in manifest.get("regras_homologadas") or [] if r["formula_sha256"] == regra["formula_sha256"]), None)
