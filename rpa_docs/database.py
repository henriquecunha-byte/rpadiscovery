from __future__ import annotations

import json
import sqlite3
import statistics
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.initialize()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self):
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, source_path TEXT NOT NULL,
                    process_context TEXT NOT NULL, audience TEXT NOT NULL, detail_level TEXT NOT NULL,
                    api_approved INTEGER NOT NULL, api_budget_usd REAL NOT NULL,
                    status TEXT NOT NULL, stage TEXT NOT NULL, progress INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT,
                    result_json TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, level TEXT NOT NULL, message TEXT NOT NULL
                );
            """)
            db.execute("UPDATE jobs SET status='QUEUED', stage='Recuperado após interrupção' WHERE status='RUNNING'")

    def create_job(self, job_id: str, payload: dict) -> dict:
        timestamp = now()
        with self.connect() as db:
            db.execute("""INSERT INTO jobs
                (id,title,source_path,process_context,audience,detail_level,api_approved,api_budget_usd,
                 status,stage,progress,created_at,updated_at,error,result_json)
                VALUES (?,?,?,?,?,?,?,?,'QUEUED','Aguardando',0,?,?,NULL,NULL)""", (
                job_id, payload["title"], payload["source_path"], payload["process_context"],
                payload["audience"], payload["detail_level"], int(payload["api_approved"]),
                payload["api_budget_usd"], timestamp, timestamp,
            ))
        self.event(job_id, "info", "Gravação recebida e colocada na fila.")
        return self.get_job(job_id)

    def update(self, job_id: str, **values):
        values["updated_at"] = now()
        encoded = {key: json.dumps(value, ensure_ascii=False) if key == "result_json" and value is not None else value for key, value in values.items()}
        columns = ", ".join(f"{key}=?" for key in encoded)
        with self.connect() as db:
            db.execute(f"UPDATE jobs SET {columns} WHERE id=?", (*encoded.values(), job_id))

    def event(self, job_id: str, level: str, message: str):
        with self.connect() as db:
            db.execute("INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,?,?)", (job_id, now(), level, message))

    def get_job(self, job_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            if result.get("result_json"):
                result["result_json"] = json.loads(result["result_json"])
            result["events"] = [dict(item) for item in db.execute("SELECT created_at,level,message FROM events WHERE job_id=? ORDER BY id", (job_id,))]
            return result

    def list_jobs(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM jobs ORDER BY created_at DESC")]

    def next_queued(self) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE status='QUEUED' ORDER BY created_at LIMIT 1").fetchone()
            return dict(row) if row else None

    def status(self, job_id: str) -> str | None:
        with self.connect() as db:
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            return str(row["status"]) if row else None

    def request_cancel(self, job_id: str) -> dict | None:
        current = self.status(job_id)
        if current is None:
            return None
        if current == "QUEUED":
            self.update(job_id, status="CANCELLED", stage="Cancelado antes de iniciar", error=None)
            self.event(job_id, "warning", "Trabalho retirado da fila.")
        elif current == "RUNNING":
            self.update(job_id, status="CANCEL_REQUESTED", stage="Cancelamento solicitado")
            self.event(job_id, "warning", "O trabalho será interrompido no próximo ponto seguro.")
        elif current not in {"CANCEL_REQUESTED", "CANCELLED"}:
            raise ValueError(current)
        return self.get_job(job_id)

    def retry(self, job_id: str) -> dict | None:
        current = self.status(job_id)
        if current is None:
            return None
        if current not in {"FAILED", "CANCELLED"}:
            raise ValueError(current)
        self.update(
            job_id,
            status="QUEUED",
            stage="Retomado — aguardando nova tentativa",
            progress=0,
            error=None,
            result_json=None,
        )
        self.event(job_id, "info", "Trabalho retomado com os arquivos já enviados.")
        return self.get_job(job_id)

    def timing(self, job: dict) -> dict:
        def parse(value: str) -> datetime:
            return datetime.fromisoformat(value)

        with self.connect() as db:
            start_row = db.execute(
                "SELECT created_at FROM events WHERE job_id=? AND message LIKE 'Organizando as gravações%' ORDER BY id DESC LIMIT 1",
                (job["id"],),
            ).fetchone()
            history_rows = db.execute("""
                SELECT j.id,
                    (SELECT created_at FROM events WHERE job_id=j.id AND message LIKE 'Organizando as gravações%' ORDER BY id LIMIT 1) AS started,
                    (SELECT created_at FROM events WHERE job_id=j.id AND level='success' ORDER BY id DESC LIMIT 1) AS finished
                FROM jobs j WHERE j.status='COMPLETED'
            """).fetchall()
            queue_position = 0
            if job["status"] == "QUEUED":
                queue_position = int(db.execute(
                    "SELECT COUNT(*) FROM jobs WHERE status='QUEUED' AND created_at<=?", (job["created_at"],)
                ).fetchone()[0])
        historical = []
        for row in history_rows:
            if row["started"] and row["finished"]:
                historical.append(max(0.0, (parse(row["finished"]) - parse(row["started"])).total_seconds()))
        terminal = job["status"] in {"COMPLETED", "FAILED", "CANCELLED"}
        now_time = parse(job["updated_at"]) if terminal else datetime.now(timezone.utc)
        started_at = start_row["created_at"] if start_row else None
        elapsed = max(0.0, (now_time - parse(started_at)).total_seconds()) if started_at else 0.0
        progress = max(0, min(100, int(job.get("progress") or 0)))
        historical_total = statistics.median(historical) if historical else None
        live_total = elapsed / (progress / 100) if elapsed and progress >= 5 else None
        if historical_total and live_total:
            estimated_total = historical_total * 0.65 + live_total * 0.35
            basis = f"mediana de {len(historical)} trabalho(s) + ritmo atual"
        elif historical_total:
            estimated_total = historical_total
            basis = f"mediana de {len(historical)} trabalho(s) concluído(s)"
        elif live_total:
            estimated_total = live_total
            basis = "ritmo observado neste trabalho"
        else:
            estimated_total = None
            basis = "aguardando dados suficientes"
        remaining = max(0.0, estimated_total - elapsed) if estimated_total is not None else None
        if terminal:
            remaining = 0.0
        return {
            "started_at": started_at,
            "elapsed_seconds": round(elapsed),
            "estimated_total_seconds": round(estimated_total) if estimated_total is not None else None,
            "remaining_seconds": round(remaining) if remaining is not None else None,
            "basis": basis,
            "history_count": len(historical),
            "queue_position": queue_position,
        }
