"""A saved document snapshot shared by the native reader and explicit exports.

Reading and exporting never invoke transcription, inference or the job queue.
The version includes referenced image bytes, not just the document timestamp.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from .config import CACHE_DIR
from .documentation_profiles import PROFILES, profile_id
from .evidence_documents import figure_catalog
from .pipeline import fallback_documentation, write_pdf_document


class DocumentUnavailable(ValueError):
    pass


@dataclass
class DocumentSnapshot:
    job: dict
    report: dict
    version: str
    figures: dict
    images: dict
    steps: list

    def public(self):
        evidence = []
        for ref, figure in self.figures.items():
            evidence.append({"id": ref, "title": figure.title, "description": figure.description,
                "source": figure.source, "timecode": figure.timecode, "uncertainty": figure.uncertainty,
                "available": figure.path is not None,
                "url": f'/api/jobs/{quote(self.job["id"], safe="")}/evidence/{quote(figure.path.name, safe="")}?v={self.version}' if figure.path else None,
                "width": figure.width, "height": figure.height,
                "warning": figure.unavailable if not figure.path else None})
        profile = profile_id(self.job)
        return {"version": self.version, "title": self.job["title"], "profile": profile,
                "profile_label": PROFILES.get(profile, PROFILES["processo"])["label"],
                "audience": self.job.get("audience") or "Equipe", "guide": self.job.get("process_context") or "",
                "documentation": self.report["documentation"], "evidence": evidence}


def referenced_ids(document):
    refs = set()
    for item in document.get("process_flow", []) + document.get("business_rules", []):
        if isinstance(item, dict):
            refs.update(str(ref) for ref in item.get("evidence_refs", []) if isinstance(ref, (str, int)))
    for section in document.get("sections", []):
        if isinstance(section, dict):
            for item in section.get("items", []):
                if isinstance(item, dict):
                    refs.update(str(ref) for ref in item.get("evidence_refs", []) if isinstance(ref, (str, int)))
    return refs


def snapshot(job, workspace):
    workspace = Path(workspace)
    try:
        original = (workspace / "relatorio.json").read_bytes()
    except FileNotFoundError:
        raise DocumentUnavailable("A documentação ainda não está disponível neste ambiente.") from None
    try:
        report = json.loads(original)
        if not isinstance(report, dict):
            raise ValueError()
        steps = report.get("evidence_steps") or report.get("steps") or []
        if not isinstance(steps, list):
            steps = []
        document = report.get("documentation")
        if not isinstance(document, dict) or not document:
            document = fallback_documentation(job, steps, "Registro legado sem síntese estruturada. Revise as evidências antes de compartilhar.")
        report["documentation"] = document
        refs = referenced_ids(document)
    except (ValueError, TypeError, KeyError, AttributeError):
        raise DocumentUnavailable("Não foi possível ler a documentação salva. Recarregue a análise ou revise os documentos.") from None
    catalog = figure_catalog(workspace, steps)
    catalog = {ref: figure for ref, figure in catalog.items() if ref in refs}
    images = {}
    digest = hashlib.sha256(original)
    digest.update(profile_id(job).encode())
    for ref, figure in sorted(catalog.items()):
        digest.update(ref.encode())
        if figure.path:
            try:
                data = figure.path.read_bytes()
            except OSError:
                figure.path = None
                figure.reason = "imagem não encontrada no momento da leitura"
            else:
                images[figure.path.name] = data
                digest.update(hashlib.sha256(data).digest())
        digest.update(str(figure.path is not None).encode())
        digest.update(json.dumps([figure.title, figure.description, figure.source, figure.timecode, figure.uncertainty], ensure_ascii=False).encode())
    # Render the stored document, not a new interpretation of today's context.
    saved_job = {**job, "title": report.get("title") or job["title"],
                 "audience": report.get("audience") or job.get("audience"),
                 "process_context": report.get("context", job.get("process_context", ""))}
    return DocumentSnapshot(saved_job, report, digest.hexdigest(), catalog, images, steps)


def export_pdf(saved):
    # Isolated export leaves the completed delivery and its ZIP untouched.
    with tempfile.TemporaryDirectory(prefix="document-export-", dir=CACHE_DIR) as folder:
        destination = Path(folder)
        (destination / "evidence").mkdir()
        normalized_steps = []
        for ref, figure in saved.figures.items():
            name = figure.path.name if figure.path else "missing.png"
            normalized_steps.append({"frame_index": ref, "image": name, "title": figure.title,
                "evidence": figure.description, "source_name": figure.source,
                "source_timecode": figure.timecode, "uncertainty": figure.uncertainty})
            if figure.path:
                (destination / "evidence" / name).write_bytes(saved.images[name])
        (destination / "analise-visual.json").write_text(json.dumps(normalized_steps, ensure_ascii=False), encoding="utf-8")
        (destination / "relatorio.json").write_text(json.dumps(saved.report, ensure_ascii=False), encoding="utf-8")
        generated = write_pdf_document(saved.job, saved.report["documentation"], destination)
        if not generated:
            raise DocumentUnavailable("A exportação em PDF não está disponível neste ambiente. Tente novamente ou baixe o ZIP.")
        return Path(generated).read_bytes()


def package_matches(saved, target):
    """Do not advertise an old package as an export of the currently read data."""
    try:
        with zipfile.ZipFile(target) as archive:
            report = json.loads(archive.read("relatorio.json"))
            if report.get("documentation") != saved.report["documentation"] or report.get("title") != saved.job["title"]:
                return False
            # A ZIP repacked after an image edit may still contain old Word/PDF
            # files. The export manifest records the evidence used to build them.
            if "manifesto-documentacao.json" in archive.namelist():
                manifest = json.loads(archive.read("manifesto-documentacao.json"))
                if manifest.get("documentation") != saved.report["documentation"]:
                    return False
                recorded = {str(item.get("id")): item for item in manifest.get("evidence", [])}
                for ref, figure in saved.figures.items():
                    entry = recorded.get(ref, {})
                    if bool(entry.get("available")) != bool(figure.path):
                        return False
                    if figure.path and entry.get("sha256") != hashlib.sha256(saved.images[figure.path.name]).hexdigest():
                        return False
            for name, content in saved.images.items():
                with archive.open(f"evidence/{name}") as source:
                    if hashlib.file_digest(source, "sha256").digest() != hashlib.sha256(content).digest():
                        return False
    except (OSError, KeyError, ValueError, TypeError, AttributeError, zipfile.BadZipFile):
        return False
    return True
