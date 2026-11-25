"""Notion as the only output (0.1.8): run, orientations, matrix components and elements and the grouped review queue
written as rows of the result bases, checked after writing, idempotent, keyed by run, never touching human fields.

Synthetic sources and a mocked Notion only: no real request, document or credential is used.
"""
import copy
import json
import time
import unittest
import uuid
from pathlib import Path

from test.quality.test_q18_revisao_enxuta import (  # noqa: E402  (shared synthetic run builders and the mocked request)
    CC, ES, NP, OA, PAGE_ID, QR, FakeNotion, Tmp, TF, cli, decided_run, publish, sim)

import notion_results as NR  # noqa: E402  (QROOT is already on sys.path through the import above)

REQUEST = {"page_id": PAGE_ID, "id_solicitacao": "SINTETICO-001", "uf": ["MG"], "ano": 2026, "status": "Elaborando Resposta"}


class FakeBases:
    """The five result bases as the connector would see them: rows with a page id and properties."""

    def __init__(self):
        self.rows = {b: [] for b in NR.BASES}

    def apply(self, base, plan):
        for c in plan["criar"]:
            self.rows[base].append({"page_id": str(uuid.uuid4()), "propriedades": copy.deepcopy(c["propriedades"])})
        for u in plan["atualizar"]:
            row = next(r for r in self.rows[base] if r["page_id"] == u["page_id"])
            row["propriedades"].update(copy.deepcopy(u["propriedades"]))

    def read(self, base, prefix=None):
        rows = copy.deepcopy(self.rows[base])
        if prefix:  # the skill reads only the rows of this run (by relation or by key prefix)
            kp = NR.KEY_PROP[base]
            rows = [r for r in rows if str(r["propriedades"].get(kp, "")).startswith(prefix)]
        return rows

    def by_key(self, base, key):
        kp = NR.KEY_PROP[base]
        return next(r for r in self.rows[base] if r["propriedades"].get(kp) == key)


def sync(run, bases, only=NR.BASES):
    out = {}
    for b in only:
        plan = NR.plan(run, b, bases.read(b))
        bases.apply(b, plan)
        out[b] = plan
        NR.confirm(run, b, bases.read(b))
    return out


