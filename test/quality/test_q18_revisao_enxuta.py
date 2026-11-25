"""Independent analysis, lean review and verified Notion delivery (synthetic sources and a mocked Notion only).

Covers: template history never used as evidence; the filled copy keeps history outside the target block and never
inherits current fields; the 70% technical floor with explicit review for indirect/unreliable evidence; the limited,
resumable second pass; the grouped review queue; and the idempotent, verified publication in the Notion request
(no "most recent request" fallback). No real request, document or credential is used.
"""
import contextlib
import copy
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QROOT = ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"
sys.path.insert(0, str(QROOT))
import cross_check as CC  # noqa: E402
import document_normalizer as DN  # noqa: E402
import esteira as ES  # noqa: E402
import evidence_check as EC  # noqa: E402
import matrix_analysis as MA  # noqa: E402
import notion_publish as NP  # noqa: E402
import orientation_analysis as OA  # noqa: E402
import quality_policy as QP  # noqa: E402
import quality_result as QR  # noqa: E402
import quality_run as RUN  # noqa: E402
import resultado_qualidade as CLI  # noqa: E402
import second_pass as SP  # noqa: E402
import template_fill as TF  # noqa: E402
import template_rules as TR  # noqa: E402
from test.quality import q17_fixtures as FX  # noqa: E402
from test.quality.test_q17_matrix import approve, proposal  # noqa: E402
from test.quality.test_q17_orientations import nao, sim  # noqa: E402

PAGE_ID = "11111111-2222-4333-8444-555555555555"  # synthetic test request, never a real one


@contextlib.contextmanager
def patched_template(change):
    """Lets a test change the synthetic template sheets before they are written (change(sheets) -> None)."""
    original = FX.make_xlsx

    def wrapper(path, sheets, *a, **kw):
        if "1.1 Base orient. pedagógicas" in sheets:
            change(sheets)
        return original(path, sheets, *a, **kw)
    FX.make_xlsx = wrapper
    try:
        yield
    finally:
        FX.make_xlsx = original


def matrix_doc(run):
    return next(f["id"] for f in RUN.load_inventory(run)["fontes"] if f["nome"] == "matriz.xlsx")


def base_run(tmp: Path, name="run", change=None, matrix=None, confirm=True, **fixture) -> Path:
    """Inputs read, image read, matrix registered (and confirmed), rule approved; orientations left to the test."""
    run = tmp / name
    with patched_template(change or (lambda s: None)):
        manifest = FX.source_set(tmp / ("src-" + name), **fixture)
    RUN.start_run(manifest, run)
    RUN.register_image_reading(run, "DOC-2:img1", "Organograma: direção, coordenação pedagógica e professores")
    MA.register(run, (matrix or proposal)(matrix_doc(run)))
    if confirm:
        MA.confirm(run, "Analista sintético", "Conferida com a resolução sintética")
    approve(run, TR.load_references(run)["template"]["matriz"]["regra"]["formula_sha256"])
    return run


def decided_run(tmp: Path, name="run", **kw) -> Path:
    run = base_run(tmp, name, **kw)
    OA.register(run, [sim("EL1"), nao("EL2"), sim("AC1", quote=FX.ORIENT_P2), sim("PA1", "DOC-2:par2", FX.GESTAO_P1), nao("PA2")])
    CC.run(run)
    assert QR.write(run)["ok"]
    return run


def cli(*argv) -> dict:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        CLI.main(list(argv) + ["--json"])
    return json.loads(buf.getvalue())


def sheet_cells(path):
    return {s["nome"]: TR._cells(s) for s in DN.read_workbook(Path(path))["abas"]}


def text(cells, ref):
    return TR._text(cells.get(DN.split_ref(ref)))


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()


# ---------------- 3.1 independence from the template history ----------------

