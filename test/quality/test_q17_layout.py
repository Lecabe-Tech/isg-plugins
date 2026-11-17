"""Grade column of PDF table values from the text layout (lesson of the MG 2026 pilot; synthetic PDFs only)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QROOT = ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"
sys.path.insert(0, str(QROOT))
import matrix_analysis as MA  # noqa: E402
import pdf_layout as PL  # noqa: E402
import quality_run as RUN  # noqa: E402
from test.cfp import pdfgen  # noqa: E402
from test.quality import q17_fixtures as FX  # noqa: E402

T = pdfgen.PdfDoc.text
FULL = "5 200 166:40:00 6 240 200:00:00 6 240 200:00:00"
LONE = "3 120 100:00:00"


def table_pdf(path: Path) -> Path:
    """Page 1: a 9h matrix table with isolated values in grade columns 1, 2 and 3. Page 2: a table with too many columns."""
    doc = pdfgen.PdfDoc(title="Matriz sintética")
    doc.add_page([T(60, 760, "MATRIZ CURRICULAR ENSINO MÉDIO EM TEMPO INTEGRAL 9 HORAS - PROPEDÊUTICO"),
                  T(300, 730, "1º Ano 2º Ano 3º Ano"),
                  T(60, 700, "Língua Portuguesa"), T(300, 700, FULL),
                  T(60, 680, "Leitura e Protagonismo"), T(300, 680, LONE),
                  T(60, 660, "Projeto Integrador A"), T(420, 660, LONE),
                  T(60, 640, "Projeto Integrador B"), T(540, 640, LONE),
                  T(60, 610, "Duração da aula: 50 minutos")])
    doc.add_page([T(60, 760, "MATRIZ 9 HORAS"), T(60, 700, "Química"), T(200, 700, "2 80"), T(300, 700, "2 80"), T(400, 700, "1 40"), T(500, 700, "9 9")])
    doc.save(path)
    return path


class LayoutTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = table_pdf(Path(self.tmp.name) / "matriz.pdf")

    def tearDown(self):
        self.tmp.cleanup()

    def test_columns_rebuilt(self):
        t = PL.page_table(self.pdf, 1)
        self.assertEqual(t["orientacao"], "retrato")
        self.assertEqual(len(t["colunas"]), 3)
        self.assertEqual(t["grupo"], 3)
        rows = {r["rotulo"]: [g[0] if g else None for g in r["grupos"]] for r in t["linhas"]}
        self.assertEqual(rows["Língua Portuguesa"], ["5", "6", "6"])
        self.assertEqual(rows["Leitura e Protagonismo"], ["3", None, None])
        self.assertEqual(rows["Projeto Integrador A"], [None, "3", None])
        self.assertEqual(rows["Projeto Integrador B"], [None, None, "3"])

    def test_check_cell(self):
        self.assertEqual(PL.check_cell(self.pdf, 1, "Projeto Integrador A", 2, 3)["estado"], "confere")
        self.assertEqual(PL.check_cell(self.pdf, 1, "Projeto Integrador A", 1, None)["estado"], "confere")  # blank in grade 1
        d = PL.check_cell(self.pdf, 1, "Projeto Integrador A", 1, 3)
        self.assertEqual(d["estado"], "diverge")
        self.assertIn("coluna(s) [2]", d["motivo"])
        self.assertEqual(PL.check_cell(self.pdf, 1, "Língua Portuguesa", 2, 5)["estado"], "diverge")
        self.assertEqual(PL.check_cell(self.pdf, 1, "Componente inexistente", 1, 1)["estado"], "indeterminado")
        u = PL.check_cell(self.pdf, 2, "Química", 1, 2)
        self.assertEqual(u["estado"], "indeterminado")  # 4 column positions for 3 grades: nothing is confirmed


class LayoutInRegistrationTest(unittest.TestCase):
    def test_register_confirms_or_rejects_the_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            table_pdf(src / "matriz.pdf")
            FX.template_xlsx(src / "template.xlsx")
            FX.ice_xlsx(src / "ice.xlsx")
            FX.orientations_pdf(src / "orient.pdf")
            m = {"schema_version": "1.0", "solicitacao_id": "SINT-LAYOUT", "uf": "MG", "ano": 2026, "modelo": "9h", "modalidade": "propedeutico",
                 "entradas": {"orientacoes_estaduais": [{"uri": "orient.pdf"}], "matriz_estadual": [{"uri": "matriz.pdf"}],
                              "template_cluster": [{"uri": "template.xlsx"}], "referencial_ice": [{"uri": "ice.xlsx"}]}}
            (src / "m.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
            run = Path(tmp) / "run"
            RUN.start_run(src / "m.json", run)
            P1, P2 = "DOC-2:p1", "DOC-2:p2"

            def comp(name, vals, unit=P1, quote=None):
                q = quote or name
                return {"nome_original": name, "nome_evidencia": {"unidade": unit, "trecho_literal": name},
                        "aulas_semanais": {s: ({"valor": v, "unidade": unit, "trecho_literal": q} if v is not None else
                                               {"valor": None, "motivo": "ausente_na_fonte", "unidade": unit, "trecho_literal": q}) for s, v in zip(MA.SERIES, vals)},
                        "classificacao": "Formação Geral Básica", "base_classificacao": "funcao_educacional", "confianca_classificacao": 95,
                        "justificativa_classificacao": "Componente da formação geral básica pela sua função."}
            prop = {"selecao": {"fonte_id": "DOC-2", "unidades": [P1, P2], "oferta": {"modalidade": "propedeutico", "modelo": "9h", "etapa": None}, "vigencia": "2026",
                                "evidencias": [{"unidade": P1, "trecho_literal": "MATRIZ CURRICULAR ENSINO MÉDIO EM TEMPO INTEGRAL 9 HORAS"}]},
                    "minutos_aula": {"valor": 50, "unidade": P1, "trecho_literal": "Duração da aula: 50 minutos"}, "total_linhas_fonte": 5,
                    "componentes": [comp("Língua Portuguesa", (5, 6, 6), quote="Língua Portuguesa " + FULL),
                                    comp("Projeto Integrador A", (None, 3, None), quote="Projeto Integrador A " + LONE),
                                    comp("Projeto Integrador B", (3, None, None), quote="Projeto Integrador B " + LONE),  # wrong grade: the 3 is in grade 3
                                    comp("Química", (2, 2, 1), unit=P2, quote="Química 2 80")]}
            MA.register(run, prop)
            c = {x["nome_original"]: x for x in MA.section(run)[0]["componentes"]}
            lp = c["Língua Portuguesa"]["aulas_semanais"]
            self.assertEqual([lp[s]["evidencia"]["metodo"] for s in MA.SERIES], ["celula_layout_conferida"] * 3)
            pa = c["Projeto Integrador A"]["aulas_semanais"]
            self.assertEqual((pa["serie2"]["status"], pa["serie2"]["evidencia"]["metodo"]), ("verificado", "celula_layout_conferida"))
            self.assertEqual((pa["serie1"]["status"], pa["serie1"]["evidencia"]["metodo"]), ("ausente_na_fonte", "celula_layout_conferida"))
            pb = c["Projeto Integrador B"]["aulas_semanais"]
            self.assertEqual((pb["serie1"]["valor"], pb["serie1"]["status"]), (None, "nao_verificado"))  # the quote matched, the column did not
            self.assertIn("pela posição na tabela", pb["serie1"]["motivo"])
            self.assertEqual(pb["serie3"]["status"], "nao_verificado")  # declared blank, but the layout has 3 there
            q = c["Química"]
            self.assertEqual(q["aulas_semanais"]["serie1"]["status"], "verificado")  # quote kept...
            self.assertTrue(q["revisar"])  # ...but the unreadable layout is flagged for review
            self.assertTrue(any("coluna não foi conferida" in m for m in q["motivos"]))


if __name__ == "__main__":
    unittest.main()
