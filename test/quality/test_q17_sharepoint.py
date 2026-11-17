"""SharePoint links as informed locations: mapped to the local OneDrive copy, never downloaded (synthetic folders only)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
QROOT = ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"
sys.path.insert(0, str(QROOT))
import quality_run as RUN  # noqa: E402
import sharepoint_link as SP  # noqa: E402
import source_resolver as SR  # noqa: E402
from test.quality import q17_fixtures as FX  # noqa: E402

HOST = "https://exemplo.sharepoint.com"
LINK = HOST + "/:b:/r/sites/Portal/Documentos%20Compartilhados/Qualidade/MG/diretrizes.pdf?csf=1&web=1&e=abc"


class ParseLinkTest(unittest.TestCase):
    def test_link_kinds(self):
        p = SP.parse_link(LINK)
        self.assertEqual((p["tipo"], p["caminho"], p["nome"]), ("caminho", "/sites/Portal/Documentos Compartilhados/Qualidade/MG/diretrizes.pdf", "diretrizes.pdf"))
        folder = SP.parse_link(HOST + "/sites/Portal/Documentos%20Compartilhados/Forms/AllItems.aspx?id=%2Fsites%2FPortal%2FDocumentos%20Compartilhados%2FQualidade&viewid=1")
        self.assertEqual((folder["caminho"], folder["nome"]), ("/sites/Portal/Documentos Compartilhados/Qualidade", None))
        self.assertEqual(SP.parse_link(HOST + "/:x:/s/Portal/EabcDEF123?e=xyz")["tipo"], "compartilhamento")
        doc = SP.parse_link(HOST + "/:x:/r/sites/Portal/_layouts/15/Doc.aspx?sourcedoc=%7B1%7D&file=Template.xlsx&action=default")
        self.assertEqual((doc["tipo"], doc["nome"]), ("documento", "Template.xlsx"))
        self.assertTrue(SP.is_sharepoint(LINK))
        for other in ("http://exemplo.sharepoint.com/x.pdf", "https://sharepoint.com.exemplo.invalid/x.pdf", "https://exemplo.gov.br/x.pdf"):
            self.assertFalse(SP.is_sharepoint(other), other)


class LocalCopyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_synced_library(self):
        mount = self.dir / "Portal - Documentos"
        (mount / "Qualidade" / "MG").mkdir(parents=True)
        (mount / "Qualidade" / "MG" / "diretrizes.pdf").write_bytes(b"%PDF-1.4")
        libs = [(HOST + "/sites/Portal/Documentos Compartilhados/", str(mount))]
        r = SP.local_copy(LINK, libraries=libs, folders=[])
        self.assertEqual((r["metodo"], r["caminho"]), ("biblioteca_sincronizada", mount / "Qualidade" / "MG" / "diretrizes.pdf"))
        other_host = [("https://outro.sharepoint.com/sites/Portal/Documentos Compartilhados/", str(mount))]
        self.assertIsNone(SP.local_copy(LINK, libraries=other_host, folders=[])["caminho"])

    def test_onedrive_shortcut_by_end_of_path(self):
        od = self.dir / "OneDrive"
        (od / "Qualidade" / "MG").mkdir(parents=True)
        (od / "Qualidade" / "MG" / "diretrizes.pdf").write_bytes(b"%PDF-1.4")
        r = SP.local_copy(LINK, libraries=[], folders=[od])
        self.assertEqual((r["metodo"], r["caminho"]), ("atalho_onedrive", od / "Qualidade" / "MG" / "diretrizes.pdf"))
        od2 = self.dir / "OneDrive2"
        (od2 / "Qualidade" / "MG").mkdir(parents=True)
        (od2 / "Qualidade" / "MG" / "diretrizes.pdf").write_bytes(b"%PDF-1.4")
        r = SP.local_copy(LINK, libraries=[], folders=[od, od2])
        self.assertIsNone(r["caminho"])  # two possible copies: never guess
        self.assertIn("mais de uma", r["motivo"])
        (self.dir / "solto.pdf").write_bytes(b"%PDF-1.4")
        r = SP.local_copy(HOST + "/:b:/r/sites/Portal/Docs/A/solto.pdf", libraries=[], folders=[self.dir])
        self.assertIsNone(r["caminho"])  # a file name alone is not enough: at least one folder must match

    def test_sharing_link_has_no_path(self):
        r = SP.local_copy(HOST + "/:x:/s/Portal/EabcDEF123?e=xyz", libraries=[], folders=[self.dir])
        self.assertIsNone(r["caminho"])
        self.assertIn("compartilhamento", r["motivo"])


class ManifestSharePointTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.src = self.dir / "src"
        self.src.mkdir()
        self.run = self.dir / "run"
        FX.ice_xlsx(self.src / "ice.xlsx")
        self.mount = self.dir / "Portal - Documentos"
        (self.mount / "Qualidade" / "MG").mkdir(parents=True)
        FX.orientations_pdf(self.mount / "Qualidade" / "MG" / "diretrizes.pdf")
        self.libs = [(HOST + "/sites/Portal/Documentos Compartilhados/", str(self.mount))]

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, entries, libs):
        m = {"schema_version": "1.0", "solicitacao_id": "SINT-SP", "uf": "MG", "ano": 2026, "modelo": "9h", "modalidade": "propedeutico",
             "entradas": {c: entries.get(c) or [{"uri": "ice.xlsx"}] for c in SR.CLASSES}}
        p = self.src / "manifesto.json"
        p.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        with mock.patch.object(SP, "synced_libraries", return_value=libs), mock.patch.object(SP, "onedrive_folders", return_value=[]):
            return RUN.start_run(p, self.run)

    def test_link_read_from_synced_copy(self):
        inv = self.start({"orientacoes_estaduais": [{"uri": LINK}]}, self.libs)
        doc = next(f for f in inv["fontes"] if "orientacoes_estaduais" in f["classes"])
        self.assertEqual(doc["uri"], LINK)  # the origin stays the SharePoint link
        self.assertEqual(doc["nome"], "diretrizes.pdf")
        self.assertEqual(doc["status_leitura"], "lida")
        self.assertIsNotNone(doc["sha256"])

    def test_folder_link_is_expanded(self):
        folder = HOST + "/sites/Portal/Documentos%20Compartilhados/Forms/AllItems.aspx?id=%2Fsites%2FPortal%2FDocumentos%20Compartilhados%2FQualidade"
        inv = self.start({"orientacoes_estaduais": [{"uri": folder}]}, self.libs)
        names = [f["nome"] for f in inv["fontes"] if "orientacoes_estaduais" in f["classes"]]
        self.assertEqual(names, ["diretrizes.pdf"])

    def test_link_without_copy_is_pending_not_downloaded(self):
        inv = self.start({"orientacoes_estaduais": [{"uri": LINK}]}, [])
        doc = next(f for f in inv["fontes"] if "orientacoes_estaduais" in f["classes"])
        self.assertEqual([p["codigo"] for p in doc["pendencias"]], ["FONTE_AUSENTE"])
        self.assertIsNone(doc["sha256"])

    def test_explicit_local_copy(self):
        FX.orientations_pdf(self.src / "baixado.pdf")
        inv = self.start({"orientacoes_estaduais": [{"uri": LINK, "copia_local": "baixado.pdf"}]}, [])
        doc = next(f for f in inv["fontes"] if "orientacoes_estaduais" in f["classes"])
        self.assertEqual((doc["uri"], doc["nome"], doc["status_leitura"]), (LINK, "baixado.pdf", "lida"))

    def test_local_copy_only_for_sharepoint(self):
        with self.assertRaises(SR.ManifestError) as e:
            self.start({"orientacoes_estaduais": [{"uri": "ice.xlsx", "copia_local": "x.pdf"}]}, [])
        self.assertEqual(e.exception.code, "MANIFESTO_INVALIDO")


if __name__ == "__main__":
    unittest.main()
