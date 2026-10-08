"""HTTP regression checks use a private database and never start the worker."""
import importlib
import io
import json
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from rpa_docs import config
from rpa_docs.database import Database
from rpa_docs.uploads import safe_upload_path


class ApiTests(unittest.TestCase):
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
        self.patches = [patch.object(self.api, "db", self.database), patch.object(self.api, "JOBS_DIR", self.jobs_root)]
        for item in self.patches:
            item.start()
        self.client = TestClient(self.api.app)

    def tearDown(self):
        self.client.close()
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def upload(self, files=None, **fields):
        data = {"title": "Processo Trevo", "api_approved": "true", "api_budget_usd": "1", **fields}
        return self.client.post("/api/jobs/upload", data=data, files=files or [("files", ("reuniao.mp4", b"fake-video", "video/mp4"))])

    def create(self, job_id="sample"):
        directory = self.jobs_root / job_id / "input"
        directory.mkdir(parents=True)
        (directory / "video.mp4").write_bytes(b"0123456789")
        return self.database.create_job(job_id, {"title": "Processo Trevo", "source_path": str(directory), "process_context": "Só Trevo", "audience": "RPA", "detail_level": "operacional", "api_approved": True, "api_budget_usd": 1})

    def test_fields_are_validated_before_any_workspace_is_written(self):
        for fields in ({"title": " "}, {"detail_level": "unknown"}, {"api_budget_usd": "0"}, {"api_budget_usd": "nan"}, {"process_context": "x" * 8001}):
            with self.subTest(fields=list(fields)):
                response = self.upload(**fields)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(list(self.jobs_root.iterdir()), [])
                self.assertEqual(self.database.list_jobs(), [])

    def test_approval_required_and_empty_file_rejected(self):
        self.assertEqual(self.upload(api_approved="false").status_code, 400)
        self.assertEqual(self.upload(files=[("files", ("empty.mp4", b"", "video/mp4"))]).status_code, 400)
        self.assertEqual(list(self.jobs_root.iterdir()), [])

    def test_invalid_zip_has_actionable_error_and_no_orphan_workspace(self):
        response = self.upload(files=[("files", ("bad.zip", b"not-a-zip", "application/zip"))])
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("ZIP", response.json()["detail"])
        self.assertEqual(list(self.jobs_root.iterdir()), [])

    def test_zip_escape_rejected_before_extracting_other_entries(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("first.mp4", b"first")
            zipped.writestr("../../escape.mp4", b"unsafe")
        response = self.upload(files=[("files", ("videos.zip", archive.getvalue(), "application/zip"))])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.jobs_root.iterdir()), [])
        self.assertFalse((self.root / "escape.mp4").exists())

    def test_zip_duplicate_video_entries_preserve_both_sources(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped, warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            zipped.writestr("video.mp4", b"first-video")
            zipped.writestr("video.mp4", b"second-video")
        response = self.upload(files=[("files", ("videos.zip", archive.getvalue(), "application/zip"))])
        self.assertEqual(response.status_code, 201, response.text)
        source = Path(response.json()["source_path"])
        videos = list(source.rglob("*.mp4"))
        self.assertEqual({path.read_bytes() for path in videos}, {b"first-video", b"second-video"})
        self.assertIsInstance(response.json()["result_json"], dict)

    def test_mixed_stack_preserves_folder_paths_and_duplicate_names(self):
        response = self.upload(files=[
            ("files", ("folder/video.mp4", b"first", "video/mp4")),
            ("files", ("folder/video.mp4", b"second", "video/mp4")),
            ("files", ("notes.txt", b"ignored", "text/plain")),
        ])
        self.assertEqual(response.status_code, 201, response.text)
        source = Path(response.json()["source_path"])
        self.assertTrue((source / "folder" / "video.mp4").is_file())
        self.assertTrue((source / "folder" / "video-2.mp4").is_file())
        self.assertFalse((source / "notes.txt").exists())

    def test_windows_special_names_and_absolute_paths_are_rejected(self):
        for name in ("C:/video.mp4", "/video.mp4", "NUL.mp4", "part/file:stream.mp4", "../video.mp4", "part./video.mp4"):
            with self.subTest(name=name), self.assertRaises(Exception):
                safe_upload_path(self.root, name)

    def test_job_list_and_detail_normalize_legacy_results(self):
        self.create()
        self.database.update("sample", status="COMPLETED", result_json={"source_count": 2})
        listing = self.client.get("/api/jobs").json()[0]
        detail = self.client.get("/api/jobs/sample").json()
        self.assertEqual(listing["result_json"], detail["result_json"])
        with self.database.connect() as connection:
            connection.execute("UPDATE jobs SET result_json='invalid json' WHERE id='sample'")
        self.assertEqual(self.client.get("/api/jobs/sample").json()["result_json"], {})
        self.assertEqual(self.client.get("/api/jobs").json()[0]["result_json"], {})

    def test_artifacts_have_individual_links_and_previews_support_range(self):
        self.create()
        workspace = self.jobs_root / "sample"
        (workspace / "documentacao-processo.docx").write_bytes(b"docx")
        (workspace / "previews").mkdir()
        (workspace / "previews" / "001-preview.mp4").write_bytes(b"0123456789")
        self.database.update("sample", status="COMPLETED", result_json={"previews": [{"file": "previews/001-preview.mp4", "created": True, "source_name": "video.mp4"}]})
        detail = self.client.get("/api/jobs/sample").json()
        self.assertTrue(detail["documents"][0]["available"])
        self.assertTrue(detail["previews"][0]["preview_url"])
        response = self.client.get(detail["previews"][0]["preview_url"], headers={"Range": "bytes=2-5"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, b"2345")
        self.assertEqual(self.client.get(detail["documents"][0]["url"]).content, b"docx")

    def test_queued_retry_does_not_expose_stale_delivery(self):
        self.create()
        workspace = self.jobs_root / "sample"
        (workspace / "preview-processo.mp4").write_bytes(b"old-preview")
        (workspace / "entrega-completa.zip").write_bytes(b"old-package")
        self.database.update("sample", status="FAILED")
        response = self.client.post("/api/jobs/sample/retry")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["package_url"])
        self.assertEqual(response.json()["previews"], [])

    def test_rebuild_is_queued_and_preserves_transcription_and_result(self):
        self.create()
        workspace = self.jobs_root / "sample"
        (workspace / "relatorio.json").write_text("{}")
        (workspace / "transcricao.json").write_text("[]")
        result = {"source_count": 1, "video": str(workspace / "input" / "video.mp4")}
        self.database.update("sample", status="COMPLETED", result_json=result)
        response = self.client.post("/api/jobs/sample/rebuild-documents")
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()["status"], "QUEUED")
        self.assertEqual(response.json()["operation"], "rebuild")
        self.assertEqual(response.json()["result_json"], result)
        self.assertEqual(self.client.post("/api/jobs/sample/rebuild-documents").status_code, 409)
        self.assertEqual(self.client.post("/api/jobs/sample/cancel").json()["status"], "CANCELLED")

    def test_legacy_completed_without_files_is_not_reported_as_no_contextual_cuts(self):
        self.create()
        self.database.update("sample", status="COMPLETED", result_json={"source_count": 2, "previews": [{"file": "previews/missing.mp4", "created": True}]})
        response = self.client.get("/api/jobs/sample")
        self.assertTrue(response.json()["delivery_missing"])
        self.assertIn("não foram encontrados", response.json()["delivery_missing_reason"])
        self.assertFalse(response.json()["can_rebuild"])
        rebuild = self.client.post("/api/jobs/sample/rebuild-documents")
        self.assertEqual(rebuild.status_code, 409)
        self.assertIn("reutilizar", rebuild.json()["detail"])
        self.assertEqual(self.database.status("sample"), "COMPLETED")

    def test_missing_source_disables_retry_and_returns_actionable_conflict(self):
        self.create()
        (self.jobs_root / "sample" / "input" / "video.mp4").unlink()
        self.database.update("sample", status="FAILED")
        detail = self.client.get("/api/jobs/sample").json()
        self.assertFalse(detail["can_retry"])
        self.assertFalse(detail["source_available"])
        self.assertIn("reutilize", detail["retry_unavailable_reason"])
        response = self.client.post("/api/jobs/sample/retry")
        self.assertEqual(response.status_code, 409)
        self.assertIn("reutilize", response.json()["detail"])
        self.assertEqual(self.database.status("sample"), "FAILED")

    def test_retry_can_relocate_legacy_job_input_path_without_changing_other_jobs(self):
        self.create()
        old_source = self.root / "old-checkout" / "jobs" / "sample" / "input"
        self.database.update("sample", status="FAILED", source_path=str(old_source))
        response = self.client.post("/api/jobs/sample/retry")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["source_path"], str(self.jobs_root / "sample" / "input"))
        self.assertEqual(response.json()["status"], "QUEUED")

    def test_cleanup_only_removes_failed_and_cancelled_workspaces(self):
        for job_id, status in (("failed", "FAILED"), ("cancelled", "CANCELLED"), ("queued", "QUEUED"), ("completed", "COMPLETED")):
            self.create(job_id)
            self.database.update(job_id, status=status)
        response = self.client.post("/api/jobs/cleanup")
        self.assertEqual(response.json(), {"removed_jobs": 2, "removed_folders": 2})
        self.assertEqual({path.name for path in self.jobs_root.iterdir()}, {"queued", "completed"})

    def test_drive_import_failure_removes_partial_downloads(self):
        def failed_download(file_ids, destination):
            destination.mkdir(parents=True)
            (destination / "partial.mp4").write_bytes(b"partial")
            raise RuntimeError("Falha simulada no download")
        with patch.object(self.api, "download_files", side_effect=failed_download):
            response = self.client.post("/api/jobs/drive-import", json={"title": "Processo Trevo", "file_ids": ["test-id"], "api_approved": True})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.jobs_root.iterdir()), [])

    def test_health_only_exposes_boolean_configuration_and_index_disables_cache(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        for key in ("worker", "ffmpeg", "ffprobe", "api_configured"):
            self.assertIsInstance(response.json()[key], bool)
        self.assertIn("no-store", self.client.get("/").headers["cache-control"])


if __name__ == "__main__":
    unittest.main()
