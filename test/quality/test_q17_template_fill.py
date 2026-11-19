"""Filled copy of the cluster template (lesson of the CE 2026 pilot), plus the two fixes of that run: selection quotes
outside the matrix table and image-read values counting as an offer (synthetic sources only)."""
import json
import re
import sys
import tempfile
import time
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QROOT = ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"
sys.path.insert(0, str(QROOT))
import cross_check as CC  # noqa: E402
import document_normalizer as DN  # noqa: E402
import esteira as ES  # noqa: E402
import matrix_analysis as MA  # noqa: E402
import quality_result as QR  # noqa: E402
import quality_run as RUN  # noqa: E402
import template_fill as TF  # noqa: E402
import template_rules as TR  # noqa: E402
from test.quality import q17_fixtures as FX  # noqa: E402
from test.quality.test_q17_matrix import SHEET, proposal  # noqa: E402
from test.quality.test_q17_result import full_cycle  # noqa: E402


def matrix_doc(run):
    return next(f["id"] for f in RUN.load_inventory(run)["fontes"] if f["nome"] == "matriz.xlsx")


class FillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cycle(self, prop=None):
        run = full_cycle(self.dir)
        if prop:
            MA.register(run, prop(matrix_doc(run)))
        CC.run(run)
        self.assertTrue(QR.write(run)["ok"])
        return run

    def test_needs_a_result(self):
        run = self.dir / "run"
        RUN.start_run(FX.source_set(self.dir / "src"), run)
        with self.assertRaises(TF.FillError) as e:
            TF.fill(run)
        self.assertEqual(e.exception.code, "RESULTADO_AUSENTE")

    def test_orientations_one_line_each_with_page_and_quote(self):
        run = self.cycle()
        r = TF.fill(run)
        out = Path(r["arquivo"])
        self.assertEqual(out.parent, run.parent)
        self.assertEqual(r["orientacoes"]["pedagogicas"]["Sim"] + r["orientacoes"]["gestao"]["Sim"], 3)
        T = TR._eqv()
        g = {k: v for k, v in T.read_template(out)["gabarito"].items() if k.endswith("|MG|2026")}
        self.assertEqual(g["1.1|EL1|MG|2026"]["valor"], "Sim")
        self.assertRegex(g["1.1|EL1|MG|2026"]["comentario"], r'^Pág\. \d+ \(diretrizes\): "')
        self.assertEqual(g["1.1|EL2|MG|2026"]["valor"], "Não")
        self.assertIn("Ausência verificada em:", g["1.1|EL2|MG|2026"]["comentario"])

    def test_copy_is_valid_and_untouched_elsewhere(self):
        run = self.cycle()
        out = Path(TF.fill(run)["arquivo"])
        src = next((run / "originais").glob(TR.load_references(run)["template"]["fonte_id"] + ".xlsx"))
        with zipfile.ZipFile(src) as a, zipfile.ZipFile(out) as b:
            for n in b.namelist():
                if n.endswith((".xml", ".rels")):
                    ET.fromstring(b.read(n))  # every part is well-formed XML
            self.assertNotIn("xl/calcChain.xml", b.namelist())
            self.assertIn('fullCalcOnLoad="1"', b.read("xl/workbook.xml").decode())
            same = [n for n in a.namelist() if n in b.namelist() and a.read(n) == b.read(n)]
            self.assertTrue(any(n.startswith("xl/worksheets/") for n in same))  # sheets not filled stay byte for byte
        self.assertEqual(src.read_bytes()[:4], b"PK\x03\x04")
        self.assertEqual(TF.default_path(run), out)

    def test_matrix_tab_with_range_and_lines_added_up(self):
        def prop(doc):
            p = proposal(doc)
            sheet = p["selecao"]["unidades"][0]
            dup = json.loads(json.dumps(p["componentes"][3]))  # 'Eletiva' twice in the source: one template line
            p["componentes"].append(dup)
            p["total_linhas_fonte"] = len(p["componentes"])
            p["componentes"][0]["aulas_semanais"]["serie1"] = {"faixa": [4, 5], "unidade": f"{sheet}!F4", "trecho_literal": "4 ou 5 aulas"}
            return p
        tmp = self.dir
        run = tmp / "run"
        RUN.start_run(FX.source_set(tmp / "src-run", range_note=True), run)
        RUN.register_image_reading(run, "DOC-2:img1", "Organograma sintético")
        MA.register(run, prop(matrix_doc(run)))
        CC.run(run)
        self.assertTrue(QR.write(run)["ok"])
        r = TF.fill(run)
        self.assertEqual(r["linhas_matriz"], len(FX.MATRIX_ROWS))
        wb = DN.read_workbook(Path(r["arquivo"]))
        tab = TR.matrix_tab(wb, "MG")
        rows = TR.matrix_rule(tab, FX.CLASSES)["preenchimento"]
        cells = TR._cells(tab)
        lay = TR.matrix_rule(tab, FX.CLASSES)["layout"]
        first = lay["linha_cabecalho"] + 1
        c1 = DN.col_to_num(lay["colunas_series"]["serie1"])
        self.assertEqual(cells[(c1, first)]["valor"], "4 ou 5")  # the range stays a range
        eletiva = next(x for x in rows if x["nome"] == "Eletiva")
        self.assertEqual((eletiva["serie1"], eletiva["serie2"], eletiva["serie3"]), (4, 4, 4))
        self.assertEqual(sum(1 for x in rows if x["nome"] == "Eletiva"), 1)

    def test_pipeline_ends_with_the_filled_template(self):
        run = self.cycle()
        s = ES.status(run)
        self.assertEqual((s["proxima"], s["concluida"]), ("template", False))
        time.sleep(0.05)
        TF.fill(run)
        self.assertTrue(ES.status(run)["concluida"])


