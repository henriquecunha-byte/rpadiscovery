from __future__ import annotations

import json
import sqlite3
import statistics
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def decode_job(row) -> dict:
    job = dict(row)
    result = job.get("result_json")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (ValueError, TypeError):
            result = None
    job["result_json"] = result if isinstance(result, dict) else {}
    return job


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
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
            columns = {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}
            if "operation" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN operation TEXT NOT NULL DEFAULT 'analysis'")
            if "queued_at" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN queued_at TEXT")
                db.execute("UPDATE jobs SET queued_at=created_at WHERE queued_at IS NULL")

    def recover_interrupted(self):
        """Called by worker startup, not by each database reader."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE jobs SET status='QUEUED', stage='Recuperado após interrupção', updated_at=? WHERE status='RUNNING'", (now(),))
            db.execute("UPDATE jobs SET status='CANCELLED', stage='Cancelado durante a interrupção', error=NULL, updated_at=? WHERE status='CANCEL_REQUESTED'", (now(),))

    def create_job(self, job_id: str, payload: dict) -> dict:
        timestamp = now()
        with self.connect() as db:
            db.execute("""INSERT INTO jobs
                (id,title,source_path,process_context,audience,detail_level,api_approved,api_budget_usd,
                 status,stage,progress,created_at,updated_at,error,result_json,queued_at)
                VALUES (?,?,?,?,?,?,?,?,'QUEUED','Aguardando',0,?,?,NULL,NULL,?)""", (
                job_id, payload["title"], payload["source_path"], payload["process_context"],
                payload["audience"], payload["detail_level"], int(payload["api_approved"]),
                payload["api_budget_usd"], timestamp, timestamp, timestamp,
            ))
        self.event(job_id, "info", "Gravação recebida e colocada na fila.")
        return self.get_job(job_id)

    def update(self, job_id: str, **values):
        values["updated_at"] = now()
        encoded = {key: json.dumps(value, ensure_ascii=False) if key == "result_json" and value is not None else value for key, value in values.items()}
        columns = ", ".join(f"{key}=?" for key in encoded)
        with self.connect() as db:
            db.execute(f"UPDATE jobs SET {columns} WHERE id=?", (*encoded.values(), job_id))

    def update_running(self, job_id: str, **values) -> bool:
        """Never let a late progress/completion callback overwrite cancellation."""
        values["updated_at"] = now()
        encoded = {key: json.dumps(value, ensure_ascii=False) if key == "result_json" and value is not None else value for key, value in values.items()}
        columns = ", ".join(f"{key}=?" for key in encoded)
        with self.connect() as db:
            cursor = db.execute(f"UPDATE jobs SET {columns} WHERE id=? AND status='RUNNING'", (*encoded.values(), job_id))
            return cursor.rowcount == 1

    def event(self, job_id: str, level: str, message: str):
        with self.connect() as db:
            db.execute("INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,?,?)", (job_id, now(), level, message))

    def get_job(self, job_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                return None
            result = decode_job(row)
            result["events"] = [dict(item) for item in db.execute("SELECT created_at,level,message FROM events WHERE job_id=? ORDER BY id", (job_id,))]
            return result

    def list_jobs(self) -> list[dict]:
        with self.connect() as db:
            return [decode_job(row) for row in db.execute("SELECT * FROM jobs ORDER BY created_at DESC")]

    def next_queued(self) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE status='QUEUED' ORDER BY queued_at,created_at,id LIMIT 1").fetchone()
            return decode_job(row) if row else None

    def claim_next(self) -> dict | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE status='QUEUED' ORDER BY queued_at,created_at,id LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET status='RUNNING', stage='Preparando', progress=2, error=NULL, updated_at=? WHERE id=?", (now(), row["id"]))
            return decode_job(db.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone())

    def status(self, job_id: str) -> str | None:
        with self.connect() as db:
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            return str(row["status"]) if row else None

    def request_cancel(self, job_id: str) -> dict | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                return None
            current = row["status"]
            if current in {"QUEUED", "RUNNING"}:
                status, stage, message = ("CANCELLED", "Cancelado antes de iniciar", "Trabalho retirado da fila.") if current == "QUEUED" else ("CANCEL_REQUESTED", "Cancelamento solicitado", "O trabalho será interrompido no próximo ponto seguro.")
                db.execute("UPDATE jobs SET status=?,stage=?,error=NULL,updated_at=? WHERE id=?", (status, stage, now(), job_id))
                db.execute("INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,'warning',?)", (job_id, now(), message))
            elif current not in {"CANCEL_REQUESTED", "CANCELLED"}:
                raise ValueError(current)
        return self.get_job(job_id)

    def retry(self, job_id: str) -> dict | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                return None
            if row["status"] not in {"FAILED", "CANCELLED"}:
                raise ValueError(row["status"])
            timestamp = now()
            db.execute("UPDATE jobs SET status='QUEUED',stage='Retomado — aguardando nova tentativa',progress=0,error=NULL,queued_at=?,updated_at=? WHERE id=?", (timestamp, timestamp, job_id))
            db.execute("INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,'info','Trabalho retomado com os arquivos já enviados.')", (job_id, timestamp))
        return self.get_job(job_id)

    def enqueue_rebuild(self, job_id: str) -> dict | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                return None
            if row["status"] != "COMPLETED":
                raise ValueError(row["status"])
            timestamp = now()
            db.execute("UPDATE jobs SET operation='rebuild',status='QUEUED',stage='Revisão de documentos e cortes na fila',progress=0,error=NULL,queued_at=?,updated_at=? WHERE id=?", (timestamp, timestamp, job_id))
            db.execute("INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,'info','Revisão enfileirada com a transcrição já disponível.')", (job_id, timestamp))
        return self.get_job(job_id)

    def timing(self, job: dict) -> dict:
        def parse(value: str) -> datetime:
            return datetime.fromisoformat(value)

        with self.connect() as db:
            start_row = db.execute(
                "SELECT created_at FROM events WHERE job_id=? AND (message LIKE 'Organizando as gravações%' OR message LIKE 'Revisando documentos%') AND created_at>=? ORDER BY id DESC LIMIT 1",
                (job["id"], job.get("queued_at") or job["created_at"]),
            ).fetchone()
            history_rows = db.execute("""
                SELECT j.id,
                    (SELECT created_at FROM events WHERE job_id=j.id AND (message LIKE 'Organizando as gravações%' OR message LIKE 'Revisando documentos%') AND created_at>=COALESCE(j.queued_at,j.created_at) ORDER BY id DESC LIMIT 1) AS started,
                    (SELECT created_at FROM events WHERE job_id=j.id AND level='success' ORDER BY id DESC LIMIT 1) AS finished
                FROM jobs j WHERE j.status='COMPLETED' AND j.operation=?
            """, (job.get("operation", "analysis"),)).fetchall()
            queue_position = 0
            if job["status"] == "QUEUED":
                queue_position = int(db.execute(
                    "SELECT COUNT(*) FROM jobs WHERE status='QUEUED' AND (queued_at<? OR (queued_at=? AND id<=?))", (job.get("queued_at") or job["created_at"], job.get("queued_at") or job["created_at"], job["id"])
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

    def cleanup_candidates(self) -> list[str]:
        with self.connect() as db:
            return [str(row["id"]) for row in db.execute(
                "SELECT id FROM jobs WHERE status IN ('FAILED','CANCELLED') ORDER BY created_at"
            ).fetchall()]

    def delete_jobs(self, job_ids: list[str]) -> int:
        if not job_ids:
            return 0
        placeholders = ",".join("?" for _ in job_ids)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            eligible = [row["id"] for row in db.execute(f"SELECT id FROM jobs WHERE id IN ({placeholders}) AND status IN ('FAILED','CANCELLED')", job_ids)]
            if not eligible:
                return 0
            placeholders = ",".join("?" for _ in eligible)
            db.execute(f"DELETE FROM events WHERE job_id IN ({placeholders})", eligible)
            cursor = db.execute(f"DELETE FROM jobs WHERE id IN ({placeholders})", eligible)
            return int(cursor.rowcount)

    def cleanup(self, remove_workspace) -> tuple[int, int]:
        """Hold the write lock so retry cannot race with directory removal."""
        folders = 0
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT id FROM jobs WHERE status IN ('FAILED','CANCELLED')").fetchall()
            for row in rows:
                folders += int(bool(remove_workspace(row["id"])))
                db.execute("DELETE FROM events WHERE job_id=?", (row["id"],))
                db.execute("DELETE FROM jobs WHERE id=?", (row["id"],))
        return len(rows), folders
