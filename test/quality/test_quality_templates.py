"""Testes sintéticos para localizar template por estado/ano sem reenvio."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"))
import quality_templates as q  # noqa: E402


def parsed(year="2026"):
    cols = {"MG-" + year: {"valor": "G", "comentario": "H"}}
    return {"sha256": "fake-for-test", "abas": {
        "1.1": {"orientacoes": [{"codigo": "EL1"}], "colunas": cols},
        "1.2": {"orientacoes": [{"codigo": "PT1"}], "colunas": cols}},
        "gabarito": {"1.1|EL1|MG|" + year: {"valor": "Sim", "comentario": "histórico"}}}


class TemplatesTest(unittest.TestCase):
    def setup_dirs(self, root):
        docs = root / "Estados" / "MG" / "2026"
        docs.mkdir(parents=True)
        orientation = docs / "diretrizes.pdf"
        orientation.write_bytes(b"PDF ficticio")
        (docs / "Matriz_Curricular.pdf").write_bytes(b"PDF ficticio")
        templates = root / "Templates" / "MG"
        templates.mkdir(parents=True)
        (templates / "template.xlsx").write_bytes(b"Excel ficticio; mock do parser")
        return root / "Estados", root / "Templates", orientation

    def test_resolve_only_year_and_orientation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(q, "read_template", return_value=parsed()):
            docs, templates, doc = self.setup_dirs(Path(tmp))
            result = q.resolver_inicio(str(docs), str(templates), 2026, str(doc))
            self.assertEqual((result["uf"], result["ano"]), ("MG", 2026))
            self.assertFalse(result["matriz_curricular_confirmada"])
            self.assertIn("Matriz_Curricular.pdf", result["possiveis_matrizes_por_nome"])
            self.assertTrue(result["template"]["arquivo"].endswith("template.xlsx"))
            self.assertEqual(result["template"]["respostas_ja_existentes"], 1)

    def test_outside_directory_requires_explicit_uf(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(q, "read_template", return_value=parsed()):
            docs, templates, _ = self.setup_dirs(Path(tmp))
            external = Path(tmp) / "enviado.pdf"
            external.write_bytes(b"PDF ficticio")
            with self.assertRaisesRegex(ValueError, "informe --uf"):
                q.resolver_inicio(str(docs), str(templates), 2026, str(external))
            result = q.resolver_inicio(str(docs), str(templates), 2026, str(external), "MG")
            self.assertEqual(result["uf"], "MG")

    def test_reject_other_year(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(q, "read_template", return_value=parsed("2025")):
            _, templates, _ = self.setup_dirs(Path(tmp))
            with self.assertRaisesRegex(ValueError, "MG-2026"):
                q.template_info(str(templates), "MG", 2026)

    def test_reject_ambiguous_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, templates, _ = self.setup_dirs(Path(tmp))
            (templates / "MG" / "outro.xlsx").write_bytes(b"Excel ficticio")
            with self.assertRaisesRegex(ValueError, "candidatos"):
                q.template_info(str(templates), "MG", 2026)

    def test_prefer_version_for_year(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(q, "read_template", return_value=parsed()):
            _, templates, _ = self.setup_dirs(Path(tmp))
            specific = templates / "MG" / "2026"
            specific.mkdir()
            (specific / "2026.xlsx").write_bytes(b"Excel ficticio")
            result = q.template_info(str(templates), "MG", 2026)
            self.assertTrue(result["arquivo"].endswith("2026.xlsx"))

    def test_require_registered_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, templates, _ = self.setup_dirs(Path(tmp))
            with self.assertRaisesRegex(ValueError, "não encontrado"):
                q.template_info(str(templates), "CE", 2026)

    def test_does_not_treat_template_as_matrix(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(q, "read_template", return_value=parsed()):
            docs, templates, doc = self.setup_dirs(Path(tmp))
            (docs / "MG" / "2026" / "Matriz_Curricular.pdf").unlink()
            result = q.resolver_inicio(str(docs), str(templates), 2026, str(doc))
            self.assertEqual(result["possiveis_matrizes_por_nome"], [])
            self.assertFalse(result["matriz_curricular_confirmada"])



class OfficialUfTest(unittest.TestCase):
    def test_same_list_as_cfp(self):
        import re
        src = (ROOT / "plugins" / "isg-model-alignment" / "scripts" / "cfp" / "isg_cfp" / "pipeline.py").read_text(encoding="utf-8")
        cfp = set(re.search(r'UF_CODES = \("([A-Z ]+)"\)', src).group(1).split())
        self.assertEqual(set(q.UF_CODES), cfp)
        self.assertEqual(len(q.UF_CODES), 27)

    def test_reject_unknown_uf(self):
        for bad in ("ZZ", "mg", "XX", "", None):
            self.assertFalse(q.is_uf(bad))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "sigla oficial"):
                q.template_info(tmp, "ZZ", 2026)


class RealWorkbookTest(unittest.TestCase):
    """The resolver with a real .xlsx and the real EQV reader (no mock)."""

    def setUp(self):
        from test.eqv.test_eqv import make_xlsx, tab_11, tab_12
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.docs = root / "Estados"
        (self.docs / "CE" / "2026").mkdir(parents=True)
        self.doc = self.docs / "CE" / "2026" / "Orientacoes-CE-2026.pdf"
        self.doc.write_bytes(b"%PDF-1.4 sintetico")
        (self.docs / "CE" / "2026" / "Matriz Curricular CE.pdf").write_bytes(b"%PDF-1.4 sintetico")
        self.templates = root / "Templates"
        (self.templates / "CE").mkdir(parents=True)
        make_xlsx(self.templates / "CE" / "template.xlsx",
                  {"1.1 Base orient. pedagógicas": tab_11(), "1.2 Base orient. gestão": tab_12()})

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolver_reads_real_workbook(self):
        r = q.resolver_inicio(str(self.docs), str(self.templates), 2026, str(self.doc))
        self.assertEqual((r["uf"], r["ano"]), ("CE", 2026))
        self.assertEqual(r["template"]["orientacoes_por_aba"], {"1.1": 3, "1.2": 1})
        self.assertEqual(len(r["template"]["sha256"]), 64)
        self.assertGreater(r["template"]["respostas_ja_existentes"], 0)
        self.assertIn("Matriz Curricular CE.pdf", r["possiveis_matrizes_por_nome"])
        self.assertFalse(r["matriz_curricular_confirmada"])

    def test_real_workbook_without_state_columns(self):
        (self.templates / "MG").mkdir()
        (self.templates / "MG" / "template.xlsx").write_bytes((self.templates / "CE" / "template.xlsx").read_bytes())
        with self.assertRaisesRegex(ValueError, "MG-2026"):
            q.template_info(str(self.templates), "MG", 2026)


if __name__ == "__main__":
    unittest.main()
