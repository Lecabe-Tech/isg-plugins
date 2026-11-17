"""SPEC-017 G0: four-class manifest and versioned result schema (synthetic data only)."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QROOT = ROOT / "plugins" / "isg-model-alignment" / "scripts" / "quality"
sys.path.insert(0, str(QROOT))
import schema_check  # noqa: E402
import source_resolver as SR  # noqa: E402

EXAMPLE = ROOT / "examples" / "quality" / "manifesto_qualidade.example.json"


def manifest():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class ManifestContractTest(unittest.TestCase):
    def test_example_is_valid(self):
        m = SR.validate_manifest(manifest())
        self.assertEqual(m["modelo"], "9h")

    def test_rejects_missing_class(self):
        for cls in SR.CLASSES:
            with self.subTest(cls=cls):
                m = manifest()
                del m["entradas"][cls]
                with self.assertRaises(SR.ManifestError) as e:
                    SR.validate_manifest(m)
                self.assertEqual(e.exception.code, "CLASSE_AUSENTE")
                m = manifest()
                m["entradas"][cls] = []
                with self.assertRaises(SR.ManifestError) as e:
                    SR.validate_manifest(m)
                self.assertEqual(e.exception.code, "CLASSE_AUSENTE")

    def test_rejects_out_of_scope_model(self):
        for modelo, modalidade in (("7h", "propedeutico"), ("9h", "tecnico"), ("9h", "EJA"), (None, "propedeutico")):
            with self.subTest(modelo=modelo, modalidade=modalidade):
                m = manifest()
                m["modelo"], m["modalidade"] = modelo, modalidade
                with self.assertRaises(SR.ManifestError) as e:
                    SR.validate_manifest(m)
                self.assertEqual(e.exception.code, "MODELO_FORA_ESCOPO")

    def test_accepts_spelling_variants(self):
        m = manifest()
        m["modelo"], m["modalidade"] = "9 horas", "Propedêutico"
        self.assertEqual(SR.validate_manifest(m)["modalidade"], "propedeutico")

    def test_rejects_wrong_uf_and_year(self):
        m = manifest()
        m["uf"] = "XX"
        with self.assertRaises(SR.ManifestError) as e:
            SR.validate_manifest(m)
        self.assertEqual(e.exception.code, "UF_INVALIDA")
        for year in (2019, "2026", 2026.0):
            m = manifest()
            m["ano"] = year
            with self.assertRaises(SR.ManifestError) as e:
                SR.validate_manifest(m)
            self.assertEqual(e.exception.code, "MANIFESTO_INVALIDO")

    def test_rejects_unknown_fields_and_plain_http(self):
        m = manifest()
        m["entradas"]["outra_classe"] = [{"uri": "x.pdf"}]
        with self.assertRaises(SR.ManifestError):
            SR.validate_manifest(m)
        for uri in ("http://exemplo.invalid/matriz.pdf", "https://exemplo.invalid/matriz.pdf"):  # closed inputs: nothing from the internet
            m = manifest()
            m["entradas"]["matriz_estadual"][0]["uri"] = uri
            with self.assertRaises(SR.ManifestError) as e:
                SR.validate_manifest(m)
            self.assertEqual(e.exception.code, "ORIGEM_NAO_PERMITIDA")
        m = manifest()
        m["entradas"]["matriz_estadual"][0]["uri"] = "smb://servidor/matriz.pdf"
        with self.assertRaises(SR.ManifestError) as e:
            SR.validate_manifest(m)
        self.assertEqual(e.exception.code, "URI_NAO_PERMITIDA")

    def test_approval_records_need_author_and_date(self):
        m = manifest()
        m["homologacao_ice"] = {"versao": "v1", "aprovado_por": "", "data": "2026-11-16"}
        with self.assertRaises(SR.ManifestError):
            SR.validate_manifest(m)
        m["homologacao_ice"] = True  # a Boolean is not an approval record
        with self.assertRaises(SR.ManifestError):
            SR.validate_manifest(m)

    def test_multiple_matrix_candidates_are_allowed_in_the_manifest(self):
        m = manifest()
        m["entradas"]["matriz_estadual"].append({"uri": "matriz/Resolucao.pdf", "papel": "matriz"})
        self.assertEqual(len(SR.validate_manifest(m)["entradas"]["matriz_estadual"]), 2)


class ResultSchemaTest(unittest.TestCase):
    def test_schemas_are_draft07(self):
        for kind in schema_check.SCHEMAS:
            s = schema_check.load_schema(kind)
            self.assertEqual(s["$schema"], "http://json-schema.org/draft-07/schema#")
            self.assertNotIn("$defs", json.dumps(s))

    def test_validator_features(self):
        root = {"definitions": {"n": {"type": "integer", "minimum": 1}}, "type": "object", "additionalProperties": False,
                "required": ["a"], "properties": {"a": {"$ref": "#/definitions/n"}, "b": {"anyOf": [{"type": "null"}, {"type": "string", "minLength": 2}]},
                                                  "c": {"type": "array", "uniqueItems": True, "maxItems": 2}}}
        ok = schema_check._collect(root, root, {"a": 2, "b": None, "c": [1, 2]}, "$")
        self.assertEqual(ok, [])
        bad = schema_check._collect(root, root, {"a": 0, "b": "x", "c": [1, 1, 1], "d": 1}, "$")
        self.assertEqual(len(bad), 5, bad)
        self.assertTrue(schema_check._collect(root, root, {"a": True}, "$"))  # a boolean is not an integer

    def test_result_rejects_external_writes_and_fake_approval(self):
        s = schema_check.load_schema("resultado")
        self.assertEqual(s["properties"]["gravacoes_externas"]["maxItems"], 0)
        self.assertEqual(s["properties"]["revisao_humana"]["properties"]["necessaria"], {"const": True})
        self.assertEqual(s["properties"]["revisao_humana"]["properties"]["status"], {"enum": ["aguardando"]})
        self.assertEqual(s["definitions"]["orientacao"]["properties"]["presenca"]["enum"], ["Sim", "Não", None])
        self.assertNotIn("SG_", json.dumps(s))


if __name__ == "__main__":
    unittest.main()
