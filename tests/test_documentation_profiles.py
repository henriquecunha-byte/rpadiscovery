"""Offline profile contracts and real document exports; no AI calls."""
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from docx import Document
from pydantic import ValidationError
from rpa_docs.context_model import DiscoveryContexto, LABELS, compile_guide, suggest_deliverables
from rpa_docs.documentation_profiles import PROFILES, document_catalog, fallback_general, normalize_general
from rpa_docs.schemas import JobCreate, DriveImport, PromptSuggestion
from rpa_docs.pipeline import create_package, synthesize_documentation, write_report

ROOT = Path(__file__).resolve().parents[1]


def profile_context(profile):
    return {"perfil": profile, "processo": "Planejamento de comunicação", "objetivo": "Documentar as decisões",
            "publico": ["equipe"], "entregaveis": PROFILES[profile]["suggestions"], "detalhamento": "detalhado"}


def sample_document(job):
    document = fallback_general(job)
    document.update(executive_summary="Foi aprovada a campanha de comunicação.", objective="Organizar o lançamento.", limitations=[])
    for section in document["sections"]:
        section["items"] = [{"title": "Campanha aprovada", "text": "A equipe aprovou a campanha e deixou a data para validação.", "timecode": "00:00:05", "evidence_refs": []}]
    document["preview_moments"] = [{"start": 5, "end": 10, "title": "Campanha", "reason": "Assunto solicitado"}]
    return document


