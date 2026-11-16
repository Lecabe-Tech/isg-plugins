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

    def test_schemas_accepted_by_claude_code(self):
        """`claude -p --json-schema` (Claude Code 2.1.x) rejects the draft 2020-12 declaration; keep draft-07 keywords only."""
        only_2020 = {"$defs", "prefixItems", "unevaluatedProperties", "unevaluatedItems", "dependentRequired",
                     "dependentSchemas", "$dynamicRef", "$dynamicAnchor", "minContains", "maxContains"}

        def keys(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    yield k
                    yield from keys(v)
            elif isinstance(node, list):
                for v in node:
                    yield from keys(v)

        for aba in s.ALL_ABAS:
            with self.subTest(aba=aba):
                schema = s.schema_for(aba)
                self.assertEqual(schema.get("$schema"), "http://json-schema.org/draft-07/schema#")
                self.assertFalse(only_2020 & set(keys(schema)))
                out = subprocess.run([sys.executable, str(QROOT / "quality_payload.py"), "esquema", "--aba", aba],
                                     capture_output=True, check=True)
                self.assertEqual(json.loads(out.stdout.decode("utf-8")), schema)

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

    def test_batch_records_and_checks_schema_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            answers = Path(tmp) / "respostas"
            answers.mkdir()
            for aba in s.WRITE_ABAS:
                (answers / (aba + ".json")).write_text(json.dumps(sample(aba), ensure_ascii=False), encoding="utf-8")
            bundle = s.assemble_responses(answers, "MG", 2026, "9h", "v1")
            self.assertEqual(set(bundle["contratos"]), set(s.WRITE_ABAS))
            self.assertEqual(bundle["contratos"]["SG_Ciclos"]["sha256"], s.schema_sha256("SG_Ciclos"))
            result = q.validate(bundle)
            self.assertTrue(result["valido"], result)
            self.assertEqual(result["contratos"], "conferidos")
            lote = Path(tmp) / "lote.json"
            lote.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            q.write_staging(q.parse_bundle(lote), Path(tmp) / "staging")
            staged = json.loads((Path(tmp) / "staging" / "lote-validado.json").read_text(encoding="utf-8"))
            self.assertEqual(staged["contratos"], bundle["contratos"])
            tampered = json.loads(json.dumps(bundle))
            tampered["contratos"]["SG_Avaliacoes"]["sha256"] = "0" * 64
            self.assertFalse(q.validate(tampered)["valido"])
            legacy = {k: v for k, v in bundle.items() if k != "contratos"}
            self.assertEqual(q.validate(legacy)["contratos"], "ausentes")

    def test_response_template_matches_schema(self):
        for aba in s.ALL_ABAS:
            with self.subTest(aba=aba):
                t = s.response_template(aba, "MG", 2026, "9h", "v1")
                schema = s.schema_for(aba)
                self.assertEqual(list(t), ["aba", "modo", "linhas", "pendencias", "fontes", "checagens"])
                self.assertEqual(t["modo"], schema["properties"]["modo"]["const"])
                if aba in s.READ_ABAS:
                    self.assertEqual(t["linhas"], [])
                    self.assertTrue(s.check_response(t)["valido"])
                    continue
                cols = list(schema["properties"]["linhas"]["items"]["properties"])
                self.assertEqual(list(t["linhas"][0]), cols)
                for col, spec in schema["properties"]["linhas"]["items"]["properties"].items():
                    if "const" in spec:
                        self.assertEqual(t["linhas"][0][col], spec["const"])
                if "CicloID" in cols:
                    self.assertEqual(t["linhas"][0]["CicloID"], "MG|2026|9h|v1")
                # a skeleton is not data: unfilled required fields must fail validation
                self.assertFalse(s.check_response(t)["valido"])
                # once the empty fields are filled, it validates
                filled = sample(aba)
                row = {k: (v if v is not None else filled["linhas"][0][k]) for k, v in t["linhas"][0].items()}
                t["linhas"] = [row]
                self.assertTrue(s.check_response(t)["valido"], s.check_response(t))

    def test_response_template_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "SG_Ciclos.json"
            args = [sys.executable, str(QROOT / "quality_payload.py"), "modelo-resposta", "--aba", "SG_Ciclos",
                    "--uf", "MG", "--ano", "2026", "--modelo", "9h", "--versao", "v1", "--saida", str(out), "--json"]
            r = subprocess.run(args, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["linhas"][0]["CicloID"], "MG|2026|9h|v1")
            again = subprocess.run(args, capture_output=True)
            self.assertEqual(again.returncode, 2)  # never overwrites an answer being filled
            bad = subprocess.run([sys.executable, str(QROOT / "quality_payload.py"), "modelo-resposta", "--aba", "SG_Ciclos",
                                  "--uf", "ZZ"], capture_output=True)
            self.assertEqual(bad.returncode, 2)

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
