"""SPEC-017 G2: curricular matrix front (synthetic sources; numbers are invented)."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QROOT = ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"
sys.path.insert(0, str(QROOT))
import matrix_analysis as MA  # noqa: E402
import quality_run as RUN  # noqa: E402
import template_rules as TR  # noqa: E402
from test.quality import q17_fixtures as FX  # noqa: E402

SHEET = "DOC-3:Integral 9h"  # diretrizes.pdf = DOC-1, gestao.docx = DOC-2, matriz.xlsx = DOC-3
CLASS = {"Língua Portuguesa": "Formação Geral Básica", "Matemática": "Formação Geral Básica", "Projeto de Vida": "Projeto de Vida",
         "Eletiva": "Eletivas de Base", "Estudo Orientado": "Estudo Orientado e Avaliação Semanal", "Robótica": "Aprofundamento"}


def proposal(doc="DOC-3"):
    """Matrix proposal citing the synthetic matrix workbook; `doc` is its id in the run."""
    return json.loads(json.dumps(_proposal()).replace('"DOC-3', '"' + doc))


def _proposal():
    comps = []
    for i, (name, a, b, c) in enumerate(FX.MATRIX_ROWS, start=4):
        comps.append({"nome_original": name, "nome_evidencia": {"unidade": f"{SHEET}!A{i}", "trecho_literal": name},
                      "aulas_semanais": {s: {"valor": v, "unidade": f"{SHEET}!{col}{i}"} for s, v, col in zip(MA.SERIES, (a, b, c), "BCD")},
                      "classificacao": CLASS[name], "base_classificacao": "funcao_educacional", "confianca_classificacao": 92,
                      "justificativa_classificacao": f"{name}: função educacional equivalente à categoria '{CLASS[name]}' do template."})
    return {"selecao": {"fonte_id": "DOC-3", "unidades": [SHEET], "oferta": {"modalidade": "propedeutico", "modelo": "9h", "etapa": "Ensino Médio em Tempo Integral"},
                        "vigencia": "2026", "evidencias": [{"unidade": f"{SHEET}!A1", "trecho_literal": "ENSINO MÉDIO EM TEMPO INTEGRAL 9 HORAS - PROPEDÊUTICO"}],
                        "candidatas_descartadas": [{"unidades": ["DOC-3:Técnico"], "motivo": "Oferta integrada ao ensino técnico"}]},
            "minutos_aula": {"valor": 50, "unidade": f"{SHEET}!A2", "trecho_literal": "Duração da hora-aula: 50 minutos"},
            "total_linhas_fonte": len(FX.MATRIX_ROWS), "componentes": comps}


def approve(run, sha):
    m = json.loads((run / "manifesto.json").read_text(encoding="utf-8"))
    m["regras_homologadas"] = [{"formula_sha256": sha, "aprovado_por": "Coordenação de Qualidade (sintético)", "data": "2026-11-16"}]
    (run / "manifesto.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")


class MatrixBase(unittest.TestCase):
    fixture = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name) / "run"
        RUN.start_run(FX.source_set(Path(self.tmp.name) / "src", **self.fixture), self.run)

    def tearDown(self):
        self.tmp.cleanup()

    def sec(self):
        return MA.section(self.run)


class TemplateRuleTest(MatrixBase):
    def test_rule_read_from_template(self):
        refs = TR.load_references(self.run)
        t = refs["template"]
        self.assertEqual(t["classificacoes"], FX.CLASSES)
        self.assertEqual(t["aba_matriz"], "2.1 Revisão Matriz MG")
        regra = t["matriz"]["regra"]
        self.assertEqual(regra["status"], "reconhecida")
        kinds = {e["elemento"]: e["tipo"] for e in regra["elementos"]}
        self.assertEqual(kinds["Matriz completa"], "soma_elementos")
        self.assertEqual(kinds["Tutoria"], "soma_classificacao")
        self.assertEqual(kinds["Parte Diversificada"], "expressao")
        self.assertNotIn("preenchimento", t["matriz"])  # analysts' fill is history: only its size is kept, never its values
        self.assertEqual(t["historico_isolado"]["linhas_matriz_preenchidas"], 6)
        self.assertEqual({k: len(v) for k, v in refs["ice"]["codigos"].items()}, {"pedagogicas": 3, "gestao": 2})


class MatrixFlowTest(MatrixBase):
    def test_happy_path_needs_confirmation_and_approved_rule(self):
        s = MA.register(self.run, proposal())
        self.assertEqual((s["verificadas"], s["nao_verificadas"], s["classificacoes_pendentes"]), (18, 0, 0))
        sec, pend = self.sec()
        codes = [p["codigo"] for p in pend]
        self.assertIn("MATRIZ_NAO_CONFIRMADA", codes)
        self.assertIn("REGRA_NAO_HOMOLOGADA", codes)
        self.assertEqual(sec["resumo_por_elemento"]["status"], "pendente_regra_homologada")
        self.assertEqual(sec["resumo_por_elemento"]["elementos"], [])  # no totals before approval (AC-017-12)
        MA.confirm(self.run, "Analista sintético")
        approve(self.run, TR.load_references(self.run)["template"]["matriz"]["regra"]["formula_sha256"])
        sec, pend = self.sec()
        self.assertEqual(pend, [])
        self.assertEqual(sec["completude"]["status"], "completa")
        el = {e["elemento"]: (e["serie1"], e["serie2"], e["serie3"]) for e in sec["resumo_por_elemento"]["elementos"]}
        self.assertEqual(el["Formação Geral Básica"], (10, 10, 10))
        self.assertEqual(el["Aprofundamento"], (0, 2, 2))
        self.assertEqual(el["Matriz completa"], (18, 20, 18))
        self.assertEqual(el["Projeto de Vida + Pós-Médio"], (2, 2, 0))
        self.assertEqual(el["Itinerários Formativos"], (8, 10, 8))
        self.assertEqual(el["Parte Diversificada"], (8, 8, 6))
        self.assertNotIn("elementos_preenchidos", TR.load_references(self.run)["template"]["matriz"])  # history stays out of the analysis
        self.assertNotIn("Horas totais", json.dumps(sec, ensure_ascii=False))  # no hours: no week factor was approved

    def test_reregister_keeps_confirmation_only_for_same_selection(self):
        MA.register(self.run, proposal())
        MA.confirm(self.run, "Analista sintético")
        MA.register(self.run, proposal())
        self.assertTrue(self.sec()[0]["selecao"]["confirmada_por_analista"])
        p = proposal()
        p["selecao"]["unidades"] = [SHEET, "DOC-3:Técnico"]
        MA.register(self.run, p)
        self.assertFalse(self.sec()[0]["selecao"]["confirmada_por_analista"])

    def test_wrong_offer_is_blocked(self):  # AC-017-02
        p = proposal()
        p["selecao"]["oferta"]["modalidade"] = "tecnico"
        with self.assertRaises(MA.MatrixError) as e:
            MA.register(self.run, p)
        self.assertEqual(e.exception.code, "MODELO_FORA_ESCOPO")
        p = proposal()
        p["componentes"][1]["aulas_semanais"]["serie1"] = {"valor": 3, "unidade": "DOC-3:Técnico!B4"}  # value from the technical sheet
        MA.register(self.run, p)
        mat = self.sec()[0]["componentes"][1]["aulas_semanais"]["serie1"]
        self.assertEqual((mat["valor"], mat["status"], mat["valor_proposto"]), (None, "nao_verificado", 3))
        self.assertIn("fora da matriz selecionada", mat["motivo"])
        p = proposal()
        p["selecao"]["unidades"] = ["DOC-3:Técnico"]
        p["selecao"]["evidencias"] = [{"unidade": "DOC-3:Técnico!A1", "trecho_literal": "ENSINO MÉDIO INTEGRADO À EDUCAÇÃO PROFISSIONAL TÉCNICA"}]
        MA.register(self.run, p)
        sel = self.sec()[0]["selecao"]
        self.assertTrue(sel["revisar"])
        self.assertTrue(any("OFERTA_9H" in m for m in sel["motivos"]))
        p["selecao"]["fonte_id"] = "DOC-1"  # orientations PDF is not declared as a matrix source
        with self.assertRaises(MA.MatrixError):
            MA.register(self.run, p)

    def test_zero_blank_and_unverified_are_different(self):  # AC-017-05
        p = proposal()
        p["componentes"][5]["aulas_semanais"]["serie1"] = {"valor": 0, "unidade": f"{SHEET}!B9"}
        p["componentes"][2]["aulas_semanais"]["serie3"] = {"valor": None, "motivo": "ausente_na_fonte", "unidade": f"{SHEET}!F6"}  # empty cell
        p["componentes"][3]["aulas_semanais"]["serie3"] = {"valor": None}
        p["componentes"][4]["aulas_semanais"]["serie3"] = {"valor": None, "motivo": "ausente_na_fonte", "unidade": f"{SHEET}!D8"}  # cell holds 4
        MA.register(self.run, p)
        comps = self.sec()[0]["componentes"]
        self.assertEqual((comps[5]["aulas_semanais"]["serie1"]["valor"], comps[5]["aulas_semanais"]["serie1"]["status"]), (0, "verificado"))
        self.assertEqual((comps[2]["aulas_semanais"]["serie3"]["valor"], comps[2]["aulas_semanais"]["serie3"]["status"]), (None, "ausente_na_fonte"))
        self.assertEqual(comps[3]["aulas_semanais"]["serie3"]["status"], "nao_verificado")
        self.assertEqual(comps[4]["aulas_semanais"]["serie3"]["status"], "nao_verificado")
        p = proposal()
        p["componentes"][0]["aulas_semanais"]["serie1"] = {"valor": 4, "unidade": f"{SHEET}!B4"}  # the cell holds 5
        MA.register(self.run, p)
        cell = self.sec()[0]["componentes"][0]["aulas_semanais"]["serie1"]
        self.assertEqual((cell["valor"], cell["status"]), (None, "nao_verificado"))
        self.assertIn("tem 5, não 4", cell["motivo"])

    def test_classification_by_name_only_is_pending(self):  # AC-017-06
        p = proposal()
        p["componentes"][5]["base_classificacao"] = "nome"
        p["componentes"][4]["classificacao"] = "Estudo Orientado"  # not in the template list
        p["componentes"][3]["justificativa_classificacao"] = "Eletiva."
        p["componentes"][0]["classificacao"] = "formação geral básica"  # accent/case variant of a listed value: accepted, written as in the template
        MA.register(self.run, p)
        MA.confirm(self.run, "Analista sintético")
        approve(self.run, TR.load_references(self.run)["template"]["matriz"]["regra"]["formula_sha256"])
        sec, pend = self.sec()
        st = [c["classificacao_status"] for c in sec["componentes"]]
        self.assertEqual(st, ["aceita", "aceita", "aceita", "pendente", "pendente", "pendente"])
        self.assertEqual(sec["componentes"][0]["classificacao"], "Formação Geral Básica")
        self.assertIn("CLASSIFICACAO_PENDENTE", [x["codigo"] for x in pend])
        self.assertNotEqual(sec["resumo_por_elemento"]["status"], "calculado")
        self.assertEqual(sec["completude"]["status"], "incompleta")

    def test_missing_rows_and_minutes(self):
        p = proposal()
        p["total_linhas_fonte"] = 7
        p["minutos_aula"] = {"valor": 45, "unidade": f"{SHEET}!A2", "trecho_literal": "Duração da hora-aula: 50 minutos"}
        MA.register(self.run, p)
        codes = [x["codigo"] for x in self.sec()[1]]
        self.assertIn("LINHAS_FALTANDO", codes)
        self.assertIn("VALOR_NAO_VERIFICADO", codes)
        p["total_linhas_fonte"] = None
        MA.register(self.run, p)
        self.assertIn("TOTAL_LINHAS_DESCONHECIDO", [x["codigo"] for x in self.sec()[1]])

    def test_candidates(self):
        c = {x["regiao"]: x for x in MA.candidates(self.run)}
        self.assertIn("9h", c[SHEET]["sinais"])
        self.assertIn("tecnico", c["DOC-3:Técnico"]["sinais"])


class MissingCacheTest(MatrixBase):
    fixture = {"missing_cache": True}

    def test_formula_without_cache_is_not_a_value(self):  # AC-017-03
        p = proposal()
        p["componentes"][0]["aulas_semanais"]["serie1"] = {"valor": 15, "unidade": f"{SHEET}!E4"}  # 'Total' formula, no cached value
        MA.register(self.run, p)
        cell = self.sec()[0]["componentes"][0]["aulas_semanais"]["serie1"]
        self.assertEqual(cell["status"], "nao_verificado")
        self.assertIn("fórmula sem valor salvo", cell["motivo"])


class ChangedRuleTest(MatrixBase):
    fixture = {"rule_variant": "alterada"}

    def test_changed_formula_changes_fingerprint(self):  # AC-017-12
        regra = TR.load_references(self.run)["template"]["matriz"]["regra"]
        self.assertEqual(regra["status"], "reconhecida")
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / "run"
            RUN.start_run(FX.source_set(Path(tmp) / "src"), other)
            standard = TR.load_references(other)["template"]["matriz"]["regra"]["formula_sha256"]
        self.assertNotEqual(regra["formula_sha256"], standard)
        approve(self.run, standard)  # approval of the old version does not apply to the changed one
        MA.register(self.run, proposal())
        self.assertEqual(self.sec()[0]["resumo_por_elemento"]["status"], "pendente_regra_homologada")

    def test_rule_different_between_series_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / "run"
            RUN.start_run(FX.source_set(Path(tmp) / "src", rule_variant="inconsistente"), other)
            regra = TR.load_references(other)["template"]["matriz"]["regra"]
            self.assertEqual((regra["status"], regra["desconhecidos"]), ("desconhecida", ["Parte Diversificada"]))
            MA.register(other, proposal())
            sec, pend = MA.section(other)
            self.assertIn("REGRA_DESCONHECIDA", [x["codigo"] for x in pend])
            self.assertEqual(sec["resumo_por_elemento"]["status"], "pendente_regra_homologada")

    def test_unknown_formula(self):
        refs = TR.load_references(self.run)
        rule = refs["template"]["matriz"]
        node = TR._parse_formula("(K12-K13)*40", {12: "Matriz completa", 13: "Formação Geral Básica"}, {"serie1": 3}, 6, "serie1")
        self.assertIsNone(node)  # the 40-week factor is not a known rule
        self.assertIsNotNone(rule)


class ImageMatrixTest(unittest.TestCase):
    def test_values_read_from_image_stay_unverified(self):  # AC-017-04
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            m = FX.source_set(src, image_page=True,
                              extra_entries={"matriz_estadual": [{"uri": "diretrizes.pdf", "papel": "matriz"}]})
            run = Path(tmp) / "run"
            RUN.start_run(m, run)
            RUN.register_image_reading(run, "DOC-1:p3", "Matriz 9h: Tutoria 1 1 1")
            p = {"selecao": {"fonte_id": "DOC-1", "unidades": ["DOC-1:p3"], "oferta": {"modalidade": "propedeutico", "modelo": "9h", "etapa": None},
                             "vigencia": "2026", "evidencias": [{"unidade": "DOC-1:p3", "trecho_literal": "Matriz 9h"}]},
                 "minutos_aula": {"valor": None, "motivo": "nao_verificado"}, "total_linhas_fonte": 1,
                 "componentes": [{"nome_original": "Tutoria", "nome_evidencia": {"unidade": "DOC-1:p3", "trecho_literal": "Tutoria"},
                                  "aulas_semanais": {s: {"valor": 1, "unidade": "DOC-1:p3", "trecho_literal": "Tutoria 1 1 1"} for s in MA.SERIES},
                                  "classificacao": "Tutoria", "base_classificacao": "funcao_educacional",
                                  "justificativa_classificacao": "Acompanhamento individual do estudante, função de tutoria do modelo."}]}
            MA.register(run, p)
            sec, pend = MA.section(run)
            cell = sec["componentes"][0]["aulas_semanais"]["serie1"]
            self.assertEqual((cell["valor"], cell["status"], cell["valor_proposto"]), (None, "nao_verificado", 1))
            self.assertEqual(cell["evidencia"]["metodo"], "interpretacao_ia")
            self.assertTrue(sec["componentes"][0]["revisar"])
            self.assertIn("VALOR_NAO_VERIFICADO", [x["codigo"] for x in pend])


class MatrixCliTest(unittest.TestCase):
    def test_cli(self):
        import subprocess
        cli = [sys.executable, str(QROOT / "resultado_qualidade.py")]
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            m = FX.source_set(Path(tmp) / "src")
            self.assertEqual(subprocess.run(cli + ["iniciar", str(m), "--pasta", str(run)], capture_output=True).returncode, 0)
            prop = Path(tmp) / "matriz.json"
            prop.write_text(json.dumps(proposal(), ensure_ascii=False), encoding="utf-8")
            run_ = lambda *a: subprocess.run(cli + list(a) + ["--pasta", str(run), "--json"], capture_output=True, text=True, encoding="utf-8")  # noqa: E731
            out = json.loads(run_("matriz-candidatas").stdout)
            self.assertTrue(out["data"]["candidatas"])
            out = run_("matriz-registrar", str(prop))
            self.assertEqual(json.loads(out.stdout)["data"]["verificadas"], 18, out.stdout)
            out = run_("matriz-confirmar", "--autor", "Analista sintético")
            self.assertEqual(json.loads(out.stdout)["code"], "MATRIZ_CONFIRMADA")
            bad = proposal()
            bad["selecao"]["oferta"]["modelo"] = "7h"
            prop.write_text(json.dumps(bad), encoding="utf-8")
            out = run_("matriz-registrar", str(prop))
            self.assertEqual((out.returncode, json.loads(out.stdout)["code"]), (1, "MODELO_FORA_ESCOPO"))


if __name__ == "__main__":
    unittest.main()
