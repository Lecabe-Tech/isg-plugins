"""Test-only fixture documents with known ground truth (SPEC-003 VAL-C01)."""
from __future__ import annotations

from .pdfgen import PdfDoc

T = PdfDoc.text

HEADER = "Currículo Paulista — Ensino Médio"
FOOTER = "Secretaria da Educação"

FILLER = [
    "O Projeto de Vida orienta os estudantes na construção de objetivos pessoais, acadêmicos e profissionais, valorizando a escuta e a reflexão sobre escolhas futuras.",
    "As competências socioemocionais são desenvolvidas de forma transversal, com atividades colaborativas que estimulam a empatia, a responsabilidade e a autonomia.",
    "A avaliação formativa acompanha o percurso de cada estudante e orienta o planejamento das próximas etapas do trabalho pedagógico em sala de aula.",
]
HYPHEN_PARA_TRUE = "A proposta é desenvolver um currículo interdisciplinar que integre as áreas do conhecimento e a vida dos estudantes."
HYPHEN_PARA_LINES = ["A proposta é desenvolver um currículo inter-", "disciplinar que integre as áreas do conhecimento e a vida dos estudantes."]


def wrap(text: str, width: int = 82) -> list:
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


def _header_footer(page_no: int) -> list:
    return [T(60, 806, HEADER, size=9), T(60, 36, FOOTER, size=9), T(480, 36, f"Página {page_no}", size=9)]


def simple_doc(pages: int = 6, title: str = "Currículo Paulista"):
    """Returns (PdfDoc, truth) where truth lists, per page, the heading text and the paragraphs exactly as they should come out."""
    doc = PdfDoc(title=title)
    truth = []
    for p in range(1, pages + 1):
        ops = _header_footer(p)
        paragraphs, heading = [], None
        y = 760.0
        if p % 2 == 1:
            heading = f"{p}. Projeto de Vida {p}"
            ops.append(T(60, y, heading, font="F2", size=16))
            y -= 30
        blocks = [("lines", HYPHEN_PARA_LINES, HYPHEN_PARA_TRUE)]
        for k in range(3):
            para = f"{FILLER[(p + k) % 3]} {FILLER[(p + k + 1) % 3]}"
            blocks.append(("wrap", wrap(para), para))
        for _, lines, true in blocks:
            for ln in lines:
                ops.append(T(60, y, ln))
                y -= 14
            y -= 10
            paragraphs.append(true)
        doc.add_page(ops)
        truth.append({"page": p, "heading": heading, "paragraphs": paragraphs})
    return doc, truth


COL_A = [
    "A escola organiza o trabalho em duas frentes complementares, ligando conteúdo e prática de forma que os estudantes percebam sentido no que aprendem em cada etapa",
]
COL_B = [
    "Os professores planejam juntos as sequências didáticas e compartilham os resultados das atividades para ajustar o ensino às necessidades reais da turma durante o ano letivo",
]


def columns_doc():
    doc = PdfDoc(title="Documento em duas colunas")
    ops = [T(60, 780, "Orientações pedagógicas", font="F2", size=16)]
    left = wrap(COL_A[0] * 3, 40)
    right = wrap(COL_B[0] * 3, 40)
    y = 740.0
    for a, b in zip(left, right):
        ops.append(T(50, y, a))
        ops.append(T(330, y, b))
        y -= 14
    doc.add_page(ops)
    return doc, {"left": " ".join(left), "right": " ".join(right)}


def mixed_doc():
    """Page 1 text + image, page 2 table, page 3 empty, page 4 text."""
    doc = PdfDoc(title="Misto")
    ops1 = [T(60, 780, "1. Visão geral", font="F2", size=16)]
    y = 740.0
    for ln in wrap(FILLER[0], 80):
        ops1.append(T(60, y, ln))
        y -= 14
    ops1.append(PdfDoc.image(60, y - 90, 120, 80))
    y -= 120
    for ln in wrap(FILLER[1], 80):
        ops1.append(T(60, y, ln))
        y -= 14
    doc.add_page(ops1)

    ops2 = [T(60, 780, "Quadro 1 — Componentes", font="F2", size=14)]
    rows = [("Componente", "Carga horária", "Etapa"), ("Projeto de Vida", "2 aulas", "1º ano"), ("Cultura Digital", "1 aula", "2º ano"), ("Protagonismo", "2 aulas", "3º ano"), ("Empreendedorismo", "1 aula", "3º ano")]
    y = 740.0
    for a, b, c in rows:
        ops2 += [T(60, y, a), T(220, y, b), T(380, y, c)]
        y -= 16
    for ln in wrap(FILLER[2], 80):
        ops2.append(T(60, y - 20, ln))
        y -= 14
    doc.add_page(ops2)

    doc.add_page([])  # empty page

    ops4 = []
    y = 780.0
    for ln in wrap(FILLER[0] + " " + FILLER[1], 80):
        ops4.append(T(60, y, ln))
        y -= 14
    doc.add_page(ops4)
    return doc


def many_empty_doc():
    """5 pages, 2 without text (40 %): status must be Reprovado, but every page must still be produced."""
    doc = PdfDoc(title="Muitas páginas vazias")
    for i in range(5):
        if i in (1, 3):
            doc.add_page([])
        else:
            ops, y = [], 780.0
            for ln in wrap(FILLER[i % 3], 80):
                ops.append(T(60, y, ln))
                y -= 14
            doc.add_page(ops)
    return doc


def big_doc(pages: int = 300):
    doc = PdfDoc(title="Documento grande")
    for p in range(1, pages + 1):
        ops = _header_footer(p)
        y = 760.0
        if p % 5 == 1:
            ops.append(T(60, y, f"{p // 5 + 1}. Seção {p // 5 + 1}", font="F2", size=16))
            y -= 30
        for k in range(3):
            for ln in wrap(f"{FILLER[(p + k) % 3]} {FILLER[(p + k + 1) % 3]}"):
                ops.append(T(60, y, ln))
                y -= 14
            y -= 10
        doc.add_page(ops)
    return doc
