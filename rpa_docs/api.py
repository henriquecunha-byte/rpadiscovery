from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import json
import os
import shutil
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .config import DATABASE, JOBS_DIR, STATIC_DIR, FFMPEG, FFPROBE
from .auth import install_auth
from .access import AccessScope, current_access, require_local_drive
from .database import Database
from .errors import log_failure
from .ai import is_configured as ai_is_configured
from .orchestrator import Orchestrator
from .schemas import DriveImport, DriveUpload, JobCreate, PromptSuggestion
from .pipeline import VIDEO_EXTENSIONS, suggest_process_prompt, write_pdf_document
from .documentation_profiles import GENERAL_EXPORTS, document_catalog, general_job
from .evidence_documents import wants_previews
from .uploads import extract_video_zip, prepare_downloaded_inputs, safe_upload_path, unique_upload_path
from .drive import authorization_url, download_files, exchange_code, list_files, status as drive_status, upload_package
from .drive_storage import local_store
from .drive import extract_folder_id
from .documentation_reader import snapshot as document_snapshot, export_pdf as export_document_pdf, package_matches, DocumentUnavailable


db = Database(DATABASE)
worker = Orchestrator(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker.start()
    yield
    worker.stop()


app = FastAPI(title="Btime RPA Docs", version="0.1.0", lifespan=lifespan)
install_auth(app)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, error: RequestValidationError):
    # Do not echo arbitrary request input or exception context into the UI.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
        for item in error.errors()
    ]})


@app.middleware("http")
async def prevent_stale_local_interface(request: Request, call_next):
    response = await call_next(request)
    route_path = request.scope.get("path", "")
    root_path = request.scope.get("root_path", "")
    if root_path and route_path.startswith(root_path + "/"):
        route_path = route_path[len(root_path):]
    if route_path == "/" or route_path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    elif route_path == "/api" or route_path.startswith("/api/"):
        # Media, ranges, errors and redirects must not survive an account change
        # in a shared browser or intermediary cache.
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        response.headers["Vary"] = ", ".join(dict.fromkeys([
            *[value.strip() for value in response.headers.get("Vary", "").split(",") if value.strip()],
            "Cookie", "Authorization",
        ]))
    return response


def owned_job(job_id: str, access: AccessScope) -> dict:
    item = db.get_job(job_id, owner_id=access.owner_id)
    if not item:
        # Do not reveal whether a different account owns this identifier.
        raise HTTPException(404, "Trabalho não encontrado")
    safe_job_path(job_id)
    return item