class IndependenceTest(Tmp):
    def test_references_keep_no_historical_values(self):
        run = base_run(self.dir)
        refs = TR.load_references(run)
        raw = json.dumps(refs, ensure_ascii=False)
        self.assertNotIn("gabarito_orientacoes", raw)
        for key in TR.HISTORY_KEYS:
            self.assertNotIn(key, refs["template"]["matriz"])
        self.assertGreater(refs["template"]["historico_isolado"]["orientacoes_preenchidas"], 0)  # only how many, never what
        self.assertEqual(refs["template"]["historico_isolado"]["linhas_matriz_preenchidas"], len(FX.MATRIX_ROWS))

    def test_template_is_not_a_searchable_source(self):
        run = base_run(self.dir)
        tid = TR.load_references(run)["template"]["fonte_id"]
        self.assertEqual(cli("unidades", "--pasta", str(run), "--fonte", tid)["code"], "TEMPLATE_NAO_E_FONTE")
        self.assertEqual(cli("buscar", "--pasta", str(run), "--termo", "Sim", "--classe", "template_cluster")["code"], "TEMPLATE_NAO_E_FONTE")
        hits = cli("buscar", "--pasta", str(run), "--termo", "Projeto de Vida")["data"]["resultados"]
        self.assertTrue(hits)
        self.assertFalse([h for h in hits if h["unidade"].startswith(tid + ":")])

    def test_template_declared_as_state_source_is_not_evidence(self):
        unit = {"id": "DOC-9:Plan!G10", "tipo": "sheet_cell", "status": "lida", "texto": "Sim — eletivas com relação direta com a BNCC",
                "localizacao": {"tipo": "sheet_cell", "aba": "Plan", "celula": "G10"}}
        index = {unit["id"]: ("DOC-9", unit)}
        ref = {"unidade": unit["id"], "trecho_literal": "eletivas com relação direta com a BNCC"}
        for wrong in ("template_cluster", "referencial_ice"):
            r = EC.check(ref, index, {"DOC-9": ["orientacoes_estaduais", wrong]}, ("orientacoes_estaduais",))
            self.assertFalse(r["ok"])
            self.assertIn("não serve como prova", r["motivo"])
        self.assertTrue(EC.check(ref, index, {"DOC-9": ["orientacoes_estaduais"]}, ("orientacoes_estaduais",))["ok"])

    def test_same_decisions_with_contradictory_history(self):
        def contradict(sheets):  # analysts' answers flipped and a different matrix fill
            for k, v in list(sheets["1.1 Base orient. pedagógicas"].items()):
                if k.startswith("G") and k[1:].isdigit() and int(k[1:]) >= 10:
                    sheets["1.1 Base orient. pedagógicas"][k] = "Não" if v == "Sim" else "Sim"
            m = next(v for n, v in sheets.items() if n.startswith("2.1 Revisão Matriz"))
            for k in list(m):
                if k[0] in "CDE" and k[1:].isdigit() and 12 <= int(k[1:]) <= 17:
                    m[k] = 9
            m["C6"], m["C8"] = 45, 2019
        a = decided_run(self.dir, "a")
        b = decided_run(self.dir, "b", change=contradict)

        def decisions(run):
            r = QR.build(run)
            return {"matriz": [{k: c[k] for k in ("nome_original", "classificacao", "classificacao_status", "revisar")}
                               | {s: (c["aulas_semanais"][s]["valor"], c["aulas_semanais"][s]["status"]) for s in MA.SERIES} for c in r["matriz"]["componentes"]],
                    "minutos": r["matriz"]["minutos_aula"]["valor"],
                    "orientacoes": {o["codigo"]: (o["presenca"], o["status"], o["confianca"]) for k in OA.TYPES for o in r["orientacoes"][k]}}
        self.assertEqual(decisions(a), decisions(b))


# ---------------- 3.2 filled copy ----------------

