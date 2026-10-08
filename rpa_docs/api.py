from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import json
import os
import shutil
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .config import DATABASE, JOBS_DIR, STATIC_DIR, FFMPEG, FFPROBE
from .database import Database
from .orchestrator import Orchestrator
from .schemas import DriveImport, DriveUpload, JobCreate, PromptSuggestion
from .pipeline import VIDEO_EXTENSIONS, suggest_process_prompt, write_pdf_document
from .uploads import extract_video_zip, prepare_downloaded_inputs, safe_upload_path, unique_upload_path
from .drive import authorization_url, download_files, exchange_code, list_files, status as drive_status, upload_package


db = Database(DATABASE)
worker = Orchestrator(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker.start()
    yield
    worker.stop()


app = FastAPI(title="Btime RPA Docs", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def prevent_stale_local_interface(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


def parsed_result(job: dict) -> dict:
    result = job.get("result_json") or {}
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            result = {}
    return result if isinstance(result, dict) else {}


def recording_file(job_id: str, result: dict) -> Path | None:
    """Gravação analisada do trabalho: a consolidada quando há pilha, a original quando há um arquivo só."""
    workspace = (JOBS_DIR / job_id).resolve()
    candidates = []
    declared = str(result.get("video") or "")
    if declared:
        candidates.append(Path(declared))
        parts = Path(declared).parts
        if job_id in parts:
            candidates.append(workspace.joinpath(*parts[parts.index(job_id) + 1:]))
    candidates.append(workspace / "gravacao-consolidada.mp4")
    for candidate in candidates:
        try:
            path = candidate.resolve()
        except OSError:
            continue
        if workspace in path.parents and path.suffix.lower() in VIDEO_EXTENSIONS and path.exists():
            return path
    return None


def existing_job_path(job_id: str, declared: str) -> Path | None:
    if not declared:
        return None
    original = Path(declared)
    candidates = [original]
    if job_id in original.parts:
        candidates.append((JOBS_DIR / job_id).joinpath(*original.parts[original.parts.index(job_id) + 1:]))
    return next((path for path in candidates if path.exists()), None)


def input_availability(job: dict) -> dict:
    workspace = JOBS_DIR / job["id"]
    result = parsed_result(job)
    source = existing_job_path(job["id"], job["source_path"])
    source_available = bool(source and (
        (source.is_file() and source.suffix.lower() in VIDEO_EXTENSIONS)
        or (source.is_dir() and any(path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS for path in source.rglob("*")))
    ))
    video = existing_job_path(job["id"], str(result.get("video") or job["source_path"]))
    originals = result.get("source_files") or ([str(video)] if video else [])
    recordings_available = bool(video and video.is_file() and originals and all(
        (path := existing_job_path(job["id"], str(value))) and path.is_file() for value in originals
    ))
    evidence_available = not result.get("evidence_count") or any((workspace / "evidence").glob("*.jpg"))
    rebuild_available = bool(recordings_available and evidence_available and (workspace / "relatorio.json").is_file() and (workspace / "transcricao.json").is_file())
    retry_available = rebuild_available if job.get("operation") == "rebuild" else source_available
    return {
        "source_available": source_available,
        "can_retry": job["status"] in {"FAILED", "CANCELLED"} and retry_available,
        "retry_unavailable_reason": "Os arquivos deste trabalho não estão disponíveis neste ambiente. Restaure a pasta original do trabalho ou reutilize o pedido e envie as gravações novamente." if not retry_available else None,
        "can_rebuild": job["status"] == "COMPLETED" and rebuild_available,
        "rebuild_unavailable_reason": "Para revisar os cortes e documentos, restaure as gravações, a transcrição e as evidências deste trabalho. Você também pode reutilizar o pedido e enviar as gravações novamente." if not rebuild_available else None,
    }


def enrich(job: dict) -> dict:
    workspace = JOBS_DIR / job["id"]
    preview_path = workspace / "preview-processo.mp4"
    preview_version = preview_path.stat().st_mtime_ns if preview_path.exists() else None
    result = parsed_result(job)
    job["result_json"] = result
    preview_items = []
    for item in result.get("previews") or []:
        if not isinstance(item, dict):
            continue
        relative = Path(item.get("file") or "")
        path = workspace / relative
        if not item.get("created"):
            preview_items.append(dict(item) | {"preview_url": None, "download_url": None})
            continue
        if not relative.name or not path.is_file() or not (
            relative.as_posix() == "preview-processo.mp4"
            or (relative.parent.as_posix() == "previews" and relative.suffix.lower() == ".mp4")
        ) or workspace.resolve() not in path.resolve().parents:
            continue
        version = path.stat().st_mtime_ns
        if relative.parent.as_posix() == "previews":
            filename = quote(relative.name)
            url = f"/api/jobs/{job['id']}/previews/{filename}?v={version}"
            download_url = f"/api/jobs/{job['id']}/previews/{filename}?download=true&v={version}"
        else:
            url = f"/api/jobs/{job['id']}/preview-processo.mp4?v={version}"
            download_url = f"/api/jobs/{job['id']}/preview-download?v={version}"
        preview_items.append(dict(item) | {"preview_url": url, "download_url": download_url})
    if not preview_items and preview_version and "previews" not in result:
        preview_items = [{
            "index": 1,
            "source_name": Path(result.get("video") or "Gravação").name,
            "duration": (result.get("preview") if isinstance(result.get("preview"), dict) else {}).get("duration", 0),
            "created": True,
            "preview_url": f"/api/jobs/{job['id']}/preview-processo.mp4?v={preview_version}",
            "download_url": f"/api/jobs/{job['id']}/preview-download?v={preview_version}",
        }]
    job["report_url"] = f"/api/jobs/{job['id']}/report" if (workspace / "relatorio.html").exists() else None
    job["previews"] = preview_items
    first_preview = next((item for item in preview_items if item.get("preview_url")), None)
    job["preview_url"] = first_preview["preview_url"] if first_preview else None
    job["preview_download_url"] = first_preview["download_url"] if first_preview else None
    job["document_url"] = f"/api/jobs/{job['id']}/documentacao-processo.docx" if (workspace / "documentacao-processo.docx").exists() else None
    job["pdf_url"] = f"/api/jobs/{job['id']}/documentacao-processo.pdf" if (workspace / "relatorio.json").exists() else None
    recording = recording_file(job["id"], result)
    job["recording_url"] = f"/api/jobs/{job['id']}/recording" if recording else None
    job["recording_name"] = recording.name if recording else None
    job["recording_size"] = recording.stat().st_size if recording else None
    job["package_url"] = f"/api/jobs/{job['id']}/package" if (workspace / "entrega-completa.zip").exists() else None
    job.update(input_availability(job))
    job["documents"] = [
        {"filename": filename, "label": label, "format": file_format,
         "available": (workspace / filename).is_file(),
         "url": f"/api/jobs/{job['id']}/{filename}" if (workspace / filename).is_file() else None}
        for filename, label, file_format in (
            ("documentacao-processo.docx", "Documentação do processo", "Word"),
            ("documentacao-processo.pdf", "Documentação do processo", "PDF"),
            ("procedimento-operacional.md", "Procedimento operacional", "Markdown"),
            ("requisitos-rpa.md", "Requisitos de automação", "Markdown"),
            ("matriz-evidencias.csv", "Matriz de evidências", "CSV"),
            ("documentacao-processo.json", "Documentação estruturada", "JSON"),
            ("roteiro-cortes.json", "Roteiro dos cortes", "JSON"),
            ("transcricao.json", "Transcrição de referência", "JSON"),
        )
    ]
    job["delivery_missing"] = job["status"] == "COMPLETED" and not (
        job["report_url"] or job["package_url"] or any(item.get("preview_url") for item in preview_items)
        or any(item["available"] for item in job["documents"])
    )
    job["delivery_missing_reason"] = (
        "O histórico desta análise foi preservado, mas os vídeos e documentos não foram encontrados neste ambiente. Restaure a pasta original do trabalho ou reutilize o pedido para reenviar as gravações."
        if job["delivery_missing"] else None
    )
    # During processing, previous/partial artifacts must not look like a new
    # completed delivery. Retry/rebuild will publish the new result at the end.
    if job["status"] != "COMPLETED":
        job["previews"] = []
        for key in ("report_url", "preview_url", "preview_download_url", "document_url", "pdf_url", "package_url"):
            job[key] = None
        for document in job["documents"]:
            document.update(available=False, url=None)
    job["output_dir"] = str(workspace.resolve())
    job["timing"] = db.timing(job)
    return job


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {
        "status": "ok", "worker": worker.thread.is_alive(),
        "ffmpeg": bool(shutil.which(FFMPEG)), "ffprobe": bool(shutil.which(FFPROBE)),
        "api_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
    }


@app.get("/api/drive/status")
def google_drive_status():
    try:
        return drive_status()
    except Exception as error:
        return {"configured": True, "connected": False, "error": str(error)}


@app.get("/api/drive/connect")
def connect_google_drive():
    try:
        return RedirectResponse(authorization_url())
    except Exception as error:
        raise HTTPException(400, str(error)) from error


@app.get("/api/drive/callback")
def google_drive_callback(request: Request, state: str):
    try:
        exchange_code(str(request.url), state)
    except Exception as error:
        raise HTTPException(400, str(error)) from error
    return RedirectResponse("/?drive=connected")


@app.post("/api/prompt/suggest")
def suggest_prompt(payload: PromptSuggestion):
    return suggest_process_prompt(payload.model_dump())


@app.get("/api/jobs")
def jobs():
    return [enrich(item) for item in db.list_jobs()]


@app.post("/api/jobs/cleanup")
def cleanup_jobs():
    jobs_root = JOBS_DIR.resolve()
    def remove_workspace(job_id):
        workspace = (JOBS_DIR / job_id).resolve()
        if workspace.parent != jobs_root:
            raise HTTPException(400, "Pasta de trabalho inválida durante a limpeza.")
        if workspace.exists():
            shutil.rmtree(workspace)
            return True
        return False
    try:
        removed_jobs, removed_folders = db.cleanup(remove_workspace)
    except OSError as error:
        raise HTTPException(409, "Não foi possível remover um arquivo em uso. Aguarde e tente novamente.") from error
    return {"removed_jobs": removed_jobs, "removed_folders": removed_folders}


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    item = db.get_job(job_id)
    if not item:
        raise HTTPException(404, "Trabalho não encontrado")
    return enrich(item)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    try:
        item = db.request_cancel(job_id)
    except ValueError as error:
        raise HTTPException(409, "Este trabalho não pode mais ser cancelado.") from error
    if not item:
        raise HTTPException(404, "Trabalho não encontrado")
    return enrich(item)


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str):
    current = db.get_job(job_id)
    if current and current["status"] in {"FAILED", "CANCELLED"}:
        availability = input_availability(current)
        if not availability["can_retry"]:
            raise HTTPException(409, availability["retry_unavailable_reason"])
        source = existing_job_path(job_id, current["source_path"])
        if source and str(source) != current["source_path"]:
            db.update(job_id, source_path=str(source))
    try:
        item = db.retry(job_id)
    except ValueError as error:
        raise HTTPException(409, "Somente trabalhos com falha ou cancelados podem ser retomados.") from error
    if not item:
        raise HTTPException(404, "Trabalho não encontrado")
    return enrich(item)


@app.post("/api/jobs", status_code=201)
def create_job(payload: JobCreate):
    source = Path(payload.source_path)
    if not source.exists():
        raise HTTPException(400, "A gravação ou pasta selecionada não foi encontrada.")
    if source.is_file() and source.suffix.lower() not in VIDEO_EXTENSIONS:
        raise HTTPException(400, "Selecione um vídeo compatível ou uma pasta com gravações.")
    if source.is_dir() and not any(path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS for path in source.rglob("*")):
        raise HTTPException(400, "A pasta selecionada não contém vídeos compatíveis.")
    if not payload.api_approved:
        raise HTTPException(400, "Autorize a análise visual para iniciar este trabalho.")
    return enrich(db.create_job(uuid4().hex[:12], payload.model_dump() | {"source_path": str(source.resolve())}))


@app.post("/api/jobs/upload", status_code=201)
async def upload_job(
    title: str = Form(...),
    process_context: str = Form(""),
    audience: str = Form("Equipe de RPA"),
    detail_level: str = Form("operacional"),
    api_approved: bool = Form(False),
    api_budget_usd: float = Form(1.0),
    files: list[UploadFile] = File(...),
):
    job_id = uuid4().hex[:12]
    workspace = JOBS_DIR / job_id
    input_dir = workspace / "input"
    persisted = False
    try:
        if not api_approved:
            raise HTTPException(400, "Autorize a análise visual para iniciar este trabalho.")
        try:
            payload = JobCreate(
                title=title, source_path=str(input_dir), process_context=process_context,
                audience=audience, detail_level=detail_level,
                api_approved=True, api_budget_usd=api_budget_usd,
            )
        except ValidationError as error:
            raise HTTPException(422, [{"loc": ["body", *item["loc"]], "msg": item["msg"], "type": item["type"]} for item in error.errors()]) from error
        supported = [upload for upload in files if Path(upload.filename or "").suffix.lower() in VIDEO_EXTENSIONS | {".zip"}]
        if not supported:
            raise HTTPException(400, "Envie pelo menos um vídeo compatível ou um ZIP com gravações.")
        # Validate every selected name before creating a job directory.
        for upload in supported:
            safe_upload_path(input_dir, upload.filename)
        input_dir.mkdir(parents=True, exist_ok=False)
        saved = 0
        for upload in supported:
            target = unique_upload_path(safe_upload_path(input_dir, upload.filename))
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as destination:
                while chunk := await upload.read(1024 * 1024):
                    destination.write(chunk)
            if target.stat().st_size == 0:
                raise HTTPException(400, f'O arquivo "{target.name}" está vazio.')
            saved += await run_in_threadpool(extract_video_zip, target, input_dir) if target.suffix.lower() == ".zip" else 1
        if not saved:
            raise HTTPException(400, "Os arquivos enviados não contêm vídeos compatíveis.")
        item = db.create_job(job_id, payload.model_dump())
        persisted = True
        return enrich(item)
    finally:
        for upload in files:
            await upload.close()
        if not persisted and workspace.exists():
            await run_in_threadpool(shutil.rmtree, workspace)


@app.get("/api/drive/files")
def google_drive_files(folder_id: str = "root", search: str = ""):
    try:
        return list_files(folder_id, search)
    except Exception as error:
        raise HTTPException(400, str(error)) from error


@app.post("/api/jobs/drive-import", status_code=201)
def import_from_drive(payload: DriveImport):
    if not payload.api_approved:
        raise HTTPException(400, "Autorize a análise visual para iniciar este trabalho.")
    job_id = uuid4().hex[:12]
    input_dir = JOBS_DIR / job_id / "input"
    try:
        downloaded = download_files(payload.file_ids, input_dir)
        saved = prepare_downloaded_inputs(downloaded, input_dir)
        if not saved:
            raise HTTPException(400, "Os arquivos escolhidos não contêm vídeos compatíveis.")
    except Exception as error:
        if input_dir.parent.exists():
            shutil.rmtree(input_dir.parent)
        if isinstance(error, HTTPException):
            raise
        raise HTTPException(400, str(error)) from error
    job_payload = JobCreate(
        title=payload.title,
        source_path=str(input_dir),
        process_context=payload.process_context,
        audience=payload.audience,
        detail_level=payload.detail_level,
        api_approved=True,
        api_budget_usd=payload.api_budget_usd,
    )
    item = db.create_job(job_id, job_payload.model_dump())
    db.event(job_id, "info", f"{len(downloaded)} arquivo(s) importado(s) diretamente do Google Drive.")
    return enrich(item)


@app.get("/api/jobs/{job_id}/report")
def report(job_id: str):
    if not db.get_job(job_id):
        raise HTTPException(404, "Trabalho não encontrado")
    path = JOBS_DIR / job_id / "relatorio.html"
    if not path.exists():
        raise HTTPException(404, "O relatório ainda não está pronto.")
    return FileResponse(path)


@app.get("/api/jobs/{job_id}/evidence/{filename}")
def evidence(job_id: str, filename: str):
    if not db.get_job(job_id):
        raise HTTPException(404, "Trabalho não encontrado")
    directory = (JOBS_DIR / job_id / "evidence").resolve()
    path = (directory / filename).resolve()
    if path.parent != directory or not path.is_file():
        raise HTTPException(404, "Evidência não encontrada")
    return FileResponse(path)


@app.get("/api/jobs/{job_id}/preview-processo.mp4")
def preview(job_id: str):
    if not db.get_job(job_id):
        raise HTTPException(404, "Trabalho não encontrado")
    path = JOBS_DIR / job_id / "preview-processo.mp4"
    if not path.exists():
        raise HTTPException(404, "O preview ainda não está pronto.")
    return FileResponse(path, media_type="video/mp4", filename=path.name, content_disposition_type="inline")


@app.get("/api/jobs/{job_id}/preview-download")
def download_preview(job_id: str):
    if not db.get_job(job_id):
        raise HTTPException(404, "Trabalho não encontrado")
    path = JOBS_DIR / job_id / "preview-processo.mp4"
    if not path.exists():
        raise HTTPException(404, "O preview ainda não está pronto.")
    return FileResponse(path, media_type="video/mp4", filename=path.name, content_disposition_type="attachment")


@app.get("/api/jobs/{job_id}/previews/{filename}")
def separated_preview(job_id: str, filename: str, download: bool = False):
    if not db.get_job(job_id):
        raise HTTPException(404, "Trabalho não encontrado")
    directory = (JOBS_DIR / job_id / "previews").resolve()
    path = (directory / filename).resolve()
    if path.parent != directory or path.suffix.lower() != ".mp4" or not path.exists():
        raise HTTPException(404, "Preview não encontrado")
    disposition = "attachment" if download else "inline"
    return FileResponse(path, media_type="video/mp4", filename=path.name, content_disposition_type=disposition)


@app.get("/api/jobs/{job_id}/recording")
def recording(job_id: str):
    item = db.get_job(job_id)
    if not item:
        raise HTTPException(404, "Trabalho não encontrado")
    path = recording_file(job_id, parsed_result(item))
    if not path:
        raise HTTPException(404, "A gravação analisada ainda não está disponível para download.")
    return FileResponse(path, filename=path.name, content_disposition_type="attachment")


@app.get("/api/jobs/{job_id}/documentacao-processo.pdf")
def documentation_pdf(job_id: str):
    item = db.get_job(job_id)
    if not item:
        raise HTTPException(404, "Trabalho não encontrado")
    workspace = JOBS_DIR / job_id
    path = workspace / "documentacao-processo.pdf"
    if not path.exists():
        report_path = workspace / "relatorio.json"
        if not report_path.exists():
            raise HTTPException(404, "A documentação ainda não está pronta para exportação.")
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            generated = write_pdf_document(item, report.get("documentation") or {}, workspace)
        except Exception as error:
            raise HTTPException(500, f"Não foi possível exportar a documentação em PDF: {error}") from error
        if not generated:
            raise HTTPException(503, "A exportação em PDF depende da biblioteca reportlab. Execute .\\setup.ps1 novamente.")
    return FileResponse(path, media_type="application/pdf", filename="documentacao-processo.pdf", content_disposition_type="attachment")


@app.get("/api/jobs/{job_id}/package")
def package(job_id: str):
    item = db.get_job(job_id)
    if not item:
        raise HTTPException(404, "Trabalho não encontrado")
    path = JOBS_DIR / job_id / "entrega-completa.zip"
    if not path.exists():
        raise HTTPException(404, "O pacote ainda não está pronto.")
    return FileResponse(path, media_type="application/zip", filename=f"{job_id}-documentacao-rpa.zip")


@app.post("/api/jobs/{job_id}/rebuild-documents", status_code=202)
def rebuild_documents(job_id: str):
    item = db.get_job(job_id)
    if not item:
        raise HTTPException(404, "Trabalho não encontrado")
    if item["status"] != "COMPLETED":
        raise HTTPException(409, "A análise precisa estar concluída para refazer somente os documentos.")
    availability = input_availability(item)
    if not availability["can_rebuild"]:
        raise HTTPException(409, availability["rebuild_unavailable_reason"])
    try:
        return enrich(db.enqueue_rebuild(job_id))
    except ValueError as error:
        raise HTTPException(409, "Este trabalho já está na fila ou em processamento.") from error


@app.get("/api/jobs/{job_id}/{filename}")
def deliverable(job_id: str, filename: str):
    allowed = {
        "documentacao-processo.docx", "procedimento-operacional.md", "requisitos-rpa.md",
        "matriz-evidencias.csv", "documentacao-processo.json", "roteiro-cortes.json", "transcricao.json",
    }
    if filename not in allowed or not db.get_job(job_id):
        raise HTTPException(404, "Entregável não encontrado")
    path = JOBS_DIR / job_id / filename
    if not path.exists():
        raise HTTPException(404, "O entregável ainda não está pronto.")
    return FileResponse(path, filename=filename, content_disposition_type="attachment")


@app.post("/api/jobs/{job_id}/drive")
def send_to_drive(job_id: str, payload: DriveUpload):
    item = db.get_job(job_id)
    if not item:
        raise HTTPException(404, "Trabalho não encontrado")
    package_path = JOBS_DIR / job_id / "entrega-completa.zip"
    if not package_path.exists():
        raise HTTPException(409, "A entrega ainda não está pronta.")
    try:
        result = upload_package(package_path, item["title"], payload.folder)
    except Exception as error:
        raise HTTPException(400, str(error)) from error
    db.event(job_id, "success", f"Pacote enviado ao Google Drive: {result.get('name', package_path.name)}")
    return result
