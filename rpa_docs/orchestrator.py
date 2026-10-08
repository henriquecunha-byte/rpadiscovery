from __future__ import annotations

import threading
import json
import shutil
import tempfile
from pathlib import Path

from .config import JOBS_DIR
from .pipeline import process, synthesize_documentation, create_job_previews, write_report, create_package


class JobCancelled(RuntimeError):
    pass


class WorkerStopping(RuntimeError):
    pass


def rebuild(job: dict, workspace: Path, progress) -> dict:
    progress(8, "Revisando documentos com a transcrição existente")
    old_report = json.loads((workspace / "relatorio.json").read_text(encoding="utf-8"))
    transcript = json.loads((workspace / "transcricao.json").read_text(encoding="utf-8"))
    raw_path = workspace / "analise-visual.json"
    steps = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else (old_report.get("evidence_steps") or old_report.get("steps") or [])
    result = dict(job.get("result_json") or {})

    def source_path(value):
        path = Path(value)
        if not path.is_file() and job["id"] in path.parts:
            path = workspace.joinpath(*path.parts[path.parts.index(job["id"]) + 1:])
        if not path.is_file():
            raise FileNotFoundError("Uma gravação original não está mais disponível para revisar os cortes.")
        return path

    video = source_path(result.get("video") or job["source_path"])
    source_videos = [source_path(value) for value in result.get("source_files") or [str(video)]]
    # Publish only after the complete revision succeeds. Cancellation leaves the
    # previous delivery intact and the existing transcription can be reused.
    with tempfile.TemporaryDirectory(prefix=".rebuild-", dir=workspace) as directory:
        staging = Path(directory)
        if (workspace / "evidence").is_dir():
            shutil.copytree(workspace / "evidence", staging / "evidence")
        shutil.copy2(workspace / "transcricao.json", staging / "transcricao.json")
        if (workspace / "transcricao-aviso.txt").is_file():
            shutil.copy2(workspace / "transcricao-aviso.txt", staging / "transcricao-aviso.txt")
        (staging / "analise-visual.json").write_text(json.dumps(steps, ensure_ascii=False), encoding="utf-8")
        documentation = synthesize_documentation(job, steps, transcript, staging)
        if not transcript:
            documentation.setdefault("limitations", []).append("Não foi possível obter falas da gravação; a análise contextual por áudio precisa ser validada antes do uso operacional.")
            documentation["preview_moments"] = []
        progress(50, "Aplicando os cortes revisados em cada gravação")
        preview, source_previews = create_job_previews(video, source_videos, steps, staging, documentation.get("preview_moments", []))
        progress(82, "Estruturando os documentos da revisão")
        write_report(job, steps, staging, video, documentation, source_previews)
        progress(94, "Preparando o pacote completo revisado")
        create_package(staging)
        warnings = [path.read_text(encoding="utf-8") for path in (staging / "transcricao-aviso.txt", staging / "documentacao-aviso.txt", staging / "documentacao-pdf-aviso.txt") if path.is_file()]
        if not preview.get("created"):
            warnings.append("Nenhum preview contextual foi gerado. Consulte as limitações da documentação e revise o contexto ou a transcrição.")
        progress(98, "Finalizando a revisão")
        generated_names = {
            "relatorio.html", "relatorio.json", "documentacao-processo.json",
            "documentacao-processo.docx", "documentacao-processo.pdf", "procedimento-operacional.md",
            "requisitos-rpa.md", "matriz-evidencias.csv", "preview-processo.mp4", "roteiro-cortes.json",
            "documentacao-aviso.txt", "documentacao-pdf-aviso.txt",
        }
        for name in generated_names:
            if not (staging / name).is_file():
                (workspace / name).unlink(missing_ok=True)
        for folder in ("previews", "roteiros"):
            for old_file in (workspace / folder).glob("*"):
                if old_file.is_file() and not (staging / folder / old_file.name).is_file():
                    old_file.unlink()
        # Never move source inputs or temporary rendering segments.
        for path in sorted(staging.iterdir(), key=lambda item: item.name == "entrega-completa.zip"):
            if path.is_file():
                path.replace(workspace / path.name)
            elif path.name in {"previews", "roteiros"}:
                destination = workspace / path.name
                destination.mkdir(exist_ok=True)
                for artifact in path.iterdir():
                    if artifact.is_file():
                        artifact.replace(destination / artifact.name)
    result.update(video=str(video), source_files=[str(path) for path in source_videos], process_step_count=len(documentation.get("process_flow", [])), preview=preview, previews=source_previews, warnings=warnings)
    return result


class Orchestrator:
    def __init__(self, database):
        self.db = database
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True, name="rpa-docs-worker")

    def start(self):
        if not self.thread.is_alive():
            self.stop_event.clear()
            self.db.recover_interrupted()
            self.thread = threading.Thread(target=self.loop, daemon=True, name="rpa-docs-worker")
            self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=5)

    def loop(self):
        while not self.stop_event.is_set():
            job = self.db.claim_next()
            if not job:
                self.stop_event.wait(1)
                continue
            job_id = job["id"]
            workspace = JOBS_DIR / job_id
            try:
                workspace.mkdir(parents=True, exist_ok=True)
                def progress(value, stage):
                    if self.db.status(job_id) == "CANCEL_REQUESTED":
                        raise JobCancelled("Cancelado pelo usuário")
                    if self.stop_event.is_set():
                        raise WorkerStopping()
                    if not self.db.update_running(job_id, progress=value, stage=stage):
                        raise JobCancelled("Cancelado pelo usuário")
                    self.db.event(job_id, "info", stage)
                action = rebuild if job.get("operation") == "rebuild" else process
                result = action(job, workspace, progress)
                if self.db.status(job_id) == "CANCEL_REQUESTED":
                    raise JobCancelled("Cancelado pelo usuário")
                if not self.db.update_running(job_id, status="COMPLETED", stage="Documentação pronta", progress=100, result_json=result):
                    raise JobCancelled("Cancelado pelo usuário")
                self.db.event(job_id, "success", "Documentação estruturada e pacote completo concluídos.")
            except WorkerStopping:
                if not self.db.update_running(job_id, status="QUEUED", stage="Pausado — aguardando reinício") and self.db.status(job_id) == "CANCEL_REQUESTED":
                    self.db.update(job_id, status="CANCELLED", stage="Cancelado", error=None)
            except JobCancelled:
                self.db.update(job_id, status="CANCELLED", stage="Cancelado", error=None)
                self.db.event(job_id, "warning", "Processamento cancelado. Os arquivos enviados foram preservados.")
            except Exception as error:
                if self.db.update_running(job_id, status="FAILED", stage="Falha no processamento", error=str(error)):
                    self.db.event(job_id, "error", str(error))
                elif self.db.status(job_id) == "CANCEL_REQUESTED":
                    self.db.update(job_id, status="CANCELLED", stage="Cancelado", error=None)
                    self.db.event(job_id, "warning", "Processamento cancelado. Os arquivos enviados foram preservados.")
