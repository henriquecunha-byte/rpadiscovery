from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from .config import DATA_DIR


TOKEN_PATH = DATA_DIR / "google-drive-token.json"
STATE_PATH = DATA_DIR / "google-drive-oauth-state.txt"
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
]


def configured() -> bool:
    return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))


def client_config() -> dict:
    return {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8770/api/drive/callback")],
        }
    }


def authorization_url() -> str:
    if not configured():
        raise RuntimeError("Configure o cliente OAuth do Google antes de conectar uma conta.")
    from google_auth_oauthlib.flow import Flow

    state = secrets.token_urlsafe(32)
    STATE_PATH.write_text(state, encoding="utf-8")
    flow = Flow.from_client_config(client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8770/api/drive/callback")
    url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    return url


def exchange_code(full_url: str, state: str):
    if not STATE_PATH.exists() or not secrets.compare_digest(STATE_PATH.read_text(encoding="utf-8"), state):
        raise RuntimeError("A autorização do Google expirou ou não corresponde a esta sessão.")
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8770/api/drive/callback")
    flow.fetch_token(authorization_response=full_url)
    TOKEN_PATH.write_text(flow.credentials.to_json(), encoding="utf-8")
    STATE_PATH.unlink(missing_ok=True)


def credentials():
    if not TOKEN_PATH.exists():
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds if creds.valid else None


def status() -> dict:
    creds = credentials() if configured() else None
    return {
        "configured": configured(),
        "connected": bool(creds),
        "default_folder_id": os.getenv("GOOGLE_DRIVE_FOLDER_ID", ""),
        "scope": "Leitura das fontes escolhidas e gravação das entregas",
    }


def extract_folder_id(value: str) -> str:
    value = (value or "").strip()
    if "/folders/" in value:
        value = value.split("/folders/", 1)[1].split("?", 1)[0].split("/", 1)[0]
    return value or os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")


def upload_package(package: Path, job_title: str, folder: str = "") -> dict:
    creds = credentials()
    if not creds:
        raise RuntimeError("Conecte uma conta do Google Drive antes de enviar a entrega.")
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    folder_id = extract_folder_id(folder)
    metadata = {"name": f"{job_title} - documentação RPA.zip"}
    if folder_id:
        metadata["parents"] = [folder_id]
    media = MediaFileUpload(str(package), mimetype="application/zip", resumable=True)
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    result = service.files().create(body=metadata, media_body=media, fields="id,name,webViewLink,parents").execute()
    return result


def list_files(folder_id: str = "root", search: str = "") -> list[dict]:
    creds = credentials()
    if not creds:
        raise RuntimeError("Conecte uma conta do Google Drive antes de escolher arquivos.")
    from googleapiclient.discovery import build

    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    folder_id = extract_folder_id(folder_id) or "root"
    query = f"'{folder_id}' in parents and trashed = false"
    if search.strip():
        escaped = search.strip().replace("'", "\\'")
        query += f" and name contains '{escaped}'"
    result = service.files().list(
        q=query,
        pageSize=200,
        orderBy="folder,name_natural",
        fields="files(id,name,mimeType,size,modifiedTime,webViewLink)",
    ).execute()
    allowed = {"application/zip", "application/x-zip-compressed", "application/vnd.google-apps.folder"}
    return [item for item in result.get("files", []) if item.get("mimeType", "").startswith("video/") or item.get("mimeType") in allowed]


def download_files(file_ids: list[str], destination: Path) -> list[Path]:
    creds = credentials()
    if not creds:
        raise RuntimeError("Conecte uma conta do Google Drive antes de importar arquivos.")
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    destination.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for file_id in file_ids:
        metadata = service.files().get(fileId=file_id, fields="id,name,mimeType,size").execute()
        if metadata.get("mimeType") == "application/vnd.google-apps.folder":
            raise RuntimeError("Abra a pasta no seletor e escolha os vídeos ou ZIPs dentro dela.")
        name = Path(metadata.get("name") or file_id).name
        target = destination / name
        request = service.files().get_media(fileId=file_id)
        with target.open("wb") as stream:
            downloader = MediaIoBaseDownload(stream, request, chunksize=8 * 1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        downloaded.append(target)
    return downloaded
