"""Native reader and revision-bound exports: temporary data, no worker or AI."""
import importlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pypdf import PdfReader
from PIL import Image
from rpa_docs import config, documentation_reader
from rpa_docs.database import Database
from rpa_docs.access import AccessScope, current_access
from rpa_docs.pipeline import write_report, create_package
from tests.test_static_evidence import fixture


class DocumentationReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = tempfile.TemporaryDirectory()
        root = Path(cls.bootstrap.name)
        with patch.object(config, "DATABASE", root / "bootstrap.sqlite3"), patch.object(config, "JOBS_DIR", root / "jobs"):
            cls.api = importlib.import_module("rpa_docs.api")

    @classmethod
    def tearDownClass(cls):
        cls.bootstrap.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.jobs = self.root / "jobs"
        self.jobs.mkdir()
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.db = Database(self.root / "test.sqlite3")
        self.patches = [patch.object(self.api, "db", self.db), patch.object(self.api, "JOBS_DIR", self.jobs), patch.object(documentation_reader, "CACHE_DIR", self.cache)]
        for item in self.patches:
            item.start()
        self.overrides = dict(self.api.app.dependency_overrides)
        self.api.app.dependency_overrides[current_access] = lambda: AccessScope(None)
        self.client = TestClient(self.api.app)

    def tearDown(self):
        self.client.close()
        self.api.app.dependency_overrides.clear()
        self.api.app.dependency_overrides.update(self.overrides)
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def prepare(self, profile="processo", owner=None):
        workspace = self.jobs / "reader-test"
        workspace.mkdir()
        job, document, steps = fixture(workspace, profile)
        job["id"] = "reader-test"
        created = self.db.create_job(job["id"], job, owner_id=owner)
        write_report(created, steps, workspace, Path("synthetic.mp4"), document, [])
        create_package(workspace)
        self.db.update(job["id"], status="COMPLETED", result_json={"evidence_count": 2})
        return workspace, document

    def read(self):
        return self.client.get("/api/jobs/reader-test/documentation")

    def test_reader_returns_all_content_and_authorized_evidence_without_machine_paths(self):
        workspace, document = self.prepare()
        response = self.read()
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["documentation"], document)
        self.assertEqual(len(data["evidence"]), 2)
        self.assertEqual(len(data["version"]), 64)
        self.assertNotIn(str(workspace).replace("\\", "\\\\"), response.text)
        self.assertNotIn("source_path", response.text)
        for figure in data["evidence"]:
            self.assertEqual(self.client.get(figure["url"]).status_code, 200)
        detail = self.client.get("/api/jobs/reader-test").json()
        self.assertEqual(detail["documentation_url"], "/api/jobs/reader-test/documentation")
        self.assertTrue(detail["documentation_revision"])

    def test_pdf_contains_the_read_document_and_images_and_does_not_rewrite_delivery(self):
        workspace, document = self.prepare()
        original = (workspace / "documentacao-processo.pdf").read_bytes()
        zip_original = (workspace / "entrega-completa.zip").read_bytes()
        version = self.read().json()["version"]
        with patch.object(self.api.worker, "start", side_effect=AssertionError("worker started")):
            response = self.client.get(f"/api/jobs/reader-test/documentation/pdf?version={version}")
        self.assertEqual(response.status_code, 200, response.text[:100])
        self.assertEqual(response.headers["x-document-version"], version)
        pdf = PdfReader(io.BytesIO(response.content))
        self.assertEqual(sum(len(page.images) for page in pdf.pages), 2)
        self.assertIn("Conferir pedido", "\n".join(page.extract_text() for page in pdf.pages))
        self.assertEqual((workspace / "documentacao-processo.pdf").read_bytes(), original)
        self.assertEqual((workspace / "entrega-completa.zip").read_bytes(), zip_original)
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_changed_document_rejects_old_pdf_and_zip_versions(self):
        workspace, _ = self.prepare()
        version = self.read().json()["version"]
        path = workspace / "relatorio.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report["documentation"]["executive_summary"] = "Nova versão para revisão."
        path.write_text(json.dumps(report), encoding="utf-8")
        for kind in ("pdf", "package"):
            response = self.client.get(f"/api/jobs/reader-test/documentation/{kind}?version={version}")
            self.assertEqual(response.status_code, 409)
        self.assertNotEqual(self.read().json()["version"], version)

    def test_changed_image_rejects_old_export_even_without_document_timestamp_change(self):
        workspace, _ = self.prepare()
        version = self.read().json()["version"]
        Image.new("RGB", (960, 540), "red").save(workspace / "evidence" / "tela-1.png")
        self.assertEqual(self.client.get(f"/api/jobs/reader-test/documentation/pdf?version={version}").status_code, 409)

    def test_current_view_cannot_download_a_package_with_old_document_or_images(self):
        workspace, _ = self.prepare()
        Image.new("RGB", (960, 540), "blue").save(workspace / "evidence" / "tela-1.png")
        version = self.read().json()["version"]
        self.assertEqual(self.client.get(f"/api/jobs/reader-test/documentation/package?version={version}").status_code, 409)
        create_package(workspace)
        self.assertEqual(self.client.get(f"/api/jobs/reader-test/documentation/package?version={version}").status_code, 409)
        report = json.loads((workspace / "relatorio.json").read_text(encoding="utf-8"))
        write_report(self.db.get_job("reader-test"), report["evidence_steps"], workspace, Path("synthetic.mp4"), report["documentation"], [])
        create_package(workspace)
        version = self.read().json()["version"]
        self.assertEqual(self.client.get(f"/api/jobs/reader-test/documentation/package?version={version}").status_code, 200)

    def test_pdf_preserves_images_referenced_only_by_a_business_rule(self):
        workspace, _ = self.prepare()
        path = workspace / "relatorio.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        for item in report["documentation"]["process_flow"]:
            item["evidence_refs"] = []
        report["documentation"]["business_rules"] = [{"rule": "Validar antes de confirmar.", "evidence_refs": [1, 2]}]
        path.write_text(json.dumps(report), encoding="utf-8")
        version = self.read().json()["version"]
        response = self.client.get(f"/api/jobs/reader-test/documentation/pdf?version={version}")
        self.assertEqual(response.status_code, 200)
        pdf = PdfReader(io.BytesIO(response.content))
        self.assertEqual(sum(len(page.images) for page in pdf.pages), 2)
        self.assertIn("Validar antes de confirmar", "\n".join(page.extract_text() for page in pdf.pages))

    def test_general_profiles_keep_their_sections_in_reader_and_pdf(self):
        for profile in ("reuniao", "treinamento", "entrevista", "pesquisa", "personalizado"):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                job, document, steps = fixture(root, profile)
                write_report(job, steps, root, Path("synthetic.mp4"), document, [])
                saved = documentation_reader.snapshot(job, root)
                self.assertEqual(saved.public()["documentation"]["sections"], document["sections"])
                self.assertEqual(saved.public()["profile"], profile)
                self.assertTrue(documentation_reader.export_pdf(saved).startswith(b"%PDF"))

    def test_zip_is_revision_guarded_and_owner_checks_precede_reading(self):
        self.prepare(owner="account-a")
        for owner, expected in (("account-b", 404), (None, 404)):
            self.api.app.dependency_overrides[current_access] = lambda owner=owner: AccessScope(owner)
            with patch.object(self.api, "document_snapshot", side_effect=AssertionError("foreign file read")):
                self.assertEqual(self.read().status_code, expected)
                for kind in ("pdf", "package"):
                    self.assertEqual(self.client.get(f"/api/jobs/reader-test/documentation/{kind}?version={'a'*64}").status_code, expected)
        self.api.app.dependency_overrides[current_access] = lambda: AccessScope("account-a")
        version = self.read().json()["version"]
        self.assertEqual(self.client.get(f"/api/jobs/reader-test/documentation/package?version={version}").status_code, 200)

    def test_pending_missing_and_corrupt_documents_offer_safe_errors(self):
        workspace, _ = self.prepare()
        self.db.update("reader-test", status="RUNNING")
        self.assertEqual(self.read().status_code, 409)
        self.db.update("reader-test", status="COMPLETED")
        (workspace / "relatorio.json").write_text("invalid", encoding="utf-8")
        response = self.read()
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(str(workspace), response.text)
        (workspace / "relatorio.json").unlink()
        self.assertEqual(self.read().status_code, 404)


if __name__ == "__main__":
    unittest.main()
