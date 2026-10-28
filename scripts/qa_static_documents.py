"""Render reproducible, explicitly synthetic examples; never read customer jobs."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_static_evidence import fixture
from rpa_docs.pipeline import write_report, create_package
from rpa_docs.documentation_profiles import PROFILES
from pypdf import PdfReader

output = ROOT / "cache" / "static-document-qa"
output.mkdir(parents=True, exist_ok=True)
summary = []
for profile in PROFILES:
    folder = output / profile
    folder.mkdir(exist_ok=True)
    # Each run keeps its own source fixture; no real video, key or API call.
    job, document, steps = fixture(folder, profile)
    job["title"] = "[QA sintético] Conferência de pedidos"
    document["executive_summary"] = "Amostra sintética de QA: duas telas demonstram a conferência e confirmação de um pedido. Não representa uma reunião real."
    document["limitations"] = ["Dados sintéticos. A interpretação da IA e a qualidade semântica não são avaliadas nesta amostra."]
    write_report(job, steps, folder, Path("fonte-sintetica.mp4"), document, [])
    create_package(folder)
    pdf = folder / ("documentacao-processo.pdf" if profile == "processo" else "documentacao.pdf")
    reader = PdfReader(pdf)
    summary.append({"profile": profile, "pdf": str(pdf), "pages": len(reader.pages), "images": sum(len(page.images) for page in reader.pages)})
(output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
