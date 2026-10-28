"""Auth preparation checks use private state, no worker and no provider network."""
import asyncio
import importlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from rpa_docs import config
from rpa_docs.auth import (
    AuthBoundaryMiddleware,
    AuthNotConfigured,
    AuthSettings,
    PendingSupabaseProvider,
    PUBLIC_AUTH_ENDPOINTS,
    SESSION_COOKIE,
)
from rpa_docs.database import Database


class AuthSettingsTests(unittest.TestCase):
    def test_default_is_explicitly_unprotected_local_mode(self):
        public = AuthSettings.from_environment({}).public_config()
        self.assertEqual(public, {
            "mode": "local", "provider": "supabase", "status": "not_configured",
            "enabled": False, "can_continue_local": True, "message": public["message"],
        })
        self.assertIn("sem proteção", public["message"])

    def test_invalid_values_fail_closed(self):
        for value in ("", " ", "false", "off", "LOCAL", "require", "invalid-secret-value"):
            with self.subTest(value=value):
                public = AuthSettings.from_environment({"AUTH_MODE": value}).public_config()
                self.assertEqual(public["mode"], "required")
                self.assertFalse(public["can_continue_local"])
                self.assertFalse(public["enabled"])
                self.assertIn("AUTH_MODE inválido", public["message"])
                self.assertNotIn("invalid-secret-value", public["message"])

    def test_environment_values_never_enable_authentication_or_leak(self):
        settings = AuthSettings.from_environment({
            "AUTH_MODE": "required",
            "SUPABASE_URL": "https://project-placeholder.invalid",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-sentinel",
            "SUPABASE_SERVICE_ROLE_KEY": "private-sentinel",
        })
        public = settings.public_config()
        self.assertEqual(public["status"], "integration_pending")
        self.assertFalse(public["enabled"])
        self.assertNotIn("sentinel", str(public))
        self.assertNotIn("project-placeholder", str(public))
        self.assertNotIn("sentinel", repr(settings))

    def test_incomplete_provider_settings_are_not_configured(self):
        for values in ({"SUPABASE_URL": "placeholder"}, {"SUPABASE_PUBLISHABLE_KEY": "placeholder"},
                       {"SUPABASE_URL": "placeholder", "SUPABASE_PUBLISHABLE_KEY": " "}):
            self.assertEqual(AuthSettings.from_environment(values).status, "not_configured")

    def test_pending_provider_rejects_all_operations(self):
        async def check():
            provider = PendingSupabaseProvider()
            for operation, args in (
                (provider.verify_access_token, ("forged-token",)),
                (provider.login, ("person@example.invalid", "password-sentinel")),
                (provider.recover, ("person@example.invalid",)),
                (provider.revoke_session, ("forged-token",)),
            ):
                with self.assertRaises(AuthNotConfigured) as caught:
                    await operation(*args)
                self.assertNotIn("sentinel", str(caught.exception))
                self.assertNotIn("forged-token", str(caught.exception))
        asyncio.run(check())

    def test_required_gate_does_not_read_request_body_or_dispatch(self):
        downstream, receive, send = AsyncMock(), AsyncMock(), AsyncMock()
        gate = AuthBoundaryMiddleware(downstream)
        with patch.dict(os.environ, {"AUTH_MODE": "required"}):
            asyncio.run(gate({"type": "http", "method": "POST", "path": "/api/jobs/upload"}, receive, send))
        downstream.assert_not_called()
        receive.assert_not_called()
        self.assertEqual(send.call_args_list[0].args[0]["status"], 503)


class AuthApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.import_workspace = tempfile.TemporaryDirectory()
        import_root = Path(cls.import_workspace.name)
        with patch.object(config, "DATABASE", import_root / "import.sqlite3"), patch.object(config, "JOBS_DIR", import_root / "jobs"):
            cls.api = importlib.import_module("rpa_docs.api")

    @classmethod
    def tearDownClass(cls):
        cls.import_workspace.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.jobs_root = self.root / "jobs"
        self.jobs_root.mkdir()
        self.database = Database(self.root / "test.sqlite3")
        self.patches = [
            patch.object(self.api, "db", self.database),
            patch.object(self.api, "JOBS_DIR", self.jobs_root),
            patch.dict(os.environ, {"AUTH_MODE": "local", "SUPABASE_URL": "", "SUPABASE_PUBLISHABLE_KEY": ""}),
        ]
        for item in self.patches:
            item.start()
        self.client = TestClient(self.api.app)

    def tearDown(self):
        self.client.close()
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def assert_unavailable(self, response):
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["code"], "auth_not_configured")
        self.assertIn("no-store", response.headers["cache-control"])

    def test_config_and_session_expose_only_prepared_contract(self):
        for mode in ("local", "required"):
            with self.subTest(mode=mode), patch.dict(os.environ, {"AUTH_MODE": mode}):
                response = self.client.get("/api/auth/config")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(set(response.json()), {"mode", "provider", "status", "enabled", "can_continue_local", "message"})
                self.assertFalse(response.json()["enabled"])
                self.assertEqual(response.json()["can_continue_local"], mode == "local")
                self.assertIn("no-store", response.headers["cache-control"])
                session = self.client.get("/api/auth/session")
                self.assertEqual(session.json(), {
                    "authenticated": False, "user": None, "mode": mode,
                    "provider": "supabase", "status": "not_configured",
                })
                self.assertNotIn("set-cookie", session.headers)

    def test_login_and_recovery_reject_before_parsing_any_body(self):
        with patch("starlette.requests.Request.body", side_effect=AssertionError("Body must not be read")):
            for mode in ("local", "required"):
                with patch.dict(os.environ, {"AUTH_MODE": mode}):
                    for endpoint in ("login", "recover"):
                        for content, media_type in (
                            (b'{"email":"person@example.invalid","password":"password-sentinel"}', "application/json"),
                            (b'{invalid JSON with password-sentinel', "application/json"),
                            (b'password=password-sentinel', "application/x-www-form-urlencoded"),
                            (b'password-sentinel', "multipart/form-data; boundary=missing"),
                            (b'', "application/json"),
                        ):
                            with self.subTest(mode=mode, endpoint=endpoint, media_type=media_type):
                                response = self.client.post(f"/api/auth/{endpoint}", content=content, headers={"Content-Type": media_type})
                                self.assert_unavailable(response)
                                self.assertNotIn("sentinel", response.text)
                                self.assertNotIn("person@example", response.text)
                                self.assertNotIn("set-cookie", response.headers)

    def test_required_mode_protects_every_existing_api_route(self):
        tested = set()
        with patch.dict(os.environ, {"AUTH_MODE": "required"}):
            for route in self.api.app.routes:
                path = getattr(route, "path", "")
                if not path.startswith("/api/"):
                    continue
                for method in route.methods:
                    if (method, path) in PUBLIC_AUTH_ENDPOINTS:
                        continue
                    target = path.replace("{job_id}", "sample").replace("{filename}", "test.mp4")
                    with self.subTest(method=method, target=target):
                        self.assert_unavailable(self.client.request(method, target, content=b'{}'))
                    tested.add(path)
        self.assertIn("/api/health", tested)
        self.assertIn("/api/jobs/upload", tested)
        self.assertIn("/api/jobs/{job_id}/package", tested)
        self.assertIn("/api/jobs/{job_id}/documentacao-processo.pdf", tested)
        self.assertIn("/api/jobs/{job_id}/drive", tested)
        self.assertEqual(self.database.list_jobs(), [])
        self.assertEqual(list(self.jobs_root.iterdir()), [])

    def test_encoded_paths_methods_and_unknown_api_routes_cannot_bypass_gate(self):
        with patch.dict(os.environ, {"AUTH_MODE": "required"}):
            for target in (
                "/%61pi/jobs", "/api%2Fjobs", "/%61%70%69%2Fjobs",
                "/api%252Fjobs", "/api/jobs%2Fsample%2Fpackage",
                "/api", "/api/unknown", "/api/auth/unknown", "/api/auth/config/",
            ):
                with self.subTest(target=target):
                    self.assert_unavailable(self.client.get(target))
            for method in ("POST", "DELETE", "HEAD", "OPTIONS"):
                response = self.client.request(method, "/api/auth/config")
                self.assertEqual(response.status_code, 503)

    def test_invalid_mode_reports_error_and_blocks_api(self):
        with patch.dict(os.environ, {"AUTH_MODE": "mistyped-mode"}):
            public = self.client.get("/api/auth/config").json()
            self.assertEqual(public["mode"], "required")
            self.assertFalse(public["can_continue_local"])
            self.assertIn("AUTH_MODE inválido", public["message"])
            self.assert_unavailable(self.client.get("/api/jobs"))
            self.assert_unavailable(self.client.post("/api/jobs/cleanup"))

    def test_proxy_root_path_cannot_bypass_api_gate(self):
        # No context manager: avoid the application lifespan and its worker.
        client = TestClient(self.api.app, root_path="/rpa")
        try:
            with patch.dict(os.environ, {"AUTH_MODE": "required"}):
                self.assert_unavailable(client.get("/rpa/api/jobs"))
                self.assert_unavailable(client.get("/rpa/%61pi/jobs/sample/package"))
                self.assertEqual(client.get("/rpa/api/auth/config").status_code, 200)
        finally:
            client.close()

    def test_populated_placeholders_do_not_enable_login_or_access(self):
        with patch.dict(os.environ, {
            "AUTH_MODE": "required", "SUPABASE_URL": "https://placeholder.invalid",
            "SUPABASE_PUBLISHABLE_KEY": "public-sentinel", "SUPABASE_SECRET_KEY": "private-sentinel",
        }):
            response = self.client.get("/api/auth/config")
            self.assertEqual(response.json()["status"], "integration_pending")
            self.assertFalse(response.json()["enabled"])
            self.assertNotIn("sentinel", response.text)
            self.assertNotIn("placeholder.invalid", response.text)
            self.assertFalse(self.client.get("/api/auth/session").json()["authenticated"])
            self.assert_unavailable(self.client.post("/api/auth/login"))
            self.assert_unavailable(self.client.get("/api/jobs"))

    def test_forged_tokens_and_cookies_never_create_a_session(self):
        self.client.cookies.set(SESSION_COOKIE, "forged-cookie")
        headers = {"Authorization": "Bearer forged-token", "X-User-Id": "invented-user"}
        for mode in ("local", "required"):
            with self.subTest(mode=mode), patch.dict(os.environ, {"AUTH_MODE": mode}):
                session = self.client.get("/api/auth/session", headers=headers)
                self.assertFalse(session.json()["authenticated"])
                self.assertIsNone(session.json()["user"])
                self.assertNotIn("set-cookie", session.headers)
                self.assert_unavailable(self.client.post("/api/auth/login", headers=headers))
                if mode == "required":
                    self.assert_unavailable(self.client.get("/api/jobs", headers=headers))

    def test_logout_is_idempotent_and_only_expires_reserved_cookie(self):
        self.client.cookies.set(SESSION_COOKIE, "forged-cookie")
        with patch.dict(os.environ, {"AUTH_MODE": "required"}):
            for _ in range(2):
                response = self.client.post("/api/auth/logout")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"authenticated": False, "user": None})
                cookie = response.headers["set-cookie"]
                self.assertIn(SESSION_COOKIE, cookie)
                self.assertIn("Max-Age=0", cookie)
                self.assertIn("HttpOnly", cookie)
                self.assertNotIn("forged-cookie", cookie)
            self.assert_unavailable(self.client.get("/api/jobs"))

    def test_login_page_and_static_assets_remain_available_when_required(self):
        with patch.dict(os.environ, {"AUTH_MODE": "required"}):
            self.assertEqual(self.client.get("/").status_code, 200)
            self.assertEqual(self.client.get("/static/app.js").status_code, 200)

    def test_local_mode_preserves_existing_api_without_authenticating(self):
        self.assertEqual(self.client.get("/api/jobs").json(), [])
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.post("/api/jobs", json={}).status_code, 422)
        self.assertEqual(self.client.post("/api/jobs/cleanup").json(), {"removed_jobs": 0, "removed_folders": 0})
        self.assertFalse(self.client.get("/api/auth/session").json()["authenticated"])


if __name__ == "__main__":
    unittest.main()
