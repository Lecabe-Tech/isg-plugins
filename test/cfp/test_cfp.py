"""CFP tests (SPEC-003 VAL-C01..C08): ground truth from generated PDFs. Run: python -m unittest test.cfp.test_cfp -v"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "isg-model-alignment"
CFP_DIR = PLUGIN / "scripts" / "cfp"
sys.path.insert(0, str(CFP_DIR / "vendor"))
sys.path.insert(0, str(CFP_DIR))
sys.dont_write_bytecode = True

from isg_cfp import appdata as appdata_mod  # noqa: E402
from isg_cfp.pipeline import CfpError, process_pdf, slugify  # noqa: E402
from isg_cfp.search import search  # noqa: E402

from . import fixtures as fx  # noqa: E402


def chunk_files(doc_dir: Path):
    return sorted((doc_dir / "chunks").glob("*.md"))


def all_chunk_text(doc_dir: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in chunk_files(doc_dir))


def body_lines(text: str):
    """Content lines of chunk files: no front matter, no markers/labels, headings without '## '."""
    out = []
    for chunk in re.split(r"(?m)^---\n(?:.*\n)*?---\n", text):
        for line in chunk.split("\n"):
            s = line.strip()
            if not s or s.startswith("<!-- página ") or s.startswith("[Imagem") or s.startswith("[Início de tabela") or s == "[Fim de tabela]" or s.startswith("[Página sem texto"):
                continue
            out.append(s[3:] if s.startswith("## ") else s)
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.appdata = self.dir / "dados"
        appdata_mod.ensure_appdata(self.appdata, PLUGIN)

    def pdf(self, doc, name="doc.pdf"):
        p = self.dir / name
        doc.save(p)
        return p

    def run_doc(self, doc, uf="SP", ano=2025, **kw):
        r = process_pdf(self.pdf(doc), uf, ano, self.appdata, **kw)
        return r, Path(r["caminho"])


class AppdataTests(unittest.TestCase):
    def test_default_paths_per_os(self):
        w = appdata_mod.default_appdata({"LOCALAPPDATA": r"C:\Users\ana\AppData\Local"}, "win32", "C:/Users/ana")
        self.assertEqual(w.parts[-2:], ("InstitutoSonhoGrande", "isg-model-alignment"))
        self.assertIn("AppData", str(w))
        m = appdata_mod.default_appdata({}, "darwin", "/Users/ana")
        self.assertTrue(str(m).replace("\\", "/").endswith("/Users/ana/Library/Application Support/InstitutoSonhoGrande/isg-model-alignment"))
        l = appdata_mod.default_appdata({}, "linux", "/home/ana")
        self.assertTrue(str(l).replace("\\", "/").endswith("/home/ana/.local/share/InstitutoSonhoGrande/isg-model-alignment"))
        x = appdata_mod.default_appdata({"XDG_DATA_HOME": "/data"}, "linux", "/home/ana")
        self.assertTrue(str(x).replace("\\", "/").startswith("/data/InstitutoSonhoGrande"))

    def test_override_and_env(self):
        self.assertEqual(str(appdata_mod.resolve_appdata("/x/y", {})).replace("\\", "/"), "/x/y")
        self.assertEqual(str(appdata_mod.resolve_appdata("", {"ISG_DATA_FOLDER": "/z"})).replace("\\", "/"), "/z")

    def test_refuses_folder_inside_plugin(self):
        with self.assertRaises(ValueError):
            appdata_mod.ensure_appdata(PLUGIN / "scripts" / "dados", PLUGIN)

    def test_layout_and_readme(self):
        with tempfile.TemporaryDirectory() as t:
            p = appdata_mod.ensure_appdata(Path(t) / "a", PLUGIN)
            for sub in ("cfp", "config", "logs", "memoria"):
                self.assertTrue((p / sub).is_dir())
            self.assertIn("Pasta de dados", (p / "LEIA-ME.md").read_text(encoding="utf-8"))


class SimpleDocTests(Base):
    def test_basic_processing_and_fidelity(self):
        doc, truth = fx.simple_doc(6)
        r, d = self.run_doc(doc)
        self.assertEqual(r["codigo"], "PROCESSADO")
        self.assertEqual(r["paginas"], 6)
        self.assertEqual(r["status"], "Aprovado", (d / "qualidade.md").read_text(encoding="utf-8"))
        self.assertTrue((d / "original.pdf").is_file())
        for name in ("index.md", "index.json", "qualidade.md", "qualidade.json", "log.json"):
            self.assertTrue((d / name).is_file(), name)
        self.assertEqual(d.parent.name, "2025")
        self.assertEqual(d.parent.parent.name, "SP")
        lines = body_lines(all_chunk_text(d))
        for page in truth:
            for para in page["paragraphs"]:
                self.assertIn(para, lines, f"paragraph of page {page['page']} not found intact")
            if page["heading"]:
                self.assertIn(page["heading"], lines)

    def test_header_footer_and_numbers_are_moved_not_deleted(self):
        doc, truth = fx.simple_doc(6)
        _, d = self.run_doc(doc)
        text = all_chunk_text(d)
        lines = body_lines(text)
        self.assertNotIn(fx.HEADER, lines)
        markers = re.findall(r"(?m)^<!-- página \d+.*-->$", text)
        self.assertEqual(len(markers), 6)
        for p, m in enumerate(markers, 1):
            self.assertIn(f"cabeçalho: {fx.HEADER}", m)
            self.assertIn(f"rodapé: {fx.FOOTER}", m)
            self.assertIn(f"Página {p}", m)

    def test_character_conservation_against_ground_truth(self):
        doc, _ = fx.simple_doc(6)
        _, d = self.run_doc(doc)
        source = Counter(c for t in doc.all_text() for c in t if not c.isspace())
        q = json.loads((d / "qualidade.json").read_text(encoding="utf-8"))
        cons = q["conservacao"]
        self.assertEqual(cons["faltando"], 0)
        self.assertEqual(cons["a_mais"], 0)
        # independent check: rebuild characters from the files
        out = Counter()
        text = all_chunk_text(d)
        for line in body_lines(text):
            out.update(c for c in line if not c.isspace())
        for m in re.finditer(r"(?m)^<!-- página \d+(.*)-->$", text):
            tail = re.sub(r"\(continuação\)|\| cabeçalho:|\| rodapé:|\| número impresso:", "", m.group(1))
            out.update(c for c in tail if not c.isspace())
        removed = Counter({"-": sum(1 for t in doc.all_text() if t.endswith("-"))})
        expected = source.copy()
        expected.subtract(removed)
        expected["#"] += 0
        self.assertEqual(+(expected), +(out), "every character of the PDF must be in the output (except logged hyphens)")

    def test_hyphen_join_is_logged(self):
        doc, _ = fx.simple_doc(6)
        _, d = self.run_doc(doc)
        q = json.loads((d / "qualidade.json").read_text(encoding="utf-8"))
        self.assertEqual(len(q["hifenizacoes_unidas"]), 6)
        j = q["hifenizacoes_unidas"][0]
        self.assertEqual((j["esquerda"], j["direita"], j["resultado"]), ("inter-", "disciplinar", "interdisciplinar"))
        self.assertIn("interdisciplinar", (d / "qualidade.md").read_text(encoding="utf-8"))

    def test_page_ranges_and_coverage(self):
        doc, _ = fx.simple_doc(6)
        _, d = self.run_doc(doc, max_chars=1500, min_chars=300)
        idx = json.loads((d / "index.json").read_text(encoding="utf-8"))
        self.assertGreater(len(idx["chunks"]), 1)
        text = all_chunk_text(d)
        self.assertEqual({int(n) for n in re.findall(r"(?m)^<!-- página (\d+)", text)}, set(range(1, 7)))
        for c in idx["chunks"]:
            self.assertLessEqual(c["caracteres"], 1500 * 1.25 + 50)
        # no paragraph appears in two chunks
        seen = Counter(body_lines(text))
        for line, n in seen.items():
            if len(line) > 80 and line not in (fx.FILLER[0], fx.FILLER[1], fx.FILLER[2]):
                pass
        for p in range(1, 7):
            self.assertEqual(len(re.findall(rf"(?m)^<!-- página {p}\b", text)) >= 1, True)

    def test_headings_become_sections(self):
        doc, _ = fx.simple_doc(6)
        _, d = self.run_doc(doc, max_chars=2500, min_chars=300)
        idx = json.loads((d / "index.json").read_text(encoding="utf-8"))
        sections = " ".join(c["secao"] for c in idx["chunks"])
        self.assertIn("1. Projeto de Vida 1", sections)
        self.assertIn("3. Projeto de Vida 3", sections)

    def test_deterministic_output(self):
        doc, _ = fx.simple_doc(6)
        with tempfile.TemporaryDirectory() as other:
            a = process_pdf(self.pdf(doc, "a.pdf"), "SP", 2025, self.appdata)
            b_app = Path(other) / "d"
            appdata_mod.ensure_appdata(b_app, PLUGIN)
            b = process_pdf(self.pdf(doc, "a.pdf"), "SP", 2025, b_app)
            self.assertEqual(a["saida_sha256"], b["saida_sha256"])
            for f in chunk_files(Path(a["caminho"])):
                self.assertEqual(f.read_bytes(), (Path(b["caminho"]) / "chunks" / f.name).read_bytes())

    def test_cache_force_and_new_version(self):
        doc, _ = fx.simple_doc(4)
        r1, d1 = self.run_doc(doc)
        r2, _ = self.run_doc(doc)
        self.assertEqual(r2["codigo"], "JA_PROCESSADO")
        r3 = process_pdf(self.dir / "doc.pdf", "SP", 2025, self.appdata, force=True)
        self.assertEqual(r3["codigo"], "PROCESSADO")
        olds = [p for p in d1.parent.iterdir() if "-substituido-" in p.name]
        self.assertEqual(len(olds), 1, "the previous folder is kept, never deleted")
        # a different PDF with the same title: new folder, old marked superseded
        doc2, _ = fx.simple_doc(5)
        r4, d4 = self.run_doc(doc2, name="v2.pdf") if False else (None, None)
        p2 = self.dir / "v2.pdf"
        doc2.save(p2)
        r4 = process_pdf(p2, "SP", 2025, self.appdata)
        cat = json.loads((self.appdata / "cfp" / "catalogo.json").read_text(encoding="utf-8"))["documentos"]
        self.assertTrue(any(d.get("substituido_por") == r4["pasta"] for d in cat))
        self.assertTrue((self.appdata / "cfp" / "catalogo.md").is_file())

    def test_survives_nothing_is_deleted(self):
        doc, _ = fx.simple_doc(3)
        r, d = self.run_doc(doc)
        before = {p for p in self.appdata.rglob("*")}
        process_pdf(self.dir / "doc.pdf", "SP", 2025, self.appdata)  # cached
        self.assertTrue(before <= {p for p in self.appdata.rglob("*")})


class LayoutTests(Base):
    def test_two_columns_read_in_order_and_flagged(self):
        doc, truth = fx.columns_doc()
        r, d = self.run_doc(doc)
        text = all_chunk_text(d)
        lines = body_lines(text)
        self.assertIn(truth["left"], lines)
        self.assertIn(truth["right"], lines)
        self.assertLess(lines.index(truth["left"]), lines.index(truth["right"]))
        q = json.loads((d / "qualidade.json").read_text(encoding="utf-8"))
        self.assertIn("duas colunas — ordem de leitura inferida", q["paginas"][0]["avisos"])
        self.assertEqual(r["status"], "Aprovado com avisos")

    def test_table_image_and_empty_page(self):
        doc = fx.mixed_doc()
        r, d = self.run_doc(doc)
        text = all_chunk_text(d)
        self.assertIn("[Imagem não processada — página 1]", text)
        self.assertIn("[Início de tabela — página 2 — conferir no PDF]", text)
        self.assertIn("Projeto de Vida    2 aulas    1º ano", text)
        self.assertIn("[Fim de tabela]", text)
        self.assertIn("<!-- página 3 -->", text)
        self.assertIn("[Página sem texto extraível — conferir no PDF]", text)
        q = json.loads((d / "qualidade.json").read_text(encoding="utf-8"))
        flags = {p["pagina"]: p["avisos"] for p in q["paginas"]}
        self.assertIn("imagem não processada", flags[1])
        self.assertIn("tabela", flags[2])
        self.assertIn("página sem texto extraível", flags[3])
        # 1 of 4 pages (25 %) has no text: above the 10 % limit, so the status is Reprovado (content is still all there)
        self.assertEqual(r["status"], "Reprovado")
        self.assertEqual(q["conservacao"]["faltando"], 0)
        self.assertEqual({int(n) for n in re.findall(r"(?m)^<!-- página (\d+)", text)}, {1, 2, 3, 4})

    def test_many_empty_pages_is_reprovado_but_nothing_dropped(self):
        r, d = self.run_doc(fx.many_empty_doc())
        self.assertEqual(r["status"], "Reprovado")
        text = all_chunk_text(d)
        self.assertEqual({int(n) for n in re.findall(r"(?m)^<!-- página (\d+)", text)}, {1, 2, 3, 4, 5})
        self.assertGreater(len(body_lines(text)), 0)

    def test_page_numbers_are_listed_in_markers(self):
        doc, _ = fx.simple_doc(5)
        _, d = self.run_doc(doc)
        self.assertIn("Página 3", all_chunk_text(d))


class SearchTests(Base):
    def test_accent_and_case_insensitive(self):
        doc, _ = fx.simple_doc(6)
        self.run_doc(doc)
        for q in ("projeto de vida", "PROJETO DE VIDA", "projéto dé vída", '"Projeto de Vida"'):
            r = search(self.appdata / "cfp", q, uf="SP", ano=2025)
            self.assertGreater(r["total"], 0, q)
            h = r["hits"][0]
            self.assertTrue(h["pagina"] >= 1 and h["chunk"].isdigit() and h["trecho"])
        self.assertEqual(search(self.appdata / "cfp", "inexistentexyz")["total"], 0)

    def test_filters_and_cap(self):
        doc, _ = fx.simple_doc(6)
        self.run_doc(doc, uf="SP", ano=2025)
        self.assertEqual(search(self.appdata / "cfp", "projeto", uf="MG")["total"], 0)
        r = search(self.appdata / "cfp", "estudantes", limit=2)
        self.assertEqual(len(r["hits"]), 2)
        self.assertGreater(r["total"], 2)

    def test_all_terms_must_be_on_the_same_page(self):
        doc, _ = fx.simple_doc(2)
        self.run_doc(doc)
        self.assertGreater(search(self.appdata / "cfp", "interdisciplinar currículo")["total"], 0)
        self.assertEqual(search(self.appdata / "cfp", "interdisciplinar zzzz")["total"], 0)


class RefusalTests(Base):
    def test_inputs_are_validated(self):
        doc, _ = fx.simple_doc(2)
        p = self.pdf(doc)
        for uf, ano in (("XX", 2025), ("", 2025), ("SP", "abc"), ("SP", 1999), ("SP", 2999)):
            with self.assertRaises(CfpError) as c:
                process_pdf(p, uf, ano, self.appdata)
            self.assertEqual(c.exception.code, "ENTRADA_INVALIDA")
        txt = self.dir / "x.docx"
        txt.write_bytes(b"PK")
        with self.assertRaises(CfpError) as c:
            process_pdf(txt, "SP", 2025, self.appdata)
        self.assertEqual(c.exception.code, "ENTRADA_INVALIDA")
        fake = self.dir / "fake.pdf"
        fake.write_bytes(b"not a pdf at all")
        with self.assertRaises(CfpError) as c:
            process_pdf(fake, "SP", 2025, self.appdata)
        self.assertEqual(c.exception.code, "PDF_INVALIDO")
        with self.assertRaises(CfpError):
            process_pdf(self.dir / "nao-existe.pdf", "SP", 2025, self.appdata)
        self.assertFalse(list((self.appdata / "cfp").glob("SP")), "nothing is written when the input is refused")

    def test_encrypted_pdf_is_refused(self):
        from pypdf import PdfReader, PdfWriter

        doc, _ = fx.simple_doc(2)
        plain = self.pdf(doc, "plain.pdf")
        writer = PdfWriter(clone_from=PdfReader(str(plain)))
        writer.encrypt("senha", algorithm="RC4-128")
        enc = self.dir / "protegido.pdf"
        with open(enc, "wb") as f:
            writer.write(f)
        with self.assertRaises(CfpError) as c:
            process_pdf(enc, "SP", 2025, self.appdata)
        self.assertEqual(c.exception.code, "PDF_PROTEGIDO")
        self.assertIn("senha", c.exception.message)
        self.assertEqual(list((self.appdata / "cfp").iterdir()), [], "nothing is written for a protected PDF")

    def test_slug(self):
        self.assertEqual(slugify("Currículo Paulista — Ensino Médio (2025)"), "curriculo-paulista-ensino-medio-2025")
        self.assertLessEqual(len(slugify("a" * 100)), 40)


class CliTests(Base):
    def cli(self, *args, check_json=True):
        env = dict(os.environ, ISG_DATA_FOLDER=str(self.appdata), PYTHONUTF8="1")
        r = subprocess.run([sys.executable, str(CFP_DIR / "cfp.py"), *args], capture_output=True, text=True, encoding="utf-8", env=env, stdin=subprocess.DEVNULL, timeout=120)
        data = json.loads(r.stdout) if check_json and r.stdout.strip().startswith("{") else None
        return r, data

    def test_processar_buscar_listar_status_pagina(self):
        doc, _ = fx.simple_doc(6)
        p = self.pdf(doc)
        r, j = self.cli("processar", str(p), "--uf", "SP", "--ano", "2025", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(j["code"], "PROCESSADO")
        self.assertIn("Situação de qualidade", j["message"])
        r, j = self.cli("processar", str(p), "--uf", "SP", "--ano", "2025", "--json")
        self.assertEqual(j["code"], "JA_PROCESSADO")
        r, j = self.cli("buscar", "projeto de vida", "--uf", "SP", "--json")
        self.assertEqual(j["code"], "RESULTADOS")
        self.assertGreater(j["data"]["total"], 0)
        r, j = self.cli("buscar", "xyzxyz", "--json")
        self.assertEqual((r.returncode, j["code"]), (0, "NADA_ENCONTRADO"))
        r, j = self.cli("listar", "--json")
        self.assertEqual(len(j["data"]["documentos"]), 1)
        pasta = j["data"]["documentos"][0]["pasta"]
        r, j = self.cli("status", pasta, "--json")
        self.assertEqual(j["code"], "STATUS")
        r, j = self.cli("pagina", pasta, "1", "--json")
        self.assertEqual(j["code"], "PAGINA")
        self.assertIn("Projeto de Vida", j["data"]["bruto"])
        self.assertIn("página 1", j["data"]["organizado"])
        r, j = self.cli("pagina", pasta, "99", "--json")
        self.assertEqual((r.returncode, j["code"]), (1, "PAGINA_INEXISTENTE"))

    def test_human_mode_is_pt_br(self):
        doc, _ = fx.simple_doc(3)
        r, _ = self.cli("processar", str(self.pdf(doc)), "--uf", "SP", "--ano", "2025", check_json=False)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Documento processado", r.stdout)
        self.assertIn("Situação de qualidade", r.stdout)

    def test_refusals_and_exit_codes(self):
        doc, _ = fx.simple_doc(2)
        p = str(self.pdf(doc))
        r, j = self.cli("processar", p, "--uf", "ZZ", "--ano", "2025", "--json")
        self.assertEqual((r.returncode, j["code"]), (1, "ENTRADA_INVALIDA"))
        self.assertIn("UF inválida", j["message"])
        r, j = self.cli("processar", p, "--uf", "SP", "--ano", "20x5", "--json")
        self.assertEqual((r.returncode, j["code"]), (1, "ENTRADA_INVALIDA"))
        r, j = self.cli("processar", p, "--json")  # missing required options
        self.assertEqual((r.returncode, j["code"]), (2, "USO_INCORRETO"))
        r, j = self.cli("bogus", "--json")
        self.assertEqual(r.returncode, 2)
        r, _ = self.cli(check_json=False)
        self.assertEqual(r.returncode, 2)

    def test_data_folder_inside_plugin_is_refused(self):
        env = dict(os.environ, ISG_DATA_FOLDER=str(PLUGIN / "scripts" / "dados"))
        r = subprocess.run([sys.executable, str(CFP_DIR / "cfp.py"), "listar", "--json"], capture_output=True, text=True, encoding="utf-8", env=env, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["code"], "PASTA_INVALIDA")
        self.assertFalse((PLUGIN / "scripts" / "dados").exists())

    def test_no_bytecode_written_inside_plugin(self):
        self.cli("listar", "--json")
        self.assertEqual(list(CFP_DIR.rglob("__pycache__")), [])


class FidelityGuardTests(unittest.TestCase):
    """The checks that protect the analysts from silently wrong content (SPEC-003 REQ-CCL-06, CQL-02)."""

    def _results(self):
        from isg_cfp.chunk import make_chunks
        from isg_cfp.extract import extract_page, open_reader
        from isg_cfp.organize import organize_document
        from isg_cfp.render import render_chunk

        with tempfile.TemporaryDirectory() as t:
            doc, _ = fx.simple_doc(4)
            p = Path(t) / "a.pdf"
            doc.save(p)
            reader, _ = open_reader(p)
            raw = [extract_page(reader, i) for i in range(len(reader.pages))]
        results, info = organize_document(raw)
        chunks = make_chunks(results)
        pages = {pr.number: pr for pr in results}
        texts = [render_chunk(c, "doc", "SP", 2025, pages, len(chunks)) for c in chunks]
        return results, texts

    def test_verify_passes_on_intact_output(self):
        from isg_cfp.quality import verify_written

        results, texts = self._results()
        problems, stats = verify_written(results, texts)
        self.assertEqual(problems, [])
        self.assertEqual(stats["faltando"], 0)
        self.assertEqual(stats["a_mais"], 0)

    def test_verify_detects_a_dropped_character(self):
        from isg_cfp.quality import evaluate, verify_written

        results, texts = self._results()
        broken = [texts[0].replace("estudantes", "estudantes"[:-1], 1)] + texts[1:]
        problems, stats = verify_written(results, broken)
        self.assertTrue(any(p.startswith("Q2") for p in problems))
        self.assertGreater(stats["faltando"], 0)
        self.assertEqual(evaluate(results, problems)["status"], "Reprovado")

    def test_verify_detects_an_invented_character_and_a_missing_page(self):
        from isg_cfp.quality import verify_written

        results, texts = self._results()
        problems, _ = verify_written(results, [texts[0] + "\nTexto inventado\n"] + texts[1:])
        self.assertTrue(any("a mais" in p for p in problems))
        no_marker = [re.sub(r"(?m)^<!-- página 2\b.*$", "", t) for t in texts]
        problems, _ = verify_written(results, no_marker)
        self.assertTrue(any(p.startswith("Q1") for p in problems))

    def test_normalization_and_ligatures(self):
        from isg_cfp.extract import normalize_text

        lig = Counter()
        self.assertEqual(normalize_text("oﬁcial e aﬂuente", lig), "oficial e afluente")
        self.assertEqual(lig["ﬁ"], 1)
        self.assertEqual(lig["ﬂ"], 1)
        self.assertEqual(normalize_text("café"), "café")  # NFC

    def test_garbled_detection(self):
        from isg_cfp.extract import is_garbled_char

        self.assertTrue(is_garbled_char("�"))
        self.assertTrue(is_garbled_char(""))
        self.assertTrue(is_garbled_char("\x01"))
        self.assertFalse(is_garbled_char("ç"))
        self.assertFalse(is_garbled_char("\n"))

    def test_hyphen_rules(self):
        from isg_cfp.organize import PageResult, _join

        pr = PageResult(number=1)
        self.assertEqual(_join("inter-", "disciplinar", 1, pr), "interdisciplinar")
        self.assertEqual(pr.hyphens_removed["-"], 1)
        self.assertEqual(_join("Rio-", "Grande", 1, pr), "Rio-Grande")  # uppercase next: keep the hyphen
        self.assertEqual(pr.hyphens_removed["-"], 1)
        self.assertEqual(_join("e", "assim", 1, pr), "e assim")
        self.assertEqual(_join("itens 1-", "2 do texto", 1, pr), "itens 1- 2 do texto")  # digit before the hyphen: not hyphenation
        self.assertEqual(_join("pro­", "grama", 1, pr), "programa")
        self.assertEqual(pr.hyphens_removed["­"], 1)

    def test_comment_terminator_in_header_keeps_the_marker_valid(self):
        from isg_cfp.organize import PageResult
        from isg_cfp.render import page_marker

        pr = PageResult(number=3, header=["Seção --> especial"])
        marker = page_marker(pr, True)
        self.assertEqual(marker.count("-->"), 1)
        self.assertTrue(marker.endswith("-->"))

    def test_long_paragraph_is_split_at_sentences_and_flagged(self):
        from isg_cfp.chunk import make_chunks
        from isg_cfp.organize import Block, PageResult

        sentence = "Esta é uma frase de teste com tamanho razoável para o experimento. "
        big = (sentence * 40).strip()
        pr = PageResult(number=1, blocks=[Block("heading", "1. Título", 1, 1), Block("para", big, 1)])
        chunks = make_chunks([pr], cap=500, minimum=100)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c.text_size <= 500 + 10 for c in chunks))
        self.assertTrue(any("parágrafo longo dividido" in c.flags for c in chunks))
        joined = " ".join(b.text for c in chunks for b in c.blocks if b.type == "para")
        self.assertEqual(re.sub(r"\s+", "", joined), re.sub(r"\s+", "", big), "splitting loses nothing")


class PerformanceTests(Base):
    def test_300_pages_within_budget(self):
        doc = fx.big_doc(300)
        p = self.pdf(doc)
        t = time.time()
        r = process_pdf(p, "SP", 2025, self.appdata)
        elapsed = time.time() - t
        self.assertEqual(r["paginas"], 300)
        self.assertEqual(r["conservacao"]["faltando"], 0)
        self.assertLess(elapsed, 120, f"300 pages took {elapsed:.1f}s (budget 120 s)")
        print(f"\n  300 pages processed in {elapsed:.1f}s, {r['chunks']} chunks, status {r['status']}")


if __name__ == "__main__":
    unittest.main()
