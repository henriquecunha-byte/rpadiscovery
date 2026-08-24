from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import json
import shutil

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import DATABASE, JOBS_DIR, STATIC_DIR
from .database import Database
from .orchestrator import Orchestrator
from .schemas import DriveImport, DriveUpload, JobCreate
from .pipeline import VIDEO_EXTENSIONS, create_job_previews, create_package, synthesize_documentation, write_report
from .uploads import extract_video_zip, prepare_downloaded_inputs, safe_upload_path
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


def enrich(job: dict) -> dict:
    workspace = JOBS_DIR / job["id"]
    preview_path = workspace / "preview-processo.mp4"
    preview_version = preview_path.stat().st_mtime_ns if preview_path.exists() else None
    result = job.get("result_json") or {}
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            result = {}
    if not isinstance(result, dict):
        result = {}
    preview_items = []
    for item in result.get("previews") or []:
        relative = Path(item.get("file") or "")
        path = workspace / relative
        if not item.get("created"):
            preview_items.append(dict(item) | {"preview_url": None, "download_url": None})
            continue
        if not relative.name or not path.exists():
            continue
        version = path.stat().st_mtime_ns
        if relative.parent.as_posix() == "previews":
            url = f"/api/jobs/{job['id']}/previews/{relative.name}?v={version}"
            download_url = f"/api/jobs/{job['id']}/previews/{relative.name}?download=true&v={version}"
        else:
            url = f"/api/jobs/{job['id']}/preview-processo.mp4?v={version}"
            download_url = f"/api/jobs/{job['id']}/preview-download?v={version}"
        preview_items.append(dict(item) | {"preview_url": url, "download_url": download_url})
    if not preview_items and preview_version:
        preview_items = [{
            "index": 1,
            "source_name": Path(result.get("video") or "Gravação").name,
            "duration": (result.get("preview") or {}).get("duration", 0),
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
    job["package_url"] = f"/api/jobs/{job['id']}/package" if (workspace / "entrega-completa.zip").exists() else None
    job["output_dir"] = str(workspace.resolve())
    job["timing"] = db.timing(job)
    return job


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "worker": worker.thread.is_alive()}


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


@app.get("/api/jobs")
def jobs():
    return [enrich(item) for item in db.list_jobs()]


@app.post("/api/jobs/cleanup")
def cleanup_jobs():
    job_ids = db.cleanup_candidates()
    removed_folders = 0
    jobs_root = JOBS_DIR.resolve()
    for job_id in job_ids:
        workspace = (JOBS_DIR / job_id).resolve()
        if workspace.parent != jobs_root:
            raise HTTPException(400, "Pasta de trabalho inválida durante a limpeza.")
        if workspace.exists():
            shutil.rmtree(workspace)
            removed_folders += 1
    removed_jobs = db.delete_jobs(job_ids)
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
    if not payload.api_approved:
        raise HTTPException(400, "Autorize a análise visual para iniciar este trabalho.")
    return enrich(db.create_job(uuid4().hex[:12], payload.model_dump()))


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
    if not api_approved:
        raise HTTPException(400, "Autorize a análise visual para iniciar este trabalho.")
    job_id = uuid4().hex[:12]
    input_dir = JOBS_DIR / job_id / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in VIDEO_EXTENSIONS | {".zip"}:
            continue
        target = safe_upload_path(input_dir, upload.filename or f"video-{saved + 1}.mp4")
        if target.exists():
            original = target
            duplicate = 2
            while target.exists():
                target = original.with_name(f"{original.stem}-{duplicate}{original.suffix}")
                duplicate += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as destination:
            while chunk := await upload.read(1024 * 1024):
                destination.write(chunk)
        await upload.close()
        saved += extract_video_zip(target, input_dir) if suffix == ".zip" else 1
    if not saved:
        raise HTTPException(400, "Envie pelo menos um vídeo compatível.")
    payload = JobCreate(
        title=title,
        source_path=str(input_dir),
        process_context=process_context,
        audience=audience,
        detail_level=detail_level,
        api_approved=True,
        api_budget_usd=api_budget_usd,
    )
    return enrich(db.create_job(job_id, payload.model_dump()))


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
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(400, str(error)) from error
    if not saved:
        raise HTTPException(400, "Os arquivos escolhidos não contêm vídeos compatíveis.")
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
    directory = (JOBS_DIR / job_id / "evidence").resolve()
    path = (directory / filename).resolve()
    if path.parent != directory or not path.exists():
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


@app.get("/api/jobs/{job_id}/package")
def package(job_id: str):
    item = db.get_job(job_id)
    if not item:
        raise HTTPException(404, "Trabalho não encontrado")
    path = JOBS_DIR / job_id / "entrega-completa.zip"
    if not path.exists():
        raise HTTPException(404, "O pacote ainda não está pronto.")
    return FileResponse(path, media_type="application/zip", filename=f"{job_id}-documentacao-rpa.zip")


@app.post("/api/jobs/{job_id}/rebuild-documents")
def rebuild_documents(job_id: str):
    item = db.get_job(job_id)
    if not item:
        raise HTTPException(404, "Trabalho não encontrado")
    if item["status"] != "COMPLETED":
        raise HTTPException(409, "A análise precisa estar concluída para refazer somente os documentos.")
    workspace = JOBS_DIR / job_id
    report_path = workspace / "relatorio.json"
    transcript_path = workspace / "transcricao.json"
    if not report_path.exists() or not transcript_path.exists():
        raise HTTPException(409, "Os insumos deste trabalho não estão disponíveis para gerar os novos documentos.")
    try:
        old_report = json.loads(report_path.read_text(encoding="utf-8"))
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
        raw_analysis_path = workspace / "analise-visual.json"
        steps = json.loads(raw_analysis_path.read_text(encoding="utf-8")) if raw_analysis_path.exists() else (old_report.get("evidence_steps") or old_report.get("steps") or [])
        if not raw_analysis_path.exists():
            raw_analysis_path.write_text(json.dumps(steps, ensure_ascii=False, indent=2), encoding="utf-8")
        result = item.get("result_json") or {}
        if isinstance(result, str):
            result = json.loads(result)
        if not isinstance(result, dict):
            result = {}
        video = Path(result.get("video") or item["source_path"])
        source_videos = [Path(path) for path in result.get("source_files") or [video]]
        documentation = synthesize_documentation(item, steps, transcript, workspace)
        preview, source_previews = create_job_previews(video, source_videos, steps, workspace, documentation.get("preview_moments", []))
        write_report(item, steps, workspace, video, documentation, source_previews)
        create_package(workspace)
        result["process_step_count"] = len(documentation.get("process_flow", []))
        result["preview"] = preview
        result["previews"] = source_previews
        result["deliverables"] = [
            "relatorio.html", "documentacao-processo.docx", "procedimento-operacional.md",
            "requisitos-rpa.md", "matriz-evidencias.csv", "documentacao-processo.json", "previews separados", "roteiro-cortes.json",
        ]
        db.update(job_id, result_json=result)
        db.event(job_id, "success", "Documentos e preview revisados por relevância contextual do assunto, sem repetir a transcrição.")
        return enrich(db.get_job(job_id))
    except Exception as error:
        raise HTTPException(500, f"Não foi possível revisar os documentos e cortes: {error}") from error


@app.get("/api/jobs/{job_id}/{filename}")
def deliverable(job_id: str, filename: str):
    allowed = {
        "documentacao-processo.docx", "procedimento-operacional.md", "requisitos-rpa.md",
        "matriz-evidencias.csv", "documentacao-processo.json",
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
