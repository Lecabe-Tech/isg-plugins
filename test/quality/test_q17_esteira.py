"""The analysis pipeline (skill `analisar`): manifest from the files sent and the stage status that drives the loop
(synthetic sources only)."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QROOT = ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"
sys.path.insert(0, str(QROOT))
import cross_check as CC  # noqa: E402
import esteira as ES  # noqa: E402
import matrix_analysis as MA  # noqa: E402
import quality_result as QR  # noqa: E402
import quality_run as RUN  # noqa: E402
import source_resolver as SR  # noqa: E402
import template_fill as TF  # noqa: E402
from test.quality import q17_fixtures as FX  # noqa: E402
from test.quality.test_q17_matrix import proposal  # noqa: E402
from test.quality.test_q17_result import full_cycle  # noqa: E402

CLI = [sys.executable, str(QROOT / "resultado_qualidade.py")]


def cli(*args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    r = subprocess.run(CLI + list(args) + ["--json"], capture_output=True, text=True, encoding="utf-8", env=env)
    return r.returncode, json.loads(r.stdout)


def states(s):
    return {e["etapa"]: e["estado"] for e in s["etapas"]}


class ManifestTest(unittest.TestCase):
    def test_state_documents_feed_both_fronts_and_empty_ice_means_configured(self):
        m = ES.manifest("ce", 2026, ["diretrizes.pdf"], ["cluster4.xlsx"], [], matriz=["matriz.xlsx"], solicitacao="QUA-13")
        SR.validate_manifest(m)
        self.assertEqual((m["uf"], m["solicitacao_id"], m["revisao"]), ("CE", "QUA-13", 1))
        self.assertEqual([e["uri"] for e in m["entradas"]["matriz_estadual"]], ["diretrizes.pdf", "matriz.xlsx"])
        self.assertEqual([e["uri"] for e in m["entradas"]["orientacoes_estaduais"]], ["diretrizes.pdf"])
        self.assertEqual(m["entradas"]["referencial_ice"], [])

    def test_request_id_is_mandatory(self):  # "UF-ANO-01" made two requests of the same UF/year collide (QUA-12 x QUA-13)
        with self.assertRaises(SR.ManifestError) as cm:
            ES.manifest("ce", 2026, ["diretrizes.pdf"], ["cluster4.xlsx"], [])
        self.assertEqual(cm.exception.code, "SOLICITACAO_AUSENTE")

    def test_notion_download_keeps_the_page_link_as_origin(self):
        link = "https://app.notion.com/p/4233eb42d1288193a6c9f8dc77bfbb5e#Orienta%C3%A7%C3%B5es%20estaduais"
        m = ES.manifest("CE", 2026, ["baixados/diretrizes.pdf"], ["baixados/cluster4.xlsx"], [], solicitacao="QUA-13",
                        origens={"baixados/diretrizes.pdf": link})
        SR.validate_manifest(m)
        self.assertEqual(m["entradas"]["orientacoes_estaduais"], [{"uri": link, "copia_local": "baixados/diretrizes.pdf", "papel": "orientacao"}])
        m["entradas"]["orientacoes_estaduais"][0].pop("copia_local")
        with self.assertRaises(SR.ManifestError):  # a Notion attachment is never fetched by the program
            SR.validate_manifest(m)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "Qualidade-CE-2026" / "manifesto.json"
            code, r = cli("manifesto-montar", "--uf", "CE", "--ano", "2026", "--solicitacao", "QUA-13", "--estado", "a.pdf", "b.docx", "--template", "c.xlsx", "--saida", str(out))
            self.assertEqual((code, r["code"]), (0, "MANIFESTO_MONTADO"))
            self.assertIn("referencial configurado", r["message"])
            self.assertEqual(len(json.loads(out.read_text(encoding="utf-8"))["entradas"]["orientacoes_estaduais"]), 2)
            code, r = cli("manifesto-montar", "--uf", "CE", "--ano", "2026", "--solicitacao", "QUA-13", "--estado", "a.pdf", "--saida", str(out))
            self.assertEqual((code, r["code"]), (1, "CLASSE_AUSENTE"))


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_folder_starts_with_the_inputs(self):
        s = ES.status(self.dir / "nada")
        self.assertEqual((s["proxima"], s["concluida"]), ("entradas", False))

    def test_stages_follow_the_run(self):
        run = self.dir / "run"
        RUN.start_run(FX.source_set(self.dir / "src"), run)
        s = ES.status(run)
        self.assertEqual(states(s)["entradas"], "feita")
        self.assertEqual(s["proxima"], "imagens")  # the DOCX picture is still unread
        RUN.register_image_reading(run, "DOC-2:img1", "Organograma sintético")
        self.assertEqual(ES.status(run)["proxima"], "matriz")
        MA.register(run, proposal(next(f["id"] for f in RUN.load_inventory(run)["fontes"] if f["nome"] == "matriz.xlsx")))
        s = ES.status(run)
        self.assertEqual((states(s)["matriz"], s["proxima"]), ("feita", "orientacoes"))

    def test_cross_check_and_result_wait_for_earlier_stages(self):
        run = self.dir / "run"
        RUN.start_run(FX.source_set(self.dir / "src"), run)
        CC.run(run)
        QR.write(run)  # a partial result exists, but images, matrix and orientations are still open
        s = ES.status(run)
        self.assertEqual((states(s)["cruzamento"], states(s)["resultado"]), ("pendente", "pendente"))

    def test_complete_and_stale_after_a_change(self):
        run = full_cycle(self.dir)
        CC.run(run)
        self.assertTrue(QR.write(run)["ok"])
        self.assertEqual(ES.status(run)["proxima"], "template")  # the filled template is the last stage
        time.sleep(0.05)
        TF.fill(run)
        s = ES.status(run)
        self.assertTrue(s["concluida"], s)
        code, r = cli("esteira", "--pasta", str(run))
        self.assertEqual((code, r["data"]["concluida"]), (0, True))
        time.sleep(0.05)
        MA.register(run, proposal(next(f["id"] for f in RUN.load_inventory(run)["fontes"] if f["nome"] == "matriz.xlsx")))
        s = ES.status(run)  # the matrix changed after the result: cross-check and result must run again
        self.assertEqual((s["proxima"], s["concluida"]), ("cruzamento", False))


if __name__ == "__main__":
    unittest.main()
