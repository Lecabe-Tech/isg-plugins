"""Testes sem dados do Instituto ou SharePoint."""
import json
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"))
import quality_payload as q  # noqa: E402

CICLO = {"CicloID": "XX|2026|9h|v1", "UF": "XX", "Ano": 2026, "Modelo": "9h",
         "Cluster": "Teste", "SituacaoOrigem": "Teste", "StatusValidacao": "Pendente revisão",
         "Publicado": "Não", "ResponsavelAprovacao": None, "ArquivoOrigem": "teste.xlsx"}


class QualityPayloadTest(unittest.TestCase):
    def test_missing_base(self):
        self.assertFalse(q.base_info(None)["configurada"])

    def test_remote_base_reference_does_not_write(self):
        r = q.base_info("https://exemplo.sharepoint.com/sites/qualidade/base.xlsx")
        self.assertEqual(r["tipo"], "url_sharepoint")
        self.assertFalse(r["verificada"])

    def test_reject_remote_http(self):
        with self.assertRaises(ValueError):
            q.base_info("http://exemplo/sharepoint/base.xlsx")

    def test_valid_cycle(self):
        r = q.validate({"lote": {"UF": "XX", "Ano": 2026, "Modelo": "9h"},
                        "abas": {"SG_Ciclos": [CICLO]}})
        self.assertTrue(r["valido"], r)

    def test_reject_published(self):
        r = q.validate({"abas": {"SG_Ciclos": [{**CICLO, "Publicado": "Sim"}]}})
        self.assertFalse(r["valido"])

    def test_reject_extra_fields(self):
        r = q.validate({"abas": {"SG_Ciclos": [{**CICLO, "Inventado": True}]}})
        self.assertFalse(r["valido"])

    def test_reject_child_without_cycle(self):
        child = {"RegistroID": "X-1", "CicloID": "XX|2026|9h|v1", "Publicado": "Não",
                 "StatusValidacao": "Importado - revisar"}
        r = q.validate({"abas": {"SG_Componentes": [child]}})
        self.assertFalse(r["valido"])

    def test_write_staging(self):
        bundle = {"lote": {}, "abas": {"SG_Ciclos": [CICLO]}, "pendencias": []}
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "staging"
            names = q.write_staging(bundle, dest)
            self.assertIn("SG_Ciclos.csv", names)
            self.assertIn("lote-validado.json", names)
            self.assertTrue((dest / "SG_Ciclos.csv").is_file())


if __name__ == "__main__":
    unittest.main()