def safe_job_path(job_id: str, relative: str | Path = "") -> Path:
    """Never follow a restored symlink/junction into another job's workspace."""
    if not job_id or job_id in {".", ".."} or any(char in job_id for char in ("/", "\\", ":")):
        raise HTTPException(404, "Trabalho não encontrado")
    workspace = JOBS_DIR.resolve() / job_id
    declared = workspace / relative
    try:
        resolved_workspace = workspace.resolve()
        resolved = declared.resolve()
    except (OSError, RuntimeError):
        raise HTTPException(404, "Arquivo não encontrado") from None
    if resolved_workspace != workspace or resolved != declared or (resolved != workspace and workspace not in resolved.parents):
        raise HTTPException(404, "Arquivo não encontrado")
    return resolved


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
    workspace = safe_job_path(job_id)
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
    workspace = safe_job_path(job["id"])
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
    evidence_available = not result.get("evidence_count") or any(path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"} for path in (workspace / "evidence").glob("*"))
    rebuild_available = bool((recordings_available or not wants_previews(job)) and evidence_available and (workspace / "relatorio.json").is_file() and (workspace / "transcricao.json").is_file())
    retry_available = rebuild_available if job.get("operation") == "rebuild" else source_available
    return {
        "source_available": source_available,
        "can_retry": job["status"] in {"FAILED", "CANCELLED"} and retry_available,
        "retry_unavailable_reason": "Os arquivos deste trabalho não estão disponíveis neste ambiente. Restaure a pasta original do trabalho ou reutilize o pedido e envie as gravações novamente." if not retry_available else None,
        "can_rebuild": job["status"] == "COMPLETED" and rebuild_available,
        "rebuild_unavailable_reason": "Para revisar os cortes e documentos, restaure as gravações, a transcrição e as evidências deste trabalho. Você também pode reutilizar o pedido e enviar as gravações novamente." if not rebuild_available else None,
    }


def enrich(job: dict, access: AccessScope) -> dict:
    job["delivery_mode"] = (job.get("contexto") or {}).get("modoEntrega", "documentacao_previews")
    workspace = safe_job_path(job["id"])
    preview_path = safe_job_path(job["id"], "preview-processo.mp4")
    preview_version = preview_path.stat().st_mtime_ns if preview_path.exists() else None
    result = parsed_result(job)
    job["result_json"] = result
    snapshot = result.get("drive_storage") or {}
    job["drive_storage"] = {key: snapshot.get(key) for key in ("webViewLink", "revision", "sources_complete")} | {"asset_count": len(snapshot.get("assets") or [])} if snapshot else None
    preview_items = []
    for item in result.get("previews") or []:
        if not isinstance(item, dict):
            continue
        relative = Path(item.get("file") or "")
        path = safe_job_path(job["id"], relative)
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
    document_stem = "documentacao" if general_job(job) else "documentacao-processo"
    job["document_url"] = f"/api/jobs/{job['id']}/{document_stem}.docx" if (workspace / f"{document_stem}.docx").exists() else None
    job["pdf_url"] = f"/api/jobs/{job['id']}/{document_stem}.pdf" if (workspace / "relatorio.json").exists() else None
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
        for filename, label, file_format in document_catalog(job)
    ]
    report_data = workspace / "relatorio.json"
    job["documentation_url"] = f"/api/jobs/{job['id']}/documentation" if job["status"] == "COMPLETED" and report_data.is_file() else None
    job["documentation_revision"] = str(report_data.stat().st_mtime_ns) if job["documentation_url"] else None
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
    job["timing"] = db.timing(job, owner_id=access.owner_id)
    if access.is_local:
        job["output_dir"] = str(workspace.resolve())
    else:
        # File access goes through the authorized endpoints, never client-chosen
        # server paths. Keep paths out of account-facing metadata.
        job.pop("source_path", None)
        job.pop("output_dir", None)
        job["result_json"] = {key: value for key, value in result.items() if key not in {"video", "source_files", "drive_storage"}}
        job["previews"] = [{key: value for key, value in item.items() if key != "source_path"} for item in job["previews"]]
        if isinstance(job["result_json"].get("previews"), list):
            job["result_json"]["previews"] = [{key: value for key, value in item.items() if key != "source_path"} for item in job["result_json"]["previews"] if isinstance(item, dict)]
    return job


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {
        "status": "ok", "worker": worker.thread.is_alive(),
        "ffmpeg": bool(shutil.which(FFMPEG)), "ffprobe": bool(shutil.which(FFPROBE)),
        "api_configured": ai_is_configured(),
    }


@app.get("/api/drive/status")
def google_drive_status(access: AccessScope = Depends(current_access)):
    if not access.is_local:
        return {"configured": False, "connected": False, "user_connection_pending": True,
                "message": "A conexão individual com o Google Drive ainda não foi configurada. A conta do ambiente local não é compartilhada."}
    try:
        return drive_status()
    except Exception as error:
        log_failure("drive_status", error)
        return {"configured": True, "connected": False, "error": "Não foi possível verificar a conexão com o Google Drive. Tente conectar novamente."}


@app.get("/api/drive/connect")
def connect_google_drive(access: AccessScope = Depends(current_access)):
    require_local_drive(access)
    try:
        return RedirectResponse(authorization_url())
    except Exception as error:
        log_failure("drive_connect", error)
        raise HTTPException(400, "Não foi possível iniciar a conexão com o Google Drive. Confira a configuração do ambiente.") from None


@app.get("/api/drive/callback")
def google_drive_callback(request: Request, state: str, access: AccessScope = Depends(current_access)):
    require_local_drive(access)
    try:
        exchange_code(str(request.url), state)
    except Exception as error:
        log_failure("drive_callback", error)
        raise HTTPException(400, "Não foi possível concluir a conexão com o Google Drive. Inicie a conexão novamente.") from None
    return RedirectResponse("/?drive=connected")


@app.post("/api/prompt/suggest")
def suggest_prompt(payload: PromptSuggestion, access: AccessScope = Depends(current_access)):
    try:
        return suggest_process_prompt(payload.model_dump())
    except Exception as error:
        log_failure("prompt_suggestion", error)
        return {"ok": False, "code": "ai_unavailable"}


