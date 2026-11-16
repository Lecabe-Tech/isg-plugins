"""SPEC-017 G1: multi-format extraction with traceability (synthetic files only)."""
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QROOT = ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"
sys.path.insert(0, str(QROOT))
import document_normalizer as DN  # noqa: E402
import quality_run as RUN  # noqa: E402
import source_resolver as SR  # noqa: E402
from test.quality import q17_fixtures as FX  # noqa: E402


def manifest_for(folder: Path, entries: dict) -> Path:
    m = {"schema_version": "1.0", "solicitacao_id": "SINT-G1", "uf": "MG", "ano": 2026, "modelo": "9h", "modalidade": "propedeutico",
         "entradas": {c: entries.get(c) or [{"uri": "ice.xlsx"}] for c in SR.CLASSES}}
    p = folder / "manifesto.json"
    p.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return p


class FakeResponse(io.BytesIO):
    def __init__(self, data: bytes, url: str):
        super().__init__(data)
        self._url = url

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.src = self.dir / "src"
        self.src.mkdir()
        self.run = self.dir / "run"

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, entries, opener=None):
        return RUN.start_run(manifest_for(self.src, entries), self.run, opener)

    def doc(self, inv, doc_id):
        return next(f for f in inv["fontes"] if f["id"] == doc_id)

    def test_all_formats_inventoried_with_locations(self):
        FX.orientations_pdf(self.src / "a.pdf", with_image_page=True)
        FX.management_docx(self.src / "b.docx")
        FX.matrix_xlsx(self.src / "m.xlsx")
        (self.src / "c.png").write_bytes(FX.png_bytes(4, 3))
        (self.src / "d.jpg").write_bytes(FX.jpeg_bytes(640, 480))
        (self.src / "e.txt").write_text("Primeiro bloco de orientações.\n\nSegundo bloco com mais texto.", encoding="utf-8")
        (self.src / "f.csv").write_text("Componente;1ª série\nMatemática;5\n", encoding="utf-8")
        (self.src / "g.html").write_text("<html><script>alert(1)</script><p>Texto oficial publicado</p></html>", encoding="utf-8")
        FX.ice_xlsx(self.src / "ice.xlsx")
        FX.template_xlsx(self.src / "t.xlsx")
        inv = self.start({"orientacoes_estaduais": [{"uri": n} for n in ("a.pdf", "b.docx", "c.png", "d.jpg", "e.txt", "f.csv", "g.html")],
                          "matriz_estadual": [{"uri": "m.xlsx"}], "template_cluster": [{"uri": "t.xlsx"}], "referencial_ice": [{"uri": "ice.xlsx"}]})
        types = {f["nome"]: f["media_type"] for f in inv["fontes"]}
        self.assertEqual(types["a.pdf"], "application/pdf")
        self.assertTrue(types["b.docx"].endswith("wordprocessingml.document"))
        self.assertEqual(types["c.png"], "image/png")
        self.assertEqual(types["d.jpg"], "image/jpeg")
        self.assertEqual(types["f.csv"], "text/csv")
        self.assertEqual(types["g.html"], "text/html")
        units = RUN.load_units(self.run)
        for f in inv["fontes"]:
            self.assertTrue(f["sha256"] and len(f["sha256"]) == 64)
            self.assertTrue(units[f["id"]], f["nome"])
            for u in units[f["id"]]:
                self.assertTrue(u["id"].startswith(f["id"] + ":"))
                self.assertIn("tipo", u["localizacao"])
            self.assertTrue((self.run / "originais").glob(f["id"] + ".*"))
        pdf = next(f for f in inv["fontes"] if f["nome"] == "a.pdf")
        pdf_units = {u["id"]: u for u in units[pdf["id"]]}
        self.assertEqual(pdf_units[pdf["id"] + ":p1"]["status"], "lida")
        self.assertIn("Base Nacional Comum Curricular", pdf_units[pdf["id"] + ":p1"]["texto"])
        self.assertEqual(pdf_units[pdf["id"] + ":p3"]["status"], "requer_interpretacao")
        self.assertEqual(pdf["status_leitura"], "lida_com_pendencias")
        self.assertIn("IMAGEM_PENDENTE", [p["codigo"] for p in pdf["pendencias"]])
        docx = next(f for f in inv["fontes"] if f["nome"] == "b.docx")
        kinds = {u["tipo"] for u in units[docx["id"]]}
        self.assertEqual(kinds, {"paragraph", "row", "image_region"})
        row = next(u for u in units[docx["id"]] if u["tipo"] == "row" and u["localizacao"]["linha"] == 3)
        self.assertEqual(row["celulas"], ["Monitoramento", "Bimestral"])
        png = next(f for f in inv["fontes"] if f["nome"] == "c.png")
        self.assertEqual(units[png["id"]][0]["localizacao"]["largura"], 4)
        jpg = next(f for f in inv["fontes"] if f["nome"] == "d.jpg")
        self.assertEqual((units[jpg["id"]][0]["localizacao"]["largura"], units[jpg["id"]][0]["localizacao"]["altura"]), (640, 480))
        html = next(f for f in inv["fontes"] if f["nome"] == "g.html")
        self.assertNotIn("alert", " ".join(u["texto"] for u in units[html["id"]]))

    def test_xlsx_formulas_merges_hidden_and_missing_cache(self):
        FX.matrix_xlsx(self.src / "m.xlsx", missing_cache=True)
        FX.template_xlsx(self.src / "t.xlsx")
        inv = self.start({"matriz_estadual": [{"uri": "m.xlsx"}], "template_cluster": [{"uri": "t.xlsx"}], "orientacoes_estaduais": [{"uri": "m.xlsx"}]})
        units = RUN.unit_index(self.run)
        m = self.doc(inv, "DOC-1")
        self.assertEqual(sorted(m["classes"]), ["matriz_estadual", "orientacoes_estaduais"])  # same bytes, two roles, one document
        e4 = units["DOC-1:Integral 9h!E4"][1]
        self.assertEqual(e4["formula"], "SUM(B4:D4)")
        self.assertIsNone(e4["valor"])
        self.assertEqual(e4["status"], "sem_valor")
        self.assertEqual(units["DOC-1:Integral 9h!B4"][1]["valor"], 5)
        self.assertEqual(units["DOC-1:Integral 9h!A1"][1]["mesclada"], "A1:E1")
        self.assertIn("FORMULA_SEM_VALOR_EM_CACHE", [p["codigo"] for p in m["pendencias"]])
        t = self.doc(inv, "DOC-2")
        self.assertTrue(units[f"{t['id']}:classificacoes!B10"][1]["oculta"])
        shared = units[f"{t['id']}:2.1 Revisão Matriz MG!L14"][1]
        self.assertEqual(shared["formula"], "SUMIFS($D:$D,$F:$F,$J14)")  # shared formula expanded from L13

    def test_duplicate_corrupted_legacy_and_mismatch(self):
        FX.ice_xlsx(self.src / "ice.xlsx")
        (self.src / "copia.xlsx").write_bytes((self.src / "ice.xlsx").read_bytes())
        (self.src / "quebrado.docx").write_bytes(b"PK\x03\x04 isto nao e um zip valido")
        (self.src / "antigo.doc").write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64)
        (self.src / "falso.pdf").write_bytes(FX.png_bytes())
        (self.src / "quebrado.pdf").write_bytes(b"%PDF-1.4\n%%EOF-corrompido")
        inv = self.start({"orientacoes_estaduais": [{"uri": n} for n in ("quebrado.docx", "antigo.doc", "falso.pdf", "quebrado.pdf", "nao-existe.pdf")],
                          "referencial_ice": [{"uri": "ice.xlsx"}, {"uri": "copia.xlsx"}]})
        by_name = {f["nome"]: f for f in inv["fontes"]}
        codes = lambda n: [p["codigo"] for p in by_name[n]["pendencias"]]  # noqa: E731
        self.assertIn("FORMATO_NAO_SUPORTADO", codes("quebrado.docx"))
        self.assertIn("FORMATO_NAO_SUPORTADO", codes("antigo.doc"))
        self.assertIn("TIPO_DIVERGENTE", codes("falso.pdf"))
        self.assertEqual(by_name["falso.pdf"]["media_type"], "image/png")
        self.assertIn("LEITURA_FALHOU", codes("quebrado.pdf"))
        self.assertEqual(by_name["quebrado.pdf"]["status_leitura"], "nao_lida")
        self.assertIn("FONTE_AUSENTE", codes("nao-existe.pdf"))
        self.assertIn("FONTE_DUPLICADA", codes("ice.xlsx"))
        self.assertNotIn("copia.xlsx", by_name)  # same bytes: one document, the repetition is recorded

    def test_urls_without_credentials(self):
        FX.ice_xlsx(self.src / "ice.xlsx")
        pdf = FX.orientations_pdf(self.src / "pub.pdf").read_bytes()

        def opener(req, timeout=60):
            self.assertNotIn("Authorization", req.headers)
            url = req.full_url
            if "negado" in url:
                raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
            if "sumiu" in url:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            if "sharepoint" in url:
                return FakeResponse(b"<html>login</html>", "https://login.microsoftonline.com/common/oauth2")
            return FakeResponse(pdf, url)
        inv = self.start({"orientacoes_estaduais": [{"uri": "https://educacao.exemplo.gov.br/diretrizes.pdf"}, {"uri": "https://exemplo.gov.br/negado.pdf"},
                                                    {"uri": "https://exemplo.gov.br/sumiu.pdf"}, {"uri": "https://exemplo.sharepoint.com/sites/x/doc.pdf"}],
                          "referencial_ice": [{"uri": "ice.xlsx"}]}, opener)
        f = inv["fontes"]
        self.assertEqual(f[0]["media_type"], "application/pdf")
        self.assertEqual(f[0]["status_leitura"], "lida")
        self.assertEqual([p["codigo"] for p in f[1]["pendencias"]], ["ACESSO_NEGADO"])
        self.assertEqual([p["codigo"] for p in f[2]["pendencias"]], ["FONTE_AUSENTE"])
        self.assertEqual([p["codigo"] for p in f[3]["pendencias"]], ["ACESSO_NEGADO"])
        self.assertEqual(f[3]["status_leitura"], "nao_lida")

    def test_version_mismatch_and_missing_approval(self):
        FX.ice_xlsx(self.src / "ice.xlsx")
        inv = self.start({"matriz_estadual": [{"uri": "ice.xlsx", "vigencia": "2024"}]})
        self.assertIn("VERSAO_DIVERGENTE", [p["codigo"] for p in inv["fontes"][0]["pendencias"]])
        self.assertIn("REFERENCIAL_NAO_HOMOLOGADO", [p["codigo"] for p in inv["pendencias"]])

    def test_search_and_image_reading(self):
        FX.orientations_pdf(self.src / "a.pdf", with_image_page=True)
        FX.ice_xlsx(self.src / "ice.xlsx")
        self.start({"orientacoes_estaduais": [{"uri": "a.pdf"}]})
        hits = DN.search(RUN.load_units(self.run), "acolhimento protagonistas")
        self.assertEqual(hits[0]["unidade"], "DOC-1:p1")
        self.assertEqual(hits[0]["localizacao"], {"tipo": "pdf_page", "pagina": 1})
        with self.assertRaises(RUN.RunError):
            RUN.register_image_reading(self.run, "DOC-1:p1", "texto")
        RUN.register_image_reading(self.run, "DOC-1:p3", "Tabela: Tutoria 1 aula semanal")
        u = RUN.unit_index(self.run)["DOC-1:p3"][1]
        self.assertEqual(u["status"], "interpretada_ia")
        inv = RUN.load_inventory(self.run)
        self.assertNotIn("IMAGEM_PENDENTE", [p["codigo"] for p in inv["fontes"][0]["pendencias"]])
        self.assertEqual(DN.search(RUN.load_units(self.run), "tutoria")[0]["status"], "interpretada_ia")

    def test_reuse_folder_of_other_request_is_refused(self):
        FX.ice_xlsx(self.src / "ice.xlsx")
        self.start({})
        m = json.loads((self.src / "manifesto.json").read_text(encoding="utf-8"))
        m["solicitacao_id"] = "OUTRA"
        (self.src / "manifesto.json").write_text(json.dumps(m), encoding="utf-8")
        with self.assertRaises(RUN.RunError):
            RUN.start_run(self.src / "manifesto.json", self.run)


