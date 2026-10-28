"""Versioned Drive asset storage; credentials stay in the local Drive adapter.

No background upload, permission changes, deletion or shared user credentials.
A snapshot is published only after every asset succeeds. Retrying an interrupted
snapshot reuses its content-addressed folder and assets rather than duplicating.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import tempfile
import threading
from pathlib import Path, PurePosixPath

from .documentation_profiles import document_catalog
from .evidence_documents import wants_previews
from .pipeline import VIDEO_EXTENSIONS, find_videos

_LOCK = threading.RLock()
FOLDER = "application/vnd.google-apps.folder"
EXTRA_DOCUMENTS = {"relatorio.html", "relatorio.json", "transcricao.json", "fontes.json",
                   "analise-visual.json", "manifesto-documentacao.json", "entrega-completa.zip"}


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def key(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def allowed(relative):
    path = PurePosixPath(relative)
    if not relative or "\\" in relative or ":" in relative or path.is_absolute() or ".." in path.parts or path.as_posix() != relative:
        return False
    if len(path.parts) == 1:
        # Union of all export profiles: recovery must also work for legacy jobs.
        from .documentation_profiles import GENERAL_EXPORTS
        return relative in EXTRA_DOCUMENTS | set(GENERAL_EXPORTS) | {
            "documentacao-processo.docx", "documentacao-processo.pdf", "documentacao-processo.json",
            "procedimento-operacional.md", "requisitos-rpa.md", "matriz-evidencias.csv",
            "intercambio-documentacao.zip", "preview-processo.mp4", "roteiro-cortes.json", "gravacao-consolidada.mp4"}
    if path.parts[0] == "input":
        return len(path.parts) == 2 and path.suffix.lower() in VIDEO_EXTENSIONS
    return len(path.parts) == 2 and ((path.parts[0] == "evidence" and path.suffix.lower() in {".png", ".jpg", ".jpeg"})
        or (path.parts[0] == "previews" and path.suffix.lower() == ".mp4")
        or (path.parts[0] == "roteiros" and path.suffix.lower() == ".json"))


def safe_target(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not allowed(relative) or not target.is_relative_to(root):
        raise ValueError("Caminho de arquivo não permitido no armazenamento.")
    return target


def inventory(job, workspace):
    workspace = Path(workspace).resolve()
    result = job.get("result_json") or {}
    sources = result.get("source_files") or []
    if not sources:
        try:
            sources = find_videos(Path(job["source_path"]))
        except (OSError, ValueError, KeyError):
            sources = []
    entries = []
    sources_complete = bool(sources)
    for index, value in enumerate(sources, 1):
        source = Path(value)
        if not source.is_file() and job["id"] in source.parts:
            source = workspace.joinpath(*source.parts[source.parts.index(job["id"]) + 1:])
        if not source.is_file() or source.suffix.lower() not in VIDEO_EXTENSIONS:
            sources_complete = False
            continue
        relative = f"input/{index:03}-{source.name}"
        if source.resolve().is_relative_to(workspace):
            stored_path = source.resolve().relative_to(workspace).as_posix()
            archived = {entry.get("path") for entry in (result.get("drive_storage") or {}).get("assets", [])}
            if stored_path.startswith("input/") and stored_path in archived:
                relative = stored_path
        entries.append((relative, source, "fontes"))
    consolidated = workspace / "gravacao-consolidada.mp4"
    if consolidated.is_file() and safe_target(workspace, "gravacao-consolidada.mp4").is_file():
        entries.append(("gravacao-consolidada.mp4", consolidated, "fontes"))
    names = EXTRA_DOCUMENTS | {name for name, _, _ in document_catalog(job)}
    if wants_previews(job):
        names |= {"preview-processo.mp4", "roteiro-cortes.json"}
    for name in sorted(names):
        target = safe_target(workspace, name)
        if target.is_file():
            entries.append((name, target, "documentos"))
    folders = [("evidence", "evidencias")]
    if wants_previews(job):
        folders += [("previews", "videos"), ("roteiros", "documentos")]
    for folder, category in folders:
        for path in sorted((workspace / folder).glob("*")):
            relative = path.relative_to(workspace).as_posix()
            if allowed(relative) and safe_target(workspace, relative).is_file():
                entries.append((relative, path, category))
    assets = [{"path": relative, "local": path, "category": category,
               "sha256": digest(path), "size": path.stat().st_size} for relative, path, category in entries]
    if not any(asset["path"].endswith(".pdf") for asset in assets):
        raise ValueError("Gere a documentação antes de arquivar esta análise.")
    return assets, sources_complete


class DriveAssetStore:
    """Inject a Drive v3 service; tests use a fake, production uses OAuth locally."""
    def __init__(self, service):
        self.files = service.files()

    def _find(self, parent, job_id, asset_key):
        literal = lambda value: value.replace("\\", "\\\\").replace("'", "\\'")
        query = (f"'{literal(parent)}' in parents and trashed = false and "
                 f"appProperties has {{ key='discovery_job' and value='{literal(job_id)}' }} and "
                 f"appProperties has {{ key='discovery_key' and value='{asset_key}' }}")
        response = self.files.list(q=query, pageSize=2, fields="files(id,name,mimeType,size,appProperties),nextPageToken",
                                   supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        found = response.get("files", [])
        if len(found) > 1 or response.get("nextPageToken"):
            raise ValueError("Foram encontradas cópias ambíguas no Drive. Revise a pasta antes de continuar.")
        return found[0] if found else None

    def _folder(self, parent, job_id, name, identity):
        asset_key = key(identity)
        found = self._find(parent, job_id, asset_key)
        if found:
            if found.get("mimeType") != FOLDER:
                raise ValueError("A estrutura remota não corresponde à pasta esperada.")
            return found["id"]
        return self.files.create(body={"name": name, "mimeType": FOLDER, "parents": [parent],
            "appProperties": {"discovery_job": job_id, "discovery_key": asset_key}},
            fields="id", supportsAllDrives=True).execute()["id"]

    def publish(self, job, workspace, parent):
        from googleapiclient.http import MediaFileUpload, MediaInMemoryUpload
        if not re.fullmatch(r"[A-Za-z0-9_-]+", parent or "") or parent == "root":
            raise ValueError("Escolha uma pasta de projeto no Drive em Integrações.")
        with _LOCK:
            metadata = self.files.get(fileId=parent, fields="mimeType,capabilities(canAddChildren),trashed", supportsAllDrives=True).execute()
            if metadata.get("trashed") or metadata.get("mimeType") != FOLDER or not metadata.get("capabilities", {}).get("canAddChildren"):
                raise ValueError("A pasta escolhida não permite adicionar arquivos.")
            assets, sources_complete = inventory(job, workspace)
            snapshot_key = key(json.dumps([(a["path"], a["sha256"], a["size"]) for a in assets], ensure_ascii=False))
            job_folder = self._folder(parent, job["id"], f'{job["title"][:100]} - {job["id"]}', "job")
            revision = self._folder(job_folder, job["id"], "revisao-" + snapshot_key[:16], snapshot_key)
            categories, published = {}, []
            for asset in assets:
                category = asset["category"]
                if category not in categories:
                    categories[category] = self._folder(revision, job["id"], category, snapshot_key + "/" + category)
                parent_id = categories[category]
                found = self._find(parent_id, job["id"], key(asset["path"]))
                if found:
                    if found.get("appProperties", {}).get("discovery_digest") != asset["sha256"] or int(found.get("size", -1)) != asset["size"]:
                        raise ValueError("Um arquivo remoto mudou. A revisão anterior não será sobrescrita.")
                    file_id = found["id"]
                else:
                    mime = mimetypes.guess_type(asset["path"])[0] or "application/octet-stream"
                    file_id = self.files.create(body={"name": PurePosixPath(asset["path"]).name, "parents": [parent_id],
                        "appProperties": {"discovery_job": job["id"], "discovery_key": key(asset["path"]), "discovery_digest": asset["sha256"]}},
                        media_body=MediaFileUpload(str(asset["local"]), mimetype=mime, resumable=True),
                        fields="id", supportsAllDrives=True).execute()["id"]
                if digest(asset["local"]) != asset["sha256"]:
                    raise ValueError("Um arquivo local mudou durante o envio. Tente arquivar novamente após concluir a revisão.")
                published.append({k: v for k, v in asset.items() if k != "local"} | {"file_id": file_id})
            snapshot = {"schema_version": 1, "job_id": job["id"], "revision": snapshot_key,
                        "folder_id": revision, "webViewLink": f"https://drive.google.com/drive/folders/{revision}",
                        "sources_complete": sources_complete, "assets": published}
            # Last remote write is the complete index. An interrupted upload is
            # resumable but never advertised as a complete snapshot by the app.
            if not self._find(revision, job["id"], key("snapshot-index")):
                self.files.create(body={"name": "manifesto-armazenamento.json", "parents": [revision],
                    "appProperties": {"discovery_job": job["id"], "discovery_key": key("snapshot-index")}},
                    media_body=MediaInMemoryUpload(json.dumps(snapshot, ensure_ascii=False).encode(), mimetype="application/json"),
                    fields="id", supportsAllDrives=True).execute()
            return snapshot

    def restore(self, job_id, workspace, snapshot):
        from googleapiclient.http import MediaIoBaseDownload
        if snapshot.get("schema_version") != 1 or snapshot.get("job_id") != job_id or not snapshot.get("assets"):
            raise ValueError("Não há índice de armazenamento válido para esta análise.")
        workspace = Path(workspace).resolve()
        assets = snapshot["assets"]
        paths = [asset["path"].casefold() for asset in assets]
        if len(paths) != len(set(paths)):
            raise ValueError("O índice contém destinos duplicados.")
        # Validate all paths before writing even the first file.
        targets = [(asset, safe_target(workspace, asset["path"])) for asset in assets]
        workspace.mkdir(parents=True, exist_ok=True)
        with _LOCK, tempfile.TemporaryDirectory(prefix=".drive-restore-", dir=workspace) as temporary:
            staged = []
            for index, (asset, target) in enumerate(targets):
                if target.exists():
                    if not target.is_file() or digest(target) != asset["sha256"]:
                        raise ValueError("Há arquivos locais diferentes. A recuperação não sobrescreve a entrega atual.")
                    continue
                remote = self.files.get(fileId=asset["file_id"], fields="appProperties,capabilities(canDownload),size,trashed", supportsAllDrives=True).execute()
                props = remote.get("appProperties", {})
                if remote.get("trashed") or not remote.get("capabilities", {}).get("canDownload") or props.get("discovery_job") != job_id or props.get("discovery_key") != key(asset["path"]) or props.get("discovery_digest") != asset["sha256"] or int(remote.get("size", -1)) != asset["size"]:
                    raise ValueError("O arquivo remoto não corresponde ao índice ou não permite download.")
                temporary_path = Path(temporary) / str(index)
                with temporary_path.open("xb") as stream:
                    downloader = MediaIoBaseDownload(stream, self.files.get_media(fileId=asset["file_id"], supportsAllDrives=True), chunksize=8 * 1024 * 1024)
                    done = False
                    while not done:
                        _, done = downloader.next_chunk()
                if temporary_path.stat().st_size != asset["size"] or digest(temporary_path) != asset["sha256"]:
                    raise ValueError("A verificação de integridade do arquivo falhou.")
                staged.append((temporary_path, target))
            for temporary_path, target in staged:
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary_path.replace(target)
            sources = [str(target) for asset, target in targets if asset["path"].startswith("input/")]
            video = str(workspace / "gravacao-consolidada.mp4") if (workspace / "gravacao-consolidada.mp4").is_file() else (sources[0] if len(sources) == 1 else None)
            return {"restored": len(staged), "sources": sources, "video": video}


def local_store():
    from .drive import credentials
    from googleapiclient.discovery import build
    creds = credentials()
    if not creds:
        raise ValueError("Conecte uma conta Google antes de usar o armazenamento.")
    return DriveAssetStore(build("drive", "v3", credentials=creds, cache_discovery=False))
