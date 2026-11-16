"""SPEC-017 G5: final JSON, summary, parity and acceptance scenarios (synthetic sources only)."""
import copy
import json
import os
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
import quality_result as QR  # noqa: E402
import quality_run as RUN  # noqa: E402
import template_rules as TR  # noqa: E402
from test.quality import q17_fixtures as FX  # noqa: E402
from test.quality.test_q17_matrix import approve, proposal  # noqa: E402
from test.quality.test_q17_orientations import ABSENCE, nao, sim  # noqa: E402

EXAMPLE = ROOT / "examples" / "quality" / "resultado_qualidade.v1.example.json"


def full_cycle(tmp: Path, name="run", **fixture) -> Path:
    """Synthetic complete 9h cycle: both fronts decided with verified evidence, rule and ICE approved."""
    run = tmp / name
    RUN.start_run(FX.source_set(tmp / ("src-" + name), **fixture), run)
    RUN.register_image_reading(run, "DOC-2:img1", "Organograma: direção, coordenação pedagógica e professores")
    MA.register(run, proposal(next(f["id"] for f in RUN.load_inventory(run)["fontes"] if f["nome"] == "matriz.xlsx")))
    MA.confirm(run, "Analista sintético", "Conferida com a resolução sintética")
    approve(run, TR.load_references(run)["template"]["matriz"]["regra"]["formula_sha256"])
    OA.register(run, [sim("EL1"), nao("EL2"), sim("AC1", quote=FX.ORIENT_P2), sim("PA1", "DOC-2:par2", FX.GESTAO_P1), nao("PA2")])
    return run


class ResultTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_cycle_is_valid(self):  # AC-017-01 + G5
        run = full_cycle(self.dir)
        r = QR.write(run)
        self.assertTrue(r["ok"], r["validacao"])
        res = r["resultado"]
        self.assertEqual(res["execucao"]["status"], "completo", [p for p in res["pendencias"] if p["bloqueia_completude"]])
        self.assertEqual(res["matriz"]["completude"]["status"], "completa")
        self.assertEqual({k: res["orientacoes"]["completude"][k]["status"] for k in ("pedagogicas", "gestao")}, {"pedagogicas": "completa", "gestao": "completa"})
        self.assertEqual(res["metricas"]["cobertura_orientacoes"], {"numerador": 5, "denominador": 5, "descricao": res["metricas"]["cobertura_orientacoes"]["descricao"]})
        self.assertEqual(res["revisao_humana"], {"necessaria": True, "status": "aguardando", "itens": res["revisao_humana"]["itens"]})
        saved = json.loads((run / QR.RESULT_FILE).read_text(encoding="utf-8"))
        self.assertTrue(QR.validate(saved)["valido"])
        md = (run / QR.SUMMARY_FILE).read_text(encoding="utf-8")
        for part in ("# Resultado da Qualidade — MG 2026", "## Matriz curricular", "| Língua Portuguesa | 5 | 5 | 5 | Formação Geral Básica", "## Orientações",
                     "## Cruzamento", "Nada foi gravado no Excel"):
            self.assertIn(part, md)
        self.assertNotIn("{", md.split("## Fontes")[1])  # readable without JSON

    def test_same_inputs_same_content(self):  # AC-017-14
        run = full_cycle(self.dir)
        a, b = QR.build(run), QR.build(run)
        self.assertEqual(a["execucao"]["conteudo_sha256"], b["execucao"]["conteudo_sha256"])
        other = full_cycle(self.dir, "run2")
        c = QR.build(other)
        self.assertEqual([f["sha256"] for f in a["fontes"]], [f["sha256"] for f in c["fontes"]])
        strip = lambda x: json.loads(json.dumps(x["orientacoes"]))  # noqa: E731
        self.assertEqual(strip(a), strip(c))
        self.assertEqual(a["matriz"]["componentes"], c["matriz"]["componentes"])
        self.assertEqual(a["matriz"]["resumo_por_elemento"], c["matriz"]["resumo_por_elemento"])

    def test_missing_document_stays_partial(self):
        run = full_cycle(self.dir, extra_entries={"orientacoes_estaduais": [{"uri": "caderno-ausente.docx"}]})
        OA.register(run, [nao("EL2", checked=("DOC-1", "DOC-2", "DOC-3"))])
        r = QR.write(run)
        self.assertTrue(r["ok"], r["validacao"])
        res = r["resultado"]
        self.assertEqual(res["execucao"]["status"], "parcial")
        el2 = next(o for o in res["orientacoes"]["pedagogicas"] if o["codigo"] == "EL2")
        self.assertIsNone(el2["presenca"])  # never Não because a file could not be read
        self.assertIn("FONTE_AUSENTE", [p["codigo"] for p in res["pendencias"]])

    def test_blocked_when_no_state_source_is_readable(self):
        src = self.dir / "src"
        FX.template_xlsx(src / "t.xlsx") if src.mkdir() is None else None
        FX.ice_xlsx(src / "i.xlsx")
        m = {"schema_version": "1.0", "solicitacao_id": "SINT-BLOQ", "uf": "MG", "ano": 2026, "modelo": "9h", "modalidade": "propedeutico",
             "entradas": {"orientacoes_estaduais": [{"uri": "nao-existe.pdf"}], "matriz_estadual": [{"uri": "tambem-nao.xlsx"}],
                          "template_cluster": [{"uri": "t.xlsx"}], "referencial_ice": [{"uri": "i.xlsx"}]}}
        (src / "m.json").write_text(json.dumps(m), encoding="utf-8")
        RUN.start_run(src / "m.json", self.dir / "run")
        r = QR.write(self.dir / "run")
        self.assertTrue(r["ok"], r["validacao"])
        self.assertEqual(r["resultado"]["execucao"]["status"], "bloqueado")
        self.assertTrue(all(o["presenca"] is None for o in r["resultado"]["orientacoes"]["pedagogicas"]))

    def test_no_downstream_writes(self):  # AC-017-17
        before = {p for p in self.dir.rglob("*")}
        run = full_cycle(self.dir)
        QR.write(run)
        created = {p for p in self.dir.rglob("*")} - before
        outside = [p for p in created if run not in p.parents and p != run and "src-run" not in str(p)]
        self.assertEqual(outside, [])
        self.assertFalse([p for p in created if p.name.startswith("SG_") or p.suffix in (".csv", ".xlsx") and run in p.parents and "originais" not in str(p)])
        res = json.loads((run / QR.RESULT_FILE).read_text(encoding="utf-8"))
        self.assertEqual(res["gravacoes_externas"], [])
        self.assertNotIn('"SG_', json.dumps(res, ensure_ascii=False))
        self.assertEqual(sorted(p.name for p in run.iterdir()), sorted(["afirmacoes.json", "consistencia.json", "fontes", "inventario.json", "manifesto.json", "matriz.json",
                                                                        "orientacoes.json", "originais", "referencias.json", QR.RESULT_FILE, QR.SUMMARY_FILE])
                         if (run / "afirmacoes.json").exists() else sorted(["consistencia.json", "fontes", "inventario.json", "manifesto.json", "matriz.json",
                                                                            "orientacoes.json", "originais", "referencias.json", QR.RESULT_FILE, QR.SUMMARY_FILE]))

    def test_semantic_validator_catches_tampering(self):
        run = full_cycle(self.dir)
        good = QR.build(run)
        self.assertTrue(QR.validate(good)["valido"])

        def tampered(fn):
            r = copy.deepcopy(good)
            fn(r)
            r["execucao"]["conteudo_sha256"] = QR.content_hash(r)
            return QR.validate(r)
        v = tampered(lambda r: r["orientacoes"]["pedagogicas"][0].update(evidencias=[]))
        self.assertIn("EL1: Sim sem citação conferida", v["erros_semanticos"])
        v = tampered(lambda r: r["orientacoes"]["pedagogicas"][1].update(fontes_verificadas=["DOC-1"]))
        self.assertIn("EL2: Não sem todas as fontes de orientação verificadas", v["erros_semanticos"])
        v = tampered(lambda r: r["referencias"]["template"]["regra"].update(homologacao=None))
        self.assertIn("resumo por elemento calculado sem regra homologada", v["erros_semanticos"])
        v = tampered(lambda r: r["matriz"]["componentes"][0]["aulas_semanais"]["serie1"].update(status="nao_verificado"))
        self.assertTrue(any("valor sem verificação" in e for e in v["erros_semanticos"]))
        v = tampered(lambda r: r["pendencias"].append({"codigo": "FONTE_AUSENTE", "frente": "entradas", "detalhe": "teste", "fonte_id": None, "bloqueia_completude": True}))
        self.assertIn("status completo com pendências ou conflitos abertos", v["erros_semanticos"])
        r = copy.deepcopy(good)
        r["matriz"]["componentes"][0]["aulas_semanais"]["serie1"]["valor"] = 9
        self.assertIn("conteudo_sha256 não confere com o conteúdo", QR.validate(r)["erros_semanticos"])
        r = copy.deepcopy(good)
        r["gravacoes_externas"] = [{"destino": "SG_Componentes"}]
        self.assertFalse(QR.validate(r)["valido"])
        r = copy.deepcopy(good)
        r["revisao_humana"]["status"] = "aprovado"
        self.assertFalse(QR.validate(r)["valido"])

    def test_parity_with_filled_template(self):  # AC-017-15 mechanics (real sample pending)
        run = full_cycle(self.dir)
        res = QR.build(run)
        key = QR.key_from_template(self.dir / "src-run" / "template.xlsx", "MG", 2026)
        rep = QR.parity(res, key)
        self.assertEqual(rep["matriz"]["pareadas"], 6)
        self.assertEqual(rep["matriz"]["campos"], {"comparados": 24, "iguais": 24, "diferentes": 0, "sem_valor_no_plugin": 0})
        self.assertEqual((rep["orientacoes"]["comparadas"], rep["orientacoes"]["iguais"]), (5, 4))
        self.assertEqual(rep["orientacoes"]["diferencas"][0]["codigo"], "PA2")  # plugin Não, analysts SIM: explained case by case
        p = proposal()
        p["componentes"][1]["aulas_semanais"]["serie2"] = {"valor": None, "motivo": "nao_verificado"}
        p["componentes"][3]["classificacao"] = "Aprofundamento"
        MA.register(run, p)
        rep = QR.parity(QR.build(run), key)
        self.assertEqual(rep["matriz"]["campos"]["sem_valor_no_plugin"], 1)
        self.assertEqual([d["campo"] for d in rep["matriz"]["diferencas"]], ["classificacao"])

    def test_committed_example_is_valid(self):
        data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.assertTrue(QR.validate(data)["valido"], QR.validate(data))
        self.assertIn("SINTETICO", data["execucao"]["id"])

    def test_cli(self):
        run = full_cycle(self.dir)
        cli = [sys.executable, str(QROOT / "resultado_qualidade.py")]
        out = subprocess.run(cli + ["resultado", "--pasta", str(run), "--json"], capture_output=True, text=True, encoding="utf-8")
        data = json.loads(out.stdout)
        self.assertEqual((out.returncode, data["data"]["status"]), (0, "completo"), out.stdout)
        res = str(run / QR.RESULT_FILE)
        self.assertEqual(subprocess.run(cli + ["validar", res, "--json"], capture_output=True).returncode, 0)
        out = subprocess.run(cli + ["resumo", res], capture_output=True, text=True, encoding="utf-8")
        self.assertIn("## Matriz curricular", out.stdout)
        out = subprocess.run(cli + ["paridade", res, "--gabarito-template", str(self.dir / "src-run" / "template.xlsx"), "--json"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(json.loads(out.stdout)["data"]["orientacoes"]["diferentes"], 1)
        bad = json.loads(Path(res).read_text(encoding="utf-8"))
        bad["execucao"]["modelo"] = "7h"
        Path(res).write_text(json.dumps(bad), encoding="utf-8")
        self.assertEqual(subprocess.run(cli + ["validar", res, "--json"], capture_output=True).returncode, 1)


def write_example():
    """Regenerates the committed synthetic example (run: python -m test.quality.test_q17_result --exemplo)."""
    with tempfile.TemporaryDirectory() as tmp:
        run = full_cycle(Path(tmp))
        CC.register(run, [{"tipo": "carga_semanal", "componente": "Estudo Orientado", "ciclo": {"uf": "MG", "ano": 2026, "modelo": "9h"},
                           "valores": {"serie1": 4, "serie2": 4, "serie3": 4}, "unidade": "DOC-1:p2",
                           "trecho_literal": "Estudo Orientado: 4 aulas na 1ª série, 4 na 2ª e 4 na 3ª série."}])
        res = QR.build(run)
    res["execucao"]["solicitacao_id"] = "EXEMPLO-SINTETICO-001"
    res["execucao"]["id"] = "EXEMPLO-SINTETICO-001-r1"
    res["execucao"]["gerado_em"] = "2026-11-16T00:00:00+00:00"
    res["matriz"]["selecao"]["confirmacao"]["data"] = "2026-11-16T00:00:00+00:00"
    res["execucao"]["conteudo_sha256"] = QR.content_hash(res)
    assert QR.validate(res)["valido"], QR.validate(res)
    EXAMPLE.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    if "--exemplo" in sys.argv:
        write_example()
    else:
        unittest.main()