class NotionOutputTest(Tmp):
    def setUp(self):
        super().setUp()
        self.run = decided_run(self.dir)
        TF.fill(self.run)
        self.bases = FakeBases()

    def deliver(self):
        NR.start(self.run, REQUEST)
        sync(self.run, self.bases)
        publish(self.run, FakeNotion())
        return NR.delivery(self.run)

    def test_full_delivery_writes_every_base_and_moves_status_last(self):
        NR.start(self.run, REQUEST)
        with self.assertRaises(NR.NotionOutputError) as e:  # the other bases hang on the run row
            NR.desired_rows(self.run, "orientacoes")
        self.assertEqual(e.exception.code, "EXECUCAO_NAO_GRAVADA")
        sync(self.run, self.bases, ("execucao",))
        self.assertFalse(NR.delivery(self.run)["pronta"])  # status never moves before everything is checked
        sync(self.run, self.bases, NR.BASES[1:])
        self.assertFalse(NR.delivery(self.run)["pronta"])  # the template is still missing
        publish(self.run, FakeNotion())
        d = NR.delivery(self.run)
        self.assertEqual((d["pronta"], d["novo_status"]), (True, NP.STATUS_DELIVERED))
        result = NP._result(self.run)
        oris = [o for k in ("pedagogicas", "gestao") for o in result["orientacoes"][k]]
        self.assertEqual(len(self.bases.rows["orientacoes"]), len(oris))
        self.assertEqual(len(self.bases.rows["componentes"]), len(result["matriz"]["componentes"]))
        self.assertEqual(len(self.bases.rows["fila"]), QR.grouped_review_queue(result)["total_grupos"])
        exe = self.bases.rows["execucao"][0]
        self.assertEqual(exe["propriedades"]["Validação humana"], "Aguardando")
        self.assertIn("plugin " + QR.plugin_version(), exe["propriedades"]["Motor"])
        self.assertEqual(exe["propriedades"]["Itens na fila"], QR.grouped_review_queue(result)["total_grupos"])
        rel = [r["propriedades"]["Execução"] for b in NR.BASES[1:] for r in self.bases.rows[b]]
        self.assertTrue(rel and all(x == [exe["page_id"]] for x in rel))
        self.assertEqual(ES.status(self.run)["etapas"][-1]["estado"], "feita")
        self.assertEqual(NR.delivery(self.run, "Concluído")["novo_status"], None)  # never regresses

    def test_keys_carry_the_run_and_two_runs_never_collide(self):
        NR.start(self.run, REQUEST)
        sync(self.run, self.bases, ("execucao", "orientacoes"))
        keys = [r["propriedades"]["Chave"] for r in self.bases.rows["orientacoes"]]
        self.assertTrue(all(k.startswith("MG-2026-SINTETICO001r1-") for k in keys), keys)
        self.assertIn("MG-2026-SINTETICO001r1-EL1", keys)
        manifest = json.loads((self.run / "manifesto.json").read_text(encoding="utf-8"))
        manifest["revisao"] = 2  # a second run of the same request (r2): new rows, the first run's rows stay
        (self.run / "manifesto.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        CC.run(self.run)
        self.assertTrue(QR.write(self.run)["ok"])
        NR.start(self.run, REQUEST)
        plan = NR.plan(self.run, "execucao", self.bases.read("execucao", "MG 2026 — SINTETICO-001-r2"))
        self.assertEqual((len(plan["criar"]), len(plan["atualizar"])), (1, 0))

    def test_rerun_is_idempotent(self):
        self.deliver()
        before = {b: len(self.bases.rows[b]) for b in NR.BASES}
        NR.start(self.run, REQUEST)
        plans = sync(self.run, self.bases)
        self.assertTrue(all(not p["criar"] and not p["atualizar"] for p in plans.values()), {b: (len(p["criar"]), len(p["atualizar"])) for b, p in plans.items()})
        self.assertEqual(before, {b: len(self.bases.rows[b]) for b in NR.BASES})

    def test_human_fields_are_never_written(self):
        self.deliver()
        key = "MG-2026-SINTETICO001r1-EL1"
        row = self.bases.by_key("orientacoes", key)
        row["propriedades"].update({"Decisão humana": "Não", "Comentário analista": "Conferido com a coordenação."})
        exe = self.bases.rows["execucao"][0]
        exe["propriedades"]["Validação humana"] = "Validado"
        time.sleep(0.05)
        OA.register(self.run, [sim("EL2")])  # a later proposal changes the result: rows are updated
        CC.run(self.run)
        self.assertTrue(QR.write(self.run)["ok"])
        NR.start(self.run, REQUEST)
        plans = sync(self.run, self.bases, ("execucao", "orientacoes"))
        for b in ("execucao", "orientacoes"):
            for u in plans[b]["atualizar"] + plans[b]["criar"]:
                self.assertFalse(set(u["propriedades"]) & (NR.HUMAN[b] - ({"Validação humana"} if u in plans[b]["criar"] else set())))
        self.assertEqual(self.bases.by_key("orientacoes", key)["propriedades"]["Decisão humana"], "Não")
        self.assertEqual(self.bases.by_key("orientacoes", key)["propriedades"]["Comentário analista"], "Conferido com a coordenação.")
        self.assertEqual(self.bases.rows["execucao"][0]["propriedades"]["Validação humana"], "Validado")
        self.assertEqual(self.bases.by_key("orientacoes", "MG-2026-SINTETICO001r1-EL2")["propriedades"]["Presença (Claude)"], "Sim")

    def test_queue_task_in_the_analysts_hands_is_not_touched(self):
        OA.register(self.run, [{"codigo": "EL2", "presenca": None, "justificativa": "A evidência registrada não basta para decidir."}])
        CC.run(self.run)
        self.assertTrue(QR.write(self.run)["ok"])
        TF.fill(self.run)
        self.deliver()
        self.assertTrue(self.bases.rows["fila"])
        task = self.bases.rows["fila"][0]
        task["propriedades"].update({"Status": "Em análise", "O que decidir": "texto editado pelo analista"})
        NR.start(self.run, REQUEST)
        plan = NR.plan(self.run, "fila", self.bases.read("fila"))
        self.assertEqual([b["chave"] for b in plan["bloqueadas"]], [task["propriedades"]["Referência"]])
        self.assertFalse(any(u["chave"] == task["propriedades"]["Referência"] for u in plan["atualizar"]))
        NR.confirm(self.run, "fila", self.bases.read("fila"))  # a task taken by the analyst does not fail the check

    def test_missing_or_duplicated_row_is_not_confirmed_and_resumes(self):
        NR.start(self.run, REQUEST)
        sync(self.run, self.bases, ("execucao",))
        plan = NR.plan(self.run, "orientacoes", [])
        plan_partial = dict(plan, criar=plan["criar"][:-1])  # one write was lost
        self.bases.apply("orientacoes", plan_partial)
        with self.assertRaises(NR.NotionOutputError) as e:
            NR.confirm(self.run, "orientacoes", self.bases.read("orientacoes"))
        self.assertEqual(e.exception.code, "NOTION_NAO_CONFERE")
        self.assertEqual(json.loads((self.run / NR.FILE).read_text(encoding="utf-8"))["bases"]["orientacoes"]["status"], "falhou")
        again = NR.plan(self.run, "orientacoes", self.bases.read("orientacoes"))  # resumes: only the lost row
        self.assertEqual(len(again["criar"]), 1)
        self.bases.apply("orientacoes", again)
        NR.confirm(self.run, "orientacoes", self.bases.read("orientacoes"))
        self.bases.rows["orientacoes"].append(copy.deepcopy(self.bases.rows["orientacoes"][0]))
        with self.assertRaises(NR.NotionOutputError) as e:
            NR.plan(self.run, "orientacoes", self.bases.read("orientacoes"))
        self.assertEqual(e.exception.code, "LINHA_DUPLICADA")

    def test_wrong_or_missing_request_writes_nothing(self):
        with self.assertRaises(NR.NotionOutputError) as e:
            NR.start(self.run, dict(REQUEST, page_id=""))
        self.assertEqual(e.exception.code, "SOLICITACAO_SEM_ID")
        for change in ({"uf": ["CE"]}, {"ano": 2025}, {"id_solicitacao": "QUA-99"}):
            with self.assertRaises(NR.NotionOutputError) as e:
                NR.start(self.run, dict(REQUEST, **change))
            self.assertEqual(e.exception.code, "SOLICITACAO_DIVERGENTE")
        self.assertFalse((self.run / NR.FILE).exists())
        with self.assertRaises(NR.NotionOutputError) as e:
            NR.plan(self.run, "execucao", [])
        self.assertEqual(e.exception.code, "SAIDA_NAO_INICIADA")

    def test_changed_result_requires_a_new_start(self):
        NR.start(self.run, REQUEST)
        time.sleep(0.05)
        OA.register(self.run, [sim("EL2")])
        CC.run(self.run)
        self.assertTrue(QR.write(self.run)["ok"])
        with self.assertRaises(NR.NotionOutputError) as e:
            NR.plan(self.run, "execucao", [])
        self.assertEqual(e.exception.code, "RESULTADO_MUDOU")

    def test_cli_round_trip(self):
        page = self.dir / "pagina.json"
        page.write_text(json.dumps(REQUEST), encoding="utf-8")
        self.assertEqual(cli("notion-iniciar", "--pasta", str(self.run), "--pagina-json", str(page))["code"], "SAIDA_INICIADA")
        r = cli("notion-linhas", "--pasta", str(self.run), "--base", "execucao")
        self.assertEqual(r["code"], "LINHAS")
        self.assertIn("## Fontes (DOC-n)", r["data"]["corpo"])
        r = cli("notion-planejar", "--pasta", str(self.run), "--base", "execucao")
        self.assertEqual(len(r["data"]["criar"]), 1)
        self.assertEqual(cli("notion-entregar", "--pasta", str(self.run))["code"], "ENTREGA_INCOMPLETA")


class IceRulesTest(Tmp):
    """Approved rules of the ICE (manifesto_ice.json, decided by the Quality team): codes, minimum load, equivalences."""

    RULES = {"versao": "SINTETICA-1", "aprovado_por": "Coordenação de Qualidade (sintético)", "data": "2026-11-20",
             "codigos": {"pedagogicas": [{"codigo": "EL9", "texto": "Orientação sintética só do ICE"}], "gestao": []},
             "carga_minima": [{"classificacao": "Projeto de Vida", "minimo_por_serie": {"serie1": 2, "serie2": 2, "serie3": 2}},
                              {"classificacao": "Estudo Orientado e Avaliação Semanal", "minimo_total": 12}],
             "equivalencias_componentes": [{"uf": "MG", "nome": "Robótica", "classificacao": "Aprofundamento"},
                                           {"uf": "CE", "nome": "Eletiva", "classificacao": "Projeto de Vida"}]}

    def run_with_rules(self, rules):
        import matrix_analysis as MA
        import quality_run as RUN
        from test.quality import q17_fixtures as FX
        from test.quality.test_q17_matrix import proposal
        from test.quality.test_q18_revisao_enxuta import matrix_doc

        path = FX.source_set(self.dir / "src")
        m = json.loads(path.read_text(encoding="utf-8"))
        m["configuracao_ice"] = rules
        path.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        run = self.dir / "run"
        RUN.start_run(path, run)
        RUN.register_image_reading(run, "DOC-2:img1", "Organograma: direção, coordenação pedagógica e professores")
        prop = proposal(matrix_doc(run))
        robot = next(c for c in prop["componentes"] if c["nome_original"] == "Robótica")
        robot.update(classificacao="", base_classificacao="nome", justificativa_classificacao="", confianca_classificacao=40)
        MA.register(run, prop)
        return run

    def test_equivalence_codes_and_minimum_load_take_effect(self):
        import matrix_analysis as MA
        import template_rules as TR

        run = self.run_with_rules(self.RULES)
        comps = {c["nome_original"]: c for c in MA.section(run)[0]["componentes"]}
        robot = comps["Robótica"]
        self.assertEqual((robot["classificacao"], robot["classificacao_status"], robot["base_classificacao"]), ("Aprofundamento", "aceita", "equivalencia_aprovada"))
        self.assertIn("Equivalência aprovada", robot["justificativa_classificacao"])
        self.assertEqual(comps["Eletiva"]["classificacao"], "Eletivas de Base")  # the CE equivalence does not apply to MG
        refs = TR.load_references(run)
        self.assertIn("EL9", [c["codigo"] for c in refs["ice"]["codigos"]["pedagogicas"]])
        self.assertTrue(any("configuração aprovada" in a for a in refs["ice"]["avisos"]))
        cons = CC.run(run)
        low = [c for c in cons["conflitos"] if c["codigo"] == "CARGA_ABAIXO_MINIMO"]
        self.assertEqual([c["entidade"] for c in low], ["Projeto de Vida"])  # 3ª série 0 < 2; Estudo Orientado 12 >= 12
        self.assertIn("3ª série 0 < 2", low[0]["detalhe"])
        self.assertTrue(QR.write(run)["ok"])

    def test_without_rules_nothing_changes(self):
        import matrix_analysis as MA

        run = self.run_with_rules(None)
        robot = next(c for c in MA.section(run)[0]["componentes"] if c["nome_original"] == "Robótica")
        self.assertEqual(robot["classificacao_status"], "pendente")
        self.assertFalse([c for c in CC.run(run)["conflitos"] if c["codigo"] == "CARGA_ABAIXO_MINIMO"])

    def test_rules_file_must_be_approved_and_valid(self):
        import ice_config as ICE

        f = self.dir / "manifesto_ice.json"
        f.write_text(json.dumps({"versao": "2026.1", "aprovado": False, "aprovado_por": None, **{k: self.RULES[k] for k in ("codigos",)}}), encoding="utf-8")
        with self.assertRaises(ICE.IceConfigError) as e:
            ICE.read_rules_file(str(f))
        self.assertEqual(e.exception.code, "ICE_NAO_APROVADO")
        f.write_text(json.dumps({"versao": "2026.1", "aprovado": True, "aprovado_por": "Qualidade", "codigos": {"pedagogicas": ["el-1"]}}), encoding="utf-8")
        with self.assertRaises(ICE.IceConfigError) as e:
            ICE.read_rules_file(str(f))
        self.assertEqual(e.exception.code, "ICE_CONFIG_INVALIDA")
        f.write_text(json.dumps({"versao": "2026.1", "aprovado": True, "aprovado_por": "Qualidade", "data": "2026-11-20",
                                 "carga_minima": self.RULES["carga_minima"]}), encoding="utf-8")
        rec = ICE.read_rules_file(str(self.dir))
        self.assertEqual((rec["versao"], rec["aprovado_por"], len(rec["carga_minima"])), ("2026.1", "Qualidade", 2))

    def test_manifest_cli_takes_the_approved_rules_file(self):
        f = self.dir / "manifesto_ice.json"
        f.write_text(json.dumps({"versao": "2026.1", "aprovado": True, "aprovado_por": "Qualidade", "data": "2026-11-20",
                                 "equivalencias_componentes": self.RULES["equivalencias_componentes"]}), encoding="utf-8")
        out = self.dir / "manifesto.json"
        r = cli("manifesto-montar", "--uf", "MG", "--ano", "2026", "--solicitacao", "QUA-20", "--estado", "a.pdf", "--template", "t.xlsx",
                "--config-ice", str(f), "--saida", str(out))
        self.assertEqual(r["code"], "MANIFESTO_MONTADO")
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["configuracao_ice"]["aprovado_por"], "Qualidade")

    def test_configured_rules_reach_a_run_whose_ice_file_came_with_the_request(self):
        import ice_config as ICE

        folder = self.dir / "ICE-oficial"
        folder.mkdir()
        (folder / "referencial.pdf").write_bytes(b"%PDF-1.4 sintetico")
        (folder / ICE.MANIFEST).write_text(json.dumps({"versao": "2026.1", "aprovado": True, "aprovado_por": "Qualidade", "data": "2026-11-20",
                                                       "documentos": ["referencial.pdf"], "equivalencias_componentes": self.RULES["equivalencias_componentes"]}),
                                           encoding="utf-8")
        m = {"entradas": {"referencial_ice": [{"uri": "baixado-da-solicitacao.pdf"}]}}
        out = ICE.fill_manifest(m, str(folder))
        self.assertEqual(out["entradas"]["referencial_ice"], m["entradas"]["referencial_ice"])  # the sent file is kept
        self.assertEqual(out["configuracao_ice"]["equivalencias_componentes"][0]["nome"], "Robótica")
        self.assertNotIn("configuracao_ice", ICE.fill_manifest(m, ""))  # nothing configured: no approved rules


