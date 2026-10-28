from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rpa_docs.database import ALL_OWNERS, Database


class OwnershipDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.database = Database(self.root / "test.sqlite3")

    def create(self, job_id, owner_id=None, **payload_overrides):
        payload = {
            "title": f"Private {job_id}", "source_path": str(self.root / job_id),
            "process_context": "Private context", "audience": "RPA",
            "detail_level": "operacional", "api_approved": False,
            "api_budget_usd": 1,
        }
        payload.update(payload_overrides)
        return self.database.create_job(job_id, payload, owner_id=owner_id)

    def trio(self, status="QUEUED"):
        for job_id, owner_id in (("a", "user-a"), ("b", "user-b"), ("local", None)):
            self.create(job_id, owner_id)
            self.database.update(job_id, status=status)

    def test_migration_is_idempotent_and_does_not_claim_legacy_jobs(self):
        path = self.root / "legacy.sqlite3"
        with closing(sqlite3.connect(path)) as db:
            db.executescript("""
                CREATE TABLE jobs (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, source_path TEXT NOT NULL,
                    process_context TEXT NOT NULL, audience TEXT NOT NULL, detail_level TEXT NOT NULL,
                    api_approved INTEGER NOT NULL, api_budget_usd REAL NOT NULL,
                    status TEXT NOT NULL, stage TEXT NOT NULL, progress INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT,
                    result_json TEXT
                );
                INSERT INTO jobs VALUES (
                    'legacy','Original','original.mp4','context','RPA','operacional',0,1,
                    'FAILED','Falhou',0,'2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00',
                    NULL,NULL
                );
            """)
        database = Database(path)
        database.initialize()
        Database(path)
        self.assertIsNone(database.get_job("legacy")["owner_id"])
        self.assertEqual(database.get_job("legacy", owner_id=None)["title"], "Original")
        self.assertIsNone(database.get_job("legacy", owner_id="user-a"))
        with database.connect() as db:
            index = [row["name"] for row in db.execute("PRAGMA index_info(jobs_owner_created_at)")]
        self.assertEqual(index, ["owner_id", "created_at"])

    def test_read_and_event_access_is_isolated_for_two_users_and_local(self):
        self.trio()
        for job_id, owner_id in (("a", "user-a"), ("b", "user-b"), ("local", None)):
            with self.subTest(owner=owner_id):
                self.assertEqual([job["id"] for job in self.database.list_jobs(owner_id=owner_id)], [job_id])
                item = self.database.get_job(job_id, owner_id=owner_id)
                self.assertEqual(len(item["events"]), 1)
                for other in {"a", "b", "local"} - {job_id}:
                    self.assertIsNone(self.database.get_job(other, owner_id=owner_id))
        self.assertEqual(len(self.database.list_jobs()), 3)
        self.assertEqual(len(self.database.list_jobs(owner_id=ALL_OWNERS)), 3)

    def test_only_trusted_create_argument_assigns_owner(self):
        payload = {
            "title": "Test", "source_path": "test.mp4", "process_context": "Context",
            "audience": "RPA", "detail_level": "operacional", "api_approved": False,
            "api_budget_usd": 1, "owner_id": "forged-user", "user_id": "forged-user",
        }
        owned = self.database.create_job("owned", payload, owner_id="verified-user")
        local = self.database.create_job("local", payload)
        self.assertEqual(owned["owner_id"], "verified-user")
        self.assertIsNone(local["owner_id"])
        self.assertIsNone(self.database.get_job("owned", owner_id="forged-user"))

    def test_owner_scope_is_parameterized_not_sql(self):
        self.trio()
        forged = "user-a' OR 1=1 --"
        self.assertEqual(self.database.list_jobs(owner_id=forged), [])
        self.assertIsNone(self.database.get_job("b", owner_id=forged))
        self.assertIsNone(self.database.request_cancel("b", owner_id=forged))
        self.assertEqual(self.database.status("b"), "QUEUED")

    def test_empty_or_invalid_owner_fails_closed(self):
        for owner_id in ("", False, 42, [], {}):
            with self.subTest(owner=owner_id):
                with self.assertRaises(ValueError):
                    self.database.list_jobs(owner_id=owner_id)
                with self.assertRaises(ValueError):
                    self.create("invalid", owner_id)
        with self.assertRaises(ValueError):
            self.create("all-users", ALL_OWNERS)

    def test_update_cannot_transfer_ownership_or_mutate_another_owner(self):
        self.trio()
        self.database.update("a", owner_id="user-b", title="Wrong")
        self.database.update("b", owner_id=None, status="FAILED")
        self.assertEqual(self.database.get_job("a")["owner_id"], "user-a")
        self.assertEqual(self.database.get_job("a")["title"], "Private a")
        self.assertEqual(self.database.status("b"), "QUEUED")
        self.database.update("a", owner_id="user-a", title="Allowed")
        self.assertEqual(self.database.get_job("a")["title"], "Allowed")
        for values in ({"id": "b"}, {"owner_id='user-b',title": "Bad"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.database.update("a", **values)
        self.assertEqual(self.database.get_job("a")["owner_id"], "user-a")

    def test_running_callbacks_preserve_owner_and_honor_explicit_scope(self):
        self.trio("RUNNING")
        self.assertFalse(self.database.update_running("b", owner_id="user-a", progress=99))
        self.assertFalse(self.database.update_running("a", owner_id=None, progress=99))
        self.assertTrue(self.database.update_running("a", owner_id="user-a", progress=30))
        self.assertTrue(self.database.update_running("b", progress=40))
        self.assertEqual(self.database.get_job("a")["owner_id"], "user-a")
        self.assertEqual(self.database.get_job("a")["progress"], 30)
        self.assertEqual(self.database.get_job("b")["owner_id"], "user-b")
        self.assertEqual(self.database.get_job("b")["progress"], 40)

    def test_cancel_does_not_reveal_or_change_other_users_jobs(self):
        self.trio()
        self.assertIsNone(self.database.request_cancel("b", owner_id="user-a"))
        self.assertIsNone(self.database.request_cancel("a", owner_id=None))
        self.assertEqual(self.database.request_cancel("a", owner_id="user-a")["status"], "CANCELLED")
        self.assertEqual(self.database.status("b"), "QUEUED")
        self.assertEqual(len(self.database.get_job("b")["events"]), 1)

    def test_retry_does_not_reveal_or_change_other_users_jobs(self):
        self.trio("FAILED")
        self.assertIsNone(self.database.retry("b", owner_id="user-a"))
        self.assertIsNone(self.database.retry("a", owner_id=None))
        self.assertEqual(self.database.retry("a", owner_id="user-a")["status"], "QUEUED")
        self.assertEqual(self.database.status("b"), "FAILED")
        self.assertEqual(len(self.database.get_job("b")["events"]), 1)

    def test_rebuild_does_not_reveal_or_change_other_users_jobs(self):
        self.trio("COMPLETED")
        self.assertIsNone(self.database.enqueue_rebuild("b", owner_id="user-a"))
        self.assertIsNone(self.database.enqueue_rebuild("a", owner_id=None))
        updated = self.database.enqueue_rebuild("a", owner_id="user-a")
        self.assertEqual(updated["status"], "QUEUED")
        self.assertEqual(updated["operation"], "rebuild")
        self.assertEqual(updated["owner_id"], "user-a")
        self.assertEqual(self.database.status("b"), "COMPLETED")
        self.assertEqual(len(self.database.get_job("b")["events"]), 1)

    def test_cleanup_candidates_do_not_include_other_owners(self):
        self.trio("FAILED")
        self.create("completed-a", "user-a")
        self.database.update("completed-a", status="COMPLETED")
        self.assertEqual(self.database.cleanup_candidates(owner_id="user-a"), ["a"])
        self.assertEqual(self.database.cleanup_candidates(owner_id="user-b"), ["b"])
        self.assertEqual(self.database.cleanup_candidates(owner_id=None), ["local"])

    def test_delete_jobs_cannot_delete_others_even_with_their_ids(self):
        self.trio("FAILED")
        self.create("running-a", "user-a")
        removed = self.database.delete_jobs(["a", "b", "local", "running-a"], owner_id="user-a")
        self.assertEqual(removed, 1)
        self.assertIsNone(self.database.get_job("a"))
        self.assertEqual({job["id"] for job in self.database.list_jobs()}, {"b", "local", "running-a"})
        self.assertEqual(len(self.database.get_job("b")["events"]), 1)
        self.assertEqual(self.database.delete_jobs(["b"], owner_id=None), 0)
        self.assertEqual(self.database.delete_jobs([], owner_id=None), 0)

    def test_cleanup_removes_only_owned_workspaces_and_rows(self):
        self.trio("CANCELLED")
        calls = []
        for job_id in ("a", "b", "local"):
            folder = self.root / job_id
            folder.mkdir()
            (folder / "preview.mp4").write_bytes(b"fixture")

        def remove_workspace(job_id):
            calls.append(job_id)
            shutil.rmtree(self.root / job_id)
            return True

        self.assertEqual(self.database.cleanup(remove_workspace, owner_id="user-a"), (1, 1))
        self.assertEqual(calls, ["a"])
        self.assertFalse((self.root / "a").exists())
        for job_id in ("b", "local"):
            self.assertTrue((self.root / job_id / "preview.mp4").is_file())
            self.assertIsNotNone(self.database.get_job(job_id))
        self.assertEqual(self.database.cleanup(remove_workspace, owner_id=None), (1, 1))
        self.assertEqual(calls, ["a", "local"])
        self.assertTrue((self.root / "b" / "preview.mp4").is_file())

    def completed_history(self, job_id, owner_id, duration):
        self.create(job_id, owner_id)
        started = datetime(2026, 1, 1, tzinfo=timezone.utc)
        finished = started + timedelta(seconds=duration)
        self.database.update(job_id, status="COMPLETED", queued_at=started.isoformat())
        with self.database.connect() as db:
            db.execute("DELETE FROM events WHERE job_id=?", (job_id,))
            db.execute("INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,?,?)",
                       (job_id, started.isoformat(), "info", "Organizando as gravações recebidas"))
            db.execute("INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,?,?)",
                       (job_id, finished.isoformat(), "success", "Documentação pronta"))

    def test_timing_uses_only_same_owner_history_and_queue(self):
        self.completed_history("history-a", "user-a", 60)
        self.completed_history("history-b", "user-b", 900)
        self.completed_history("history-local", None, 1200)
        for job_id, owner_id in (("queue-b", "user-b"), ("queue-local", None), ("queue-a1", "user-a"), ("queue-a2", "user-a")):
            self.create(job_id, owner_id)
            self.database.update(job_id, queued_at="2026-01-02T00:00:00+00:00")
        timing = self.database.timing(self.database.get_job("queue-a2"), owner_id="user-a")
        self.assertEqual(timing["history_count"], 1)
        self.assertEqual(timing["estimated_total_seconds"], 60)
        self.assertEqual(timing["queue_position"], 2)
        local = self.database.timing(self.database.get_job("queue-local"), owner_id=None)
        self.assertEqual(local["history_count"], 1)
        self.assertEqual(local["estimated_total_seconds"], 1200)
        self.assertEqual(local["queue_position"], 1)

    def test_timing_reloads_owned_record_instead_of_trusting_input(self):
        self.trio()
        other_job = self.database.get_job("b")
        other_job["owner_id"] = "user-a"
        self.assertIsNone(self.database.timing(other_job, owner_id="user-a"))
        self.assertIsNone(self.database.timing({"id": "absent"}, owner_id="user-a"))
        self.assertIsNone(self.database.timing(self.database.get_job("a"), owner_id=None))
        own_job = self.database.get_job("a")
        own_job.update(status="RUNNING", progress=100, queued_at="not-a-timestamp")
        self.assertEqual(self.database.timing(own_job, owner_id="user-a")["queue_position"], 1)

    def test_worker_claim_recovery_and_callbacks_keep_original_owner(self):
        self.trio()
        self.database.update("b", queued_at="2026-01-01T00:00:00+00:00")
        claimed = self.database.claim_next()
        self.assertEqual(claimed["id"], "b")
        self.assertEqual(claimed["owner_id"], "user-b")
        self.assertTrue(self.database.update_running("b", progress=20))
        self.database.recover_interrupted()
        self.assertEqual(self.database.get_job("b")["owner_id"], "user-b")
        self.assertEqual(self.database.status("b"), "QUEUED")
        self.database.initialize()
        self.assertEqual(self.database.get_job("b")["owner_id"], "user-b")


if __name__ == "__main__":
    unittest.main()
