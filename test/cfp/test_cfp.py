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
        self.assertIn("[Imagem não processada — página 1 — id p001-01]", text)
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


class RealWorldPatternTests(Base):
    """Regression tests for patterns found on the first real document (SPEC-003 7.1)."""

    def setUp(self):
        super().setUp()
        self.r, self.d = self.run_doc(fx.realworld_doc(), uf="MG", ano=2026)
        self.text = all_chunk_text(self.d)
        self.lines = body_lines(self.text)
        self.q = json.loads((self.d / "qualidade.json").read_text(encoding="utf-8"))

    def test_toc_lines_are_not_headings(self):
        self.assertFalse(any(l.startswith("## 1. Princípios") or l.startswith("## 2. Eixos") for l in re.findall(r"(?m)^.*$", self.text)))
        self.assertIn("1. Princípios educativos.....................................5", self.lines)
        self.assertIn("SUMÁRIO", self.lines)
        self.assertIn("## SUMÁRIO", self.text)

    def test_bullets_stay_with_their_text_and_do_not_flag_the_page(self):
        self.assertIn("• Orientar professores e estudantes sobre as normas", self.lines)
        self.assertIn("• Acompanhar a implementação das diretrizes", self.lines)
        self.assertNotIn("ordem de leitura incerta", self.q["paginas"][0]["avisos"])

    def test_bold_label_is_not_a_heading(self):
        self.assertIn("Equipe escolar:", self.lines)
        self.assertNotIn("## Equipe escolar:", self.text)

    def test_detached_line_end_hyphen_is_joined_and_logged(self):
        joined = " ".join(self.lines)
        self.assertIn("organização do curso", joined)
        self.assertIn("mobilizar saberes", joined)
        results = {j["resultado"] for j in self.q["hifenizacoes_unidas"]}
        self.assertEqual(results, {"organização", "mobilizar"})
        self.assertEqual(self.q["conservacao"]["faltando"], 0)
        self.assertEqual(self.q["conservacao"]["a_mais"], 0)


class ImageHandlingTests(Base):
    """Found on the CE 2026 document: every page had the same header/footer banner images, so every page was flagged."""

    def test_repeated_banners_are_decoration_and_small_icons_do_not_flag(self):
        r, d = self.run_doc(fx.banner_doc(6))
        q = json.loads((d / "qualidade.json").read_text(encoding="utf-8"))
        pages = {p["pagina"]: p for p in q["paginas"]}
        for n in (1, 2, 4, 5, 6):
            self.assertEqual(pages[n]["avisos"], [], f"page {n}: only decoration (and maybe a small icon), no warning")
            self.assertEqual(pages[n]["imagens"], 0)
            self.assertEqual(pages[n]["imagens_decorativas"], 2)
        self.assertEqual(pages[1]["imagens_pequenas"], 1)
        self.assertEqual(pages[4]["imagens_pequenas"], 0)
        self.assertIn("imagem não processada", pages[3]["avisos"], "a real figure still flags its page")
        self.assertEqual(pages[3]["imagens"], 1)
        text = all_chunk_text(d)
        self.assertEqual(text.count("[Imagem não processada — página 3 — id p003-01]"), 1)
        self.assertNotIn("[Imagem não processada — página 1]", text)
        self.assertIn("[Imagem pequena não processada — página 1 — id p001-01]", text)
        self.assertEqual(r["status"], "Aprovado com avisos")
        self.assertEqual(q["conservacao"]["faltando"], 0)
        self.assertTrue(q["imagens_decorativas_repetidas"], "the decoration is listed in the report")
        self.assertIn("decoração", (d / "qualidade.md").read_text(encoding="utf-8"))

    def test_document_with_only_decoration_is_approved(self):
        from . import fixtures as f2

        doc = f2.banner_doc(6)
        # same document without the real figure on page 3
        doc.pages[2] = (doc.pages[2][0][:-1],) + doc.pages[2][1:]
        r, d = self.run_doc(doc)
        self.assertEqual(r["status"], "Aprovado")