class CliG1Test(unittest.TestCase):
    def test_cli_contract(self):
        import subprocess
        cli = [sys.executable, str(QROOT / "resultado_qualidade.py")]
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            m = FX.source_set(src)
            out = subprocess.run(cli + ["manifesto-validar", str(m), "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(out.returncode, 0, out.stdout)
            self.assertEqual(json.loads(out.stdout)["code"], "MANIFESTO_VALIDO")
            out = subprocess.run(cli + ["iniciar", str(m), "--pasta", str(Path(tmp) / "run"), "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(out.returncode, 0, out.stdout)
            self.assertEqual(len(json.loads(out.stdout)["data"]["fontes"]), 5)
            out = subprocess.run(cli + ["buscar", "--pasta", str(Path(tmp) / "run"), "--termo", "plano de ação", "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertTrue(json.loads(out.stdout)["data"]["resultados"])
            bad = json.loads(m.read_text(encoding="utf-8"))
            bad["modelo"] = "7h"
            m.write_text(json.dumps(bad), encoding="utf-8")
            out = subprocess.run(cli + ["manifesto-validar", str(m), "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(out.returncode, 1)
            self.assertEqual(json.loads(out.stdout)["code"], "MODELO_FORA_ESCOPO")
            out = subprocess.run(cli + ["comando-inexistente", "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(out.returncode, 2)
            out = subprocess.run(cli + ["inventario", "--pasta", str(Path(tmp) / "vazia"), "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual((out.returncode, json.loads(out.stdout)["code"]), (1, "EXECUCAO_INEXISTENTE"))


if __name__ == "__main__":
    unittest.main()