class FilledCopyTest(Tmp):
    def test_other_years_and_ufs_preserved_outside_the_block(self):
        def add_2025(sheets):
            t = sheets["1.1 Base orient. pedagógicas"]
            t.update({"I8": "MG", "I9": "2025", "J9": "Observações/comentários"})
            for k in range(len(FX.ICE_PED)):
                t[f"I{10 + k}"], t[f"J{10 + k}"] = "Não", f"comentário de 2025 linha {k}"
        run = decided_run(self.dir, change=add_2025)
        out = TF.fill(run)["arquivo"]
        s = sheet_cells(out)["1.1 Base orient. pedagógicas"]
        for k in range(len(FX.ICE_PED)):
            self.assertIn(text(s, f"G{10 + k}"), ("Sim", "Não", "Pendente"))
            self.assertEqual((text(s, f"I{10 + k}"), text(s, f"J{10 + k}")), ("Não", f"comentário de 2025 linha {k}"))

    def test_absent_current_fields_do_not_inherit(self):
        def prop(doc):
            p = proposal(doc)
            p["selecao"]["vigencia"] = None
            del p["minutos_aula"]
            return p
        run = base_run(self.dir, matrix=prop)
        OA.register(run, [sim("EL1")])  # the others stay not evaluated: their cells must not keep old answers
        CC.run(run)
        self.assertTrue(QR.write(run)["ok"])
        mins = json.loads((run / "matriz.json").read_text(encoding="utf-8"))["minutos_aula"]
        self.assertIn("não informada na proposta", mins["motivo"])
        self.assertNotIn("valor vazio sem motivo", mins["motivo"])
        r = TF.fill(run)
        cells = sheet_cells(r["arquivo"])
        m = cells["2.1 Revisão Matriz MG"]
        self.assertEqual((text(m, "C6"), text(m, "C8")), ("", ""))  # template had 50 and 2026 from the previous fill
        t11 = cells["1.1 Base orient. pedagógicas"]
        self.assertEqual(text(t11, "G11"), "")  # EL2 not evaluated: the analysts' "Não" did not survive
        self.assertTrue(r["entrega_valida"])

    def test_missing_uf_block_blocks_the_delivery(self):
        def other_year(sheets):
            sheets["1.1 Base orient. pedagógicas"]["G9"] = "2025"
        run = decided_run(self.dir, change=other_year)
        r = TF.fill(run)
        self.assertFalse(r["entrega_valida"])
        self.assertTrue(any(b.startswith("BLOCO_UF_ANO_AUSENTE") for b in r["bloqueios"]))
        out = cli("template-preencher", "--pasta", str(run))
        self.assertEqual((out["ok"], out["code"]), (False, "ENTREGA_BLOQUEADA"))
        self.assertEqual(ES.status(run)["proxima"], "template")
        with self.assertRaises(NP.PublishError) as e:
            NP.prepare(run, PAGE_ID)
        self.assertEqual(e.exception.code, "ENTREGA_BLOQUEADA")

    def test_yellow_follows_the_review_state(self):
        o = {"presenca": "Sim", "evidencias": [], "justificativa": "x", "revisar": False, "confianca": 72}
        self.assertFalse(TF.orientation_cells(o, {})[2])
        self.assertTrue(TF.orientation_cells({**o, "revisar": True}, {})[2])
        self.assertTrue(TF.orientation_cells({**o, "presenca": None, "motivos": []}, {})[2])


# ---------------- 4 confidence floor ----------------

