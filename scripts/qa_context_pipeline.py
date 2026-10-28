"""Structured context → real synthetic media/exports, with inference mocked.

Run with --fixtures pointing to the isolated qa_server.py fixture directory.
No credentials, production jobs, transcription models or cloud calls are used.
"""
import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rpa_docs import pipeline
from rpa_docs import documentation_profiles as profiles
from rpa_docs.schemas import JobCreate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--profile", choices=list(profiles.PROFILES), default="processo")
    args = parser.parse_args()
    fixture_root = args.fixtures.resolve()
    assert fixture_root.is_relative_to(ROOT / "cache")
    inputs = fixture_root / "jobs" / "qa-completed" / "input"
    assert len(list(inputs.glob("*.mp4"))) == 2
    workspace = Path(tempfile.mkdtemp(prefix="context-pipeline-", dir=ROOT / "cache"))
    source = workspace / "input"
    shutil.copytree(inputs, source)
    context = {"cliente": "Cliente sintético QA", "processo": "Conferência de pedidos",
               "solucoes": ["rpa", "integracao"], "etapaDestino": "spec_rpa",
               "publico": ["rpa"], "entregaveis": ["fluxo_atual", "campos_io", "prints_por_tela"],
               "entregaveisTocado": True, "instrucoesExtras": "Registrar dúvidas sem inventar respostas."}
    if args.profile != "processo":
        context = {"perfil": args.profile, "processo": "Análise sintética multiarea",
                   "objetivo": "Registrar conteúdo e dúvidas sem pressupor um processo operacional.",
                   "publico": ["equipe"], "entregaveis": profiles.PROFILES[args.profile]["suggestions"],
                   "detalhamento": "operacional"}
    job = JobCreate(contexto=context, source_path=str(source), api_approved=True).model_dump()
    job["id"] = "qa-context-pipeline"
    guide = job["process_context"]

    def transcribe(video, target):
        transcript = [{"start": 5, "end": 7, "text": "Conferência de pedidos simulada."},
                      {"start": 45, "end": 47, "text": "Validação simulada da segunda gravação."}]
        (target / "transcricao.json").write_text(json.dumps(transcript), encoding="utf-8")
        return transcript

    def analyze(evidence, transcript, target, received_guide, detail):
        assert received_guide == guide
        assert detail == "operacional"
        return [{"time": 6, "timecode": "00:00:06", "title": "Conferir pedido",
                 "action": "Etapa sintética; não representa conteúdo de reunião real.",
                 "image": evidence[0]["image"], "system": "Ambiente sintético", "relevant": True}]

    def synthesize(received_job, steps, transcript, target):
        assert received_job["contexto"].get("cliente", "") == context.get("cliente", "")
        assert received_job["process_context"] == guide
        document = pipeline.fallback_documentation(received_job, steps, "Inferência simulada para QA de integração.")
        if args.profile != "processo":
            assert document["profile"] == args.profile
            for section in document["sections"]:
                section["items"] = [{"title": "Registro de QA", "text": "Conteúdo sintético para validar exportações.",
                                     "evidence_refs": [1], "timecode": "00:00:06"}]
        document["preview_moments"] = [{"start": 5, "end": 7}, {"start": 45, "end": 47}]
        return document

    with patch.object(pipeline, "transcribe", side_effect=transcribe), patch.object(pipeline, "analyze", side_effect=analyze), patch.object(pipeline, "synthesize_documentation", side_effect=synthesize):
        result = pipeline.process(job, workspace, lambda value, stage: None)
    assert result["source_count"] == 2
    assert len(result["previews"]) == 2 and all(item["created"] for item in result["previews"])
    assert json.loads((workspace / "relatorio.json").read_text(encoding="utf-8"))["context"] == guide
    general = args.profile != "processo"
    markdown_name = profiles.PROFILES[args.profile]["filename"]
    document_stem = "documentacao" if general else "documentacao-processo"
    assert guide in (workspace / markdown_name).read_text(encoding="utf-8")
    with zipfile.ZipFile(workspace / f"{document_stem}.docx") as docx:
        assert ("Conteúdo sintético" if general else context["cliente"]) in docx.read("word/document.xml").decode()
    with zipfile.ZipFile(workspace / "entrega-completa.zip") as package:
        assert package.testzip() is None
        assert sum(name.startswith("previews/") and name.endswith(".mp4") for name in package.namelist()) == 2
        assert f"{document_stem}.pdf" in package.namelist()
        if general:
            assert "requisitos-rpa.md" not in package.namelist()
            assert "documentacao-processo.docx" not in package.namelist()
    print(json.dumps({"passed": True, "profile": args.profile, "synthetic": True, "inference": "mocked", "previews": 2, "workspace": str(workspace)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