class PrefilledTemplateTest(unittest.TestCase):
    """MG 2026 rerun: the template arrived filled by the analysts; nothing of that fill may stay in the copy."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.run = full_cycle(self.dir, real_layout=True)
        CC.run(self.run)
        self.assertTrue(QR.write(self.run)["ok"])

    def tearDown(self):
        self.tmp.cleanup()

    def sheets(self, path):
        return {s["nome"]: TR._cells(s) for s in DN.read_workbook(Path(path))["abas"]}

    def text(self, cells, ref):
        return TR._text(cells.get(DN.split_ref(ref)))

    def test_whole_uf_block_is_replaced(self):
        r = TF.fill(self.run)
        self.assertGreater(r["preenchimento_anterior"]["orientacoes"], 0)
        self.assertTrue(any("paridade" in a for a in r["avisos"]))
        s = self.sheets(r["arquivo"])["1.1 Base orient. pedagógicas"]
        for row in range(10, 10 + len(FX.ICE_PED)):
            self.assertIn(self.text(s, f"G{row}"), ("Sim", "Não", "Pendente"))
            self.assertNotIn("antigo", self.text(s, f"H{row}"))
            self.assertEqual(self.text(s, f"I{row}"), "")  # the second observation column of the block is emptied
            self.assertEqual((self.text(s, f"J{row}"), self.text(s, f"K{row}")), ("Sim", "comentário de SP"))  # other UF untouched
        g = self.sheets(r["arquivo"])["1.2 Base orient. gestão"]
        self.assertNotIn("antigo", self.text(g, "H10"))

    def test_matrix_notes_replaced_and_template_formulas_kept(self):
        out = TF.fill(self.run)["arquivo"]
        m = self.sheets(out)["2.1 Revisão Matriz MG"]
        self.assertTrue(self.text(m, "F5").startswith("Preenchido pelo plugin de Qualidade"))
        self.assertEqual(self.text(m, "N15"), "")  # analysts' note beside the table
        i12 = m.get(DN.split_ref("I12")) or {}
        self.assertTrue(i12.get("formula"))
        self.assertNotIn("antiga", str(i12.get("valor") or ""))  # no stale cached text of the old note

    def test_only_the_analysed_uf_is_visible(self):
        out = TF.fill(self.run)["arquivo"]
        with zipfile.ZipFile(out) as z:
            wb = z.read("xl/workbook.xml").decode("utf-8")
            sheet11 = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertRegex(wb, r'<sheet state="hidden" name="2\.2 Revisão Matriz SP"')
        hidden = TF.Sheet(sheet11, TF.Styles(None)).hidden_columns()
        self.assertEqual(hidden, {10, 11})  # SP 2026 columns J and K
        out2 = TF.fill(self.run, self.dir / "todas.xlsx", somente_uf=False)["arquivo"]
        with zipfile.ZipFile(out2) as z:
            self.assertNotIn('state="hidden" name="2.2', z.read("xl/workbook.xml").decode("utf-8"))


class SheetColumnsTest(unittest.TestCase):
    def test_hidden_and_hiding_columns(self):
        xml = ('<worksheet><cols><col min="1" max="3" width="5" customWidth="1"/><col min="9" max="9" width="7" hidden="1" customWidth="1"/></cols>'
               '<sheetData/></worksheet>')
        sh = TF.Sheet(xml, TF.Styles(None))
        self.assertEqual(sh.hidden_columns(), {9})
        sh.hide_columns({2, 10})
        self.assertEqual(sh.hidden_columns(), {2, 9, 10})
        cols = re.findall(r"<col [^>]*/>", sh.xml)
        self.assertEqual([tuple(map(int, re.search(r'min="(\d+)"[^>]*max="(\d+)"', c).groups())) for c in cols], [(1, 1), (2, 2), (3, 3), (9, 9), (10, 10)])
        self.assertTrue(all('width="5"' in c for c in cols[:3]))  # the split keeps the width of the original span


class CeFixesTest(unittest.TestCase):
    def test_selection_quote_outside_the_table_but_same_document(self):
        with tempfile.TemporaryDirectory() as t:
            run = Path(t) / "run"
            RUN.start_run(FX.source_set(Path(t) / "src"), run)
            doc = matrix_doc(run)
            p = proposal(doc)
            p["selecao"]["evidencias"] = [{"unidade": f"{doc}:Técnico!A1", "trecho_literal": "MATRIZ CURRICULAR - ENSINO MÉDIO INTEGRADO"},
                                          {"unidade": "DOC-1:p1", "trecho_literal": "Diretrizes pedagógicas da rede estadual 2026"}]
            MA.register(run, p)
            sel = json.loads((run / "matriz.json").read_text(encoding="utf-8"))["selecao"]
            self.assertEqual([e["verificacao"] for e in sel["evidencias"]], ["conferida"])
            self.assertTrue(any("não é do documento da matriz" in m for m in sel["motivos"]))

    def test_image_read_value_counts_as_offer(self):
        cell = {"valor": None, "status": "nao_verificado", "valor_proposto": 2, "evidencia": None, "motivo": "conteúdo em imagem"}
        self.assertTrue(MA.offered(cell))
        self.assertFalse(MA.offered({**cell, "valor_proposto": 0}))
        self.assertFalse(MA.offered({**cell, "valor_proposto": None}))


if __name__ == "__main__":
    unittest.main()
