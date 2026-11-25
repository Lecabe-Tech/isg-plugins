"""Shared decision policy of the Quality flow (SPEC-017): one place for the technical confidence floor.

The Quality flow uses 70% as the minimum technical confidence for orientations, matrix classifications and the yellow
marks of the filled template. The legacy EQV flow keeps its own `DEFAULT_MINIMUM = 85` (`isg_eqv.rules`): it has other
consumers and is not changed here.

Confidence never replaces evidence. Above 70% a decision still goes to review when:
  * the only verified evidence is indirect (relation 'Indireta') or comes from an unreliable page or an image reading;
  * a 'Não' was given while flagged pages or pending images could hide the orientation;
  * the quote is missing, invented or from a source that is not a state document (then it is not even a decision);
  * a matrix value was read from an image, is a range, diverges between readings or was not verified.
The EQV caps (84 for indirect, 75 for unreliable/absence risk) were below 85 and so forced review by themselves; with a
70% floor they no longer do, so the review is made explicit by `review_reasons()` instead of relying on the percentage.
"""
from __future__ import annotations

QUALITY_MIN_CONFIDENCE = 70

REASON_INDIRECT = "evidência só indireta: o documento evidencia a orientação sem afirmá-la (revisão humana, mesmo acima de 70%)"
REASON_UNRELIABLE = "evidência só de página com aviso ou de leitura de imagem (revisão humana, mesmo acima de 70%)"
REASON_ABSENCE_RISK = "Não com páginas com aviso ou imagens pendentes que poderiam conter a orientação (revisão humana, mesmo acima de 70%)"


def review_reasons(presenca: str | None, evidencias_eqv: list, contexto: dict) -> list:
    """Reasons that keep a technically decided orientation in review regardless of the confidence value.
    evidencias_eqv: [{'verificada', 'relacao', 'origem', 'pagina_nao_confiavel'}] (the EQV adapter format)."""
    out = []
    if presenca == "Sim":
        verified = [e for e in evidencias_eqv if e.get("verificada")]
        if verified and all(e.get("relacao") == "Indireta" for e in verified):
            out.append(REASON_INDIRECT)
        if verified and all(e.get("origem", "texto") != "texto" or e.get("pagina_nao_confiavel") for e in verified):
            out.append(REASON_UNRELIABLE)
    elif presenca == "Não":
        if contexto.get("risco_de_ocultar"):
            out.append(REASON_ABSENCE_RISK)
    return out