@app.get("/api/jobs")
def jobs(access: AccessScope = Depends(current_access)):
    return [enrich(item, access) for item in db.list_jobs(owner_id=access.owner_id)]


@app.post("/api/jobs/cleanup")
def cleanup_jobs(access: AccessScope = Depends(current_access)):
    jobs_root = JOBS_DIR.resolve()
    def remove_workspace(job_id):
        workspace = safe_job_path(job_id)
        if workspace.parent != jobs_root:
            raise HTTPException(400, "Pasta de trabalho inválida durante a limpeza.")
        if workspace.exists():
            shutil.rmtree(workspace)
            return True
        return False
    try:
        removed_jobs, removed_folders = db.cleanup(remove_workspace, owner_id=access.owner_id)
    except OSError as error:
        raise HTTPException(409, "Não foi possível remover um arquivo em uso. Aguarde e tente novamente.") from error
    return {"removed_jobs": removed_jobs, "removed_folders": removed_folders}


@app.get("/api/jobs/{job_id}")
def job(job_id: str, access: AccessScope = Depends(current_access)):
    return enrich(owned_job(job_id, access), access)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str, access: AccessScope = Depends(current_access)):
    owned_job(job_id, access)
    try:
        item = db.request_cancel(job_id, owner_id=access.owner_id)
    except ValueError as error:
        raise HTTPException(409, "Este trabalho não pode mais ser cancelado.") from error
    if not item:
        raise HTTPException(404, "Trabalho não encontrado")
    return enrich(item, access)


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str, access: AccessScope = Depends(current_access)):
    current = owned_job(job_id, access)
    if current and current["status"] in {"FAILED", "CANCELLED"}:
        availability = input_availability(current)
        if not availability["can_retry"]:
            raise HTTPException(409, availability["retry_unavailable_reason"])
        source = existing_job_path(job_id, current["source_path"])
        if source and str(source) != current["source_path"]:
            db.update(job_id, source_path=str(source), owner_id=access.owner_id)
    try:
        item = db.retry(job_id, owner_id=access.owner_id)
    except ValueError as error:
        raise HTTPException(409, "Somente trabalhos com falha ou cancelados podem ser retomados.") from error
    if not item:
        raise HTTPException(404, "Trabalho não encontrado")
    return enrich(item, access)


@app.post("/api/jobs", status_code=201)
def create_job(payload: JobCreate, access: AccessScope = Depends(current_access)):
    if not access.is_local:
        raise HTTPException(403, "Para esta conta, envie o vídeo, a pasta ou o ZIP pelo seletor de arquivos. Caminhos internos do servidor não podem ser importados.")
    source = Path(payload.source_path).resolve()
    jobs_root = JOBS_DIR.resolve()
    def reserved(path: Path) -> bool:
        resolved = path.resolve()
        return resolved == jobs_root or jobs_root in resolved.parents or resolved in jobs_root.parents
    if reserved(source):
        raise HTTPException(400, "A pasta interna de análises não pode ser usada como origem. Envie uma gravação original pelo seletor de arquivos.")
    if not source.exists():
        raise HTTPException(400, "A gravação ou pasta selecionada não foi encontrada.")
    if source.is_file() and source.suffix.lower() not in VIDEO_EXTENSIONS:
        raise HTTPException(400, "Selecione um vídeo compatível ou uma pasta com gravações.")
    if source.is_dir() and not any(path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS for path in source.rglob("*")):
        raise HTTPException(400, "A pasta selecionada não contém vídeos compatíveis.")
    if source.is_dir() and any(reserved(path) for path in source.rglob("*") if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS):
        raise HTTPException(400, "A seleção contém uma referência à pasta interna de análises. Envie apenas gravações originais.")
    if not payload.api_approved:
        raise HTTPException(400, "Autorize a análise visual para iniciar este trabalho.")
    return enrich(db.create_job(uuid4().hex[:12], payload.model_dump() | {"source_path": str(source)}, owner_id=access.owner_id), access)


