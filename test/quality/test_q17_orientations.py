"""SPEC-017 G3: orientations front (synthetic documents; codes and texts are invented)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QROOT = ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"
sys.path.insert(0, str(QROOT))
import orientation_analysis as OA  # noqa: E402
import quality_run as RUN  # noqa: E402
from test.quality import q17_fixtures as FX  # noqa: E402

# diretrizes.pdf = DOC-1, gestao.docx = DOC-2, matriz.xlsx = DOC-3, template.xlsx = DOC-4, ice.xlsx = DOC-5
ABSENCE = {"itens_considerados": ["Diretrizes: seções de eletivas e acolhimento", "Caderno de gestão: todo"], "onde_procurou": "Todos os documentos de orientação, inclusive tabelas e imagens"}


def sim(code, unit="DOC-1:p1", quote=FX.ORIENT_P1, rel="Equivalente", conf=92):
    return {"codigo": code, "presenca": "Sim", "confianca": conf, "justificativa": "O documento estadual afirma a prática.",
            "evidencias": [{"unidade": unit, "trecho_literal": quote, "relacao": rel}]}


def nao(code, checked=("DOC-1", "DOC-2"), ausencia=ABSENCE):
    return {"codigo": code, "presenca": "Não", "confianca": 90, "justificativa": "Nenhum documento trata do tema.", "ausencia": ausencia, "fontes_verificadas": list(checked)}


class Base(unittest.TestCase):
    fixture = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name) / "run"
        RUN.start_run(FX.source_set(Path(self.tmp.name) / "src", **self.fixture), self.run)

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self):
        sec, pend = OA.section(self.run)
        return {r["codigo"]: r for r in sec["pedagogicas"] + sec["gestao"]}, sec, pend


class ReconcileTest(Base):
    def test_equal_sets(self):
        _, sec, pend = self.rows()
        c = sec["codigos"]
        self.assertEqual(c["status"], "reconciliado_por_igualdade")
        self.assertEqual(c["aplicaveis"], {"pedagogicas": 3, "gestao": 2})
        self.assertIn("homologado", c["autoridade"])
        self.assertEqual(sec["completude"]["pedagogicas"]["status"], "nao_iniciada")
        self.assertIn("ORIENTACAO_NAO_AVALIADA", [p["codigo"] for p in pend])


class CodeMismatchTest(Base):
    fixture = {"ice_extra": [("EL3", "Eletiva com culminância", "Eletivas de Base")]}

    def test_mismatch_blocks_completeness_until_approved_mapping(self):  # AC-017-13
        _, sec, pend = self.rows()
        self.assertEqual(sec["codigos"]["status"], "nao_reconciliado")
        self.assertEqual(sec["codigos"]["somente_ice"], ["EL3"])
        self.assertIsNone(sec["codigos"]["aplicaveis"]["pedagogicas"])
        self.assertIn("CODIGOS_NAO_RECONCILIADOS", [p["codigo"] for p in pend])
        self.assertEqual(len(sec["pedagogicas"]), 4)  # union is evaluated, but the denominator stays unknown
        RUN.register_image_reading(self.run, "DOC-2:img1", "Organograma: direção, coordenação, professores")
        OA.register(self.run, [sim(c) for c in ("EL1", "EL2", "AC1", "EL3")])
        _, sec, _ = self.rows()
        self.assertEqual(sec["completude"]["pedagogicas"]["status"], "incompleta")
        m = json.loads((self.run / "manifesto.json").read_text(encoding="utf-8"))
        m["aplicabilidade_codigos"] = {"aprovado_por": "Coordenação (sintético)", "data": "2026-11-16", "pedagogicas": ["EL1", "EL2", "AC1", "EL3"],
                                       "gestao": ["PA1", "PA2"], "exclusoes": [{"codigo": "EL3", "motivo": "Código novo ainda não aplicável em 2026"}]}
        (self.run / "manifesto.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        _, sec, _ = self.rows()
        self.assertEqual(sec["codigos"]["status"], "reconciliado_por_mapeamento_aprovado")
        self.assertEqual(sec["codigos"]["aplicaveis"]["pedagogicas"], 3)
        self.assertEqual(sec["codigos"]["exclusoes"][0]["codigo"], "EL3")
        self.assertEqual(sec["completude"]["pedagogicas"]["status"], "completa")


class DecisionTest(Base):
    def test_verified_sim_across_documents(self):  # AC-017-07
        OA.register(self.run, [sim("EL1"), sim("PA1", "DOC-2:par2", FX.GESTAO_P1), sim("AC1", quote=FX.ORIENT_P2, rel="Indireta")])
        rows, _, _ = self.rows()
        self.assertEqual((rows["EL1"]["presenca"], rows["EL1"]["status"]), ("Sim", "decidido"))
        self.assertEqual(rows["PA1"]["presenca"], "Sim")  # found in another booklet (DOCX)
        self.assertEqual(rows["PA1"]["evidencias"][0]["localizacao"], {"tipo": "paragraph", "paragrafo": 2})
        self.assertEqual((rows["AC1"]["presenca"], rows["AC1"]["status"], rows["AC1"]["revisar"]), ("Sim", "decidido_revisar", True))

    def test_sim_without_verified_state_quote_is_pending(self):
        OA.register(self.run, [sim("EL1", quote="As eletivas são definidas exclusivamente pelos estudantes de cada turma escolar."),
                               sim("EL2", "DOC-5:orientações_referenciais_ICE!D3", "Uso de metodologias ativas"),  # ICE is a rule, not evidence
                               sim("AC1", "DOC-4:1.1 Base orient. pedagógicas!G12", "Sim")])  # template answers are not evidence
        rows, _, _ = self.rows()
        for code in ("EL1", "EL2", "AC1"):
            self.assertIsNone(rows[code]["presenca"], code)
            self.assertEqual(rows[code]["status"], "pendente")
            self.assertIn("PENDENTE_EVIDENCIA", rows[code]["pendencias"])
        self.assertIn("não é fonte aceita", " ".join(rows["EL2"]["motivos"]))

    def test_nao_needs_full_coverage_and_every_document(self):  # AC-017-08
        OA.register(self.run, [nao("EL2")])
        rows, _, pend = self.rows()
        self.assertIsNone(rows["EL2"]["presenca"])  # the DOCX has an image not read yet
        self.assertIn("COBERTURA_DOCUMENTAL_INCOMPLETA", rows["EL2"]["pendencias"])
        self.assertIn("COBERTURA_DOCUMENTAL_INCOMPLETA", [p["codigo"] for p in pend])
        RUN.register_image_reading(self.run, "DOC-2:img1", "Organograma: direção, coordenação, professores")
        OA.register(self.run, [nao("EL2"), nao("PA2", checked=("DOC-1",)), nao("AC1", ausencia={"itens_considerados": [], "onde_procurou": ""})])
        rows, _, _ = self.rows()
        self.assertEqual(rows["EL2"]["presenca"], "Não")
        self.assertIsNone(rows["PA2"]["presenca"])
        self.assertIn("DOC-2", " ".join(rows["PA2"]["motivos"]))
        self.assertIsNone(rows["AC1"]["presenca"])
        self.assertIn("PENDENTE_EVIDENCIA", rows["AC1"]["pendencias"])

    def test_analyst_decision_is_kept(self):
        OA.analyst_decision(self.run, "EL2", "Não", "Confirmado com a coordenação regional.", "Analista sintético")
        r = OA.register(self.run, [sim("EL2")])
        self.assertEqual(r["preservadas_do_analista"], ["EL2"])
        rows, _, _ = self.rows()
        self.assertEqual((rows["EL2"]["presenca"], rows["EL2"]["origem"]), ("Não", "analista"))
        with self.assertRaises(OA.OrientationError):
            OA.analyst_decision(self.run, "ZZ9", "Sim", "Justificativa longa o bastante.", "Analista")

    def test_unknown_code_is_reported(self):
        r = OA.register(self.run, [sim("XX1")])
        self.assertEqual(r["codigos_desconhecidos"], ["XX1"])


class InaccessibleTest(Base):
    fixture = {"extra_entries": {"orientacoes_estaduais": [{"uri": "https://exemplo.gov.br/caderno-que-nao-abre.pdf"}]}}

    def test_inaccessible_document_blocks_nao_not_sim(self):  # AC-017-08
        RUN.register_image_reading(self.run, "DOC-2:img1", "Organograma")
        OA.register(self.run, [nao("EL2", checked=("DOC-1", "DOC-2", "DOC-3")), sim("EL1")])
        rows, _, _ = self.rows()
        self.assertIsNone(rows["EL2"]["presenca"])
        self.assertEqual(rows["EL1"]["presenca"], "Sim")


class EqvImportTest(Base):
    def test_adapter(self):
        RUN.register_image_reading(self.run, "DOC-2:img1", "Organograma")
        eqv = Path(self.tmp.name) / "eqv" / "celulas"
        eqv.mkdir(parents=True)
        cells = [
            {"aba": "1.1", "codigo": "EL1", "valor": "Sim", "valor_proposto": "Sim", "confianca_proposta": 92, "explicacao": "Afirmado nas diretrizes.",
             "evidencias": [{"documento": "Diretrizes", "pagina": 1, "trecho": FX.ORIENT_P1, "relacao": "Equivalente"}], "decidido_por": "IA"},
            {"aba": "1.1", "codigo": "EL2", "valor": "Não", "revisar": True, "valor_proposto": "Sim", "confianca_proposta": 80, "explicacao": "Parece haver.",
             "evidencias": [{"documento": "Diretrizes", "pagina": 2, "trecho": "Metodologias ativas são obrigatórias em todas as eletivas da rede.", "relacao": "Equivalente"}], "decidido_por": "IA"},
            {"aba": "1.2", "codigo": "PA2", "valor": "Não", "valor_proposto": "Não", "confianca_proposta": 88, "explicacao": "Sem menção.",
             "ausencia": ABSENCE, "evidencias": [], "decidido_por": "IA"},
            {"aba": "1.2", "codigo": "PA1", "valor": "Sim", "explicacao": "Analista confirmou.", "evidencias": [], "decidido_por": "analista"},
        ]
        for c in cells:
            (eqv / f"{c['aba']}-{c['codigo']}.json").write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
        r = OA.import_eqv(self.run, eqv.parent, {"Diretrizes": "DOC-1", "Gestão": "DOC-2"})
        self.assertEqual(r["importadas"], 4)
        self.assertEqual(r["convertidas_em_pendencia"], 1)
        rows, _, _ = self.rows()
        self.assertEqual((rows["EL1"]["presenca"], rows["EL1"]["origem"]), ("Sim", "eqv_importada"))
        self.assertIsNone(rows["EL2"]["presenca"])  # EQV "Não + Revisar" for lack of proof -> null + PENDENTE_EVIDENCIA
        self.assertEqual(rows["PA2"]["presenca"], "Não")
        self.assertEqual((rows["PA1"]["presenca"], rows["PA1"]["origem"], rows["PA1"]["revisar"]), ("Sim", "analista", True))
        with self.assertRaises(OA.OrientationError):
            OA.import_eqv(self.run, eqv.parent, {"Diretrizes": "DOC-99"})


class OrientationCliTest(Base):
    def test_cli(self):
        cli = [sys.executable, str(QROOT / "resultado_qualidade.py")]
        prop = Path(self.tmp.name) / "o.json"
        prop.write_text(json.dumps({"orientacoes": [sim("EL1"), sim("XX1")]}, ensure_ascii=False), encoding="utf-8")
        out = subprocess.run(cli + ["orientacoes-registrar", str(prop), "--pasta", str(self.run), "--json"], capture_output=True, text=True, encoding="utf-8")
        data = json.loads(out.stdout)
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertEqual(data["data"]["codigos_desconhecidos"], ["XX1"])
        out = subprocess.run(cli + ["orientacoes-codigos", "--pasta", str(self.run), "--json"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(json.loads(out.stdout)["data"]["codigos"]["status"], "reconciliado_por_igualdade")
        out = subprocess.run(cli + ["orientacao-decidir", "--pasta", str(self.run), "--codigo", "EL2", "--presenca", "Não", "--justificativa", "Confirmado com a regional.",
                                    "--autor", "Analista", "--json"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(json.loads(out.stdout)["code"], "DECISAO_REGISTRADA")


if __name__ == "__main__":
    unittest.main()