class ProfileTests(unittest.TestCase):
    def test_all_available_audiences_fit_each_request_contract(self):
        context = {**profile_context("personalizado"), "publico": list(LABELS["publico"]), "publicoOutro": "X" * 60}
        for schema, extras in ((JobCreate, {"source_path": "synthetic.mp4"}),
                               (DriveImport, {"file_ids": ["synthetic"]}), (PromptSuggestion, {})):
            with self.subTest(schema=schema.__name__):
                request = schema(contexto=context, **extras)
                self.assertGreater(len(request.audience), 160)
                self.assertIn("X" * 60, request.audience)

    def test_general_profiles_accept_no_client_solution_or_stage(self):
        for profile in PROFILES:
            if profile == "processo":
                continue
            with self.subTest(profile=profile):
                context = DiscoveryContexto.model_validate(profile_context(profile))
                self.assertEqual(context.cliente, "")
                job = JobCreate(contexto=context, source_path="synthetic.mp4").model_dump()
                self.assertEqual(job["detail_level"], "detalhado")
                self.assertNotIn("Solução em vista", job["process_context"])
                self.assertNotIn("potencial de automação", job["process_context"])

    def test_legacy_contract_still_requires_client_solution_stage(self):
        with self.assertRaises(ValidationError):
            DiscoveryContexto.model_validate({"processo": "Pedidos", "publico": ["rpa"], "entregaveis": ["fluxo_atual"]})

    def test_profile_and_deliverable_mismatch_is_rejected(self):
        for delta in ({"perfil": "inventado"}, {"entregaveis": ["campos_io"]}, {"entregaveis": ["achados"]}):
            with self.subTest(delta=delta), self.assertRaises(ValidationError):
                DiscoveryContexto.model_validate({**profile_context("reuniao"), **delta})

    def test_js_and_python_compile_identical_guides_for_every_profile(self):
        contexts = []
        for profile in PROFILES:
            if profile == "processo":
                continue
            context = {**profile_context(profile), "sistemas": ["CRM", "Marca"], "dadosSensiveis": True,
                       "instrucoesExtras": "Preserve as dúvidas; não atribua falas por nome.", "cliente": "Marketing"}
            contexts.append(context)
        script = "const m=require('./rpa_docs/static/context-model.js');const c=JSON.parse(require('fs').readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(c.map(x=>[m.compileGuide(x),m.suggestDeliverables(x)])));"
        response = subprocess.run(["node", "-e", script], cwd=ROOT, input=json.dumps(contexts), capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertEqual(json.loads(response.stdout), [[compile_guide(context), suggest_deliverables(context)] for context in contexts])

    def test_manual_guide_is_preserved_and_general_fields_are_authoritative(self):
        context = {**profile_context("pesquisa"), "guiaEditado": True, "guia": "Observe apenas dúvidas sobre a campanha."}
        job = JobCreate(contexto=context, source_path="synthetic.mp4", title="Ignored", audience="RPA").model_dump()
        self.assertEqual(job["process_context"], context["guia"])
        self.assertEqual(job["contexto"]["perfil"], "pesquisa")
        self.assertEqual(job["audience"], "Equipe")

    def test_general_synthesis_contract_and_response_are_not_process_shaped(self):
        for profile in PROFILES:
            if profile == "processo":
                continue
            job = JobCreate(contexto=profile_context(profile), source_path="synthetic.mp4").model_dump()
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as directory, patch("rpa_docs.pipeline.OpenAI") as client:
                client.return_value.responses.create.return_value = SimpleNamespace(output_text=json.dumps(sample_document(job)))
                result = synthesize_documentation(job, [], [{"start": 5, "end": 10, "text": "A campanha está aprovada."}], Path(directory))
                prompt = client.return_value.responses.create.call_args.kwargs["input"]
                contract = json.loads(prompt.split("Retorne JSON puro exatamente com esta estrutura:")[1])
                self.assertEqual(contract["profile"], profile)
                self.assertNotIn("process_flow", contract)
                self.assertNotIn("automation_opportunities", result)
                self.assertEqual(result["sections"][0]["items"][0]["text"], "A equipe aprovou a campanha e deixou a data para validação.")

    def test_bad_provider_schema_falls_back_honestly(self):
        job = JobCreate(contexto=profile_context("reuniao"), source_path="synthetic.mp4").model_dump()
        with tempfile.TemporaryDirectory() as directory, patch("rpa_docs.pipeline.OpenAI") as client:
            client.return_value.responses.create.return_value = SimpleNamespace(output_text='{"process_flow": []}')
            result = synthesize_documentation(job, [], [], Path(directory))
            self.assertTrue((Path(directory) / "documentacao-aviso.txt").exists())
            self.assertEqual(result["preview_moments"], [])
            self.assertNotIn("process_flow", result)

    def test_normalization_removes_unrequested_sections_and_invalid_evidence(self):
        job = JobCreate(contexto=profile_context("reuniao"), source_path="synthetic.mp4").model_dump()
        document = sample_document(job)
        document["sections"][0]["items"][0].update(evidence_refs=[1, 999, 1], timecode="not-a-time")
        document["sections"].append({"id": "automation_opportunities", "items": [{"text": "invented"}]})
        result = normalize_general(document, job, [{"frame_index": 1}])
        self.assertEqual(result["sections"][0]["items"][0]["evidence_refs"], [1])
        self.assertEqual(result["sections"][0]["items"][0]["timecode"], "")
        self.assertNotIn("invented", json.dumps(result))

    def test_exports_for_every_general_profile_and_zip_excludes_legacy_artifacts(self):
        for profile in PROFILES:
            if profile == "processo":
                continue
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                job = JobCreate(contexto=profile_context(profile), source_path="synthetic.mp4").model_dump()
                job["title"] = '<script>alert("qa")</script> Campanha'
                document = sample_document(job)
                write_report(job, [], workspace, Path("synthetic.mp4"), document, [])
                html = (workspace / "relatorio.html").read_text(encoding="utf-8")
                self.assertNotIn('<script>alert("qa")', html)
                self.assertIn("Campanha aprovada", html)
                self.assertNotIn("REQUISITOS PARA RPA", html)
                self.assertNotIn("requisitos-rpa.md", html)
                word = Document(workspace / "documentacao.docx")
                self.assertEqual(word.core_properties.subject, PROFILES[profile]["document"])
                self.assertTrue(any("Campanha aprovada" in paragraph.text for paragraph in word.paragraphs))
                self.assertTrue((workspace / "documentacao.pdf").read_bytes().startswith(b"%PDF"))
                self.assertFalse((workspace / "requisitos-rpa.md").exists())
                self.assertIn("Guia recebido", (workspace / PROFILES[profile]["filename"]).read_text(encoding="utf-8"))
                (workspace / "requisitos-rpa.md").write_text("old stale output", encoding="utf-8")
                (workspace / "documentacao-processo.docx").write_text("old stale output", encoding="utf-8")
                create_package(workspace)
                with zipfile.ZipFile(workspace / "entrega-completa.zip") as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertIn(PROFILES[profile]["filename"], archive.namelist())
                    self.assertIn("documentacao.docx", archive.namelist())
                    self.assertNotIn("requisitos-rpa.md", archive.namelist())
                    self.assertNotIn("documentacao-processo.docx", archive.namelist())


if __name__ == "__main__":
    unittest.main()