class ConfidenceTest(Tmp):
    def setUp(self):
        super().setUp()
        self.run = base_run(self.dir)
        inv = RUN.load_inventory(self.run)
        self.index = RUN.unit_index(self.run)
        self.classes = {f["id"]: f["classes"] for f in inv["fontes"]}
        self.ctx = OA._context(inv)

    def d(self, p, ctx=None):
        return OA.decide(p, self.index, self.classes, ctx or self.ctx)

    def test_shared_floor(self):
        self.assertEqual(QP.QUALITY_MIN_CONFIDENCE, 70)
        self.assertEqual(MA.MIN_CLASS_CONFIDENCE, 70)
        self.assertEqual(TF.MIN_CONF, 70)
        import isg_eqv.rules as R
        self.assertEqual(R.DEFAULT_MINIMUM, 85)  # the legacy EQV flow is not changed

    def test_direct_quote_70_is_decided_and_69_goes_to_review(self):
        self.assertEqual(self.d(sim("EL1", conf=70))["status"], "decidido")
        r = self.d(sim("EL1", conf=69))
        self.assertEqual((r["presenca"], r["status"], r["revisar"]), ("Sim", "decidido_revisar", True))
        self.assertTrue(any("abaixo do mínimo de 70%" in m for m in r["motivos"]))

    def test_no_valid_quote_is_pending_whatever_the_confidence(self):
        p = sim("EL1", conf=99, quote="texto que não está no documento estadual de jeito nenhum")
        self.assertEqual((self.d(p)["presenca"], self.d(p)["status"]), (None, "pendente"))
        tid = TR.load_references(self.run)["template"]["fonte_id"]
        p = sim("EL1", conf=99, unit=f"{tid}:1.1 Base orient. pedagógicas!G10", quote="Sim")
        self.assertEqual(self.d(p)["status"], "pendente")

    def test_indirect_or_distinct_evidence_is_not_decided_by_confidence(self):
        r = self.d(sim("EL1", conf=95, rel="Indireta"))
        self.assertEqual(r["status"], "decidido_revisar")
        self.assertIn(QP.REASON_INDIRECT, r["motivos"])
        self.assertEqual(self.d(sim("EL1", conf=95, rel="Distinto"))["status"], "pendente")

    def test_no_without_proof_or_coverage_is_pending(self):
        self.assertEqual(self.d(nao("EL2", ausencia=None))["status"], "pendente")
        self.assertEqual(self.d(nao("EL2", checked=("DOC-1",)))["status"], "pendente")
        r = self.d(nao("EL2"), {**self.ctx, "risco_de_ocultar": True})
        self.assertEqual(r["status"], "decidido_revisar")
        self.assertIn(QP.REASON_ABSENCE_RISK, r["motivos"])

    def test_matrix_classification_floor_and_image_values(self):
        def prop(conf):
            def f(doc):
                p = proposal(doc)
                for c in p["componentes"]:
                    c["confianca_classificacao"] = conf
                return p
            return f
        MA.register(self.run, prop(75)(matrix_doc(self.run)))
        self.assertFalse(any(c["revisar"] for c in MA.section(self.run)[0]["componentes"]))
        MA.register(self.run, prop(65)(matrix_doc(self.run)))
        self.assertTrue(all(c["revisar"] for c in MA.section(self.run)[0]["componentes"]))


# ---------------- 5 second pass ----------------

def range_matrix(doc):
    p = proposal(doc)
    sheet = p["selecao"]["unidades"][0]
    p["componentes"][0]["aulas_semanais"]["serie1"] = {"faixa": [4, 5], "unidade": f"{sheet}!F4", "trecho_literal": "4 ou 5 aulas"}
    return p


