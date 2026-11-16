"""Testes dos contratos estruturados, sem dados reais do Instituto."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QROOT = ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"
sys.path.insert(0, str(QROOT))
import quality_structured as s
import quality_payload as q


def sample(aba):
    schema = s.schema_for(aba)
    fields = schema["properties"]["linhas"].get("items", {}).get("properties", {})
    row = {}
    for key, spec in fields.items():
        typ = spec.get("type")
        if "const" in spec:
            value = spec["const"]
        elif key == "UF":
            value = "MG"
        elif key == "Ano":
            value = 2026
        elif key == "Modelo":
            value = "9h"
        elif key == "CicloID":
            value = "MG|2026|9h|v1"
        elif key == "Tipo":
            value = "Pedagógica"
        elif key == "Presenca":
            value = "Sim"
        elif key in ("RegistroID", "ResumoID", "DocumentoID"):
            value = "MG-" + key + "-1"
        elif isinstance(typ, list):
            value = None
        elif typ == "null":
            value = None
        elif typ == "integer":
            value = 2026 if key == "Ano" else 1
        elif typ == "number":
            value = 4.0
        elif typ == "string":
            value = "teste"
        else:
            raise AssertionError((aba, key, spec))
        row[key] = value
    return {"aba": aba, "modo": schema["properties"]["modo"]["const"],
            "linhas": [row] if aba in s.WRITE_ABAS else [],
            "pendencias": [], "fontes": [{"arquivo": "origem.pdf", "localizador": "p. 2"}],
            "checagens": ["Fonte identificada."]}


class StructuredOutputTest(unittest.TestCase):
    def test_all_eleven(self):
        self.assertEqual(len(s.ALL_ABAS), 11)
        for aba in s.ALL_ABAS:
            with self.subTest(aba=aba):
                result = s.check_response(sample(aba))
                self.assertTrue(result["valido"], result)
                schema = s.schema_for(aba)
                self.assertEqual(set(schema["required"]), set(schema["properties"]))

    def test_five_data_schemas_match_excel(self):
        for aba in s.WRITE_ABAS:
            self.assertEqual(list(s.schema_for(aba)["properties"]["linhas"]["items"]["properties"]),
                             q.SCHEMA[aba])

    def test_missing_and_extra_fields(self):
        doc = sample("SG_Ciclos")
        del doc["linhas"][0]["UF"]
        self.assertFalse(s.check_response(doc)["valido"])
        doc = sample("SG_Ciclos")
        doc["linhas"][0]["CampoInventado"] = True
        self.assertFalse(s.check_response(doc)["valido"])

    def test_types_and_publication(self):
        for invalid_year in (True, "2026", 2026.4):
            doc = sample("SG_Ciclos")
            doc["linhas"][0]["Ano"] = invalid_year
            self.assertFalse(s.check_response(doc)["valido"])
        doc = sample("SG_Ciclos")
        doc["linhas"][0]["Publicado"] = "Sim"
        self.assertFalse(s.check_response(doc)["valido"])

    def test_sentinels(self):
        doc = sample("SG_Avaliacoes")
        doc["linhas"][0]["Presenca"] = None
        self.assertTrue(s.check_response(doc)["valido"])
        doc["linhas"][0]["Presenca"] = "Não avaliado"
        self.assertFalse(s.check_response(doc)["valido"])
        doc = sample("SG_Avaliacoes")
        doc["linhas"][0]["Aprovador"] = "Claude"
        self.assertFalse(s.check_response(doc)["valido"])

    def test_nullable_document_reference(self):
        doc = sample("SG_Avaliacoes")
        doc["linhas"][0]["DocumentoID"] = None
        self.assertTrue(s.check_response(doc)["valido"], s.check_response(doc))
        doc["linhas"][0]["DocumentoID"] = "  "
        self.assertFalse(s.check_response(doc)["valido"])
        doc = sample("SG_Documentos")
        doc["linhas"][0]["DocumentoID"] = None
        self.assertFalse(s.check_response(doc)["valido"])

    def test_fontes_survive_prepare(self):
        with tempfile.TemporaryDirectory() as tmp:
            answers = Path(tmp) / "respostas"
            answers.mkdir()
            for aba in s.WRITE_ABAS:
                (answers / (aba + ".json")).write_text(
                    json.dumps({"structured_output": sample(aba)}, ensure_ascii=False), encoding="utf-8")
            lote = Path(tmp) / "lote.json"
            lote.write_text(json.dumps(s.assemble_responses(answers, "MG", 2026, "9h", "v1"), ensure_ascii=False),
                            encoding="utf-8")
            bundle = q.parse_bundle(lote)
            self.assertEqual(len(bundle["fontes"]), len(s.WRITE_ABAS))
            q.write_staging(bundle, Path(tmp) / "staging")
            staged = json.loads((Path(tmp) / "staging" / "lote-validado.json").read_text(encoding="utf-8"))
            self.assertEqual(staged["fontes"][0]["arquivo"], "origem.pdf")

    def test_reference_and_approval_readonly(self):
        for aba in s.READ_ABAS:
            doc = sample(aba)
            doc["linhas"] = [{}]
            self.assertFalse(s.check_response(doc)["valido"])

    def test_cli_wrapper_without_structured_output(self):
        self.assertFalse(s.check_response({"type": "result", "result": "texto em Markdown"})["valido"])
        self.assertTrue(s.check_response({"structured_output": sample("SG_Ciclos")})["valido"])

    def test_cross_model_id(self):
        doc = sample("SG_Componentes")
        doc["linhas"][0]["CicloID"] = "MG|2026|7h|v1"
        self.assertFalse(s.check_response(doc)["valido"])

    def test_assemble_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            for aba in s.WRITE_ABAS:
                (Path(tmp) / (aba + ".json")).write_text(
                    json.dumps({"structured_output": sample(aba)}, ensure_ascii=False), encoding="utf-8")
            bundle = s.assemble_responses(Path(tmp), "MG", 2026, "9h", "v1")
            self.assertTrue(q.validate(bundle)["valido"], q.validate(bundle))

    def test_assemble_without_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Falta resposta"):
                s.assemble_responses(Path(tmp), "MG", 2026, "9h", "v1")

    def test_schema_cli(self):
        c = subprocess.run([sys.executable, str(QROOT / "quality_payload.py"),
                            "esquema", "--aba", "SG_Ciclos"], text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(c.stdout)["properties"]["aba"]["const"], "SG_Ciclos")


if __name__ == "__main__":
    unittest.main()
