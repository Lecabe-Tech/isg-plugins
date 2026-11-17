"""Lessons of the MG 2026 pilot: parallel batches, dry-run check, review queue and the new commands (synthetic data)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QROOT = ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"
sys.path.insert(0, str(QROOT))
import cross_check as CC  # noqa: E402
import orientation_analysis as OA  # noqa: E402
import quality_result as QR  # noqa: E402
import quality_run as RUN  # noqa: E402
from test.quality import q17_fixtures as FX  # noqa: E402
from test.quality.test_q17_orientations import nao, sim  # noqa: E402
from test.quality.test_q17_result import full_cycle  # noqa: E402

CLI = [sys.executable, str(QROOT / "resultado_qualidade.py")]


class BatchesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.run = self.dir / "run"
        RUN.start_run(FX.source_set(self.dir / "src"), self.run)

    def tearDown(self):
        self.tmp.cleanup()

    def test_batches_carry_no_analyst_answers(self):
        out = self.dir / "lotes"
        r = OA.export_batches(self.run, out, size=3)
        self.assertEqual([b["codigos"] for b in r["lotes"]], [3, 2])
        self.assertFalse(r["cobertura_completa"])  # the synthetic DOCX picture is not read yet
        doc = (out / "documentos.md").read_text(encoding="utf-8")
        self.assertIn("## DOC-1:p1", doc)
        self.assertIn("[IMAGEM SEM LEITURA", doc)
        self.assertNotIn("DOC-4", doc)  # the template is not a state orientation document
        batch = json.loads((out / "lote_A.json").read_text(encoding="utf-8"))
        self.assertEqual(set(batch[0]), {"codigo", "tipo", "elemento", "texto"})
        self.assertTrue((out / "INSTRUCOES.md").exists())

    def test_dry_run_check(self):
        RUN.register_image_reading(self.run, "DOC-2:img1", "Organograma")
        r = OA.check_proposals(self.run, [sim("EL1"), sim("EL2", quote="Frase que não existe em nenhum dos documentos estaduais enviados."), nao("PA2"), {"codigo": "XX9"}])
        codes = {p["codigo"] for p in r["problemas"]}
        self.assertEqual(codes, {"EL2", "XX9"})
        self.assertEqual(r["resultaria"], {"sim": 1, "nao": 1, "pendente": 1})
        self.assertFalse((self.run / "orientacoes.json").exists())  # nothing registered


class ReviewQueueTest(unittest.TestCase):
    def test_queue_order_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = full_cycle(Path(tmp))
            OA.register(run, [sim("AC1", quote=FX.ORIENT_P2, rel="Indireta"), {"codigo": "EL2", "presenca": None, "justificativa": "Sem evidência."}])
            CC.register(run, [{"tipo": "exigencia_normativa", "componente": "Química", "ciclo": {"uf": "MG", "ano": 2026, "modelo": "9h"},
                               "unidade": "DOC-5:matriz_referencial_ICE!A3", "trecho_literal": "Química"}])
            res = QR.build(run)
            q = QR.review_queue(res)
            self.assertEqual([i["ordem"] for i in q], list(range(1, len(q) + 1)))
            self.assertEqual(q[0]["prioridade"], min(i["prioridade"] for i in q))
            refs = [i["referencia"] for i in q]
            self.assertTrue(any(r.startswith("NORMATIVO_VS_OFERTA") for r in refs))
            self.assertLess(refs.index("EL2"), refs.index("AC1"))  # pending before low-confidence decided
            self.assertTrue(all(i["decisao"] for i in q))
            self.assertIn("## Fila de revisão", QR.summary_md(res))


class NewCommandsTest(unittest.TestCase):
    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            RUN.start_run(FX.source_set(Path(tmp) / "src", image_page=True), run)
            j = lambda *a: subprocess.run(CLI + list(a) + ["--json"], capture_output=True, text=True, encoding="utf-8")  # noqa: E731
            out = j("imagens", "--pasta", str(run))
            self.assertEqual(sorted(i["unidade"] for i in json.loads(out.stdout)["data"]["imagens"]), ["DOC-1:p3", "DOC-2:img1"])
            out = j("tabela-pdf", "--pasta", str(run), "--unidade", "DOC-1:p2")
            self.assertEqual(out.returncode, 0, out.stdout)
            self.assertEqual(json.loads(j("tabela-pdf", "--pasta", str(run), "--unidade", "DOC-3:Integral 9h!A1").stdout)["code"], "UNIDADE_INVALIDA")
            out = j("orientacoes-lotes", "--pasta", str(run), "--saida", str(Path(tmp) / "lotes"))
            self.assertEqual(len(json.loads(out.stdout)["data"]["lotes"]), 1)
            prop = Path(tmp) / "p.json"
            prop.write_text(json.dumps({"orientacoes": [sim("EL1")]}, ensure_ascii=False), encoding="utf-8")
            out = j("orientacoes-conferir", str(prop), "--pasta", str(run))
            self.assertEqual((out.returncode, json.loads(out.stdout)["code"]), (0, "CONFERIDO"))
            prop.write_text(json.dumps({"orientacoes": [sim("EL1", quote="Trecho inventado que não aparece no documento estadual.")]}, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(j("orientacoes-conferir", str(prop), "--pasta", str(run)).returncode, 1)
            run2 = full_cycle(Path(tmp), "run2")
            QR.write(run2)
            out = j("revisao-fila", str(run2 / QR.RESULT_FILE))
            self.assertEqual(json.loads(out.stdout)["code"], "FILA")


if __name__ == "__main__":
    unittest.main()
