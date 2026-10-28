"""No real provider, media analysis, or credentials are used in these tests."""
import builtins
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx
from openai import APIConnectionError, APIError, APITimeoutError, AuthenticationError, RateLimitError

from rpa_docs.context_model import compile_guide
from rpa_docs.database import Database
from rpa_docs.errors import PublicProcessingError, log_failure, public_failure
from rpa_docs.orchestrator import Orchestrator
from rpa_docs.pipeline import suggest_process_prompt, transcribe, write_docx_document, write_pdf_document


PRIVATE = "PRIVATE_SENTINEL bearer API_SECRET https://private.invalid/request"


class UnprintableError(Exception):
    def __str__(self):
        raise AssertionError("Private exception was rendered")

    def __repr__(self):
        raise AssertionError("Private exception was represented")


class SafeFailureTests(unittest.TestCase):
    def test_every_sdk_exception_has_identical_neutral_contract_and_minimal_logs(self):
        request = httpx.Request("POST", "https://private.invalid/responses", headers={"Authorization": PRIVATE})
        failures = (
            AuthenticationError(PRIVATE, response=httpx.Response(401, request=request), body={"key": PRIVATE}),
            RateLimitError(PRIVATE, response=httpx.Response(429, request=request), body={"request": PRIVATE}),
            APITimeoutError(request=request),
            APIConnectionError(message=PRIVATE, request=request),
            APIError(PRIVATE, request=request, body={"request": PRIVATE}),
            UnprintableError(),
        )
        for failure in failures:
            with self.subTest(type=type(failure).__name__), patch("rpa_docs.pipeline.create_client", side_effect=failure), self.assertLogs("rpa_docs.failures") as captured:
                result = suggest_process_prompt({"contexto": {"cliente": "Cliente", "processo": "Pedidos"}})
            self.assertEqual(result, {"ok": False, "code": "ai_unavailable"})
            self.assertEqual(len(captured.records), 1)
            record = captured.records[0]
            self.assertIsNone(record.exc_info)
            self.assertIsNone(record.stack_info)
            self.assertRegex(record.getMessage(), r"^operation=guide_improvement type=[A-Za-z]+ status=\d+$")
            self.assertNotIn("PRIVATE", record.getMessage())
            self.assertNotIn("private.invalid", record.getMessage())
            self.assertNotIn("API_SECRET", record.getMessage())

    def test_log_does_not_stringify_status_metadata(self):
        error = UnprintableError()
        error.status_code = UnprintableError()
        with self.assertLogs("rpa_docs.failures") as captured:
            log_failure("guide_improvement", error)
        self.assertEqual(captured.records[0].getMessage(), "operation=guide_improvement type=UnprintableError status=0")

    def test_provider_receives_only_structured_fields_and_current_guide(self):
        context = {"cliente": "Cliente", "processo": "Pedidos", "solucoes": ["ia", "integracao"],
                   "etapaDestino": "doc_tecnica", "publico": ["squad_ia"], "sistemas": ["Excel"],
                   "entregaveis": ["fluxo_atual"], "instrucoesExtras": "Não inclua faturamento.",
                   "sources": ["private-recording.mp4"], "source_path": "private-recording.mov"}
        guide = compile_guide(context)
        with patch("rpa_docs.pipeline.create_client") as client:
            client.return_value.responses.create.return_value = SimpleNamespace(output_text="Organize com clareza o processo de pedidos para a equipe técnica.")
            result = suggest_process_prompt({"contexto": context, "process_context": guide, "sources": ["secret.webm"]})
        messages = client.return_value.responses.create.call_args.kwargs["input"]
        self.assertEqual(messages[0]["role"], "system")
        payload = json.loads(messages[1]["content"])
        self.assertEqual(payload["guia_atual"], guide)
        self.assertEqual(payload["contexto"]["sistemas"], ["Excel"])
        self.assertNotIn("sources", payload["contexto"])
        self.assertNotIn("source_path", payload["contexto"])
        self.assertNotIn("recording.mp4", json.dumps(messages))
        self.assertNotIn("secret.webm", json.dumps(messages))
        self.assertTrue(result["ok"])
        for rule in guide[guide.index("Regras de corte:"):].splitlines():
            if rule.strip():
                self.assertIn(rule, result["prompt"])
        for instruction in ("Não invente sistemas, telas, campos, números", "Preserve integralmente", "Não atribua falas"):
            self.assertIn(instruction, messages[0]["content"])

    def test_partial_context_can_improve_without_destination_or_audience(self):
        with patch("rpa_docs.pipeline.create_client") as client:
            client.return_value.responses.create.return_value = SimpleNamespace(output_text="Analise o processo de pedidos do cliente conforme o conteúdo da reunião.")
            result = suggest_process_prompt({"contexto": {"cliente": "Cliente", "processo": "Pedidos"}})
        self.assertTrue(result["ok"])
        self.assertIn("Regras de evidência:", result["prompt"])

    def test_sensitive_data_rule_and_manual_exclusions_cannot_be_dropped_by_model(self):
        guide = "Não inclua faturamento. Preserve a decisão final, mesmo quando a tela mudar."
        context = {"cliente": "Cliente", "processo": "Pedidos", "dadosSensiveis": True, "guiaEditado": True}
        with patch("rpa_docs.pipeline.create_client") as client:
            client.return_value.responses.create.return_value = SimpleNamespace(output_text="Organize as informações sobre pedidos com objetividade e clareza.")
            result = suggest_process_prompt({"contexto": context, "process_context": guide})
        self.assertTrue(result["ok"])
        self.assertIn(guide, result["prompt"])
        for marker in ("[CPF]", "[NOME]", "[DADO DE SAÚDE]", "[VALOR]"):
            self.assertIn(marker, result["prompt"])

    def test_overlong_response_is_not_truncated_or_returned_as_success(self):
        with patch("rpa_docs.pipeline.create_client") as client:
            client.return_value.responses.create.return_value = SimpleNamespace(output_text="x" * 8000)
            result = suggest_process_prompt({"contexto": {"cliente": "Cliente", "processo": "Pedidos"}})
        self.assertEqual(result, {"ok": False, "code": "ai_unavailable"})

    def test_public_failure_uses_only_allowlisted_messages(self):
        self.assertIn("retomar", public_failure(UnprintableError()))
        self.assertIn("permissões", public_failure(PermissionError(PRIVATE)))
        self.assertIn("não está disponível", public_failure(FileNotFoundError(PRIVATE)))
        self.assertNotIn(PRIVATE, public_failure(PublicProcessingError(PRIVATE)))
        self.assertNotIn(PRIVATE, public_failure(RuntimeError(PRIVATE), operation=PRIVATE))

    def test_transcription_warning_does_not_persist_local_exception(self):
        fake_whisper = SimpleNamespace(WhisperModel=Mock(side_effect=UnprintableError()))
        with tempfile.TemporaryDirectory() as folder, patch.dict("sys.modules", {"faster_whisper": fake_whisper}):
            workspace = Path(folder)
            self.assertEqual(transcribe(workspace / "input.mp4", workspace), [])
            warning = (workspace / "transcricao-aviso.txt").read_text(encoding="utf-8")
        self.assertIn("Transcrição indisponível", warning)
        self.assertNotIn("UnprintableError", warning)

    def test_missing_export_dependency_never_reaches_downloadable_warning_as_raw_exception(self):
        original_import = builtins.__import__
        for function, module, artifact in (
            (write_docx_document, "docx", "documentacao-aviso.txt"),
            (write_pdf_document, "reportlab", "documentacao-pdf-aviso.txt"),
        ):
            def import_without_dependency(name, *args, **kwargs):
                if name == module or name.startswith(module + "."):
                    raise ImportError(PRIVATE)
                return original_import(name, *args, **kwargs)
            with self.subTest(module=module), tempfile.TemporaryDirectory() as folder, patch("builtins.__import__", side_effect=import_without_dependency):
                workspace = Path(folder)
                self.assertIsNone(function({}, {}, workspace))
                warning = (workspace / artifact).read_text(encoding="utf-8")
            self.assertIn("dependências", warning)
            self.assertNotIn(PRIVATE, warning)

    def test_worker_history_cannot_persist_private_failure_or_its_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            database = Database(root / "jobs.sqlite")
            database.create_job("sample", {"title": "Pedidos", "source_path": str(root / "input.mp4"), "process_context": "Contexto", "audience": "Equipe", "detail_level": "operacional", "api_approved": True, "api_budget_usd": 1})
            worker = Orchestrator(database)
            def fail(*_):
                worker.stop_event.set()
                raise UnprintableError()
            with patch("rpa_docs.orchestrator.JOBS_DIR", root / "jobs"), patch("rpa_docs.orchestrator.process", side_effect=fail):
                worker.loop()
            job = database.get_job("sample")
            self.assertEqual(job["status"], "FAILED")
            self.assertIn("retomar", job["error"])
            self.assertNotIn("UnprintableError", json.dumps(job))
            self.assertNotIn("Traceback", json.dumps(job))
            self.assertEqual(job["events"][-1]["message"], job["error"])


if __name__ == "__main__":
    unittest.main()