class RowShapeTest(unittest.TestCase):
    RESULT = {"execucao": {"uf": "CE", "ano": 2026, "solicitacao_id": "QUA-13", "revisao": 1, "id": "QUA-13-r1"}}

    def cell(self, status, valor=None, proposto=None, faixa=None, metodo="citacao_conferida"):
        return {"status": status, "valor": valor, "valor_proposto": proposto, "faixa": faixa,
                "evidencia": {"fonte_id": "DOC-1", "unidade": "DOC-1:p89-img1", "metodo": metodo, "verificacao": "nao_verificavel"}}

    def test_range_and_absent_cells_stay_empty_never_zero(self):
        comp = {"id": "C001", "nome_original": "Língua Portuguesa e suas Literaturas", "classificacao": "Formação Geral Básica", "classificacao_status": "aceita",
                "justificativa_classificacao": "Componente da FGB.", "revisar": True, "motivos": ["VALOR_EM_FAIXA"],
                "aulas_semanais": {"serie1": self.cell("faixa", faixa={"min": 3, "max": 4}), "serie2": self.cell("nao_verificado", proposto=4, metodo="interpretacao_ia"),
                                   "serie3": dict(self.cell("ausente_na_fonte"), evidencia=None)}}
        row = NR._component_row(self.RESULT, comp, ["Formação Geral Básica"], ["x"])
        self.assertEqual((row["Aulas 1ª série"], row["Aulas 2ª série"], row["Aulas 3ª série"]), (None, 4, None))
        self.assertEqual(row["Chave"], "CE-2026-QUA13r1-C001")
        self.assertIn("3 ou 4", row["Justificativa"])
        self.assertIn("imagem por IA", row["Justificativa"])
        self.assertIn("3ª série", row["Justificativa"])

    def test_elements_only_with_an_approved_rule(self):
        result = dict(self.RESULT, matriz={"resumo_por_elemento": {"status": "pendente_regra_homologada", "motivo": "REGRA_NAO_HOMOLOGADA", "elementos": []},
                                          "minutos_aula": {"status": "nao_verificado", "valor": None}},
                      referencias={"template": {"classificacoes": ["Formação Geral Básica"]}})
        self.assertEqual(NR._element_rows(result, ["x"]), [])
        result["matriz"]["resumo_por_elemento"] = {"status": "calculado", "motivo": "Regra homologada.", "elementos": [
            {"elemento": "Matriz completa", "serie1": 45, "serie2": 45, "serie3": 45}, {"elemento": "Formação Geral Básica", "serie1": 24, "serie2": 24, "serie3": 18},
            {"elemento": "Projeto de Vida + Pós-Médio", "serie1": 4, "serie2": 4, "serie3": 4}]}
        rows = NR._element_rows(result, ["x"])
        self.assertEqual([r["Regra"] for r in rows], ["TOTAL", "CLASSE", "PVPOS"])
        self.assertEqual(rows[1]["Chave"], "CE-2026-QUA13r1-E02")

    def test_review_count_is_the_queue(self):
        with self.subTest("the result count is the detailed queue"):
            import tempfile

            with tempfile.TemporaryDirectory() as t:
                run = decided_run(Path(t))
                r = NP._result(run)
                self.assertEqual(r["revisao_humana"]["itens"], len(QR.review_queue(r)))
                r["revisao_humana"]["itens"] += 5  # the QUA-13 mismatch (105 x 110) is now a semantic error
                r["execucao"]["conteudo_sha256"] = QR.content_hash(r)
                self.assertIn("revisao_humana.itens não confere com a fila de revisão", QR.semantic_errors(r))


if __name__ == "__main__":
    unittest.main()
