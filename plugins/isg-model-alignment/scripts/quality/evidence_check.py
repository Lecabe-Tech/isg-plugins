"""SPEC-017: checks one cited piece of evidence against the located units of the run (shared by every front).

A quote counts only if it is in the cited unit (letters and digits, ignoring accents, case, spacing and punctuation:
the EQV rule); a spreadsheet value counts only if the cited cell holds that number; anything read from an image is
`nao_verificavel` (AI-made) and never becomes a verified value.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent / "eqv") not in sys.path:
    sys.path.insert(0, str(HERE.parent / "eqv"))
from isg_eqv.evidence import fragments, squash  # noqa: E402

IMAGE_STATUS = ("requer_interpretacao", "interpretada_ia")
STATE_CLASSES = {"orientacoes_estaduais", "matriz_estadual"}
NOT_STATE = {"template_cluster", "referencial_ice"}


def quote_found(quote: str, text: str, min_len: int) -> tuple:
    frags = fragments(quote or "")
    if not frags:
        return False, "citação vazia"
    if sum(len(f) for f in frags) < min_len:
        return False, "citação curta demais para servir de prova"
    page = squash(text)
    if any(f not in page for f in frags):
        return False, "trecho não encontrado na unidade citada"
    return True, ""


def number_in(quote: str, number) -> bool:
    n = int(number) if float(number).is_integer() else number
    return re.search(r"(?<![\d,.])%s(?![\d]|[,.]\d)" % re.escape(str(n)), quote or "") is not None


def in_region(uid: str, region: list) -> bool:
    """A region is a unit id (PDF page, text block), a sheet ('DOC-1:Aba') or a DOCX table ('DOC-2:tab1')."""
    return any(uid == r or uid.startswith(r + "!") or uid.startswith(r + "-l") for r in region)


def check(ref: dict, index: dict, doc_classes: dict, allowed: tuple, min_len: int = 20, number=None, region: list | None = None) -> dict:
    """ref: {'unidade', 'trecho_literal', 'relacao'?}; index: {unit id: (doc_id, unit)}; doc_classes: {doc_id: [classes]}.
    Returns {'ok': bool, 'motivo': str, 'evidencia': schema evidence | None}."""
    uid = str((ref or {}).get("unidade") or "")
    quote = str((ref or {}).get("trecho_literal") or "")
    rel = (ref or {}).get("relacao")
    if uid not in index:
        return {"ok": False, "motivo": f"unidade inexistente: {uid or '(vazia)'}", "evidencia": None}
    doc_id, unit = index[uid]
    ev = {"fonte_id": doc_id, "unidade": uid, "localizacao": unit["localizacao"], "trecho_literal": quote,
          "metodo": "citacao_conferida", "verificacao": "nao_conferida", "relacao": rel if rel in ("Equivalente", "Parte de", "Cobre", "Indireta", "Distinto") else None}
    if not set(doc_classes.get(doc_id, [])) & set(allowed):
        return {"ok": False, "motivo": f"{doc_id} não é fonte aceita para esta evidência ({', '.join(allowed)})", "evidencia": ev}
    wrong = set(doc_classes.get(doc_id, [])) & (NOT_STATE - set(allowed))
    if wrong and set(allowed) & STATE_CLASSES:
        # the same file declared as a state document AND as template or ICE (an input classification mistake): the
        # template's historical answers and the ICE criteria are never proof of what the state offers
        return {"ok": False, "motivo": f"{doc_id} também está declarado como {', '.join(sorted(wrong))}: não serve como prova de oferta estadual", "evidencia": ev}
    if region and not in_region(uid, region):
        return {"ok": False, "motivo": "a unidade está fora da matriz selecionada", "evidencia": ev}
    if unit["status"] in IMAGE_STATUS:
        ev.update(metodo="interpretacao_ia", verificacao="nao_verificavel")
        return {"ok": False, "motivo": "conteúdo em imagem: leitura de IA, não verificável pelo programa", "evidencia": ev}
    if unit["tipo"] == "sheet_cell" and number is not None and not isinstance(unit.get("valor"), str):
        ev["metodo"] = "celula_conferida"
        ev["trecho_literal"] = quote or unit["texto"]
        v = unit.get("valor")
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return {"ok": False, "motivo": "a célula citada não tem número" + (" (fórmula sem valor salvo)" if unit.get("formula") is not None and v is None else ""), "evidencia": ev}
        if float(v) != float(number):
            return {"ok": False, "motivo": f"a célula citada tem {v}, não {number}", "evidencia": ev}
        ev["verificacao"] = "conferida"
        return {"ok": True, "motivo": "", "evidencia": ev}
    found, why = quote_found(quote, unit.get("texto", ""), min_len)
    if not found:
        return {"ok": False, "motivo": why, "evidencia": ev}
    if number is not None and not number_in(quote, number):
        return {"ok": False, "motivo": f"o número {number} não aparece no trecho citado", "evidencia": ev}
    ev["verificacao"] = "conferida"
    return {"ok": True, "motivo": "", "evidencia": ev}
