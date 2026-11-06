"""Decision rules (SPEC-005 4.4, REQ-CRS-02): the AI proposes, the CODE decides value, flag and confidence.

Value is always `Sim` or `Não`. Doubt is shown by the `revisar` flag, the confidence and the reasons, never by an empty cell.
"""
from __future__ import annotations

DEFAULT_MINIMUM = 85
CAP_UNRELIABLE = 75  # evidence only from flagged pages or AI-made image interpretations (SPEC-003 REQ-CAG-04, SPEC-004 REQ-SAG-02)
CAP_INDIRECT = 84  # the document evidences the orientation without stating it: below any default minimum, so it is flagged
CAP_ABSENCE = 90  # a "Não" is weaker proof than a "Sim"
CAP_ABSENCE_RISK = 75  # ... and weaker still when flagged pages or pending images could hide the orientation
ANALYST_CONFIDENCE = 95
VALUES = ("Sim", "Não")
RELATIONS = ("Equivalente", "Parte de", "Cobre", "Indireta", "Distinto")


def normalize_value(v) -> str | None:
    s = str(v or "").strip().lower().replace("ã", "a")
    return {"sim": "Sim", "nao": "Não"}.get(s)


def cap(value: int, ceiling: int) -> int:
    return min(int(value), ceiling)


def absence_is_valid(ausencia) -> bool:
    """A proof of absence names what was considered and where it was looked for (REQ-CMT-06)."""
    return bool(ausencia) and bool(ausencia.get("itens_considerados")) and bool(str(ausencia.get("onde_procurou", "")).strip())


def decide(proposta: dict, evidencias: list, minimo: int = DEFAULT_MINIMUM, contexto: dict | None = None) -> dict:
    """proposta: {'valor', 'confianca', 'ausencia'?}; evidencias: [{'verificada', 'relacao', 'origem', 'pagina_nao_confiavel'}];
    contexto: {'documento_reprovado', 'memoria_em_conflito', 'cobertura_completa', 'risco_de_ocultar'}.
    Returns {'valor', 'revisar', 'confianca', 'motivos': [PT-BR]}."""
    ctx = contexto or {}
    motivos: list = []
    proposed = normalize_value(proposta.get("valor"))
    try:
        conf = max(0, min(100, int(round(float(proposta.get("confianca", 0))))))
    except (TypeError, ValueError):
        conf = 0
        motivos.append("confiança ausente ou inválida")
    verified = [e for e in evidencias if e.get("verificada")]
    if proposed is None:
        motivos.append("valor proposto inválido (use Sim ou Não)")
        proposed = "Não"
        conf = min(conf, 50)
    revisar = False

    if proposed == "Sim":
        if not verified:
            valor = "Não"  # never claim an orientation exists without a quote proven in the document
            revisar = True
            conf = min(conf, 50)
            motivos.append("a IA propôs Sim, mas nenhuma citação foi verificada no documento; o valor fica Não até conferência" if evidencias else "a IA propôs Sim sem citação")
        else:
            valor = "Sim"
            if all(e.get("origem", "texto") != "texto" or e.get("pagina_nao_confiavel") for e in verified):
                conf = cap(conf, CAP_UNRELIABLE)
                motivos.append("a evidência vem só de páginas com aviso do CFP ou de interpretação de imagem feita por IA")
            if all(e.get("relacao") == "Indireta" for e in verified):
                conf = cap(conf, CAP_INDIRECT)
                motivos.append("o documento evidencia a orientação sem afirmá-la diretamente")
    else:
        valor = "Não"
        ausencia = proposta.get("ausencia")
        if not absence_is_valid(ausencia):
            revisar = True
            conf = min(conf, 50)
            motivos.append("Não sem prova de ausência (itens considerados e onde se procurou)")
        else:
            conf = cap(conf, CAP_ABSENCE)
            if not ctx.get("cobertura_completa", True) or ctx.get("risco_de_ocultar"):
                conf = cap(conf, CAP_ABSENCE_RISK)
                motivos.append("o inventário não cobre todo o documento, ou há páginas com aviso ou imagens pendentes que poderiam conter a orientação")

    if ctx.get("memoria_em_conflito"):
        revisar = True
        motivos.append("a memória compartilhada diverge do que o documento diz")
    if ctx.get("documento_reprovado"):
        revisar = True
        motivos.append("um dos documentos está Reprovado na qualidade do CFP")
    if conf < minimo:
        revisar = True
        motivos.append(f"confiança {conf}% abaixo do mínimo de {minimo}%")
    return {"valor": valor, "revisar": revisar, "confianca": conf, "motivos": motivos}


def tab_capitalization(valor: str, tab: str) -> str:
    """Tab 1.2 of the template writes SIM/NÃO in upper case; tab 1.1 writes Sim/Não."""
    return valor.upper() if tab == "1.2" else valor