class SecondPassTest(Tmp):
    def setUp(self):
        super().setUp()
        self.run = base_run(self.dir, matrix=range_matrix, range_note=True)
        OA.register(self.run, [sim("EL1", conf=60), sim("EL2", quote="isto não está no documento estadual sintético"),
                               sim("AC1", quote=FX.ORIENT_P2, conf=60), sim("PA1", "DOC-2:par2", FX.GESTAO_P1), nao("PA2")])
        OA.analyst_decision(self.run, "PA2", "Não", "Decisão do analista sintético para teste", "Analista sintético")

    def test_plan_selects_only_doubts_without_previous_answers(self):
        r = SP.plan(self.run, self.dir / "re")
        rec = json.loads((self.run / SP.FILE).read_text(encoding="utf-8"))
        self.assertEqual(sorted(rec["orientacoes"]["selecionadas"]), ["AC1", "EL1", "EL2"])  # PA1 decided, PA2 analyst
        lote = json.loads((self.dir / "re" / "lote_A.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(x["codigo"] for x in lote), ["AC1", "EL1", "EL2"])
        self.assertNotIn("presenca", json.dumps(lote))
        self.assertIn("Segunda passagem", (self.dir / "re" / "INSTRUCOES.md").read_text(encoding="utf-8"))
        self.assertEqual(r["componentes"], 1)
        self.assertTrue((self.dir / "re" / "MATRIZ_SEGUNDA_LEITURA.md").exists())
        self.assertEqual(ES.status(self.run)["proxima"], "reanalise")

    def test_better_replaces_worse_or_contradictory_does_not(self):
        SP.plan(self.run, self.dir / "re")
        r = SP.register_orientations(self.run, [sim("EL1", conf=90), sim("EL2", quote="continua fora do documento estadual sintético"),
                                                nao("AC1"), nao("PA2"), sim("PA1", "DOC-2:par2", FX.GESTAO_P1)])
        self.assertEqual((r["substituidas"], r["mantidas"], r["divergentes"]), (["EL1"], ["EL2"], ["AC1"]))
        self.assertEqual(sorted(r["fora_da_selecao"]), ["PA1", "PA2"])
        store = json.loads((self.run / "orientacoes.json").read_text(encoding="utf-8"))
        self.assertEqual((store["EL1"]["status"], store["EL1"]["presenca"]), ("decidido", "Sim"))
        self.assertEqual((store["EL2"]["status"], store["EL2"]["presenca"]), ("pendente", None))
        self.assertEqual((store["AC1"]["presenca"], store["AC1"]["status"]), ("Sim", "decidido_revisar"))  # first kept, in review
        self.assertTrue(any("divergente" in m for m in store["AC1"]["motivos"]))
        self.assertEqual(store["PA2"]["origem"], "analista")
        again = SP.register_orientations(self.run, [sim("EL2")])
        self.assertEqual(again["ja_reavaliadas"], ["EL2"])  # one look per item and round

    def test_one_round_per_input_version_and_resumable(self):
        SP.plan(self.run, self.dir / "re")
        self.assertTrue(SP.plan(self.run, self.dir / "re")["retomada"])
        SP.register_orientations(self.run, [sim("EL1", conf=90)])
        SP.register_matrix(self.run, {"componentes": [{"nome_original": "Língua Portuguesa", "aulas_semanais": {"serie1": {"faixa": [4, 5]}, "serie2": 5, "serie3": 5}}]})
        SP.finish(self.run)
        self.assertTrue(SP.plan(self.run, self.dir / "re")["ja_concluida"])
        self.assertEqual(SP.status(self.run)["estado"], "feita")
        with self.assertRaises(SP.SecondPassError):
            SP.register_orientations(self.run, [sim("EL2")])
        RUN.register_image_reading(self.run, "DOC-2:img1", "Organograma revisto: direção e professores")  # inputs changed
        self.assertEqual(SP.status(self.run)["estado"], "pendente")
        self.assertFalse(SP.plan(self.run, self.dir / "re2")["ja_concluida"])

    def test_matrix_second_reading_never_changes_values(self):
        SP.plan(self.run, self.dir / "re")
        before = json.loads((self.run / "matriz.json").read_text(encoding="utf-8"))
        r = SP.register_matrix(self.run, {"componentes": [{"nome_original": "Língua Portuguesa", "aulas_semanais": {"serie1": 4, "serie2": 5, "serie3": 5}}]})
        self.assertEqual(r["divergem"], ["Língua Portuguesa"])
        after = json.loads((self.run / "matriz.json").read_text(encoding="utf-8"))
        c0, c1 = before["componentes"][0], after["componentes"][0]
        self.assertEqual(c0["aulas_semanais"], c1["aulas_semanais"])
        self.assertTrue(c1["revisar"])
        self.assertTrue(any(m.startswith("duas leituras divergem") for m in c1["motivos"]))

    def test_missing_document_requested_once(self):
        SP.plan(self.run, self.dir / "re")
        SP.request_document(self.run, "Matrizes Curriculares para EEMTIs 2026", "valores exatos", ["C001 1ª série"])
        SP.request_document(self.run, "matrizes curriculares para EEMTIs 2026", "", ["C001 1ª série", "C004 2ª série"])
        CC.run(self.run)
        res = QR.build(self.run)
        reqs = [p for p in res["pendencias"] if p["detalhe"].startswith("Documento solicitado na reanálise")]
        self.assertEqual(len(reqs), 1)
        self.assertIn("C001 1ª série, C004 2ª série", reqs[0]["detalhe"])
        self.assertTrue(QR.validate(res)["valido"])


# ---------------- 6 grouped queue ----------------

class GroupedQueueTest(Tmp):
    def result(self):
        run = base_run(self.dir, matrix=range_matrix, range_note=True, confirm=False)
        OA.register(run, [sim("EL1", conf=60), sim("EL2", quote="isto não está no documento estadual sintético"), sim("AC1", quote=FX.ORIENT_P2),
                          sim("PA1", "DOC-2:par2", FX.GESTAO_P1), nao("PA2")])
        CC.run(run)
        self.assertTrue(QR.write(run)["ok"])
        r = json.loads((run / QR.RESULT_FILE).read_text(encoding="utf-8"))
        conflict = {"codigo": "CONFLITO_ENTRE_FONTES", "gravidade": "media", "predicado": "aulas", "entidade": "X", "valores": [], "fontes": [],
                    "resolucao_pendente": True, "detalhe": "sintético"}
        r["consistencia"]["conflitos"] += [dict(conflict, entidade="Matemática"), dict(conflict, entidade="Robótica")]
        return run, r

    def test_every_detailed_item_kept_and_conflicts_apart(self):
        run, r = self.result()
        detailed = QR.review_queue(r)
        g = QR.grouped_review_queue(r)
        self.assertEqual(g["total_itens_detalhados"], len(detailed))
        covered = {i["ordem"] for x in g["grupos"] for i in x["itens"]}
        self.assertEqual(covered, {i["ordem"] for i in detailed})
        conflicts = [x for x in g["grupos"] if x["id"].startswith("G-CONFLITO-")]
        self.assertEqual(len(conflicts), 2)
        self.assertTrue(all(len(x["itens"]) == 1 for x in conflicts))
        faixa = next(x for x in g["grupos"] if x["id"] == "G-FAIXA")
        self.assertTrue(any("Língua Portuguesa, 1ª série" in c for c in faixa["celulas"]))
        self.assertIn("G-SELECAO", [x["id"] for x in g["grupos"]])
        self.assertIn("G-ORIENTACAO-EL2", [x["id"] for x in g["grupos"]])
        self.assertEqual([x["id"] for x in g["grupos"]], [x["id"] for x in QR.grouped_review_queue(copy.deepcopy(r))["grupos"]])  # stable ids
        self.assertTrue(all(x["confirmacao_individual"] for x in g["grupos"] if x["id"] in ("G-FAIXA", "G-CLASSIFICACAO")))

    def test_cli_and_summary(self):
        run, _ = self.result()
        out = cli("revisao-fila", "--pasta", str(run), "--agrupada", "--saida", str(self.dir / "g.json"))
        self.assertEqual((out["ok"], out["code"]), (True, "FILA_AGRUPADA"))
        self.assertTrue((self.dir / "g.json").exists())
        self.assertEqual(cli("revisao-fila", str(run / QR.RESULT_FILE))["code"], "FILA")
        md = (run / QR.SUMMARY_FILE).read_text(encoding="utf-8")
        self.assertIn("## Fila de revisão (agrupada)", md)
        self.assertIn("não é o número de campos", md)
        self.assertIn("--agrupada", md)


# ---------------- 7 Notion publication (mocked connector) ----------------

class FakeNotion:
    """Minimal stand-in for the request page and the upload endpoint (what the connector would do)."""

    def __init__(self, status="Elaborando Resposta", files=None, uf="MG", ano=2026):
        self.page = {"page_id": PAGE_ID, "id_solicitacao": "SINTETICO-001", "uf": [uf], "ano": ano, "status": status,
                     "template_preenchido": list(files or [])}
        self.uploads = {}
        self.fail = False

    def read(self):
        return copy.deepcopy(self.page)

    def create_upload(self, name):
        uid = "abcdef01-2345-4678-9abc-%012d" % (len(self.uploads) + 1)
        self.uploads[uid] = {"name": name, "status": "pending"}
        return uid

    def opener_for(self, uid):
        notion = self

        class Resp:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps(self.body).encode()

        def opener(req, timeout=None):
            if notion.fail:
                raise OSError("conexão recusada por https://upload.invalid/xyz")
            assert b'name="file"' in req["data"] and req["method"] == "POST"
            notion.uploads[uid]["status"] = "uploaded"
            return Resp({"id": uid, "status": "uploaded", "filename": notion.uploads[uid]["name"]})
        return opener

    def update(self, props):
        value = props["Template Preenchido"]
        files = []
        for v in value:
            if isinstance(v, str):
                files.append(next(f for f in self.page["template_preenchido"] if f["id"] == v))
            else:
                uid = v["file_upload"]["id"]
                assert self.uploads[uid]["status"] == "uploaded"
                files.append({"nome": self.uploads[uid]["name"], "id": uid})
        self.page["template_preenchido"] = files


def publish(run, notion):
    pub = NP.prepare(run, PAGE_ID, "SINTETICO-001")
    if pub["acao"] == "nada_a_fazer":
        return pub
    NP.check_page(run, notion.read())
    uid = notion.create_upload(pub["nome"])
    NP.send(run, "https://upload.invalid/one-time", {"Notion-Version": "x"}, uid, opener=notion.opener_for(uid))
    payload = NP.properties_payload(run, notion.read())
    if payload["propriedades"]:
        notion.update(payload["propriedades"])
    return NP.confirm(run, notion.read())


class PublicationTest(Tmp):
    def setUp(self):
        super().setUp()
        self.run = decided_run(self.dir)
        TF.fill(self.run)

    def test_success_keeps_earlier_attachments_and_moves_status(self):
        old = {"nome": "SINTETICO-001-r0-anterior.xlsx", "id": "99999999-0000-4000-8000-000000000001"}
        notion = FakeNotion(files=[old])
        r = publish(self.run, notion)
        self.assertTrue(r["confirmada"])
        self.assertEqual(r["novo_status"], NP.STATUS_DELIVERED)
        names = [f["nome"] for f in notion.page["template_preenchido"]]
        self.assertEqual(names, [old["nome"], "SINTETICO-001-r1-MG-2026-template-preenchido.xlsx"])
        pub = json.loads((self.run / NP.FILE).read_text(encoding="utf-8"))
        self.assertEqual(pub["status"], "confirmada")
        self.assertNotIn("upload.invalid", json.dumps(pub))  # the signed URL is never stored
        self.assertEqual(ES.status(self.run)["etapas"][-1]["etapa"], "publicacao")
        self.assertEqual(ES.status(self.run)["etapas"][-1]["estado"], "feita")

    def test_repeat_is_idempotent_and_never_regresses_status(self):
        notion = FakeNotion(status="Concluído")
        r = publish(self.run, notion)
        self.assertIsNone(r["novo_status"])
        self.assertEqual(publish(self.run, notion)["acao"], "nada_a_fazer")
        self.assertEqual(len(notion.page["template_preenchido"]), 1)
        self.assertEqual(len(notion.uploads), 1)

    def test_no_page_id_and_ambiguous_lookup(self):
        with self.assertRaises(NP.PublishError) as e:
            NP.prepare(self.run, "")
        self.assertEqual(e.exception.code, "SOLICITACAO_SEM_ID")
        rows = [{"page_id": PAGE_ID, "id_solicitacao": "QUA-7", "uf": ["MG"], "ano": 2026},
                {"page_id": "22222222-2222-4333-8444-555555555555", "id_solicitacao": "QUA-7", "uf": ["MG"], "ano": 2026},
                {"page_id": "33333333-2222-4333-8444-555555555555", "id_solicitacao": "QUA-8", "uf": ["MG"], "ano": 2026}]
        for rs, code in ((rows, "SOLICITACAO_AMBIGUA"), (rows[2:], "SOLICITACAO_NAO_ENCONTRADA"), ([], "SOLICITACAO_NAO_ENCONTRADA")):
            with self.assertRaises(NP.PublishError) as e:
                NP.select_request(rs, "QUA-7", "MG", 2026)
            self.assertEqual(e.exception.code, code)
        self.assertEqual(NP.select_request(rows[1:], "qua 7", "MG", 2026)["page_id"], "22222222-2222-4333-8444-555555555555")

    def test_wrong_page_or_failed_upload_never_publishes(self):
        notion = FakeNotion(uf="CE")
        NP.prepare(self.run, PAGE_ID)
        with self.assertRaises(NP.PublishError) as e:
            NP.check_page(self.run, notion.read())
        self.assertEqual(e.exception.code, "SOLICITACAO_DIVERGENTE")
        with self.assertRaises(NP.PublishError):
            NP.send(self.run, "https://upload.invalid/x", {}, "abcdef01-2345-4678-9abc-000000000001", opener=notion.opener_for("x"))
        notion = FakeNotion()
        NP.prepare(self.run, PAGE_ID)
        NP.check_page(self.run, notion.read())
        uid = notion.create_upload("x.xlsx")
        notion.fail = True
        with self.assertRaises(NP.PublishError) as e:
            NP.send(self.run, "https://upload.invalid/x", {}, uid, opener=notion.opener_for(uid))
        self.assertEqual(e.exception.code, "UPLOAD_FALHOU")
        pub = json.loads((self.run / NP.FILE).read_text(encoding="utf-8"))
        self.assertEqual(pub["status"], "falhou")
        self.assertNotIn("upload.invalid", json.dumps(pub))
        self.assertEqual(notion.page["template_preenchido"], [])
        notion.fail = False  # resumes without re-running the analysis
        self.assertTrue(publish(self.run, notion)["confirmada"])

    def test_not_confirmed_without_the_file_on_the_page(self):
        notion = FakeNotion()
        pub = NP.prepare(self.run, PAGE_ID)
        NP.check_page(self.run, notion.read())
        uid = notion.create_upload(pub["nome"])
        NP.send(self.run, "https://upload.invalid/x", {}, uid, opener=notion.opener_for(uid))
        with self.assertRaises(NP.PublishError) as e:
            NP.confirm(self.run, notion.read())  # the property was never updated
        self.assertEqual(e.exception.code, "ARQUIVO_NAO_ENCONTRADO_NA_PAGINA")
        self.assertNotEqual(json.loads((self.run / NP.FILE).read_text(encoding="utf-8"))["status"], "confirmada")

    def test_stale_or_changed_excel_is_refused(self):
        time.sleep(0.05)
        OA.register(self.run, [sim("EL2")])  # a later decision changes the result
        CC.run(self.run)
        self.assertTrue(QR.write(self.run)["ok"])
        with self.assertRaises(NP.PublishError) as e:
            NP.prepare(self.run, PAGE_ID)
        self.assertEqual(e.exception.code, "XLSX_DESATUALIZADO")
        rec = TF.fill(self.run)
        Path(rec["arquivo"]).write_bytes(Path(rec["arquivo"]).read_bytes() + b"x")
        with self.assertRaises(NP.PublishError) as e:
            NP.prepare(self.run, PAGE_ID)
        self.assertEqual(e.exception.code, "XLSX_ALTERADO")

    def test_execution_row_never_overwrites_human_validation(self):
        publish(self.run, FakeNotion())
        new = NP.execution_payload(self.run, [])
        self.assertEqual((new["acao"], new["propriedades"]["Validação humana"]), ("criar", "Aguardando"))
        self.assertEqual(new["propriedades"]["Execução"], "MG 2026 — SINTETICO-001-r1")
        row = {"page_id": "44444444-2222-4333-8444-555555555555", "execucao": "MG 2026 — SINTETICO-001-r1"}
        upd = NP.execution_payload(self.run, [row])
        self.assertEqual(upd["acao"], "atualizar")
        self.assertNotIn("Validação humana", upd["propriedades"])
        with self.assertRaises(NP.PublishError) as e:
            NP.execution_payload(self.run, [row, dict(row, page_id="55555555-2222-4333-8444-555555555555")])
        self.assertEqual(e.exception.code, "EXECUCAO_DUPLICADA")


if __name__ == "__main__":
    unittest.main()
