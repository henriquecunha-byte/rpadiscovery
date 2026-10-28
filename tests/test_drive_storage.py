"""No token access or network: provider contract exercised with an in-memory Drive."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rpa_docs.drive_storage import DriveAssetStore, FOLDER, inventory
from rpa_docs.database import Database


class Request:
    def __init__(self, value):
        self.value = value
    def execute(self):
        return copy.deepcopy(self.value)


class FakeDrive:
    def __init__(self):
        self.items = {"project": {"id": "project", "mimeType": FOLDER, "capabilities": {"canAddChildren": True}}}
        self.bytes = {}
        self.fail_upload = False
    def files(self):
        return self
    def get(self, fileId, **kwargs):
        assert kwargs.get("supportsAllDrives")
        return Request(self.items[fileId])
    def list(self, q, **kwargs):
        assert kwargs["supportsAllDrives"] and kwargs["includeItemsFromAllDrives"]
        parent = re.search(r"^'([^']+)'", q)[1]
        job = re.search(r"key='discovery_job' and value='([^']+)'", q)[1]
        asset = re.search(r"key='discovery_key' and value='([^']+)'", q)[1]
        return Request({"files": [item for item in self.items.values() if parent in item.get("parents", [])
            and item.get("appProperties", {}).get("discovery_job") == job and item.get("appProperties", {}).get("discovery_key") == asset]})
    def create(self, body, media_body=None, **kwargs):
        assert kwargs["supportsAllDrives"]
        if media_body and self.fail_upload:
            raise OSError("synthetic interruption")
        identity = "file-" + str(len(self.items))
        item = copy.deepcopy(body) | {"id": identity, "capabilities": {"canDownload": True}}
        if media_body:
            self.bytes[identity] = media_body.getbytes(0, media_body.size())
            item["size"] = str(len(self.bytes[identity]))
        self.items[identity] = item
        return Request(item)
    def get_media(self, fileId, **kwargs):
        assert kwargs["supportsAllDrives"]
        return Request(self.bytes[fileId])


class Downloader:
    def __init__(self, stream, request, **kwargs):
        self.stream, self.request = stream, request
    def next_chunk(self):
        self.stream.write(self.request.execute())
        return None, True


class DriveStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "jobs" / "sample"
        (self.workspace / "input").mkdir(parents=True)
        (self.workspace / "input" / "meeting.mp4").write_bytes(b"synthetic-original")
        (self.workspace / "documentacao-processo.pdf").write_bytes(b"synthetic-pdf")
        (self.workspace / "entrega-completa.zip").write_bytes(b"synthetic-zip")
        (self.workspace / ".env").write_text("secret=never-upload", encoding="utf-8")
        (self.workspace / "documentacao-aviso.txt").write_text("private-error", encoding="utf-8")
        self.job = {"id": "sample", "title": "QA project", "source_path": str(self.workspace / "input"), "contexto": {"modoEntrega": "documentacao"}, "result_json": {}}
        self.fake = FakeDrive()
        self.store = DriveAssetStore(self.fake)
        self.downloader = patch("googleapiclient.http.MediaIoBaseDownload", Downloader)
        self.downloader.start()
    def tearDown(self):
        self.downloader.stop()
        self.temporary.cleanup()

    def test_snapshot_is_idempotent_and_whitelisted(self):
        first = self.store.publish(self.job, self.workspace, "project")
        count = len(self.fake.items)
        second = self.store.publish(self.job, self.workspace, "project")
        self.assertEqual(first, second)
        self.assertEqual(count, len(self.fake.items))
        self.assertTrue(first["sources_complete"])
        self.assertEqual(len(first["assets"]), 3)
        self.assertNotIn("secret", json.dumps(first))
        self.assertNotIn(str(self.workspace), json.dumps(first))

    def test_changed_delivery_creates_a_new_revision_not_an_overwrite(self):
        first = self.store.publish(self.job, self.workspace, "project")
        (self.workspace / "documentacao-processo.pdf").write_bytes(b"revised-pdf")
        second = self.store.publish(self.job, self.workspace, "project")
        self.assertNotEqual(first["folder_id"], second["folder_id"])
        old_pdf = next(a for a in first["assets"] if a["path"].endswith(".pdf"))
        self.assertEqual(self.fake.bytes[old_pdf["file_id"]], b"synthetic-pdf")

    def test_interrupted_snapshot_resumes_without_duplicate_folders(self):
        self.fake.fail_upload = True
        with self.assertRaises(OSError):
            self.store.publish(self.job, self.workspace, "project")
        folders = [item["id"] for item in self.fake.items.values() if item.get("mimeType") == FOLDER]
        self.fake.fail_upload = False
        snapshot = self.store.publish(self.job, self.workspace, "project")
        self.assertTrue(all(identity in self.fake.items for identity in folders))
        self.assertEqual(len(snapshot["assets"]), 3)
        self.assertEqual(len([item for item in self.fake.items.values() if item.get("name") == "QA project - sample"]), 1)

    def test_assets_recover_into_a_fresh_job_workspace_without_original_local_files(self):
        snapshot = self.store.publish(self.job, self.workspace, "project")
        recovered = self.root / "fresh" / "sample"
        response = self.store.restore("sample", recovered, snapshot)
        self.assertEqual(response["restored"], 3)
        self.assertEqual((recovered / "documentacao-processo.pdf").read_bytes(), b"synthetic-pdf")
        self.assertEqual(Path(response["video"]).read_bytes(), b"synthetic-original")
        self.assertEqual(self.store.restore("sample", recovered, snapshot)["restored"], 0)

    def test_corruption_does_not_publish_any_recovered_file(self):
        snapshot = self.store.publish(self.job, self.workspace, "project")
        self.fake.bytes[snapshot["assets"][-1]["file_id"]] = b"corrupted"
        recovered = self.root / "corrupt"
        with self.assertRaises(ValueError):
            self.store.restore("sample", recovered, snapshot)
        self.assertFalse(any(path.is_file() for path in recovered.rglob("*")))

    def test_wrong_job_paths_and_existing_changes_are_rejected(self):
        snapshot = self.store.publish(self.job, self.workspace, "project")
        with self.assertRaises(ValueError):
            self.store.restore("other", self.root / "wrong-job", snapshot)
        tampered = copy.deepcopy(snapshot)
        tampered["assets"][0]["path"] = "../../outside.mp4"
        with self.assertRaises(ValueError):
            self.store.restore("sample", self.root / "wrong-path", tampered)
        recovered = self.root / "existing"
        recovered.mkdir()
        (recovered / "documentacao-processo.pdf").write_bytes(b"keep-my-changes")
        with self.assertRaises(ValueError):
            self.store.restore("sample", recovered, snapshot)
        self.assertEqual((recovered / "documentacao-processo.pdf").read_bytes(), b"keep-my-changes")

    def test_missing_sources_are_explicit_and_folder_is_required(self):
        self.job["result_json"]["source_files"] = [str(self.root / "absent.mp4")]
        self.assertFalse(self.store.publish(self.job, self.workspace, "project")["sources_complete"])
        for parent in ("", "root", "invalid/folder"):
            with self.assertRaises(ValueError):
                self.store.publish(self.job, self.workspace, parent)

    def test_database_publishes_only_owned_unchanged_completed_snapshots(self):
        database = Database(self.root / "test.sqlite3")
        payload = dict(title="QA", source_path="source", process_context="QA", audience="QA", detail_level="operacional", api_approved=True, api_budget_usd=1)
        database.create_job("sample", payload, owner_id="account-a")
        database.update("sample", status="COMPLETED", result_json={"preserve": 1})
        job = database.get_job("sample", owner_id="account-a")
        with self.assertRaises(ValueError):
            database.save_drive_snapshot("sample", {"assets": []}, expected_updated_at=job["updated_at"], owner_id="account-b")
        database.save_drive_snapshot("sample", {"assets": []}, expected_updated_at=job["updated_at"], owner_id="account-a")
        self.assertEqual(database.get_job("sample", owner_id="account-a")["result_json"]["preserve"], 1)
        with self.assertRaises(ValueError):
            database.save_drive_snapshot("sample", {"assets": []}, expected_updated_at=job["updated_at"], owner_id="account-a")


if __name__ == "__main__":
    unittest.main()
