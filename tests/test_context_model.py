"""Shared compiler snapshots and strict structured request validation."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from pydantic import ValidationError

from rpa_docs.context_model import (
    DiscoveryContextDraft, DiscoveryContexto, ENTREGAVEIS_SUGERIDOS,
    LABELS, compile_guide, suggest_deliverables,
)
from rpa_docs.schemas import DriveImport, JobCreate, PromptSuggestion


FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "context_snapshots.json").read_text(encoding="utf-8"))


class ContextModelTests(unittest.TestCase):
    def context(self):
        return deepcopy(FIXTURES[0]["contexto"])

    def test_four_shared_exact_snapshots(self):
        for case in FIXTURES:
            with self.subTest(case=case["name"]):
                self.assertEqual(compile_guide(case["contexto"]), case["guide"])

    def test_source_names_and_placeholders_are_never_injected(self):
        for case in FIXTURES:
            result = compile_guide({**case["contexto"], "sources": ["meeting.mp4", "screen.mov", "review.webm"]})
            for forbidden in (".mp4", ".mov", ".webm", "Processo operacional"):
                self.assertNotIn(forbidden, result)

    def test_empty_optional_fields_omit_their_whole_lines(self):
        context = self.context()
        context.update(objetivo="  ", sistemas=[], instrucoesExtras="", publico=[], etapaDestino=None, entregaveis=[])
        result = compile_guide(context)
        for omitted in ("Por que está sendo mapeado:", "Sistemas citados:", "Instruções adicionais:", "Quem vai ler:", "Este material alimenta", "O que a análise precisa entregar:"):
            self.assertNotIn(omitted, result)

    def test_partial_compiler_does_not_invent_a_process(self):
        result = compile_guide({})
        self.assertNotIn('sobre ""', result)
        self.assertNotIn("Cliente:", result)
        self.assertIn("Regras de evidência:", result)

    def test_shared_suggestion_matrix_has_exact_declared_bases(self):
        expected = {
            "desenho": ["fluxo_atual", "sistemas_telas", "volume_tempo", "dores", "oportunidades", "perguntas_abertas"],
            "doc_tecnica": ["fluxo_atual", "sistemas_telas", "campos_io", "regras_excecoes", "volume_tempo", "perguntas_abertas"],
            "spec_rpa": ["fluxo_atual", "sistemas_telas", "campos_io", "regras_excecoes", "prints_por_tela", "perguntas_abertas"],
        }
        self.assertEqual(ENTREGAVEIS_SUGERIDOS["base"], expected)
        self.assertEqual(ENTREGAVEIS_SUGERIDOS["extra"], {"rpa": ["campos_io", "prints_por_tela"], "ia": ["regras_excecoes"], "integracao": ["campos_io", "sistemas_telas"], "flow": ["fluxo_atual", "regras_excecoes"], "indefinido": ["oportunidades"]})

    def test_every_suggestion_is_ordered_union_without_duplicates(self):
        for stage, base in ENTREGAVEIS_SUGERIDOS["base"].items():
            for solution, extra in ENTREGAVEIS_SUGERIDOS["extra"].items():
                with self.subTest(stage=stage, solution=solution):
                    expected = [key for key in LABELS["entregaveis"] if key in set(base + extra)]
                    self.assertEqual(suggest_deliverables({"etapaDestino": stage, "solucoes": [solution]}), expected)

    def test_no_stage_no_suggestions_even_with_solution(self):
        self.assertEqual(suggest_deliverables({"solucoes": ["rpa"]}), [])

    def test_full_model_requires_every_required_context_field(self):
        for field in ("cliente", "processo", "solucoes", "etapaDestino", "publico", "entregaveis"):
            with self.subTest(field=field):
                context = self.context()
                del context[field]
                with self.assertRaises(ValidationError):
                    DiscoveryContexto.model_validate(context)

    def test_whitespace_required_names_and_empty_required_lists_rejected(self):
        for field, value in (("cliente", "  "), ("processo", "\n"), ("solucoes", []), ("publico", []), ("entregaveis", []), ("etapaDestino", None)):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                DiscoveryContexto.model_validate({**self.context(), field: value})

    def test_other_audience_requires_text(self):
        with self.assertRaises(ValidationError):
            DiscoveryContexto.model_validate({**self.context(), "publico": ["outro"], "publicoOutro": " "})
        result = DiscoveryContexto.model_validate({**self.context(), "publico": ["outro"], "publicoOutro": "Operações"})
        self.assertIn("Quem vai ler: Operações.", result.guia)

    def test_unknown_ids_duplicates_and_exclusive_undefined_rejected(self):
        for field, value in (("solucoes", ["unknown"]), ("solucoes", ["rpa", "rpa"]), ("solucoes", ["indefinido", "rpa"]), ("publico", ["admin"]), ("entregaveis", ["everything"]), ("etapaDestino", "outro")):
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                DiscoveryContexto.model_validate({**self.context(), field: value})

    def test_all_text_limits_are_enforced(self):
        for field, limit in (("cliente", 80), ("processo", 100), ("objetivo", 400), ("publicoOutro", 60), ("instrucoesExtras", 1500)):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                DiscoveryContexto.model_validate({**self.context(), field: "a" * (limit + 1)})

    def test_tags_enforce_count_size_nonempty_and_uniqueness(self):
        for systems in ([str(index) for index in range(16)], [" "], ["x" * 81], ["Excel", "excel"], [2]):
            with self.subTest(systems=systems), self.assertRaises(ValidationError):
                DiscoveryContexto.model_validate({**self.context(), "sistemas": systems})

    def test_tags_and_names_trim_whitespace(self):
        result = DiscoveryContexto.model_validate({**self.context(), "cliente": "  Trevo  ", "sistemas": [" Excel "]})
        self.assertEqual(result.cliente, "Trevo")
        self.assertEqual(result.sistemas, ["Excel"])

    def test_flags_are_strict_booleans(self):
        for flag in ("guiaEditado", "dadosSensiveis", "entregaveisTocado", "etapaDestinoTocado"):
            with self.subTest(flag=flag), self.assertRaises(ValidationError):
                DiscoveryContexto.model_validate({**self.context(), flag: "false"})

    def test_unedited_client_guide_is_ignored_including_oversized_or_invalid_text(self):
        for supplied in ("INJECTED GUIDE", "a" * 9000, {"forged": True}, None):
            result = DiscoveryContexto.model_validate({**self.context(), "guia": supplied, "guiaEditado": False})
            self.assertEqual(result.guia, FIXTURES[0]["guide"])

    def test_manual_guide_preserved_and_not_overwritten(self):
        result = DiscoveryContexto.model_validate({**self.context(), "guiaEditado": True, "guia": "Meu guia personalizado."})
        self.assertEqual(result.guia, "Meu guia personalizado.")

    def test_manual_guide_cannot_be_empty_or_too_long(self):
        for guide in ("", "  ", "x" * 8001):
            with self.subTest(length=len(guide)), self.assertRaises(ValidationError):
                DiscoveryContexto.model_validate({**self.context(), "guiaEditado": True, "guia": guide})

    def test_sensitive_rule_is_opt_in(self):
        plain = DiscoveryContexto.model_validate(self.context())
        sensitive = DiscoveryContexto.model_validate({**self.context(), "dadosSensiveis": True})
        self.assertNotIn("[CPF]", plain.guia)
        for marker in ("[CPF]", "[NOME]", "[DADO DE SAÚDE]", "[VALOR]"):
            self.assertIn(marker, sensitive.guia)

    def test_unknown_context_fields_rejected(self):
        with self.assertRaises(ValidationError):
            DiscoveryContexto.model_validate({**self.context(), "sources": ["private.mp4"]})

    def test_draft_allows_incomplete_form_for_ai(self):
        draft = DiscoveryContextDraft(cliente="Trevo", processo="Pedidos")
        self.assertIsNone(draft.etapaDestino)
        self.assertEqual(draft.publico, [])
        self.assertIn('sobre "Pedidos"', draft.guia)
        result = PromptSuggestion(contexto={"cliente": "Trevo", "processo": "Pedidos"})
        self.assertEqual(result.title, "Pedidos")
        self.assertEqual(result.process_context, result.contexto.guia)

    def test_structured_jobs_derive_legacy_fields_from_authoritative_context(self):
        for schema, source in ((JobCreate, {"source_path": "video.mp4"}), (DriveImport, {"file_ids": ["drive-id"]})):
            with self.subTest(schema=schema.__name__):
                result = schema(**source, contexto=self.context(), title="FORGED", audience="FORGED", process_context="FORGED", detail_level="detalhado")
                self.assertEqual(result.title, "Gestão de pedidos")
                self.assertEqual(result.process_context, FIXTURES[0]["guide"])
                self.assertEqual(result.audience, "Equipe de RPA")
                self.assertEqual(result.detail_level, "operacional")
                self.assertIsInstance(result.model_dump()["contexto"], dict)

    def test_stage_maps_to_existing_pipeline_levels(self):
        for stage, expected in (("desenho", "resumido"), ("doc_tecnica", "operacional"), ("spec_rpa", "operacional")):
            result = JobCreate(source_path="video.mp4", contexto={**self.context(), "etapaDestino": stage})
            self.assertEqual(result.detail_level, expected)

    def test_legacy_requests_unchanged_without_context(self):
        result = JobCreate(title="Aula", source_path="video.mp4", process_context="Meu guia", audience="Turma", detail_level="detalhado")
        self.assertIsNone(result.contexto)
        self.assertEqual((result.title, result.process_context, result.audience, result.detail_level), ("Aula", "Meu guia", "Turma", "detalhado"))
        with self.assertRaises(ValidationError):
            JobCreate(title="a", source_path="video.mp4")

    def test_one_character_structured_process_is_valid_and_never_concatenates_client(self):
        result = JobCreate(source_path="video.mp4", contexto={**self.context(), "processo": "X"})
        self.assertEqual(result.title, "X")

    def test_browser_manual_touch_flags_survive_serialization(self):
        result = DiscoveryContexto.model_validate({**self.context(), "etapaDestinoTocado": True, "entregaveisTocado": True})
        self.assertTrue(result.model_dump()["etapaDestinoTocado"])
        self.assertTrue(result.model_dump()["entregaveisTocado"])


if __name__ == "__main__":
    unittest.main()
