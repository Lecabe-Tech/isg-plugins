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
    ops1.append(PdfDoc.image(60, y - 210, 300, 200, name="Im2"))  # a real figure: 12 % of the page
    y -= 230
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


def realworld_doc():
    """Patterns found on a real state document (MG 2026): table-of-contents lines with dot leaders, bullets drawn apart from
    their text, bold "Label:" lines, and justified text whose line-end hyphen is a separate fragment at the right margin."""
    doc = PdfDoc(title="Padrões reais")
    ops = [T(60, 780, "SUMÁRIO", font="F2", size=16)]
    y = 750.0
    for line in ("1. Princípios educativos.....................................5", "2. Eixos formativos........................................12", "3. Práticas educativas....................................20"):
        ops.append(T(60, y, line))
        y -= 16
    ops.append(T(60, y - 10, "Equipe escolar:", font="F2", size=11))
    y -= 36
    for item in ("Orientar professores e estudantes sobre as normas", "Verificar o preenchimento do guia de ensino", "Acompanhar a implementação das diretrizes"):
        ops.append(T(60, y, "•"))
        ops.append(T(78, y, item))
        y -= 16
    y -= 14
    # justified text: the hyphen is a separate fragment at the right margin
    rows = [("A coordenação da educação profissional deve orga", "nização do curso e acompanhar os estudantes durante o ano letivo."),
            ("Os projetos integradores ajudam a mobi", "lizar saberes e a monitorar os resultados de cada turma.")]
    for first, rest in rows:
        ops.append(T(60, y, first))
        ops.append(T(540, y, "-"))
        ops.append(T(60, y - 14, rest))
        y -= 38
    doc.add_page(ops)
    return doc


def banner_doc(pages: int = 6):
    """Every page has the same header and footer banner image (decoration) and a small icon; page 3 also has a real figure."""
    doc = PdfDoc(title="Faixas decorativas")
    for p in range(1, pages + 1):
        ops = [PdfDoc.image(0, 792, 595, 50), PdfDoc.image(0, 0, 595, 50)]  # same picture on every page: decoration
        y = 740.0
        for ln in wrap(FILLER[p % 3], 80):
            ops.append(T(60, y, ln))
            y -= 14
        if p in (1, 2):
            ops.append(PdfDoc.image(60, y - 30, 20, 20, name="Im2"))  # a small icon (0.1 % of the page), on 2 of 6 pages
        if p == 3:
            ops.append(PdfDoc.image(60, 300, 400, 250, name="Im3"))  # a real figure (30 % of the page), on 1 page
        doc.add_page(ops)
    return doc


def narrow_columns_doc():
    """Two text columns with a gutter smaller than the segment gap (found on the CE 2026 document): without start-position
    detection the two columns were glued into one line and read in the wrong order."""
    doc = PdfDoc(title="Colunas estreitas")
    ops = []
    x = 50.0
    for word in "3.2. A comunidade de aprendizagem como modelo de escola".split():  # heading drawn word by word, across the gutter
        ops.append(T(x, 790, word, font="F2", size=14))
        x += len(word) * 7.0 + 4.0
    left = wrap(COL_A[0] * 3, 38)
    right = wrap(COL_B[0] * 3, 38)
    n = min(len(left), len(right))
    left, right = left[:n], right[:n]
    y = 750.0
    for a, b in zip(left, right):
        ops.append(T(50, y, a))
        ops.append(T(282, y, b))  # about 12 pt after the estimated end of the left line
        y -= 14
    doc.add_page(ops)
    return doc, {"left": " ".join(left), "right": " ".join(right)}


def images_doc():
    """SPEC-004: raw RGB (Im4), JPEG (Im5), unsupported CCITT (Im6), indexed (Im7), a drawn chart, a cover that is one image.
    Im4 appears on pages 1, 2 and 6 (3 of 8 pages: not decoration) so it is also a duplicate."""
    doc = PdfDoc(title="Documento com imagens")

    def body(p, y=700.0):
        ops = []
        for ln in wrap(FILLER[p % 3], 80):
            ops.append(T(60, y, ln))
            y -= 14
        return ops, y

    ops, y = body(1)
    ops.append(PdfDoc.image(60, 300, 300, 300, name="Im4"))
    ops.append(T(60, 280, "Figura 1 — Distribuição das matrículas por rede"))
    doc.add_page(ops)
    ops, y = body(2)
    ops.append(PdfDoc.image(60, 300, 300, 300, name="Im5"))
    ops.append(PdfDoc.image(60, 100, 150, 150, name="Im4"))  # same picture as page 1: duplicate
    doc.add_page(ops)
    ops, y = body(3)
    ops.append(PdfDoc.image(60, 300, 300, 300, name="Im6"))  # CCITT: cannot be extracted
    doc.add_page(ops)
    ops, y = body(4)
    ops.append(PdfDoc.image(60, 300, 300, 300, name="Im7"))
    doc.add_page(ops)
    ops, y = body(5)
    ops.append(PdfDoc.vector_chart(60, 200))
    doc.add_page(ops)
    doc.add_page([PdfDoc.image(0, 842, 595, 842, name="Im4")])  # a cover: only one big image, no text
    for p in (7, 8):
        ops, y = body(p)
        doc.add_page(ops)
    return doc
