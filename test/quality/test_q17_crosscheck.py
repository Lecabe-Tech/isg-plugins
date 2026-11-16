"""SPEC-017 G4: typed cross-check between the two fronts (synthetic sources)."""
import hashlib
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
import matrix_analysis as MA  # noqa: E402
import orientation_analysis as OA  # noqa: E402
import quality_run as RUN  # noqa: E402
from test.quality import q17_fixtures as FX  # noqa: E402
from test.quality.test_q17_matrix import proposal  # noqa: E402

CYCLE = {"uf": "MG", "ano": 2026, "modelo": "9h"}
EO_PAGE = "DOC-1:p2"


def eo_quote(third):
    return f"Estudo Orientado: 4 aulas na 1ª série, 4 na 2ª e {third} na 3ª série."


class Base(unittest.TestCase):
    fixture = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name) / "run"
        RUN.start_run(FX.source_set(Path(self.tmp.name) / "src", **self.fixture), self.run)
        self.mdoc = next(f["id"] for f in RUN.load_inventory(self.run)["fontes"] if f["nome"] == "matriz.xlsx")
        MA.register(self.run, proposal(self.mdoc))

    def tearDown(self):
        self.tmp.cleanup()

    def codes(self, res):
        return [c["codigo"] for c in res["conflitos"]]