@app.post("/api/jobs/upload", status_code=201)
async def upload_job(
    title: str = Form(""),
    process_context: str = Form(""),
    audience: str = Form("Equipe"),
    detail_level: str = Form("operacional"),
    api_approved: bool = Form(False),
    api_budget_usd: float = Form(1.0),
    contexto: str | None = Form(None),
    files: list[UploadFile] = File(...),
    access: AccessScope = Depends(current_access),
):
    job_id = uuid4().hex[:12]
    workspace = JOBS_DIR / job_id
    input_dir = workspace / "input"
    persisted = False
    try:
        if not api_approved:
            raise HTTPException(400, "Autorize a análise visual para iniciar este trabalho.")
        try:
            structured_context = json.loads(contexto) if contexto is not None else None
            if contexto is not None and not isinstance(structured_context, dict):
                raise HTTPException(422, "O contexto deve ser um objeto JSON válido.")
            payload = JobCreate(
                title=title, source_path=str(input_dir), process_context=process_context,
                audience=audience, detail_level=detail_level,
                api_approved=True, api_budget_usd=api_budget_usd, contexto=structured_context,
            )
        except json.JSONDecodeError:
            raise HTTPException(422, "Não foi possível ler o contexto. Revise os campos e tente novamente.") from None
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
        item = db.create_job(job_id, payload.model_dump(), owner_id=access.owner_id)
        persisted = True
        return enrich(item, access)
    finally:
        for upload in files:
            await upload.close()
        if not persisted and workspace.exists():
            await run_in_threadpool(shutil.rmtree, workspace)


@app.get("/api/drive/files")
def google_drive_files(folder_id: str = "root", search: str = "", access: AccessScope = Depends(current_access)):
    require_local_drive(access)
    try:
        return list_files(folder_id, search)
    except Exception as error:
        log_failure("drive_files", error)
        raise HTTPException(400, "Não foi possível listar os arquivos do Google Drive. Confira sua conexão e tente novamente.") from None


@app.post("/api/jobs/drive-import", status_code=201)
def import_from_drive(payload: DriveImport, access: AccessScope = Depends(current_access)):
    require_local_drive(access)
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
        log_failure("drive_import", error)
        raise HTTPException(400, "Não foi possível importar os arquivos do Google Drive. Confira o acesso aos arquivos e tente novamente.") from None
    job_payload = JobCreate(
        title=payload.title,
        source_path=str(input_dir),
        process_context=payload.process_context,
        audience=payload.audience,
        detail_level=payload.detail_level,
        api_approved=True,
        api_budget_usd=payload.api_budget_usd,
        contexto=payload.contexto,
    )
    item = db.create_job(job_id, job_payload.model_dump(), owner_id=access.owner_id)
    db.event(job_id, "info", f"{len(downloaded)} arquivo(s) importado(s) diretamente do Google Drive.")
    return enrich(item, access)


@app.get("/api/jobs/{job_id}/report")
def report(job_id: str, access: AccessScope = Depends(current_access)):
    owned_job(job_id, access)
    path = safe_job_path(job_id, "relatorio.html")
    if not path.exists():
        raise HTTPException(404, "O relatório ainda não está pronto.")
    return FileResponse(path)


def readable_document(job_id, access, version=None):
    item = owned_job(job_id, access)
    if item["status"] != "COMPLETED":
        raise HTTPException(409, "A documentação ficará disponível quando a análise terminar.")
    try:
        saved = document_snapshot(item, safe_job_path(job_id))
    except DocumentUnavailable as error:
        raise HTTPException(404, str(error)) from None
    if version is not None and version != saved.version:
        raise HTTPException(409, "O documento foi atualizado. Atualize a leitura antes de exportar esta versão.")
    return saved


@app.get("/api/jobs/{job_id}/documentation")
def read_documentation(job_id: str, access: AccessScope = Depends(current_access)):
    return readable_document(job_id, access).public()


@app.get("/api/jobs/{job_id}/documentation/pdf")
def export_read_document(job_id: str, version: str = Query(pattern=r"^[a-f0-9]{64}$"), access: AccessScope = Depends(current_access)):
    saved = readable_document(job_id, access, version)
    try:
        content = export_document_pdf(saved)
    except Exception as error:
        log_failure("pdf_export", error)
        raise HTTPException(503, "Não foi possível exportar este documento em PDF. Tente novamente ou baixe o ZIP.") from None
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="documentacao.pdf"', "X-Document-Version": saved.version})


