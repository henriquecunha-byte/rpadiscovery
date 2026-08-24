from __future__ import annotations

import threading
import time
from pathlib import Path

from .config import JOBS_DIR
from .pipeline import process


class JobCancelled(RuntimeError):
    pass


class Orchestrator:
    def __init__(self, database):
        self.db = database
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True, name="rpa-docs-worker")

    def start(self):
        if not self.thread.is_alive():
            self.thread.start()

    def stop(self):
        self.stop_event.set()

    def loop(self):
        while not self.stop_event.is_set():
            job = self.db.next_queued()
            if not job:
                self.stop_event.wait(1)
                continue
            job_id = job["id"]
            workspace = JOBS_DIR / job_id
            workspace.mkdir(parents=True, exist_ok=True)
            self.db.update(job_id, status="RUNNING", stage="Preparando", progress=2, error=None)
            try:
                def progress(value, stage):
                    if self.db.status(job_id) == "CANCEL_REQUESTED":
                        raise JobCancelled("Cancelado pelo usuário")
                    self.db.update(job_id, progress=value, stage=stage)
                    self.db.event(job_id, "info", stage)
                result = process(job, workspace, progress)
                if self.db.status(job_id) == "CANCEL_REQUESTED":
                    raise JobCancelled("Cancelado pelo usuário")
                self.db.update(job_id, status="COMPLETED", stage="Documentação pronta", progress=100, result_json=result)
                self.db.event(job_id, "success", "Relatório navegável concluído.")
            except JobCancelled:
                self.db.update(job_id, status="CANCELLED", stage="Cancelado", error=None)
                self.db.event(job_id, "warning", "Processamento cancelado. Os arquivos enviados foram preservados.")
            except Exception as error:
                self.db.update(job_id, status="FAILED", stage="Falha no processamento", error=str(error))
                self.db.event(job_id, "error", str(error))