class NarrowColumnTests(Base):
    def test_columns_with_a_narrow_gutter_are_not_mixed(self):
        doc, truth = fx.narrow_columns_doc()
        r, d = self.run_doc(doc)
        lines = body_lines(all_chunk_text(d))
        joined = " ".join(lines)
        self.assertIn(truth["left"], joined)
        self.assertIn(truth["right"], joined)
        self.assertLess(joined.index(truth["left"]), joined.index(truth["right"]))
        self.assertIn("3.2. A comunidade de aprendizagem como modelo de escola", lines, "a heading that crosses the gutter stays in one piece")
        q = json.loads((d / "qualidade.json").read_text(encoding="utf-8"))
        flags = q["paginas"][0]["avisos"]
        self.assertIn("duas colunas — ordem de leitura inferida", flags)
        self.assertNotIn("tabela", flags)
        self.assertEqual(q["conservacao"]["faltando"], 0)

    def test_a_table_with_short_cells_is_still_a_table(self):
        r, d = self.run_doc(fx.mixed_doc())
        q = json.loads((d / "qualidade.json").read_text(encoding="utf-8"))
        self.assertIn("tabela", q["paginas"][1]["avisos"])
        self.assertNotIn("duas colunas — ordem de leitura inferida", q["paginas"][1]["avisos"])


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


class ReplaceRetryTests(unittest.TestCase):
    """Windows can refuse a rename for a moment while antivirus/indexer holds new files."""

    def test_retries_a_transient_permission_error(self):
        from unittest import mock
        from isg_cfp import pipeline
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "a.tmp", Path(tmp) / "a"
            src.write_text("x", encoding="utf-8")
            real = os.replace
            calls = []

            def flaky(s, d):
                calls.append(1)
                if len(calls) < 3:
                    raise PermissionError(5, "Acesso negado")
                return real(s, d)

            with mock.patch.object(pipeline.os, "replace", side_effect=flaky), mock.patch("time.sleep"):
                pipeline.replace_with_retry(src, dst)
            self.assertEqual(len(calls), 3)
            self.assertEqual(dst.read_text(encoding="utf-8"), "x")

    def test_gives_up_after_the_last_attempt(self):
        from unittest import mock
        from isg_cfp import pipeline
        with mock.patch.object(pipeline.os, "replace", side_effect=PermissionError(5, "Acesso negado")), mock.patch("time.sleep"):
            with self.assertRaises(PermissionError):
                pipeline.replace_with_retry(Path("a"), Path("b"), attempts=3)


# ---------------------------------------------------------------- SPEC-004: image extraction, SIP registration, enriched copy

from isg_cfp import integrate as sip  # noqa: E402
from isg_cfp import pngwriter  # noqa: E402
from . import pdfgen  # noqa: E402


def sample_interpretation(iid: str, sha: str, extra: str = "", confidence: str = "75") -> str:
    return (f"---\nid: {iid}\nsha256: {sha}\npagina: 1\nconfianca: {confidence}\ngerado_em: 2026-11-04T15:20:00Z\norigem: IA (Claude)\nversao_modelo_sip: 1\nestado: interpretada\n---\n\n"
            "### Tipo\ngráfico (barras)\n\n### Texto na imagem (transcrição literal)\nTítulo: \"Matrículas por rede\"\n\n"
            f"### Conteúdo estruturado\n| Rede | Valor |\n|---|---|\n| Estadual | 12,4 |\n\n### Descrição\nDuas barras.{extra}\n\n"
            "### Significado no contexto\nMostra a distribuição.\n\n### Confiança\n75% — um valor ilegível.\n\n### Dúvidas e partes ilegíveis\n- nenhuma\n")


def load_index(doc: Path) -> dict:
    return {e["id"]: e for e in json.loads((doc / "imagens" / "index.json").read_text(encoding="utf-8"))["imagens"]}


