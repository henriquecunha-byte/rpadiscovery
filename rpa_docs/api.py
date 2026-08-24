from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import DATABASE, JOBS_DIR, STATIC_DIR
from .database import Database
from .orchestrator import Orchestrator
from .schemas import DriveImport, DriveUpload, JobCreate
from .pipeline import VIDEO_EXTENSIONS
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
    job["report_url"] = f"/api/jobs/{job['id']}/report" if (workspace / "relatorio.html").exists() else None
    job["preview_url"] = f"/api/jobs/{job['id']}/preview-processo.mp4" if (workspace / "preview-processo.mp4").exists() else None
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
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@app.get("/api/jobs/{job_id}/package")
def package(job_id: str):
    item = db.get_job(job_id)
    if not item:
        raise HTTPException(404, "Trabalho não encontrado")
    path = JOBS_DIR / job_id / "entrega-completa.zip"
    if not path.exists():
        raise HTTPException(404, "O pacote ainda não está pronto.")
    return FileResponse(path, media_type="application/zip", filename=f"{job_id}-documentacao-rpa.zip")


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
