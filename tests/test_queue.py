import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from rpa_docs.database import Database
from rpa_docs.orchestrator import JobCancelled, Orchestrator, rebuild


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = Database(self.root / "test.sqlite3")

    def tearDown(self):
        self.temporary.cleanup()

    def create(self, job_id="sample"):
        return self.database.create_job(job_id, {"title": "Processo Trevo", "source_path": str(self.root / "video.mp4"), "process_context": "Somente Trevo", "audience": "RPA", "detail_level": "operacional", "api_approved": True, "api_budget_usd": 1})

    def test_only_one_worker_can_claim_a_job(self):
        self.create()
        barrier = threading.Barrier(2)
        def claim():
            barrier.wait()
            return self.database.claim_next()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = list(pool.map(lambda _: claim(), range(2)))
        self.assertEqual(sum(job is not None for job in jobs), 1)
        self.assertEqual(self.database.status("sample"), "RUNNING")

    def test_cancel_before_claim_never_starts(self):
        self.create()
        self.database.request_cancel("sample")
        self.assertIsNone(self.database.claim_next())
        self.assertEqual(self.database.status("sample"), "CANCELLED")

    def test_cancel_cannot_be_overwritten_by_late_progress_or_completion(self):
        self.create()
        self.database.claim_next()
        self.database.request_cancel("sample")
        self.assertFalse(self.database.update_running("sample", progress=80, stage="Preview"))
        self.assertFalse(self.database.update_running("sample", status="COMPLETED", progress=100))
        self.assertEqual(self.database.status("sample"), "CANCEL_REQUESTED")

    def test_database_reader_does_not_requeue_running_work(self):
        self.create()
        self.database.claim_next()
        another_reader = Database(self.root / "test.sqlite3")
        self.assertEqual(another_reader.status("sample"), "RUNNING")

    def test_restart_recovers_running_and_finishes_pending_cancellation(self):
        self.create("running")
        self.create("cancelling")
        self.database.update("running", status="RUNNING")
        self.database.update("cancelling", status="CANCEL_REQUESTED")
        self.database.recover_interrupted()
        self.assertEqual(self.database.status("running"), "QUEUED")
        self.assertEqual(self.database.status("cancelling"), "CANCELLED")

    def test_retry_goes_to_end_of_queue_and_resets_elapsed_time(self):
        self.create("first")
        self.database.update("first", status="FAILED")
        self.database.event("first", "info", "Organizando as gravações recebidas")
        self.create("second")
        retried = self.database.retry("first")
        self.assertEqual(self.database.next_queued()["id"], "second")
        timing = self.database.timing(retried)
        self.assertEqual(timing["elapsed_seconds"], 0)
        self.assertIsNone(timing["started_at"])
        self.assertEqual(timing["queue_position"], 2)

    def test_cleanup_stale_candidate_cannot_delete_retried_events(self):
        self.create()
        self.database.update("sample", status="FAILED")
        candidates = self.database.cleanup_candidates()
        self.database.retry("sample")
        self.assertEqual(self.database.delete_jobs(candidates), 0)
        self.assertEqual(self.database.status("sample"), "QUEUED")
        self.assertGreater(len(self.database.get_job("sample")["events"]), 0)

    def test_rebuild_claim_preserves_operation_and_last_result(self):
        self.create()
        self.database.update("sample", status="COMPLETED", result_json={"video": "video.mp4"})
        self.database.enqueue_rebuild("sample")
        claimed = self.database.claim_next()
        self.assertEqual(claimed["operation"], "rebuild")
        self.assertEqual(claimed["result_json"], {"video": "video.mp4"})

    def test_worker_error_after_cancel_marks_cancelled_not_failed(self):
        self.create()
        worker = Orchestrator(self.database)
        def interrupted(job, workspace, progress):
            self.database.request_cancel(job["id"])
            worker.stop_event.set()
            raise RuntimeError("Interrupted tool")
        with patch("rpa_docs.orchestrator.JOBS_DIR", self.root / "jobs"), patch("rpa_docs.orchestrator.process", side_effect=interrupted):
            worker.loop()
        self.assertEqual(self.database.status("sample"), "CANCELLED")
        self.assertIsNone(self.database.get_job("sample")["error"])

    def test_worker_can_start_after_it_was_stopped(self):
        worker = Orchestrator(self.database)
        worker.start()
        worker.stop()
        worker.start()
        self.assertTrue(worker.thread.is_alive())
        worker.stop()

    def prepare_rebuild(self):
        workspace = self.root / "sample"
        workspace.mkdir()
        video = workspace / "video.mp4"
        video.write_bytes(b"video")
        (workspace / "relatorio.json").write_text('{"steps": []}')
        (workspace / "transcricao.json").write_text("[]")
        (workspace / "entrega-completa.zip").write_bytes(b"previous-complete-delivery")
        job = {"id": "sample", "title": "Trevo", "source_path": str(video), "result_json": {"video": str(video), "source_files": [str(video)]}}
        return job, workspace

    def test_rebuild_cancellation_keeps_previous_delivery(self):
        job, workspace = self.prepare_rebuild()
        def progress(value, stage):
            if value >= 50:
                raise JobCancelled()
        with patch("rpa_docs.orchestrator.synthesize_documentation", return_value={"limitations": [], "preview_moments": []}):
            with self.assertRaises(JobCancelled):
                rebuild(job, workspace, progress)
        self.assertEqual((workspace / "entrega-completa.zip").read_bytes(), b"previous-complete-delivery")
        self.assertEqual(list(workspace.glob(".rebuild-*")), [])

    def test_rebuild_without_transcript_does_not_invent_contextual_cuts(self):
        job, workspace = self.prepare_rebuild()
        (workspace / "preview-processo.mp4").write_bytes(b"obsolete-preview")
        (workspace / "documentacao-processo.docx").write_bytes(b"obsolete-word")
        (workspace / "previews").mkdir()
        (workspace / "previews" / "old.mp4").write_bytes(b"obsolete-source-preview")
        def fake_report(job, steps, staging, video, documentation, previews):
            (staging / "relatorio.html").write_text("revised")
        def fake_package(staging):
            (staging / "entrega-completa.zip").write_bytes(b"new-delivery")
        with patch("rpa_docs.orchestrator.synthesize_documentation", return_value={"limitations": [], "preview_moments": [{"start": 0, "end": 10}], "process_flow": []}), patch("rpa_docs.orchestrator.create_job_previews", return_value=({"created": False}, [])) as previews, patch("rpa_docs.orchestrator.write_report", side_effect=fake_report), patch("rpa_docs.orchestrator.create_package", side_effect=fake_package):
            result = rebuild(job, workspace, lambda *_: None)
        self.assertEqual(previews.call_args.args[4], [])
        self.assertFalse(result["preview"]["created"])
        self.assertTrue(result["warnings"])
        self.assertEqual((workspace / "entrega-completa.zip").read_bytes(), b"new-delivery")
        self.assertFalse((workspace / "preview-processo.mp4").exists())
        self.assertFalse((workspace / "documentacao-processo.docx").exists())
        self.assertEqual(list((workspace / "previews").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