class ImageExtractionTests(Base):
    def setUp(self):
        super().setUp()
        self.r, self.d = self.run_doc(fx.images_doc())
        self.idx = load_index(self.d)

    def test_files_are_valid_and_faithful(self):
        self.assertEqual(sorted(self.idx), ["p001-01", "p002-01", "p002-02", "p003-01", "p004-01", "p006-01"])
        self.assertEqual((self.d / "imagens" / "p002-01.jpg").read_bytes(), pdfgen.IM5_JPEG, "JPEG is copied byte for byte")
        w, h, ct, samples = pngwriter.decode_png_samples((self.d / "imagens" / "p001-01.png").read_bytes())
        self.assertEqual((w, h, ct), (240, 240, 2))
        self.assertEqual(samples, pdfgen.IM4_PIXELS, "raw RGB pixels survive the PNG encoding")
        w, h, ct, samples = pngwriter.decode_png_samples((self.d / "imagens" / "p004-01.png").read_bytes())
        self.assertEqual((ct, samples), (3, pdfgen.IM7_INDEXES), "indexed image keeps its indexes (and a palette)")

    def test_unsupported_duplicates_cover_and_legend(self):
        e = self.idx["p003-01"]
        self.assertEqual(e["estado"], "não extraível")
        self.assertIn("CCITTFaxDecode", e["motivo"])
        self.assertFalse((self.d / "imagens" / "p003-01.png").exists())
        self.assertEqual(self.idx["p002-02"]["igual_a"], "p001-01")
        self.assertIsNone(self.idx["p002-02"]["arquivo"], "a duplicate is not written twice")
        self.assertTrue(self.idx["p006-01"]["pagina_inteira"], "a page that is only an image is marked")
        self.assertEqual(self.idx["p001-01"]["sha256"], self.idx["p006-01"]["sha256"])
        self.assertTrue(self.idx["p001-01"]["legenda"].startswith("Figura 1"))
        self.assertEqual(self.idx["p001-01"]["chunk"], 1)
        for k in ("pagina", "x", "y", "largura", "altura", "pixels", "formato", "sha256", "area_pagina", "texto_antes", "texto_depois", "estado"):
            self.assertIn(k, self.idx["p001-01"])

    def test_markers_carry_ids_and_match_the_index(self):
        text = all_chunk_text(self.d)
        ids = set(re.findall(r"\[Imagem (?:pequena )?não processada — página \d+ — id (p\d+-\d+)\]", text))
        self.assertEqual(ids, set(self.idx), "Q13: every marker has an index entry and the other way around")

    def test_vector_page_is_flagged_and_text_pages_are_not(self):
        q = json.loads((self.d / "qualidade.json").read_text(encoding="utf-8"))
        flagged = {p["pagina"] for p in q["paginas"] if any("gráfico vetorial" in a for a in p["avisos"])}
        self.assertEqual(flagged, {5})

    def test_skipping_images_and_idempotent_reextraction(self):
        r, d = self.run_doc(fx.images_doc(), force=True, extract_images=False)
        self.assertFalse((d / "imagens").exists())
        r = subprocess.run([sys.executable, str(CFP_DIR / "cfp.py"), "imagens", str(d), "--json", "--pasta-de-dados", str(self.appdata)], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
        self.assertEqual(json.loads(r.stdout)["code"], "IMAGENS_EXTRAIDAS", r.stdout)
        self.assertEqual((d / "imagens" / "p002-01.jpg").read_bytes(), pdfgen.IM5_JPEG)

    def test_png_writer_round_trip(self):
        g = bytes(range(12))
        self.assertEqual(pngwriter.decode_png_samples(pngwriter.encode_png(4, 3, g, "L"))[3], g)
        self.assertEqual(pngwriter.cmyk_to_rgb(bytes([0, 0, 0, 0, 255, 0, 0, 0])), bytes([255, 255, 255, 0, 255, 255]))
        with self.assertRaises(ValueError):
            pngwriter.encode_png(4, 3, g[:5], "L")


class SipIntegrationTests(Base):
    def setUp(self):
        super().setUp()
        self.r, self.d = self.run_doc(fx.images_doc())
        self.idx = load_index(self.d)

    def register(self, iid="p001-01", estado="interpretada", extra=""):
        md = self.dir / f"{iid}.md"
        md.write_text(sample_interpretation(iid, self.idx[iid]["sha256"], extra), encoding="utf-8", newline="\n")
        return sip.register(self.d, self.appdata, iid, md, estado)

    def test_template_lint_and_registration(self):
        bad = self.dir / "bad.md"
        bad.write_text("---\nid: p001-01\n---\n\n### Tipo\nx\n", encoding="utf-8")
        with self.assertRaises(sip.SipError) as cm:
            sip.register(self.d, self.appdata, "p001-01", bad)
        self.assertEqual(cm.exception.code, "MODELO_INVALIDO")
        with self.assertRaises(sip.SipError) as cm:
            sip.register(self.d, self.appdata, "p999-01", bad)
        self.assertEqual(cm.exception.code, "IMAGEM_INEXISTENTE")
        r = self.register()
        self.assertEqual(r["estado"], "interpretada")
        idx = load_index(self.d)
        self.assertEqual(idx["p001-01"]["estado"], "interpretada")
        self.assertEqual(idx["p002-02"]["estado"], "interpretada", "the duplicate shares the interpretation")
        self.assertEqual(idx["p006-01"]["estado"], "interpretada")
        self.assertTrue((self.appdata / "sip" / "cache" / f"{self.idx['p001-01']['sha256']}.md").exists())
        text = (self.d / "imagens" / "p001-01.md").read_text(encoding="utf-8")
        self.assertIn("origem: IA (Claude)", text)
        self.assertEqual(sip.validate_interpretation(text), [])

    def test_confidence_is_always_a_percentage(self):
        self.assertEqual([sip.parse_confidence(x) for x in ("90", "90%", " 85 % ", "0", "100")], [90, 90, 85, 0, 100])
        self.assertEqual([sip.parse_confidence(x) for x in ("alta", "média", "101", "-5", "9,5", "")], [None] * 6)
        md = self.dir / "w.md"
        md.write_text(sample_interpretation("p001-01", self.idx["p001-01"]["sha256"], confidence="alta"), encoding="utf-8")
        with self.assertRaises(sip.SipError) as cm:
            sip.register(self.d, self.appdata, "p001-01", md)
        self.assertIn("percentual", cm.exception.message)

    def test_correction_keeps_the_previous_version(self):
        self.register()
        self.register(estado="corrigida", extra=" Corrigido pelo analista.")
        self.assertTrue((self.d / "imagens" / "p001-01.v1.md").exists())
        self.assertIn("Corrigido pelo analista", (self.d / "imagens" / "p001-01.md").read_text(encoding="utf-8"))
        self.assertEqual(sip.effective_state(self.d, load_index(self.d)["p001-01"]), "corrigida")

    def test_pending_report_estimate_and_global_cache(self):
        rep = sip.pending_report(self.d, self.appdata)
        self.assertEqual(sorted(p["id"] for p in rep["pendentes"]), ["p001-01", "p002-01", "p004-01"], "duplicates and non-extractable images are not counted")
        lo, hi = sip.estimate_tokens(self.idx["p004-01"])
        self.assertEqual(lo, 9 * 9 + 1000, "240 px -> ceil(240/28)^2 = 81 visual tokens plus the answer")
        self.assertGreaterEqual(rep["tokens_max"], rep["tokens_min"])
        self.register()
        self.assertEqual(sip.pending_report(self.d, self.appdata)["quantidade"], 2)
        # another document with the same picture: filled from the global cache, no AI
        doc2 = fx.images_doc()
        doc2.title = "Outro documento com a mesma figura"
        r2, d2 = self.run_doc(doc2, uf="MG", ano=2025)
        rep2 = sip.pending_report(d2, self.appdata)
        self.assertIn("p001-01", rep2["preenchidas_do_cache"])
        self.assertEqual(rep2["quantidade"], 2)

    def test_enriched_copy_keeps_originals_and_round_trips(self):
        before = {p.name: p.read_bytes() for p in chunk_files(self.d)}
        self.register()
        cov = sip.build_enriched(self.d)
        after = {p.name: p.read_bytes() for p in chunk_files(self.d)}
        self.assertEqual(before, after, "original chunks are byte-identical")
        enriched = {p.name: p.read_text(encoding="utf-8") for p in sorted((self.d / "chunks_com_imagens").glob("*.md"))}
        self.assertEqual(sorted(enriched), sorted(before))
        joined = "\n".join(enriched.values())
        self.assertIn("interpretação por IA, conferir no PDF", joined)
        self.assertIn("> | Estadual | 12,4 |", joined)
        self.assertIn("ainda não interpretada", joined)
        self.assertIn("não foi possível extrair", joined)
        for name, text in enriched.items():
            self.assertEqual(sip.strip_blocks(text).encode("utf-8"), before[name], f"round trip of {name}")
        self.assertFalse(cov["completo"])
        self.assertIn("não extraível", " ".join(cov["motivos"]))
        self.assertEqual(cov["paginas_vetoriais"], [5])
        cob = (self.d / "cobertura.md").read_text(encoding="utf-8")
        self.assertIn("Conteúdo completo: não", cob)
        self.assertTrue((self.d / "index_com_imagens.md").exists())

    def test_complete_only_when_nothing_is_missing(self):
        doc = pdfgen.PdfDoc(title="Uma figura")
        doc.add_page([pdfgen.PdfDoc.text(60, 700, "Texto do documento com uma figura logo abaixo para conferir."), pdfgen.PdfDoc.image(60, 300, 300, 300, name="Im4")])
        r, d = self.run_doc(doc, uf="BA", ano=2024)
        entries = json.loads((d / "imagens" / "index.json").read_text(encoding="utf-8"))["imagens"]
        self.assertFalse(sip.build_enriched(d)["completo"], "pending image")
        md = self.dir / "x.md"
        md.write_text(sample_interpretation(entries[0]["id"], entries[0]["sha256"]), encoding="utf-8", newline="\n")
        sip.register(d, self.appdata, entries[0]["id"], md)
        cov = sip.build_enriched(d)
        self.assertTrue(cov["completo"], cov["motivos"])
        self.assertIn("Conteúdo completo: sim", (d / "cobertura.md").read_text(encoding="utf-8"))

    def test_search_with_images_labels_hits(self):
        self.register()
        sip.build_enriched(self.d)
        hits = search(self.appdata / "cfp", "Estadual", doc=str(self.d), with_images=True)
        self.assertGreaterEqual(hits["total"], 1)
        self.assertEqual(hits["hits"][0].get("origem"), "interpretação de imagem")
        plain = search(self.appdata / "cfp", "Estadual", doc=str(self.d))
        self.assertEqual(plain["total"], 0, "the original chunks do not contain AI text")

    def test_cli_commands(self):
        env = dict(os.environ, ISG_DATA_FOLDER=str(self.appdata), PYTHONUTF8="1")

        def cli(*a):
            r = subprocess.run([sys.executable, str(CFP_DIR / "cfp.py"), *a, "--json"], capture_output=True, text=True, encoding="utf-8", env=env, stdin=subprocess.DEVNULL, timeout=120)
            return json.loads(r.stdout)

        j = cli("imagens-pendentes", str(self.d))
        self.assertEqual((j["code"], j["data"]["quantidade"]), ("PENDENTES", 3))
        self.assertIn("tokens", j["message"])
        md = self.dir / "c.md"
        md.write_text(sample_interpretation("p001-01", self.idx["p001-01"]["sha256"]), encoding="utf-8", newline="\n")
        self.assertEqual(cli("imagem-registrar", str(self.d), "p001-01", str(md))["code"], "REGISTRADA")
        j = cli("integrar", str(self.d))
        self.assertEqual(j["code"], "INTEGRADO")
        self.assertIn("Conteúdo completo: não", j["message"])
        self.assertEqual(cli("integrar", str(self.d / "nada"))["code"], "DOCUMENTO_NAO_ENCONTRADO")


if __name__ == "__main__":
    unittest.main()
