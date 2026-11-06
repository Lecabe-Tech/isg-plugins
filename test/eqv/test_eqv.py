"""EQV tests (SPEC-005 VAL-E01, VAL-E02): generated workbooks only; no real analyst data in the repository."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "isg-model-alignment"
EQV_DIR = PLUGIN / "scripts" / "eqv"
sys.path.insert(0, str(EQV_DIR))
sys.dont_write_bytecode = True

from isg_eqv import evidence as E  # noqa: E402
from isg_eqv import template as T  # noqa: E402


def col(n: int) -> str:
    return T.num_to_col(n)


def make_xlsx(path: Path, sheets: dict, hidden: tuple = ()) -> None:
    """sheets: {name: {(col_num, row): text}} -> a minimal .xlsx with inline strings (what the reader must also accept)."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        names = list(sheets)
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>')
        z.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="%s" xmlns:r="%s"><sheets>%s</sheets></workbook>' % (
            T.NS_MAIN, T.NS_REL, "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"%s/>' % (escape(n), i + 1, i + 1, ' state="hidden"' if n in hidden else "") for i, n in enumerate(names))))
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="%s">%s</Relationships>' % (
            T.NS_PKG_REL, "".join('<Relationship Id="rId%d" Target="worksheets/sheet%d.xml"/>' % (i + 1, i + 1) for i in range(len(names)))))
        for i, n in enumerate(names):
            rows: dict = {}
            for (c, r), v in sheets[n].items():
                rows.setdefault(r, []).append((c, v))
            body = ""
            for r in sorted(rows):
                body += '<row r="%d">%s</row>' % (r, "".join('<c r="%s%d" t="inlineStr"><is><t>%s</t></is></c>' % (col(c), r, escape(v)) for c, v in sorted(rows[r])))
            z.writestr("xl/worksheets/sheet%d.xml" % (i + 1), '<?xml version="1.0"?><worksheet xmlns="%s"><sheetData>%s</sheetData></worksheet>' % (T.NS_MAIN, body))


def tab_11(shift: int = 0) -> dict:
    """Mimics tab 1.1: UF labels in row 8, headers in row 9, data from row 10; groups only on the first row of a block."""
    c = {}
    heads = ["Componente e/ou prática educativa (1º nível)", "Componente e/ou prática educativa (2º nível)", "Código da orientação", "Orientação", "Classificação"]
    for i, h in enumerate(heads):
        c[(2 + i + shift, 9)] = h
    for i, (uf, years) in enumerate((("CE", (2025, 2026)), ("PE", (2025, 2026)))):
        base = 7 + shift + i * 4
        c[(base, 8)] = uf
        for j, y in enumerate(years):
            c[(base + j * 2, 9)] = str(y)
            c[(base + j * 2 + 1, 9)] = "Observações/comentários"
    rows = [("Eletivas", "-", "EL1", "Relação direta com a BNCC", "Imprescindível"), ("", "-", "EL2", "Uso de metodologias ativas", "Desejável"),
            ("Acolhimento", "Acolhimento inicial", "AC1", "Recepção dos estudantes", "Imprescindível")]
    for k, r in enumerate(rows):
        for i, v in enumerate(r):
            if v:
                c[(2 + i + shift, 10 + k)] = v
        c[(7 + shift, 10 + k)] = "Sim" if k != 1 else "Não"
        c[(8 + shift, 10 + k)] = f"Pág. {70 + k} (Orientações 2025): \"texto de teste número {k}\""
        c[(9 + shift, 10 + k)] = "Sim"
        c[(11 + shift, 10 + k)] = "Não"
    return c


def tab_12() -> dict:
    c = {(2, 9): "Bloco", (3, 9): "Sub bloco", (4, 9): "Código da orientação", (5, 9): "Orientação", (6, 9): "Classificação", (7, 8): "CE", (7, 9): "2026", (8, 9): "Observações/comentários"}
    c.update({(2, 10): "Princípios da TGE", (3, 10): "Ciclo Virtuoso", (4, 10): "PT1", (5, 10): "A escola produz resultados", (6, 10): "Imprescindível", (7, 10): "SIM", (8, 10): "Trecho de teste"})
    return c


class TemplateReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def book(self, **kw):
        p = self.dir / "t.xlsx"
        make_xlsx(p, {"Leia-me": {(2, 2): "x"}, "1.1 Base orient. pedagógicas": kw.get("t11", tab_11()), "1.2 Base orient. gestão": kw.get("t12", tab_12()), "classificacoes": {(2, 2): "a"}}, hidden=("classificacoes",))
        return p

    def test_reads_orientations_columns_and_answers(self):
        t = T.read_template(self.book())
        a = t["abas"]["1.1"]
        self.assertEqual([o["codigo"] for o in a["orientacoes"]], ["EL1", "EL2", "AC1"])
        self.assertEqual([o["grupo"] for o in a["orientacoes"]], ["Eletivas", "Eletivas", "Acolhimento"], "groups are filled down")
        self.assertEqual(a["orientacoes"][2]["subgrupo"], "Acolhimento inicial")
        self.assertEqual(a["orientacoes"][0]["subgrupo"], "", "'-' means no sub-group")
        self.assertEqual(a["orientacoes"][1]["classificacao"], "Desejável")
        self.assertEqual(sorted(a["colunas"]), ["CE-2025", "CE-2026", "PE-2025", "PE-2026"])
        self.assertEqual(a["colunas"]["CE-2026"], {"valor": "I", "comentario": "J"})
        self.assertEqual(len(t["abas"]["1.2"]["orientacoes"]), 1)
        self.assertEqual(t["abas"]["1.2"]["colunas"]["CE-2026"]["valor"], "G")
        k = t["gabarito"]["1.1|EL1|CE|2025"]
        self.assertEqual(k["valor"], "Sim")
        self.assertIn("Pág. 70", k["comentario"])
        self.assertEqual(t["gabarito"]["1.2|PT1|CE|2026"]["valor"], "SIM", "each tab keeps its own capitalization")
        self.assertEqual(t["avisos"], [])

    def test_columns_are_found_from_headers_not_from_letters(self):
        t = T.read_template(self.book(t11=tab_11(shift=2)))
        self.assertEqual(t["abas"]["1.1"]["colunas"]["CE-2025"], {"valor": "I", "comentario": "J"})
        self.assertEqual(t["abas"]["1.1"]["orientacoes"][0]["codigo"], "EL1")

    def test_unknown_layout_stops_without_guessing(self):
        bad = tab_11()
        bad = {k: v for k, v in bad.items() if not str(v).startswith("Código")}
        with self.assertRaises(T.TemplateError) as cm:
            T.read_template(self.book(t11=bad))
        self.assertEqual(cm.exception.code, "LAYOUT_DESCONHECIDO")
        p = self.dir / "other.xlsx"
        make_xlsx(p, {"Planilha1": {(1, 1): "x"}})
        with self.assertRaises(T.TemplateError) as cm:
            T.read_template(p)
        self.assertEqual(cm.exception.code, "ABA_AUSENTE")
        (self.dir / "not.xlsx").write_bytes(b"not a zip")
        with self.assertRaises(T.TemplateError) as cm:
            T.read_template(self.dir / "not.xlsx")
        self.assertEqual(cm.exception.code, "ARQUIVO_INVALIDO")

    def test_warns_about_duplicates_and_empty_texts_and_never_modifies_the_file(self):
        t11 = tab_11()
        t11[(4, 11)] = "EL1"  # duplicate code on the second row
        del t11[(5, 12)]  # AC1 without text
        p = self.book(t11=t11)
        before = p.read_bytes()
        t = T.read_template(p)
        self.assertTrue(any("repetido" in a for a in t["avisos"]))
        self.assertTrue(any("sem texto" in a for a in t["avisos"]))
        self.assertEqual(p.read_bytes(), before, "the template is never modified")

    def test_cli_modelo(self):
        p = self.book()
        out = self.dir / "saida"
        r = subprocess.run([sys.executable, str(EQV_DIR / "eqv.py"), "modelo", str(p), "--saida", str(out), "--json"], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, env=dict(os.environ, PYTHONUTF8="1", ISG_DATA_FOLDER=str(self.dir / "dados")))
        j = json.loads(r.stdout)
        self.assertEqual((r.returncode, j["code"]), (0, "MODELO_LIDO"), r.stdout)
        self.assertIn("nada foi alterado", j["message"])
        self.assertEqual(json.loads((out / "orientacoes.json").read_text(encoding="utf-8"))["orientacoes"]["1.1"][0]["codigo"], "EL1")
        self.assertIn("1.1|EL1|CE|2025", json.loads((out / "gabarito.json").read_text(encoding="utf-8")))
        r = subprocess.run([sys.executable, str(EQV_DIR / "eqv.py"), "modelo", str(self.dir / "nada.xlsx"), "--json"], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
        self.assertEqual((r.returncode, json.loads(r.stdout)["code"]), (1, "ENTRADA_INVALIDA"))


class EvidenceTests(unittest.TestCase):
    PAGE = "<!-- página 71 -->\nOs componentes eletivos contribuem com um currículo personalizado às demandas dos sujeitos, ampliando, diversifi-\ncando e/ou aprofundando conceitos."

    def test_verbatim_with_normalization(self):
        self.assertTrue(E.verify("Os componentes eletivos contribuem com um currículo personalizado às demandas", self.PAGE)["ok"])
        self.assertTrue(E.verify('"os COMPONENTES eletivos contribuem com um curriculo personalizado as demandas"', self.PAGE)["ok"], "accents, case, quotes")
        self.assertTrue(E.verify("ampliando, diversificando e/ou aprofundando conceitos", self.PAGE)["ok"], "line-end hyphen")

    def test_rejects_paraphrase_invented_and_too_short(self):
        self.assertFalse(E.verify("Os componentes eletivos contribuem para um currículo personalizado às demandas", self.PAGE)["ok"], "one changed word")
        self.assertFalse(E.verify("A escola deve oferecer eletivas todos os dias da semana letiva", self.PAGE)["ok"])
        self.assertEqual(E.verify("eletivas", self.PAGE)["motivo"], "citação curta demais para servir de prova")
        self.assertFalse(E.verify("", self.PAGE)["ok"])

    def test_ellipsis_checks_each_piece(self):
        self.assertTrue(E.verify("Os componentes eletivos contribuem com um currículo (...) aprofundando conceitos", self.PAGE)["ok"])
        self.assertFalse(E.verify("Os componentes eletivos contribuem com um currículo … e também formam professores", self.PAGE)["ok"])


# ---------------------------------------------------------------- rules, inventory, cells, review, export (SPEC-005 4.4, REQ-CIV/CRS/CFB)

from isg_eqv import export as X  # noqa: E402
from isg_eqv import rules as R  # noqa: E402
from isg_eqv import store as S  # noqa: E402

sys.path.insert(0, str(PLUGIN / "scripts" / "cfp"))
sys.path.insert(0, str(PLUGIN / "scripts" / "cfp" / "vendor"))
from isg_cfp import appdata as appdata_mod  # noqa: E402
from isg_cfp.pipeline import process_pdf  # noqa: E402

from ..cfp import fixtures as cfp_fx  # noqa: E402
from ..cfp import pdfgen  # noqa: E402

QUOTE1 = "Os componentes eletivos contribuem com um currículo personalizado às demandas dos sujeitos da escola"
QUOTE2 = "O Estudo Orientado acontece em duas aulas semanais com acompanhamento de um professor responsável"


def state_pdf() -> pdfgen.PdfDoc:
    doc = pdfgen.PdfDoc(title="Orientações de teste")
    for text in (QUOTE1 + ". " + cfp_fx.FILLER[0], QUOTE2 + ". " + cfp_fx.FILLER[1]):
        ops, y = [], 700.0
        for ln in cfp_fx.wrap(text, 80):
            ops.append(pdfgen.PdfDoc.text(60, y, ln))
            y -= 14
        doc.add_page(ops)
    return doc


def ev(page=1, quote=QUOTE1, relation="Equivalente", origin="texto", doc="Orientações 2026"):
    return {"documento": doc, "pagina": page, "trecho": quote, "relacao": relation, "origem": origin, "item": "Eletivas"}


def proposal(tab="1.1", code="EL1", value="Sim", conf=92, evidences=None, **kw):
    p = {"aba": tab, "codigo": code, "valor": value, "confianca": conf, "explicacao": "Explicação de teste.", "evidencias": evidences if evidences is not None else [ev()]}
    p.update(kw)
    return p


class RulesTests(unittest.TestCase):
    def test_table_of_section_4_4(self):
        good = [{"verificada": True, "relacao": "Equivalente", "origem": "texto"}]
        r = R.decide({"valor": "Sim", "confianca": 92}, good)
        self.assertEqual((r["valor"], r["revisar"], r["confianca"]), ("Sim", False, 92))
        r = R.decide({"valor": "Sim", "confianca": 70}, good)
        self.assertEqual((r["valor"], r["revisar"]), ("Sim", True), "below the minimum: value kept, flagged")
        r = R.decide({"valor": "Sim", "confianca": 95}, [{"verificada": True, "relacao": "Indireta", "origem": "texto"}])
        self.assertEqual((r["valor"], r["revisar"], r["confianca"]), ("Sim", True, 84), "indirect evidence is capped below the minimum")
        r = R.decide({"valor": "Sim", "confianca": 95}, [{"verificada": True, "relacao": "Equivalente", "origem": "interpretação de imagem (IA)"}])
        self.assertEqual((r["revisar"], r["confianca"]), (True, 75), "AI image interpretation caps at 75")
        r = R.decide({"valor": "Sim", "confianca": 95}, [{"verificada": True, "relacao": "Equivalente", "origem": "texto", "pagina_nao_confiavel": True}])
        self.assertEqual((r["revisar"], r["confianca"]), (True, 75), "flagged page caps at 75")

    def test_sim_without_verified_quote_becomes_nao_and_review(self):
        r = R.decide({"valor": "Sim", "confianca": 99}, [{"verificada": False, "relacao": "Equivalente", "origem": "texto"}])
        self.assertEqual((r["valor"], r["revisar"]), ("Não", True))
        self.assertLessEqual(r["confianca"], 50)
        r = R.decide({"valor": "Sim", "confianca": 99}, [])
        self.assertEqual((r["valor"], r["revisar"]), ("Não", True))

    def test_nao_needs_a_proof_of_absence(self):
        proof = {"itens_considerados": ["Tutoria"], "onde_procurou": "todas as seções"}
        r = R.decide({"valor": "Não", "confianca": 95, "ausencia": proof}, [], contexto={"cobertura_completa": True})
        self.assertEqual((r["valor"], r["revisar"], r["confianca"]), ("Não", False, 90), "absence is capped at 90")
        r = R.decide({"valor": "Não", "confianca": 95, "ausencia": proof}, [], contexto={"cobertura_completa": False})
        self.assertEqual((r["revisar"], r["confianca"]), (True, 75), "incomplete inventory caps at 75 and flags")
        r = R.decide({"valor": "Não", "confianca": 95}, [])
        self.assertEqual((r["valor"], r["revisar"]), ("Não", True), "no proof of absence")
        r = R.decide({"valor": "Não", "confianca": 95, "ausencia": {"itens_considerados": [], "onde_procurou": ""}}, [])
        self.assertTrue(r["revisar"])

    def test_context_and_input_checks(self):
        good = [{"verificada": True, "relacao": "Equivalente", "origem": "texto"}]
        self.assertTrue(R.decide({"valor": "Sim", "confianca": 95}, good, contexto={"memoria_em_conflito": True})["revisar"])
        self.assertTrue(R.decide({"valor": "Sim", "confianca": 95}, good, contexto={"documento_reprovado": True})["revisar"])
        r = R.decide({"valor": "talvez", "confianca": "x"}, good)
        self.assertEqual((r["valor"], r["revisar"]), ("Não", True), "invalid proposals never leave an empty or odd value")
        self.assertEqual(R.decide({"valor": "sim", "confianca": 120}, good)["confianca"], 100)
        self.assertEqual((R.tab_capitalization("Sim", "1.2"), R.tab_capitalization("Não", "1.2"), R.tab_capitalization("Não", "1.1")), ("SIM", "NÃO", "Não"))


class FlowBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.appdata = self.dir / "dados"
        appdata_mod.ensure_appdata(self.appdata, PLUGIN)
        pdf = self.dir / "orientacoes.pdf"
        state_pdf().save(pdf)
        r = process_pdf(pdf, "CE", 2026, self.appdata)
        self.doc = Path(r["caminho"])
        self.template = self.dir / "template.xlsx"
        make_xlsx(self.template, {"1.1 Base orient. pedagógicas": tab_11(), "1.2 Base orient. gestão": tab_12()})
        self.template_bytes = self.template.read_bytes()
        self.info = S.start_run(self.appdata, self.template, "CE", 2026, [("Orientações 2026", str(self.doc))], self.appdata / "cfp")
        self.rd = S.run_dir(self.appdata, "CE", 2026)
        S._PAGE_CACHE.clear()


class RunTests(FlowBase):
    def test_start_stores_orientations_key_and_estimate(self):
        self.assertEqual(self.info["abas"], {"1.1": 3, "1.2": 1})
        key = S.read_json(self.rd / "gabarito.json")
        self.assertTrue(all("|CE|2026" in k for k in key), "only the chosen UF and year")
        self.assertEqual(key["1.1|EL1|CE|2026"]["valor"], "Sim")
        self.assertGreater(self.info["tokens_max"], 0)
        self.assertGreaterEqual(self.info["tokens_max"], self.info["tokens_min"])
        self.assertEqual(self.template.read_bytes(), self.template_bytes, "the template is never modified")

    def test_refuses_missing_year_unknown_doc_and_reprovado(self):
        with self.assertRaises(S.EqvError) as cm:
            S.start_run(self.appdata, self.template, "CE", 2031, [("A", str(self.doc))], self.appdata / "cfp")
        self.assertEqual(cm.exception.code, "SEM_COLUNAS")
        with self.assertRaises(S.EqvError) as cm:
            S.start_run(self.appdata, self.template, "CE", 2026, [("A", str(self.dir / "nada"))], self.appdata / "cfp")
        self.assertEqual(cm.exception.code, "DOCUMENTO_NAO_ENCONTRADO")
        idx = json.loads((self.doc / "index.json").read_text(encoding="utf-8"))
        idx["situacao"] = "Reprovado"
        (self.doc / "index.json").write_text(json.dumps(idx), encoding="utf-8")
        with self.assertRaises(S.EqvError) as cm:
            S.start_run(self.appdata, self.template, "CE", 2026, [("A", str(self.doc))], self.appdata / "cfp")
        self.assertEqual(cm.exception.code, "DOCUMENTO_REPROVADO")

    def test_inventory_verifies_quotes_and_reports_real_page(self):
        items = [{"grupo": "Eletivas", "titulo": "Currículo personalizado", "descricao": "d", "pagina": 1, "trecho": QUOTE1},
                 {"grupo": "Eletivas", "titulo": "Inventado", "descricao": "d", "pagina": 1, "trecho": "A escola oferece aulas de xadrez todas as manhãs da semana"},
                 {"grupo": "Estudo Orientado", "titulo": "Duas aulas", "descricao": "d", "pagina": 1, "trecho": QUOTE2}]  # cited page 1, really on page 2
        r = S.register_inventory(self.rd, "Orientações 2026", items, [1])
        self.assertEqual(r["aceitos"], 2)
        self.assertEqual(len(r["rejeitados"]), 1)
        inv = S.read_json(S.inventory_path(self.rd, "Orientações 2026"))
        self.assertEqual([i["pagina"] for i in inv["itens"]], [1, 2], "the real page is reported")
        self.assertIn("nota", inv["itens"][1])
        self.assertEqual(S.inventory_status(self.rd)["Orientações 2026"]["completo"], True)


class CellTests(FlowBase):
    def test_sim_with_verified_quote_and_comment_convention(self):
        r = S.register_cell(self.rd, proposal())
        self.assertEqual((r["valor"], r["revisar"], r["confianca"]), ("Sim", False, 92))
        c = S.read_json(S.cell_path(self.rd, "1.1", "EL1"))
        self.assertTrue(c["comentario"].startswith('Pág. 1 (Orientações 2026): "Os componentes eletivos'))
        self.assertTrue(c["comentario"].endswith("(pré-preenchido por IA)"))
        self.assertTrue(c["evidencias"][0]["verificada"])

    def test_comment_lists_pages_and_quotes_in_the_same_order(self):
        S.register_cell(self.rd, proposal(code="EL2", evidences=[ev(page=2, quote=QUOTE2), ev(page=1, quote=QUOTE1)]))
        c = S.read_json(S.cell_path(self.rd, "1.1", "EL2"))["comentario"]
        self.assertTrue(c.startswith("Págs. 1 e 2 (Orientações 2026): "), c)
        self.assertLess(c.index("Os componentes eletivos"), c.index("O Estudo Orientado"))

    def test_invented_quote_never_makes_a_sim(self):
        r = S.register_cell(self.rd, proposal(evidences=[ev(quote="A escola oferece aulas de xadrez todas as manhãs da semana letiva")]))
        self.assertEqual((r["valor"], r["revisar"]), ("Não", True))
        self.assertTrue(r["rejeitadas"])

    def test_quote_on_a_nearby_page_is_accepted_with_the_real_page(self):
        S.register_cell(self.rd, proposal(code="EL2", evidences=[ev(page=1, quote=QUOTE2)]))
        c = S.read_json(S.cell_path(self.rd, "1.1", "EL2"))
        self.assertEqual((c["valor"], c["evidencias"][0]["pagina"]), ("Sim", 2))
        self.assertIn("Pág. 2", c["comentario"])

    def test_nao_with_and_without_absence_proof_and_tab_capitalization(self):
        proof = {"itens_considerados": ["Tutoria (Distinto)"], "onde_procurou": "todas as seções", "resumo": "Não há menção a acolhimento inicial."}
        r = S.register_cell(self.rd, proposal(code="AC1", value="Não", conf=95, evidences=[], ausencia=proof))
        self.assertEqual(r["valor"], "Não")
        self.assertTrue(r["revisar"], "the inventory covers no chunk yet, so the proof is weak: flagged")
        self.assertLessEqual(r["confianca"], 75)
        r = S.register_cell(self.rd, proposal(code="EL2", value="Não", conf=95, evidences=[]))
        self.assertTrue(r["revisar"])
        S.register_cell(self.rd, proposal(tab="1.2", code="PT1", conf=92))
        self.assertEqual(S.read_json(S.cell_path(self.rd, "1.2", "PT1"))["valor_planilha"], "SIM")

    def test_unknown_orientation_and_document(self):
        with self.assertRaises(S.EqvError) as cm:
            S.register_cell(self.rd, proposal(code="ZZ9"))
        self.assertEqual(cm.exception.code, "ORIENTACAO_INEXISTENTE")
        with self.assertRaises(S.EqvError) as cm:
            S.register_cell(self.rd, proposal(evidences=[ev(doc="Outro")]))
        self.assertEqual(cm.exception.code, "DOCUMENTO_DESCONHECIDO")

    def test_analyst_decision_overrides_and_survives_reruns(self):
        S.register_cell(self.rd, proposal(code="EL2", conf=60))
        d = S.decide(self.rd, "1.1", "EL2", "não", "Não há essa prática no documento", "Ana")
        self.assertEqual(d["valor"], "Não")
        self.assertEqual(d["memoria_sugerida"]["tipo"], "Rejeição")
        again = S.register_cell(self.rd, proposal(code="EL2", value="Sim", conf=99))
        self.assertTrue(again["mantida"])
        c = S.read_json(S.cell_path(self.rd, "1.1", "EL2"))
        self.assertEqual((c["valor"], c["revisar"], c["confianca"], c["decidido_por"]), ("Não", False, 95, "analista"))
        with self.assertRaises(S.EqvError):
            S.decide(self.rd, "1.1", "EL2", "talvez")


class ExportTests(FlowBase):
    def fill_all(self):
        S.register_cell(self.rd, proposal(code="EL1"))
        S.register_cell(self.rd, proposal(code="EL2", value="Sim", evidences=[ev(page=2, quote=QUOTE2)], conf=70))
        S.register_cell(self.rd, proposal(code="AC1", value="Não", conf=80, evidences=[], ausencia={"itens_considerados": ["x"], "onde_procurou": "tudo", "resumo": "Sem menção."}))
        S.register_cell(self.rd, proposal(tab="1.2", code="PT1"))

    def test_export_files_columns_and_original_row_order(self):
        self.fill_all()
        r = X.export(self.rd)
        for name in ("resultado_1.1.xlsx", "resultado_1.1.csv", "resultado_1.2.xlsx", "resultado_1.2.csv", "resultado.md", "resultado.json"):
            self.assertTrue((self.rd / name).exists(), name)
        sheets = T.read_sheets(self.rd / "resultado_1.1.xlsx")
        cells = sheets["Resultado"]
        self.assertEqual([cells[(i + 1, 1)] for i in range(12)], X.HEADERS)
        self.assertEqual([cells[(1, r)] for r in (2, 3, 4)], ["EL1", "EL2", "AC1"], "template row order")
        self.assertEqual((cells[(6, 2)], cells[(6, 3)], cells[(6, 4)]), ("Sim", "Sim", "Não"))
        self.assertEqual(cells[(9, 3)], "Sim", "EL2 was below the minimum: Revisar = Sim")
        self.assertEqual(T.read_sheets(self.rd / "resultado_1.2.xlsx")["Resultado"][(6, 2)], "SIM")
        csv_text = (self.rd / "resultado_1.1.csv").read_text(encoding="utf-8")
        self.assertTrue(csv_text.startswith("﻿Código;Bloco;"))
        self.assertIn("(pré-preenchido por IA)", csv_text)
        self.assertEqual(self.template.read_bytes(), self.template_bytes)
        self.assertTrue(r["comparacao_completa"]["completo"], r["comparacao_completa"])

    def test_pending_rows_are_marked_and_completeness_says_no(self):
        S.register_cell(self.rd, proposal(code="EL1"))
        r = X.export(self.rd)
        self.assertFalse(r["comparacao_completa"]["completo"])
        self.assertIn("ainda não comparada", " ".join(r["comparacao_completa"]["motivos"]))
        cells = T.read_sheets(self.rd / "resultado_1.1.xlsx")["Resultado"]
        self.assertEqual(cells[(10, 3)], "Ainda não comparada.", "a row not compared yet says so and is flagged")
        self.assertEqual(cells[(9, 3)], "Sim")
        md = (self.rd / "resultado.md").read_text(encoding="utf-8")
        self.assertIn("Comparação completa: não", md)
        self.assertIn("Orientações 2026", md)

    def test_measure_against_the_analysts_answers(self):
        self.fill_all()
        S.decide(self.rd, "1.1", "EL2", "Não", "x")  # the template key says Sim for CE 2026 in every row of the fixture
        m = X.measure(self.rd)
        self.assertEqual(m["avaliadas"], 4)
        self.assertEqual(m["concordam"], 2)
        self.assertEqual((m["falso_nao"], m["falso_sim"]), (2, 0))
        self.assertEqual(m["concordancia_pct"], 50.0)


class EqvCliTests(FlowBase):
    def cli(self, *a):
        env = dict(os.environ, PYTHONUTF8="1", ISG_DATA_FOLDER=str(self.appdata))
        r = subprocess.run([sys.executable, str(EQV_DIR / "eqv.py"), *a, "--json"], capture_output=True, text=True, encoding="utf-8", env=env, stdin=subprocess.DEVNULL, timeout=120)
        return r.returncode, json.loads(r.stdout)

    def test_full_cli_flow(self):
        rc, j = self.cli("iniciar", str(self.template), "--uf", "CE", "--ano", "2026", "--doc", f"Orientações 2026={self.doc}")
        self.assertEqual((rc, j["code"]), (0, "INICIADA"), j)
        self.assertIn("estimativa aproximada", j["message"])
        inv = self.dir / "inv.json"
        inv.write_text(json.dumps({"itens": [{"grupo": "Eletivas", "titulo": "t", "descricao": "d", "pagina": 1, "trecho": QUOTE1}]}), encoding="utf-8")
        rc, j = self.cli("inventario-registrar", "Orientações 2026", str(inv), "--chunks", "1", "--uf", "CE", "--ano", "2026")
        self.assertEqual(j["code"], "INVENTARIO_REGISTRADO", j)
        cell = self.dir / "cell.json"
        cell.write_text(json.dumps([proposal(), proposal(code="EL2", value="Sim", conf=60, evidences=[ev(page=2, quote=QUOTE2)])]), encoding="utf-8")
        rc, j = self.cli("celula-registrar", str(cell), "--uf", "CE", "--ano", "2026")
        self.assertEqual(j["code"], "CELULAS_REGISTRADAS", j)
        self.assertIn("revisar", j["message"])
        rc, j = self.cli("decidir", "1.1", "EL2", "--valor", "Sim", "--motivo", "confirmado", "--uf", "CE", "--ano", "2026")
        self.assertEqual(j["code"], "DECIDIDA", j)
        rc, j = self.cli("status", "--uf", "CE", "--ano", "2026")
        self.assertEqual(j["data"]["abas"]["1.1"]["comparadas"], 2)
        rc, j = self.cli("exportar", "--uf", "CE", "--ano", "2026")
        self.assertEqual(j["code"], "EXPORTADO", j)
        rc, j = self.cli("medir", "--uf", "CE", "--ano", "2026")
        self.assertEqual(j["code"], "MEDIDA", j)
        rc, j = self.cli("status", "--uf", "SP", "--ano", "2026")
        self.assertEqual((rc, j["code"]), (1, "EXECUCAO_NAO_INICIADA"))


if __name__ == "__main__":
    unittest.main()
