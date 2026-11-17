"""Lessons of the CE 2026 pilot: ranges in the matrix, configured ICE reference, template of another cluster, repeated
images (synthetic sources; numbers are invented)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
QROOT = ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"
sys.path.insert(0, str(QROOT))
import ice_config as ICE  # noqa: E402
import matrix_analysis as MA  # noqa: E402
import quality_result as QR  # noqa: E402
import quality_run as RUN  # noqa: E402
from test.quality import q17_fixtures as FX  # noqa: E402
from test.quality.test_q17_matrix import SHEET, proposal  # noqa: E402

NO_ENV = {k: v for k, v in os.environ.items() if k != ICE.ENV}


class RangeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name) / "run"
        RUN.start_run(FX.source_set(Path(self.tmp.name) / "src", range_note=True), self.run)

    def tearDown(self):
        self.tmp.cleanup()

    def prop(self, faixa=(4, 5), quote="4 ou 5 aulas"):
        p = proposal()
        p["componentes"][0]["aulas_semanais"]["serie1"] = {"faixa": list(faixa), "unidade": f"{SHEET}!F4", "trecho_literal": quote}
        last = 4 + len(FX.MATRIX_ROWS)
        p["totais_fonte"] = [{"rotulo": "Total semanal", "serie": 1, "valor": sum(r[1] for r in FX.MATRIX_ROWS), "unidade": f"{SHEET}!B{last}"},
                             {"rotulo": "Formação Geral Básica", "classificacao": "Formação Geral Básica", "serie": 1, "valor": 50, "unidade": f"{SHEET}!A2",
                              "trecho_literal": "Duração da hora-aula: 50 minutos"}]
        p["documento_oficial_citado"] = {"titulo": "Matrizes da escola (sintético)", "unidade": f"{SHEET}!F4", "trecho_literal": "conforme a matriz da escola"}
        return p

    def test_range_is_kept_never_resolved(self):
        MA.register(self.run, self.prop())
        sec, pend = MA.section(self.run)
        cell = sec["componentes"][0]["aulas_semanais"]["serie1"]
        self.assertEqual((cell["status"], cell["valor"], cell["faixa"]["min"], cell["faixa"]["max"]), ("faixa", None, 4, 5))
        self.assertEqual(sec["completude"]["celulas_em_faixa"], 1)
        codes = {p["codigo"]: p["detalhe"] for p in pend}
        self.assertIn("VALOR_EM_FAIXA", codes)
        self.assertIn("Matrizes da escola (sintético)", codes["VALOR_EM_FAIXA"])  # the cited document is asked for, never searched
        self.assertTrue(sec["componentes"][0]["revisar"])

    def test_source_totals_are_checked_against_the_ranges(self):
        MA.register(self.run, self.prop())
        sec, pend = MA.section(self.run)
        total, fgb = sec["totais_fonte"]
        self.assertEqual((total["estado"], total["soma_min"], total["soma_max"]), ("cabe", 17, 18))
        self.assertEqual((fgb["estado"], fgb["soma_min"], fgb["soma_max"]), ("nao_cabe", 9, 10))
        self.assertIn("TOTAL_FONTE_NAO_CABE", [p["codigo"] for p in pend])

    def test_range_quote_must_have_both_ends(self):
        MA.register(self.run, self.prop(faixa=(4, 6)))
        cell = MA.section(self.run)[0]["componentes"][0]["aulas_semanais"]["serie1"]
        self.assertEqual(cell["status"], "nao_verificado")
        self.assertIn("6", cell["motivo"])
        MA.register(self.run, self.prop(faixa=(5, 4)))
        self.assertIn("faixa inválida", MA.section(self.run)[0]["componentes"][0]["aulas_semanais"]["serie1"]["motivo"])

    def test_result_with_range_is_valid_and_readable(self):
        MA.register(self.run, self.prop())
        r = QR.write(self.run)
        self.assertTrue(r["ok"], r["validacao"])
        self.assertEqual(r["resultado"]["schema_version"], "1.2")
        md = Path(r["resumo"]).read_text(encoding="utf-8")
        self.assertIn("| Língua Portuguesa | 4–5 |", md)
        self.assertIn("**não cabe**", md)
        self.assertIn("VALOR_EM_FAIXA", [q["referencia"] for q in QR.review_queue(r["resultado"])])


def ice_folder(base: Path, versao="ICE 2026", aprovado=True, data="2026-11-10", name="ReferenciaisICE", file="ice.xlsx") -> Path:
    folder = base / name
    folder.mkdir(parents=True)
    FX.ice_xlsx(folder / file)
    (folder / ICE.MANIFEST).write_text(json.dumps({"versao": versao, "aprovado": aprovado, "aprovado_por": "Qualidade (sintético)" if aprovado else None,
                                                   "data": data, "referencias": {"orientacoes_pedagogicas": {"arquivo": file, "aba": "x"}}}), encoding="utf-8")
    return folder


class IceConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    @mock.patch.dict(os.environ, NO_ENV, clear=True)
    def test_refusals(self):
        for arg, code in (("", "ICE_NAO_CONFIGURADO"), ("${user_config.quality_ice_reference}", "ICE_NAO_CONFIGURADO"), (str(self.dir / "nao-existe"), "ICE_NAO_CONFIGURADO")):
            with self.subTest(arg=arg), self.assertRaises(ICE.IceConfigError) as e:
                ICE.load(arg)
            self.assertEqual(e.exception.code, code)
        for kw, code in (({"versao": "cópia de TESTE", "name": "a"}, "ICE_DE_TESTE"), ({"aprovado": False, "name": "b"}, "ICE_NAO_APROVADO"),
                         ({"file": "ice-teste.xlsx", "name": "c"}, "ICE_DE_TESTE")):
            with self.subTest(kw=kw), self.assertRaises(ICE.IceConfigError) as e:
                ICE.load(str(ice_folder(self.dir, **kw)))
            self.assertEqual(e.exception.code, code)

    @mock.patch.dict(os.environ, NO_ENV, clear=True)
    def test_empty_reference_uses_the_configured_one(self):
        folder = ice_folder(self.dir)
        src = FX.source_set(self.dir / "src", homologado=False)
        m = json.loads(src.read_text(encoding="utf-8"))
        m["entradas"]["referencial_ice"] = []
        src.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(ICE.IceConfigError):
            RUN.start_run(src, self.dir / "run0")  # nothing configured: the run does not start
        self.assertFalse((self.dir / "run0").exists())
        inv = RUN.start_run(src, self.dir / "run", ice_dir=str(folder))
        ice = [f for f in inv["fontes"] if "referencial_ice" in f["classes"]]
        self.assertEqual([f["nome"] for f in ice], ["ice.xlsx"])
        saved = RUN.load_manifest(self.dir / "run")
        self.assertEqual(saved["homologacao_ice"]["aprovado_por"], "Qualidade (sintético)")
        self.assertNotIn("REFERENCIAL_NAO_HOMOLOGADO", [p["codigo"] for p in inv["pendencias"]])


class TemplateOfOtherClusterTest(unittest.TestCase):
    def test_stops_before_reading(self):
        with tempfile.TemporaryDirectory() as t:
            src = FX.source_set(Path(t) / "src")
            FX.template_xlsx(Path(t) / "src" / "template.xlsx", uf="SP")
            with self.assertRaises(RUN.RunError) as e:
                RUN.start_run(src, Path(t) / "run")
            self.assertEqual(e.exception.code, "TEMPLATE_SEM_UF")
            self.assertIn("SP", e.exception.message)
            self.assertFalse((Path(t) / "run" / "inventario.json").exists())


class RepeatedImageTest(unittest.TestCase):
    def test_read_once_copied_to_the_same_picture(self):
        with tempfile.TemporaryDirectory() as t:
            src = FX.source_set(Path(t) / "src")
            long = "Texto de página comum, longo o suficiente para contar como página de texto."
            FX.make_pdf(Path(t) / "src" / "diretrizes.pdf", [["Diretrizes pedagógicas da rede estadual 2026", FX.ORIENT_P1, FX.ORIENT_P2], ["x"], [long], ["y"], [long]],
                        image_pages=(2, 4))
            run = Path(t) / "run"
            RUN.start_run(src, run)
            pend = {p["unidade"]: p for p in RUN.pending_images(run)}
            self.assertEqual((pend["DOC-1:p2"]["mesma_imagem_que"], pend["DOC-1:p4"]["mesma_imagem_que"]), (None, "DOC-1:p2"))
            r = RUN.register_image_reading(run, "DOC-1:p2", "Figura decorativa, sem conteúdo.")
            self.assertEqual(r["copiada_para"], ["DOC-1:p4"])
            units = dict(RUN.unit_index(run))
            self.assertEqual(units["DOC-1:p4"][1]["status"], "interpretada_ia")
            self.assertTrue(units["DOC-1:p4"][1]["interpretacao_ia"].startswith("(Mesma imagem de DOC-1:p2.)"))
            self.assertNotIn("DOC-1:p4", [p["unidade"] for p in RUN.pending_images(run)])


if __name__ == "__main__":
    unittest.main()
