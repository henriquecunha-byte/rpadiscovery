"""Exercise real SDK serialization with synthetic HTTP; no cloud requests."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI as SDKClient

from rpa_docs import ai
from rpa_docs.errors import PublicProcessingError
from rpa_docs.pipeline import analyze, suggest_process_prompt, synthesize_documentation


class AIProviderTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AI_PROVIDER": "lovable", "LOVABLE_API_KEY": "qa-lovable-secret",
            "LOVABLE_MODEL": "openai/gpt-5.6-luna",
            "OPENAI_API_KEY": "qa-legacy-secret", "OPENAI_MODEL": "legacy-model",
            "OPENAI_BASE_URL": "https://do-not-use.invalid/v1",
            "OPENAI_ORG_ID": "legacy-org", "OPENAI_PROJECT_ID": "legacy-project",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.requests = []
        self.status = 200
        self.output = "Organize o conteúdo conforme o pedido e preserve as evidências verificáveis."
        self.factory = patch("rpa_docs.ai.OpenAI", side_effect=self.client)
        self.factory_mock = self.factory.start()
        self.addCleanup(self.factory.stop)

    def client(self, **kwargs):
        client = SDKClient(http_client=httpx.Client(transport=httpx.MockTransport(self.respond)), **kwargs)
        self.addCleanup(client.close)
        return client

    def respond(self, request):
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={"error": {"message": "PRIVATE_SENTINEL qa-lovable-secret"}})
        return httpx.Response(200, json={
            "id": "resp_qa", "object": "response", "created_at": 1,
            "model": "openai/gpt-5.6-luna", "status": "completed",
            "output": [{"type": "message", "id": "msg_qa", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": self.output, "annotations": []}]}],
        })

    def test_lovable_is_default_even_with_old_openai_key(self):
        os.environ.pop("AI_PROVIDER")
        config = ai.settings()
        self.assertEqual(config.provider, "lovable")
        self.assertEqual(config.model, "openai/gpt-5.6-luna")
        self.assertNotIn("secret", repr(config))
        self.assertTrue(ai.is_configured())

    def test_missing_lovable_key_does_not_use_openai_or_make_a_request(self):
        os.environ["LOVABLE_API_KEY"] = " "
        self.assertFalse(ai.is_configured())
        with self.assertRaises(PublicProcessingError) as captured:
            ai.create_client()
        self.assertEqual(captured.exception.code, "ai_configuration")
        self.factory_mock.assert_not_called()
        self.assertEqual(self.requests, [])

    def test_invalid_provider_fails_closed(self):
        for provider in ("", "typo", "https://do-not-use.invalid"):
            with self.subTest(provider=provider), patch.dict(os.environ, {"AI_PROVIDER": provider}):
                self.assertFalse(ai.is_configured())
                with self.assertRaises(PublicProcessingError):
                    ai.create_client()
        self.factory_mock.assert_not_called()

    def test_model_override_belongs_only_to_selected_provider(self):
        os.environ["LOVABLE_MODEL"] = "google/gemini-3-flash-preview"
        self.assertEqual(ai.model_name(), "google/gemini-3-flash-preview")
        os.environ["LOVABLE_MODEL"] = " "
        self.assertEqual(ai.model_name(), "openai/gpt-5.6-luna")
        os.environ["AI_PROVIDER"] = "openai"
        self.assertEqual(ai.model_name(), "legacy-model")

    def test_guide_uses_lovable_endpoint_and_preserves_message_roles(self):
        result = suggest_process_prompt({"process_context": "Registrar apenas o treinamento de atendimento."})
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        self.assertEqual(str(request.url), ai.LOVABLE_BASE_URL + "/responses")
        self.assertEqual(request.headers["authorization"], "Bearer qa-lovable-secret")
        self.assertEqual(request.headers["Lovable-API-Key"], "qa-lovable-secret")
        self.assertNotIn("legacy", str(request.headers))
        payload = json.loads(request.content)
        self.assertEqual(payload["model"], "openai/gpt-5.6-luna")
        self.assertEqual([m["role"] for m in payload["input"]], ["system", "user"])
        self.assertIn("treinamento", payload["input"][1]["content"])
        self.assertNotIn("secret", request.content.decode())

    def test_visual_request_preserves_image_and_adjacent_speech(self):
        self.output = '{"steps":[{"frame_index":1,"title":"Tela confirmada"}]}'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "evidence").mkdir()
            (root / "evidence" / "frame.jpg").write_bytes(b"synthetic-image")
            steps = analyze([{"image": "frame.jpg", "index": 1, "time": 4}],
                            [{"start": 0, "end": 8, "text": "Esta é a tela de cadastro."}],
                            root, "Documentar o treinamento", "operacional")
        self.assertEqual(steps[0]["title"], "Tela confirmada")
        content = json.loads(self.requests[0].content)["input"][0]["content"]
        self.assertIn("tela de cadastro", content[1]["text"])
        self.assertEqual(content[2]["type"], "input_image")
        self.assertTrue(content[2]["image_url"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(content[2]["detail"], "low")

    def test_document_synthesis_uses_gateway_and_retains_json_contract(self):
        self.output = '{"process_flow": [], "executive_summary":"Resumo verificado no teste"}'
        with tempfile.TemporaryDirectory() as directory:
            result = synthesize_documentation({"title": "Análise de teste"}, [], [], Path(directory))
        self.assertEqual(result["executive_summary"], "Resumo verificado no teste")
        self.assertEqual(str(self.requests[0].url), ai.LOVABLE_BASE_URL + "/responses")
        self.assertIsInstance(json.loads(self.requests[0].content)["input"], str)

    def test_http_failures_are_safe_and_do_not_retry_or_switch_provider(self):
        for status in (401, 402, 403, 429, 500):
            with self.subTest(status=status):
                self.status = status
                self.requests.clear()
                with self.assertLogs("rpa_docs.failures") as captured:
                    result = suggest_process_prompt({"title": "Teste"})
                self.assertEqual(result, {"ok": False, "code": "ai_unavailable"})
                self.assertEqual(len(self.requests), 1)
                self.assertEqual(self.requests[0].url.host, "ai.gateway.lovable.dev")
                self.assertNotIn("PRIVATE_SENTINEL", str(captured.output))
                self.assertNotIn("qa-lovable-secret", str(captured.output))

    def test_out_of_credits_warns_without_leaking_provider_body(self):
        self.status = 402
        with tempfile.TemporaryDirectory() as directory, self.assertLogs("rpa_docs.failures"):
            root = Path(directory)
            synthesize_documentation({"title": "Teste"}, [], [], root)
            warning = (root / "documentacao-aviso.txt").read_text(encoding="utf-8")
        self.assertIn("créditos", warning)
        self.assertNotIn("PRIVATE_SENTINEL", warning)
        self.assertNotIn("secret", warning)

    def test_explicit_openai_mode_never_sends_lovable_key(self):
        os.environ["AI_PROVIDER"] = "openai"
        result = suggest_process_prompt({"title": "Teste"})
        self.assertTrue(result["ok"])
        request = self.requests[0]
        self.assertEqual(str(request.url), ai.OPENAI_BASE_URL + "/responses")
        self.assertEqual(request.headers["authorization"], "Bearer qa-legacy-secret")
        self.assertNotIn("Lovable-API-Key", request.headers)
        self.assertEqual(json.loads(request.content)["model"], "legacy-model")

    def test_explicit_openai_without_key_does_not_use_lovable_key(self):
        os.environ.update(AI_PROVIDER="openai", OPENAI_API_KEY="")
        self.assertFalse(ai.is_configured())
        with self.assertRaises(PublicProcessingError):
            ai.create_client()
        self.factory_mock.assert_not_called()