@app.get("/api/jobs/{job_id}/documentation/package")
def export_read_package(job_id: str, version: str = Query(pattern=r"^[a-f0-9]{64}$"), access: AccessScope = Depends(current_access)):
    saved = readable_document(job_id, access, version)
    target = safe_job_path(job_id, "entrega-completa.zip")
    if not target.is_file():
        raise HTTPException(404, "O pacote desta análise não está disponível neste ambiente.")
    if not package_matches(saved, target):
        raise HTTPException(409, "O pacote salvo não corresponde a este documento. Revise os documentos da análise antes de baixar o ZIP.")
    return FileResponse(target, media_type="application/zip", filename=f"{job_id}-documentacao.zip", headers={"X-Document-Version": saved.version})


@app.get("/api/jobs/{job_id}/evidence/{filename}")
def evidence(job_id: str, filename: str, access: AccessScope = Depends(current_access)):
    owned_job(job_id, access)
    directory = safe_job_path(job_id, "evidence")
    path = safe_job_path(job_id, Path("evidence") / filename)
    if path.parent != directory or not path.is_file():
        raise HTTPException(404, "Evidência não encontrada")
    return FileResponse(path)


@app.get("/api/jobs/{job_id}/preview-processo.mp4")
def preview(job_id: str, access: AccessScope = Depends(current_access)):
    owned_job(job_id, access)
    path = safe_job_path(job_id, "preview-processo.mp4")
    if not path.exists():
        raise HTTPException(404, "O preview ainda não está pronto.")
    return FileResponse(path, media_type="video/mp4", filename=path.name, content_disposition_type="inline")


@app.get("/api/jobs/{job_id}/preview-download")
def download_preview(job_id: str, access: AccessScope = Depends(current_access)):
    owned_job(job_id, access)
    path = safe_job_path(job_id, "preview-processo.mp4")
    if not path.exists():
        raise HTTPException(404, "O preview ainda não está pronto.")
    return FileResponse(path, media_type="video/mp4", filename=path.name, content_disposition_type="attachment")


@app.get("/api/jobs/{job_id}/previews/{filename}")
def separated_preview(job_id: str, filename: str, download: bool = False, access: AccessScope = Depends(current_access)):
    owned_job(job_id, access)
    directory = safe_job_path(job_id, "previews")
    path = safe_job_path(job_id, Path("previews") / filename)
    if path.parent != directory or path.suffix.lower() != ".mp4" or not path.exists():
        raise HTTPException(404, "Preview não encontrado")
    disposition = "attachment" if download else "inline"
    return FileResponse(path, media_type="video/mp4", filename=path.name, content_disposition_type=disposition)


@app.get("/api/jobs/{job_id}/recording")
def recording(job_id: str, access: AccessScope = Depends(current_access)):
    item = owned_job(job_id, access)
    path = recording_file(job_id, parsed_result(item))
    if not path:
        raise HTTPException(404, "A gravação analisada ainda não está disponível para download.")
    return FileResponse(path, filename=path.name, content_disposition_type="attachment")


@app.get("/api/jobs/{job_id}/documentacao-processo.pdf")
@app.get("/api/jobs/{job_id}/documentacao.pdf")
def documentation_pdf(job_id: str, access: AccessScope = Depends(current_access)):
    item = owned_job(job_id, access)
    workspace = safe_job_path(job_id)
    filename = "documentacao.pdf" if general_job(item) else "documentacao-processo.pdf"
    path = safe_job_path(job_id, filename)
    if not path.exists():
        report_path = safe_job_path(job_id, "relatorio.json")
        if not report_path.exists():
            raise HTTPException(404, "A documentação ainda não está pronta para exportação.")
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            generated = write_pdf_document(item, report.get("documentation") or {}, workspace)
        except Exception as error:
            log_failure("pdf_export", error)
            raise HTTPException(500, "Não foi possível exportar a documentação em PDF. Tente novamente ou baixe o documento Word.") from None
        if not generated:
            raise HTTPException(503, "A exportação em PDF depende da biblioteca reportlab. Execute .\\setup.ps1 novamente.")
    return FileResponse(path, media_type="application/pdf", filename=filename, content_disposition_type="attachment")


@app.get("/api/jobs/{job_id}/package")
def package(job_id: str, access: AccessScope = Depends(current_access)):
    owned_job(job_id, access)
    path = safe_job_path(job_id, "entrega-completa.zip")
    if not path.exists():
        raise HTTPException(404, "O pacote ainda não está pronto.")
    return FileResponse(path, media_type="application/zip", filename=f"{job_id}-documentacao.zip")


