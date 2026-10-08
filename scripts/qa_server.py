"""Disposable UI/API QA server. Synthetic sources only; worker and cloud calls off.

Run: .venv/Scripts/python.exe scripts/qa_server.py
No production job or credential is modified. The printed cache directory holds
only this run's fixtures and can be inspected after stopping the process.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
cache = ROOT / "cache"
cache.mkdir(exist_ok=True)
qa_root = Path(tempfile.mkdtemp(prefix="ui-qa-", dir=cache))
os.environ["RPA_DATA_ROOT"] = str(qa_root)
os.environ["OPENAI_API_KEY"] = ""
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""

from rpa_docs.api import app, db, worker
from rpa_docs.config import FFMPEG, JOBS_DIR
from rpa_docs.pipeline import prepare_source, extract_evidence, create_job_previews, create_package, write_report, fallback_documentation


def job_payload(title, source, context="Documentar a gestão de pedidos da Trevo. Manter regras e exceções discutidas; remover conversas sem relação com o processo."):
    return dict(title=title, source_path=str(source), process_context=context,
                audience="Equipe de RPA", detail_level="operacional", api_approved=True, api_budget_usd=1)


workspace = JOBS_DIR / "qa-completed"
source_dir = workspace / "input"
source_dir.mkdir(parents=True)
sources = []
for index, color in enumerate(["0x571EE6", "0x16634B"], 1):
    source = source_dir / f"{index:02d}-reuniao-sintetica.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c={color}:s=640x360:r=24:d=30", "-f", "lavfi", "-i", f"sine=frequency={400+index*100}:duration=30",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(source)], check=True)
    sources.append(source)
job = db.create_job("qa-completed", job_payload("[QA sintético] Gestão de pedidos — Trevo", source_dir))
video, source_videos = prepare_source(source_dir, workspace)
evidence = extract_evidence(video, workspace / "evidence", interval=20)
steps = [dict(image=evidence[0]["image"], time=6, timecode="00:00:06", title="Registrar o pedido", action="Demonstração sintética de QA; não representa reunião real.", system="Ambiente de teste", evidence="Cor sólida e áudio sintético para validar mídia.")]
moments = [{"start":5,"end":7,"reason":"Trecho sintético 1"},{"start":45,"end":47,"reason":"Trecho sintético 2"}]
preview, previews = create_job_previews(video, source_videos, steps, workspace, moments)
document = fallback_documentation(job, steps, "Dados sintéticos de QA, sem inferência de IA.")
document["preview_moments"] = moments
(workspace / "transcricao.json").write_text(json.dumps([{"start":5,"end":7,"text":"Transcrição simulada para teste."}], ensure_ascii=False), encoding="utf-8")
write_report(job, steps, workspace, video, document, previews)
create_package(workspace)
db.update("qa-completed", status="COMPLETED", progress=100, stage="Documentação pronta", result_json=dict(video=str(video), source_files=[str(p) for p in sources], source_count=2, evidence_count=len(evidence), process_step_count=1, previews=previews, preview=preview, warnings=["Demonstração sintética: a qualidade semântica da IA não é avaliada por este cenário."]))
db.event("qa-completed", "success", "Previews e documentação sintéticos disponíveis para teste.")
for job_id, title, status, progress, stage in [
    ("qa-failed", "[QA sintético] Conciliação de cadastros", "FAILED", 38, "Falha no processamento"),
    ("qa-cancelled", "[QA sintético] Atualização de fornecedores", "CANCELLED", 0, "Cancelado antes de iniciar"),
    ("qa-running", "[QA sintético] Fechamento operacional", "RUNNING", 62, "Organizando regras e exceções"),
    ("qa-queued", "[QA sintético] Conferência de documentos", "QUEUED", 0, "Aguardando"),
]:
    db.create_job(job_id, job_payload(title, source_dir))
    db.update(job_id, status=status, progress=progress, stage=stage, error="Arquivo indisponível durante a leitura." if status == "FAILED" else None)
    db.event(job_id, "error" if status=="FAILED" else "info", stage)

# Explicitly no worker processing or cloud calls. Health models an available
# worker for UI scenarios; all job transitions are exercised by API tests.
worker.thread = SimpleNamespace(is_alive=lambda: True)
print(f"QA_FIXTURES={qa_root}", flush=True)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8772, lifespan="off")
