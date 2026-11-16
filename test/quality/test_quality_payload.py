"""Testes sem dados do Instituto ou SharePoint."""
import json
import hashlib
import zipfile
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


    def _create_source_folders(self, home):
        docs = home / "estados"
        mg = docs / "MG" / "2026"
        mg.mkdir(parents=True)
        (mg / "curriculo.pdf").write_bytes("Documento sintético".encode("utf-8"))
        ice = home / "ice"
        ice.mkdir()
        workbook = ice / "ice_teste.xlsx"
        sheets = ["matriz_referencial_ICE", "orientações_referenciais_ICE", "orientações_modelo_gestão", "criterios_calculo"]
        xml = '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets>'
        for i, sheet in enumerate(sheets):
            xml += f'<sheet name="{sheet}" sheetId="{i+1}"/>'
        xml += '</sheets></workbook>'
        with zipfile.ZipFile(workbook, "w") as z:
            z.writestr("xl/workbook.xml", xml)
        digest = hashlib.sha256(workbook.read_bytes()).hexdigest()
        def entry(sheet):
            return {"arquivo": workbook.name, "aba": sheet, "sha256": digest}
        manifest = {"versao": "teste-local-2026", "aprovado": True, "aprovado_por": "teste",
                    "referencias": {
                        "matrizes": {"9h": entry(sheets[0])},
                        "orientacoes_pedagogicas": entry(sheets[1]),
                        "orientacoes_gestao": entry(sheets[2]),
                        "criterios": entry(sheets[3])}}
        (ice / "manifesto_ice.json").write_text(json.dumps(manifest), encoding="utf-8")
        return docs, ice

    def test_fontes_validas_9h(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs, ice = self._create_source_folders(Path(tmp))
            result = q.fontes_info(str(docs), str(ice), "MG", 2026, "9h")
            self.assertTrue(result["pronto_para_analisar"])
            self.assertEqual(result["documentos"], ["curriculo.pdf"])
            self.assertTrue(result["referencias"]["matriz"]["hash_conferido"])

    def test_fontes_sem_gabarito_7h_bloqueia(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs, ice = self._create_source_folders(Path(tmp))
            with self.assertRaisesRegex(ValueError, "7h"):
                q.fontes_info(str(docs), str(ice), "MG", 2026, "7h")

    def test_fontes_sem_aprovacao_bloqueia(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs, ice = self._create_source_folders(Path(tmp))
            path = ice / "manifesto_ice.json"
            cfg = json.loads(path.read_text(encoding="utf-8"))
            cfg["aprovado"] = False
            path.write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "aprovação"):
                q.fontes_info(str(docs), str(ice), "MG", 2026, "9h")

    def test_fontes_hash_divergente_bloqueia(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs, ice = self._create_source_folders(Path(tmp))
            path = ice / "manifesto_ice.json"
            cfg = json.loads(path.read_text(encoding="utf-8"))
            cfg["referencias"]["matrizes"]["9h"]["sha256"] = "0" * 64
            path.write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                q.fontes_info(str(docs), str(ice), "MG", 2026, "9h")

    def test_fontes_link_sharepoint_nao_e_pasta(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs, ice = self._create_source_folders(Path(tmp))
            with self.assertRaisesRegex(ValueError, "URL"):
                q.fontes_info("https://example.sharepoint.com/docs", str(ice), "MG", 2026, "9h")

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