class CrossCheckTest(Base):
    def test_offer_without_specific_orientation_is_not_a_conflict(self):  # AC-017-09
        OA.register(self.run, [{"codigo": "EL2", "presenca": None, "justificativa": "Sem evidência sobre metodologias ativas."}])
        res = CC.run(self.run)
        self.assertNotIn("CONTRADICAO_OFERTA_CARGA", self.codes(res))
        self.assertTrue(any(c["regra"] == "oferta_x_orientacao" and c["resultado"] == "sem_conflito" for c in res["checagens"]))

    def test_explicit_non_offer_vs_positive_load(self):  # AC-017-10
        src = Path(self.tmp.name) / "src"
        FX.make_docx(src / "comunicado.docx", [("p", "Comunicado 2026"), ("p", "No ensino médio em tempo integral de 9 horas a Matemática não será ofertada na rede em 2026.")])
        m = json.loads((src / "manifesto.json").read_text(encoding="utf-8"))
        m["entradas"]["orientacoes_estaduais"].append({"uri": "comunicado.docx"})
        (src / "manifesto.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        run = Path(self.tmp.name) / "run2"
        RUN.start_run(src / "manifesto.json", run)
        mdoc = next(f["id"] for f in RUN.load_inventory(run)["fontes"] if f["nome"] == "matriz.xlsx")
        MA.register(run, proposal(mdoc))
        doc = next(f["id"] for f in RUN.load_inventory(run)["fontes"] if f["nome"] == "comunicado.docx")
        CC.register(run, [{"tipo": "nao_oferta", "componente": "Matemática", "ciclo": CYCLE, "unidade": f"{doc}:par2",
                           "trecho_literal": "a Matemática não será ofertada na rede em 2026"}])
        res = CC.run(run)
        c = next(x for x in res["conflitos"] if x["codigo"] == "CONTRADICAO_OFERTA_CARGA")
        self.assertEqual((c["gravidade"], c["entidade"]), ("alta", "Matemática"))
        self.assertEqual(sorted(c["fontes"]), sorted([doc, mdoc]))  # both sources preserved
        self.assertEqual(c["valores"][0]["valor"], {"serie1": 5, "serie2": 5, "serie3": 5})

    def test_other_cycle_and_unverified_are_ignored(self):
        CC.register(self.run, [{"tipo": "nao_oferta", "componente": "Matemática", "ciclo": {"uf": "MG", "ano": 2025, "modelo": "9h"}, "unidade": "DOC-1:p1",
                                "trecho_literal": "Diretrizes pedagógicas da rede estadual 2026"},
                               {"tipo": "nao_oferta", "componente": "Matemática", "ciclo": CYCLE, "unidade": "DOC-1:p1", "trecho_literal": "Matemática não será ofertada"}])
        res = CC.run(self.run)
        self.assertNotIn("CONTRADICAO_OFERTA_CARGA", self.codes(res))
        self.assertEqual([c["resultado"] for c in res["checagens"][:2]], ["ignorada", "ignorada"])


class SourceConflictTest(Base):
    fixture = {"conflicting_eo": True, "extra_entries": {"matriz_estadual": [{"uri": "diretrizes.pdf", "papel": "matriz"}]}}

    def test_444_vs_445(self):  # AC-017-11
        r = CC.register(self.run, [{"tipo": "carga_semanal", "componente": "Estudo Orientado", "ciclo": CYCLE, "valores": {"serie1": 4, "serie2": 4, "serie3": 5},
                                    "unidade": EO_PAGE, "trecho_literal": eo_quote(5)}])
        self.assertEqual(r["verificadas"], 1)
        before = MA.section(self.run)[0]
        res = CC.run(self.run)
        c = next(x for x in res["conflitos"] if x["codigo"] == "CONFLITO_ENTRE_FONTES")
        self.assertEqual(c["valores"][0]["valor"], {"serie1": 4, "serie2": 4, "serie3": 4})
        self.assertEqual(c["valores"][1]["valor"], {"serie1": 4, "serie2": 4, "serie3": 5})
        self.assertTrue(c["resolucao_pendente"])
        self.assertEqual(MA.section(self.run)[0], before)  # the matrix front was not corrected by the other source

    def test_values_must_be_in_the_quote(self):
        r = CC.register(self.run, [{"tipo": "carga_semanal", "componente": "Estudo Orientado", "ciclo": CYCLE, "valores": {"serie1": 4, "serie2": 4, "serie3": 6},
                                    "unidade": EO_PAGE, "trecho_literal": eo_quote(5)}])
        self.assertEqual(r["verificadas"], 0)


class NormativeTest(Base):
    def test_ice_requirement_vs_real_offer(self):
        r = CC.register(self.run, [{"tipo": "exigencia_normativa", "componente": "Química", "ciclo": CYCLE, "unidade": "DOC-5:matriz_referencial_ICE!A3", "trecho_literal": "Química"},
                                   {"tipo": "exigencia_normativa", "componente": "Língua Portuguesa", "ciclo": CYCLE, "unidade": "DOC-5:matriz_referencial_ICE!A2", "trecho_literal": "Língua Portuguesa"},
                                   {"tipo": "exigencia_normativa", "componente": "Química", "ciclo": CYCLE, "unidade": "DOC-1:p1", "trecho_literal": "Diretrizes pedagógicas"}])
        self.assertEqual(r["verificadas"], 2)  # a state document is not the ICE reference
        res = CC.run(self.run)
        norm = [c for c in res["conflitos"] if c["codigo"] == "NORMATIVO_VS_OFERTA"]
        self.assertEqual([c["entidade"] for c in norm], ["Química"])
        self.assertNotIn("Química", [c["nome_original"] for c in MA.section(self.run)[0]["componentes"]])  # no lessons invented

    def test_fronts_are_read_only_and_result_is_stable(self):
        files = [self.run / "matriz.json"]
        OA.register(self.run, [{"codigo": "EL1", "presenca": "Sim", "confianca": 92, "justificativa": "Afirmado.", "evidencias": [{"unidade": "DOC-1:p1", "trecho_literal": FX.ORIENT_P1}]}])
        files.append(self.run / "orientacoes.json")
        digest = [hashlib.sha256(f.read_bytes()).hexdigest() for f in files]
        a = CC.run(self.run)
        b = CC.run(self.run)
        self.assertEqual(a, b)
        self.assertEqual([hashlib.sha256(f.read_bytes()).hexdigest() for f in files], digest)


class UnknownFilesTest(Base):
    fixture = {"extra_entries": {"orientacoes_estaduais": [{"uri": "caderno-ausente.pdf"}]}}

    def test_inaccessible_file_is_reported(self):
        res = CC.run(self.run)
        cov = [c for c in res["conflitos"] if c["codigo"] == "COBERTURA_DOCUMENTAL_INCOMPLETA"]
        self.assertTrue(any("caderno-ausente.pdf" in c["detalhe"] for c in cov))


class ClassificationPendingTest(Base):
    def test_pending_classification_keeps_lessons(self):
        p = proposal(self.mdoc)
        p["componentes"][5]["base_classificacao"] = "nome"
        MA.register(self.run, p)
        res = CC.run(self.run)
        c = next(x for x in res["conflitos"] if x["codigo"] == "CLASSIFICACAO_PENDENTE")
        self.assertEqual(c["entidade"], "Robótica")
        self.assertEqual(MA.section(self.run)[0]["componentes"][5]["aulas_semanais"]["serie2"]["valor"], 2)


class CliTest(Base):
    def test_cli(self):
        cli = [sys.executable, str(QROOT / "resultado_qualidade.py")]
        f = Path(self.tmp.name) / "a.json"
        f.write_text(json.dumps({"afirmacoes": [{"tipo": "exigencia_normativa", "componente": "Química", "ciclo": CYCLE, "unidade": "DOC-5:matriz_referencial_ICE!A3",
                                                 "trecho_literal": "Química"}]}, ensure_ascii=False), encoding="utf-8")
        out = subprocess.run(cli + ["afirmacoes-registrar", str(f), "--pasta", str(self.run), "--json"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(json.loads(out.stdout)["data"]["verificadas"], 1, out.stdout)
        out = subprocess.run(cli + ["cruzar", "--pasta", str(self.run), "--json"], capture_output=True, text=True, encoding="utf-8")
        self.assertIn("NORMATIVO_VS_OFERTA", [c["codigo"] for c in json.loads(out.stdout)["data"]["conflitos"]])


if __name__ == "__main__":
    unittest.main()
