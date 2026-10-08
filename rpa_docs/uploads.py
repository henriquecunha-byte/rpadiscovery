from __future__ import annotations

import zipfile
import stat
from pathlib import Path

from fastapi import HTTPException

from .pipeline import VIDEO_EXTENSIONS


def safe_upload_path(root: Path, filename: str) -> Path:
    normalized = filename.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{prefix}{index}" for prefix in ("COM", "LPT") for index in range(1, 10)}
    if (normalized.startswith("/") or not parts or any(
        part == ".." or any(ord(char) < 32 or char in '<>:"|?*' for char in part)
        or part.endswith((".", " ")) or part.split(".")[0].upper() in reserved
        for part in parts
    )):
        raise HTTPException(400, "Nome de arquivo inválido no upload.")
    target = (root.joinpath(*parts)).resolve()
    if root.resolve() not in target.parents:
        raise HTTPException(400, "Destino de upload inválido.")
    return target


def unique_upload_path(path: Path) -> Path:
    candidate = path
    index = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        index += 1
    return candidate


def extract_video_zip(archive_path: Path, input_dir: Path) -> int:
    count = 0
    total_size = 0
    created = []
    extraction_root = unique_upload_path(input_dir / archive_path.stem)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members) > 2000:
                raise HTTPException(400, "O ZIP contém arquivos demais.")
            videos = []
            # Validate every selected entry before extracting any content.
            for member in members:
                if member.is_dir() or Path(member.filename).suffix.lower() not in VIDEO_EXTENSIONS:
                    continue
                target = safe_upload_path(extraction_root, member.filename)
                if member.flag_bits & 1 or stat.S_ISLNK(member.external_attr >> 16):
                    raise HTTPException(400, "O ZIP não pode conter vídeos protegidos por senha ou links simbólicos.")
                if member.file_size == 0:
                    raise HTTPException(400, "O ZIP contém um vídeo vazio.")
                total_size += member.file_size
                if total_size > 200 * 1024 * 1024 * 1024:
                    raise HTTPException(400, "O conteúdo descompactado excede o limite de 200 GB.")
                videos.append((member, target))
            for member, target in videos:
                target = unique_upload_path(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                created.append(target)
                with archive.open(member) as source, target.open("xb") as destination:
                    while chunk := source.read(1024 * 1024):
                        destination.write(chunk)
                count += 1
    except Exception as error:
        for target in created:
            target.unlink(missing_ok=True)
        if isinstance(error, (zipfile.BadZipFile, RuntimeError, NotImplementedError)):
            raise HTTPException(400, "O ZIP está inválido, corrompido ou usa uma compactação não suportada.") from error
        raise
    return count


def prepare_downloaded_inputs(paths: list[Path], input_dir: Path) -> int:
    count = 0
    for path in paths:
        if path.suffix.lower() == ".zip":
            count += extract_video_zip(path, input_dir)
        elif path.suffix.lower() in VIDEO_EXTENSIONS:
            count += 1
    return count