@app.post("/api/jobs/{job_id}/rebuild-documents", status_code=202)
def rebuild_documents(job_id: str, access: AccessScope = Depends(current_access)):
    item = owned_job(job_id, access)
    if item["status"] != "COMPLETED":
        raise HTTPException(409, "A análise precisa estar concluída para refazer somente os documentos.")
    availability = input_availability(item)
    if not availability["can_rebuild"]:
        raise HTTPException(409, availability["rebuild_unavailable_reason"])
    try:
        return enrich(db.enqueue_rebuild(job_id, owner_id=access.owner_id), access)
    except ValueError as error:
        raise HTTPException(409, "Este trabalho já está na fila ou em processamento.") from error


@app.get("/api/jobs/{job_id}/{filename}")
def deliverable(job_id: str, filename: str, access: AccessScope = Depends(current_access)):
    owned_job(job_id, access)
    allowed = {
        "documentacao-processo.docx", "procedimento-operacional.md", "requisitos-rpa.md",
        "matriz-evidencias.csv", "documentacao-processo.json", "roteiro-cortes.json", "transcricao.json",
    }
    allowed.update(GENERAL_EXPORTS)
    allowed.update({"manifesto-documentacao.json", "intercambio-documentacao.zip", "fontes.json"})
    if filename not in allowed:
        raise HTTPException(404, "Entregável não encontrado")
    path = safe_job_path(job_id, filename)
    if not path.exists():
        raise HTTPException(404, "O entregável ainda não está pronto.")
    return FileResponse(path, filename=filename, content_disposition_type="attachment")


@app.post("/api/jobs/{job_id}/drive")
def send_to_drive(job_id: str, payload: DriveUpload, access: AccessScope = Depends(current_access)):
    item = owned_job(job_id, access)
    require_local_drive(access)
    if item["status"] != "COMPLETED":
        raise HTTPException(409, "Conclua a análise antes de enviar a entrega.")
    package_path = safe_job_path(job_id, "entrega-completa.zip")
    if not package_path.exists():
        raise HTTPException(409, "A entrega ainda não está pronta.")
    try:
        if payload.include_assets:
            snapshot = local_store().publish(item, safe_job_path(job_id), extract_folder_id(payload.folder))
            db.save_drive_snapshot(job_id, snapshot, expected_updated_at=item["updated_at"], owner_id=access.owner_id)
            db.event(job_id, "success", "Revisão arquivada no Drive com índice de arquivos e integridade.")
            return {"webViewLink": snapshot["webViewLink"], "asset_count": len(snapshot["assets"]), "sources_complete": snapshot["sources_complete"]}
        result = upload_package(package_path, item["title"], payload.folder)
    except Exception as error:
        log_failure("drive_upload", error)
        raise HTTPException(400, "Não foi possível enviar o pacote ao Google Drive. Confira a pasta de destino e tente novamente.") from None
    db.event(job_id, "success", f"Pacote enviado ao Google Drive: {result.get('name', package_path.name)}")
    return result


@app.post("/api/jobs/{job_id}/drive/restore")
def restore_from_drive(job_id: str, access: AccessScope = Depends(current_access)):
    item = owned_job(job_id, access)
    require_local_drive(access)
    if item["status"] != "COMPLETED":
        raise HTTPException(409, "Aguarde a análise terminar antes de recuperar seus arquivos.")
    snapshot = parsed_result(item).get("drive_storage")
    if not snapshot:
        raise HTTPException(409, "Esta análise ainda não foi arquivada com seus arquivos no Drive.")
    try:
        restored = local_store().restore(job_id, safe_job_path(job_id), snapshot)
        if restored.get("sources"):
            db.save_restored_sources(job_id, restored["sources"], restored.get("video"), owner_id=access.owner_id)
    except Exception as error:
        log_failure("drive_restore", error)
        raise HTTPException(400, "Não foi possível recuperar os arquivos. Confira o acesso ao Drive e se há arquivos locais diferentes; nada existente será sobrescrito.") from None
    db.event(job_id, "success", f'Arquivos recuperados do Drive: {restored["restored"]}.')
    return {"restored": restored["restored"], "job": enrich(owned_job(job_id, access), access)}
