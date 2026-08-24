from __future__ import annotations

import zipfile
from pathlib import Path

from fastapi import HTTPException

from .pipeline import VIDEO_EXTENSIONS


def safe_upload_path(root: Path, filename: str) -> Path:
    parts = [part for part in filename.replace("\\", "/").split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise HTTPException(400, "Nome de arquivo inválido no upload.")
    target = (root.joinpath(*parts)).resolve()
    if root.resolve() not in target.parents:
        raise HTTPException(400, "Destino de upload inválido.")
    return target


def extract_video_zip(archive_path: Path, input_dir: Path) -> int:
    count = 0
    total_size = 0
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) > 2000:
            raise HTTPException(400, "O ZIP contém arquivos demais.")
        for member in members:
            if member.is_dir() or Path(member.filename).suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            total_size += member.file_size
            if total_size > 200 * 1024 * 1024 * 1024:
                raise HTTPException(400, "O conteúdo descompactado excede o limite de 200 GB.")
            target = safe_upload_path(input_dir / archive_path.stem, member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as destination:
                while chunk := source.read(1024 * 1024):
                    destination.write(chunk)
            count += 1
    return count


def prepare_downloaded_inputs(paths: list[Path], input_dir: Path) -> int:
    count = 0
    for path in paths:
        if path.suffix.lower() == ".zip":
            count += extract_video_zip(path, input_dir)
        elif path.suffix.lower() in VIDEO_EXTENSIONS:
            count += 1
    return count
