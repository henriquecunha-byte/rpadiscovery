"""Account A/B/legacy isolation via trusted dependency overrides, never fake HTTP login.

All files and databases are temporary. No worker or provider network is started.
"""
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from rpa_docs import config
from rpa_docs.access import AccessScope, current_access
from rpa_docs.auth import VerifiedIdentity
from rpa_docs.database import Database


class OwnershipApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.import_workspace = tempfile.TemporaryDirectory()
        root = Path(cls.import_workspace.name)
        with patch.object(config, "DATABASE", root / "import.sqlite3"), patch.object(config, "JOBS_DIR", root / "jobs"):
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
        self.patches = [patch.object(self.api, "db", self.database), patch.object(self.api, "JOBS_DIR", self.jobs_root), patch.dict(os.environ, {"AUTH_MODE": "local"})]
        for item in self.patches:
            item.start()
        self.previous_overrides = dict(self.api.app.dependency_overrides)
        self.client = TestClient(self.api.app)
        self.scope("account-a")

    def tearDown(self):
        self.client.close()
        self.api.app.dependency_overrides.clear()
        self.api.app.dependency_overrides.update(self.previous_overrides)
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def scope(self, owner):
        self.api.app.dependency_overrides[current_access] = lambda: AccessScope(owner)

    def create(self, job_id, owner, status="COMPLETED"):
        directory = self.jobs_root / job_id
        (directory / "input").mkdir(parents=True)
        source = directory / "input" / "source.mp4"
        source.write_bytes(b"0123456789-recording")
        payload = dict(title=f"Private {job_id}", source_path=str(source.parent), process_context=f"Context {job_id}", audience="Equipe", detail_level="operacional", api_approved=True, api_budget_usd=1)
        self.database.create_job(job_id, payload, owner_id=owner)
        for name in ["relatorio.html", "documentacao-processo.pdf", "documentacao-processo.docx", "procedimento-operacional.md", "requisitos-rpa.md", "matriz-evidencias.csv", "documentacao-processo.json", "roteiro-cortes.json", "transcricao.json", "entrega-completa.zip", "preview-processo.mp4"]:
            (directory / name).write_bytes(b"0123456789-private-artifact")
        (directory / "evidence").mkdir()
        for name in ("intercambio-documentacao.zip", "manifesto-documentacao.json", "fontes.json"):
            (directory / name).write_bytes(b"private-integration-artifact")
        (directory / "evidence" / "frame.jpg").write_bytes(b"private-evidence")
        (directory / "previews").mkdir()
        (directory / "previews" / "one.mp4").write_bytes(b"0123456789-separated-preview")
        (directory / "relatorio.json").write_text('{"documentation":{}}', encoding="utf-8")
        for name in ["documentacao.docx", "documentacao.json", "documentacao.md", "registro-reuniao.md", "guia-treinamento.md", "registro-entrevista.md", "relatorio-pesquisa.md"]:
            (directory / name).write_bytes(b"0123456789-private-artifact")
        self.database.update(job_id, status=status, progress=100 if status == "COMPLETED" else 0,
                             result_json={"video": str(source), "source_files": [str(source)], "source_count": 1,
                                          "previews": [{"file": "previews/one.mp4", "created": True, "source_name": "source.mp4", "source_path": str(source)}]})
        self.database.event(job_id, "info", f"Private event {job_id}")
        return directory

    @staticmethod
    def urls(job_id):
        return [f"/api/jobs/{job_id}" + suffix for suffix in [
            "", "/report", "/evidence/frame.jpg", "/preview-processo.mp4", "/preview-download",
            "/previews/one.mp4", "/previews/one.mp4?download=true&v=1", "/recording",
            "/documentacao-processo.pdf", "/package", "/documentacao-processo.docx",
            "/procedimento-operacional.md", "/requisitos-rpa.md", "/matriz-evidencias.csv",
            "/documentacao-processo.json", "/roteiro-cortes.json", "/transcricao.json",
            "/documentacao.docx", "/documentacao.pdf", "/documentacao.json", "/documentacao.md",
            "/registro-reuniao.md", "/guia-treinamento.md", "/registro-entrevista.md", "/relatorio-pesquisa.md",
            "/intercambio-documentacao.zip", "/manifesto-documentacao.json", "/fontes.json",
        ]]

    def test_lists_and_metadata_are_scoped_before_enrichment(self):
        self.create("a", "account-a")
        self.create("b", "account-b")
        self.create("local", None)
        response = self.client.get("/api/jobs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], ["a"])
        self.assertNotIn("source_path", response.json()[0])
        self.assertNotIn("output_dir", response.json()[0])
        self.assertNotIn("video", response.json()[0]["result_json"])
        self.assertNotIn("source_files", response.json()[0]["result_json"])
        self.assertNotIn("source_path", response.json()[0]["previews"][0])
        self.assertNotIn("source_path", response.json()[0]["result_json"]["previews"][0])
        self.assertNotIn("Context b", response.text)
        self.assertNotIn(str(self.jobs_root).replace("\\", "\\\\"), response.text)
        self.scope("account-b")
        self.assertEqual([item["id"] for item in self.client.get("/api/jobs").json()], ["b"])
        self.scope(None)
        self.assertEqual([item["id"] for item in self.client.get("/api/jobs").json()], ["local"])
        self.assertIn("source_path", self.client.get("/api/jobs/local").json())

    def test_all_reads_and_downloads_reject_foreign_and_legacy_without_file_io(self):
        self.create("b", "account-b")
        self.create("local", None)
        with patch.object(self.api, "FileResponse", side_effect=AssertionError("private file opened")), patch.object(self.api, "write_pdf_document", side_effect=AssertionError("private PDF generated")):
            for job_id in ("b", "local", "nonexistent"):
                for url in self.urls(job_id):
                    with self.subTest(url=url):
                        response = self.client.get(url)
                        self.assertEqual(response.status_code, 404, response.text)
                        self.assertEqual(response.json(), {"detail": "Trabalho não encontrado"})
                        self.assertIn("private", response.headers["cache-control"])
                        self.assertIn("no-store", response.headers["cache-control"])

    def test_owner_can_download_every_deliverable_and_use_range_without_public_cache(self):
        self.create("a", "account-a")
        for url in self.urls("a"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn("no-store", response.headers["cache-control"])
                self.assertIn("Cookie", response.headers["vary"])
        response = self.client.get("/api/jobs/a/previews/one.mp4", headers={"Range": "bytes=0-3"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, b"0123")
        self.assertIn("private", response.headers["cache-control"])

    def test_foreign_range_head_encoded_id_and_owner_query_do_not_bypass(self):
        self.create("b", "account-b")
        for url in ("/api/jobs/b/previews/one.mp4", "/api/jobs/%62/package", "/api/jobs/b?owner_id=account-b", "/api/jobs/b/package?download=true"):
            response = self.client.get(url, headers={"Range": "bytes=0-3", "X-User-Id": "account-b", "Authorization": "Bearer forged"})
            self.assertEqual(response.status_code, 404, response.text)
            self.assertNotIn(b"0123", response.content)
            self.assertNotIn(self.client.head(url).status_code, {200, 206})

    def test_private_cache_policy_is_kept_behind_a_proxy_prefix(self):
        self.create("a", "account-a")
        client = TestClient(self.api.app, root_path="/discovery")
        try:
            response = client.get("/discovery/api/jobs/a/package")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("private", response.headers["cache-control"])
            self.assertIn("no-store", response.headers["cache-control"])
        finally:
            client.close()

    def test_foreign_mutations_do_not_change_rows_events_or_call_drive(self):
        directory = self.create("b", "account-b")
        before = self.database.get_job("b")
        with patch.object(self.api, "upload_package", side_effect=AssertionError("Drive called")):
            for suffix in ("cancel", "retry", "rebuild-documents", "drive"):
                response = self.client.post(f"/api/jobs/b/{suffix}", json={"folder": "foreign-folder", "owner_id": "account-b"})
                self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(self.database.get_job("b"), before)
        self.assertTrue((directory / "entrega-completa.zip").exists())

    def test_cleanup_removes_only_current_owner_failed_or_cancelled_work(self):
        own = self.create("a-fail", "account-a", "FAILED")
        foreign = self.create("b-fail", "account-b", "FAILED")
        legacy = self.create("local-fail", None, "CANCELLED")
        completed = self.create("a-done", "account-a")
        response = self.client.post("/api/jobs/cleanup")
        self.assertEqual(response.json(), {"removed_jobs": 1, "removed_folders": 1})
        self.assertFalse(own.exists())
        self.assertIsNone(self.database.get_job("a-fail"))
        for job_id, path in (("b-fail", foreign), ("local-fail", legacy), ("a-done", completed)):
            self.assertTrue(path.exists())
            self.assertIsNotNone(self.database.get_job(job_id))

    def test_upload_owner_is_derived_from_trusted_scope_not_form_or_headers(self):
        response = self.client.post("/api/jobs/upload", data={"title": "Training", "api_approved": "true", "owner_id": "account-b", "user_id": "account-b"}, files=[("files", ("training.mp4", b"synthetic", "video/mp4"))], headers={"X-User-Id": "account-b"})
        self.assertEqual(response.status_code, 201, response.text)
        item = self.database.get_job(response.json()["id"])
        self.assertEqual(item["owner_id"], "account-a")
        self.assertNotIn("source_path", response.json())
        self.scope("account-b")
        self.assertEqual(self.client.get(f"/api/jobs/{item['id']}").status_code, 404)

    def test_retry_cancel_and_rebuild_keep_owner(self):
        self.create("a", "account-a", "FAILED")
        self.assertEqual(self.client.post("/api/jobs/a/retry").status_code, 200)
        self.assertEqual(self.client.post("/api/jobs/a/cancel").status_code, 200)
        self.database.update("a", status="COMPLETED")
        self.assertEqual(self.client.post("/api/jobs/a/rebuild-documents").status_code, 202)
        self.assertEqual(self.database.get_job("a")["owner_id"], "account-a")

    def test_account_cannot_import_a_server_path_even_if_it_exists(self):
        other = self.create("b", "account-b")
        for path in (other / "input", self.root / "missing.mp4"):
            response = self.client.post("/api/jobs", json={"title": "Forbidden path", "source_path": str(path), "api_approved": True})
            self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(len(self.database.list_jobs()), 1)

    def test_local_path_import_cannot_reference_job_storage_or_parent_directory(self):
        directory = self.create("b", "account-b")
        self.scope(None)
        for path in (directory / "input" / "source.mp4", directory / "input", self.jobs_root, self.root):
            response = self.client.post("/api/jobs", json={"title": "Local path", "source_path": str(path), "api_approved": True})
            self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(len(self.database.list_jobs()), 1)

    def test_local_external_source_still_works_and_stays_local(self):
        source = self.root / "meeting.mp4"
        source.write_bytes(b"synthetic")
        self.scope(None)
        response = self.client.post("/api/jobs", json={"title": "Local meeting", "source_path": str(source), "api_approved": True, "owner_id": "account-a"})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertIsNone(response.json()["owner_id"])
        self.scope("account-a")
        self.assertEqual(self.client.get("/api/jobs").json(), [])

    def test_account_drive_does_not_touch_shared_token_or_global_folder(self):
        self.create("a", "account-a")
        targets = ("drive_status", "authorization_url", "exchange_code", "list_files", "download_files", "upload_package")
        mocks = [patch.object(self.api, name, side_effect=AssertionError(f"shared {name} called")) for name in targets]
        for item in mocks:
            item.start()
        try:
            status = self.client.get("/api/drive/status")
            self.assertEqual(status.status_code, 200)
            self.assertFalse(status.json()["connected"])
            self.assertNotIn("default_folder_id", status.json())
            for url in ("/api/drive/connect", "/api/drive/callback?state=forged", "/api/drive/files"):
                self.assertEqual(self.client.get(url, follow_redirects=False).status_code, 503)
            self.assertEqual(self.client.post("/api/jobs/drive-import", json={"title": "Private import", "file_ids": ["x"], "api_approved": True}).status_code, 503)
            self.assertEqual(self.client.post("/api/jobs/a/drive", json={"folder": "x"}).status_code, 503)
        finally:
            for item in reversed(mocks):
                item.stop()

    def test_asset_storage_cannot_bypass_owner_or_use_a_global_account_token(self):
        self.create("a", "account-a")
        self.create("b", "account-b")
        with patch.object(self.api, "local_store", side_effect=AssertionError("global token accessed")):
            for job_id, expected in (("a", 503), ("b", 404)):
                self.assertEqual(self.client.post(f"/api/jobs/{job_id}/drive", json={"folder": "project", "include_assets": True}).status_code, expected)
                self.assertEqual(self.client.post(f"/api/jobs/{job_id}/drive/restore").status_code, expected)

    def test_browser_headers_cookies_or_query_never_create_verified_identity(self):
        self.create("a", "account-a")
        self.api.app.dependency_overrides.pop(current_access)
        self.client.cookies.set("btime_rpa_session", "forged-account-a")
        response = self.client.get("/api/jobs?owner_id=account-a", headers={"X-User-Id": "account-a", "Authorization": "Bearer account-a"})
        self.assertEqual(response.json(), [])
        self.assertEqual(self.client.get("/api/jobs/a/package").status_code, 404)

    def test_required_mode_remains_closed_even_with_test_account_dependency(self):
        self.create("a", "account-a")
        with patch.dict(os.environ, {"AUTH_MODE": "required"}):
            response = self.client.get("/api/jobs/a/package")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["code"], "auth_not_configured")

    def test_restored_workspace_alias_cannot_read_or_delete_another_workspace(self):
        own = self.create("a", "account-a", "FAILED")
        foreign = self.create("b", "account-b", "FAILED")
        resolve = Path.resolve
        # Deterministically model junction resolution on hosts lacking symlink privileges.
        def resolve_alias(path, *args, **kwargs):
            return resolve(foreign if path == own else path, *args, **kwargs)
        with patch.object(Path, "resolve", resolve_alias), patch.object(self.api.shutil, "rmtree", side_effect=AssertionError("private directory deleted")):
            self.assertEqual(self.client.get("/api/jobs/a/package").status_code, 404)
            self.assertEqual(self.client.post("/api/jobs/cleanup").status_code, 404)
        self.assertTrue((foreign / "entrega-completa.zip").exists())
        self.assertIsNotNone(self.database.get_job("b"))
        self.assertIsNotNone(self.database.get_job("a"))

    def test_restored_artifact_alias_is_rejected_before_read_or_pdf_generation(self):
        own = self.create("a", "account-a")
        foreign = self.create("b", "account-b")
        resolve = Path.resolve
        for suffix in ("entrega-completa.zip", "documentacao-processo.pdf", "relatorio.html", "previews/one.mp4", "evidence/frame.jpg"):
            target = own / suffix
            def resolve_alias(path, *args, **kwargs):
                return resolve(foreign / suffix if path == target else path, *args, **kwargs)
            url = {"entrega-completa.zip": "package", "relatorio.html": "report"}.get(suffix, suffix)
            with self.subTest(suffix=suffix), patch.object(Path, "resolve", resolve_alias), patch.object(self.api, "FileResponse", side_effect=AssertionError("private file opened")):
                self.assertEqual(self.client.get(f"/api/jobs/a/{url}").status_code, 404)


class VerifiedAccessTests(unittest.TestCase):
    def test_only_verified_server_identity_supplies_account_owner(self):
        request = Request({"type": "http", "headers": [], "state": {"verified_identity": VerifiedIdentity("user-a", "session-a")}})
        self.assertEqual(current_access(request), AccessScope("user-a"))

    def test_invalid_server_identity_does_not_fall_back_to_local(self):
        with patch.dict(os.environ, {"AUTH_MODE": "local"}):
            for value in ({"user_id": "a"}, VerifiedIdentity("", "session"), VerifiedIdentity("a", "")):
                request = Request({"type": "http", "headers": [], "state": {"verified_identity": value}})
                with self.assertRaises(HTTPException) as caught:
                    current_access(request)
                self.assertEqual(caught.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
