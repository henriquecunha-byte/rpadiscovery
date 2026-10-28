"""Build a truthful local demo, then publish COMPLETED atomically; never enqueue AI."""
import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rpa_docs.config import DATABASE, JOBS_DIR
from rpa_docs.database import Database, now
from rpa_docs.schemas import JobCreate
from rpa_docs.pipeline import write_report, create_package
from rpa_docs.documentation_profiles import document_catalog
from docx import Document
from pypdf import PdfReader

STAGING = ROOT / "cache" / "demo-reembolsos-20261019"
DISCLAIMER = "DEMONSTRAÇÃO: conteúdo e telas fictícios, preparados manualmente sem IA. Nenhuma gravação foi processada, nenhuma conta foi conectada e nenhum pagamento foi realizado."


def content():
    context = {"perfil": "processo", "modoEntrega": "documentacao", "cliente": "Empresa fictícia",
               "processo": "DEMO Solicitação de reembolsos", "solucoes": ["rpa"], "etapaDestino": "spec_rpa",
               "publico": ["outro"], "publicoOutro": "Financeiro e Operações", "entregaveis": ["fluxo_atual"],
               "instrucoesExtras": "Exemplo fictício para visualizar a documentação tela a tela. Não representa política da btime. Valores, regras e papéis são ilustrativos.",
               "guiaEditado": True, "guia": "Demonstrar o registro, a conferência, a aprovação e a programação de um reembolso. Relacionar cada etapa ao print correspondente. Separar agendamento de pagamento efetivado. Todas as regras e telas deste exemplo são fictícias."}
    payload = JobCreate(title="DEMO Solicitação de reembolsos", source_path=str(STAGING / "sem-gravacao"),
                        contexto=context, api_approved=False, api_budget_usd=0.1).model_dump()
    definitions = [
        ("Registrar a despesa", "Colaborador", "Categoria, centro de custo, valor e data",
         "O colaborador registra a categoria Transporte, informa o centro de custo Projeto Aurora, preenche R$ 148,60 e a data de 16/10/2026. Salva o rascunho para conferir a documentação antes do envio.",
         "Despesa e informações de alocação", "Solicitação em rascunho", "Campos obrigatórios incompletos devem ser corrigidos antes do envio.",
         "A tela ilustrativa mostra os quatro campos preenchidos e o botão Salvar e continuar."),
        ("Conferir e enviar para aprovação", "Colaborador", "Comprovante e botão Enviar para aprovação",
         "O colaborador confere o anexo recibo-demo.pdf, o valor e o centro de custo. Neste cenário fictício, o limite por solicitação é R$ 500,00. Com o anexo presente e os dados completos, envia a solicitação ao gestor.",
         "Rascunho e comprovante", "Solicitação aguardando aprovação", "Um comprovante ausente impede o envio. O tratamento acima do limite precisa ser definido.",
         "O resumo ilustra o comprovante anexado, o valor de R$ 148,60 e o limite fictício de R$ 500,00."),
        ("Analisar a solicitação e decidir", "Gestor do projeto", "Botões Aprovar solicitação e Devolver para ajuste",
         "O gestor analisa a solicitação RB-DEMO-0042, confere o motivo, a categoria, a alocação e o comprovante. Pode aprovar o pedido ou devolvê-lo ao colaborador para ajuste. No caminho principal ilustrado, aprova a despesa de R$ 148,60.",
         "Solicitação aguardando aprovação", "Solicitação aprovada ou devolvida", "Na devolução, o colaborador corrige os dados antes de uma nova análise.",
         "A tela de decisão mostra o responsável pela análise, os dados da solicitação e as duas ações possíveis."),
        ("Programar o reembolso", "Financeiro", "Data programada e situação Agendado",
         "O financeiro recebe o pedido aprovado e registra 21/10/2026 como data programada. A solicitação fica Agendada, com a aprovação vinculada ao registro. Agendamento não significa pagamento efetivado; a confirmação bancária está fora desta demonstração.",
         "Solicitação aprovada", "Reembolso programado", "A baixa como Pago depende de confirmação posterior, não mostrada neste exemplo.",
         "O último print ilustra R$ 148,60 aprovados, a data programada e a situação Agendado."),
    ]
    steps, flow = [], []
    for index, (title, actor, control, description, input_value, output, decision, evidence) in enumerate(definitions, 1):
        steps.append({"frame_index": index, "time": index * 60, "timecode": f"00:0{index}:00",
                      "image": f"demo-tela-{index}.png", "title": title, "action": description,
                      "system": "Portal de despesas fictício", "field_or_control": control,
                      "evidence": evidence, "source_name": "Roteiro demonstrativo fictício",
                      "source_timecode": f"Etapa ilustrativa {index}", "uncertainty": "Tela desenhada para esta demonstração; não extraída de vídeo.",
                      "transcript": "Não há fala transcrita. Este exemplo foi preparado manualmente para demonstrar a relação entre a descrição e a imagem."})
        flow.append({"sequence": index, "title": title, "description": description, "actor": actor,
                     "system": "Portal de despesas fictício", "input": input_value, "output": output,
                     "decision_or_exception": decision, "evidence_refs": [index]})
    document = {
        "executive_summary": "Exemplo fictício do fluxo de reembolso, do registro da despesa à programação pelo financeiro. O caminho principal usa uma solicitação de R$ 148,60, vinculada ao Projeto Aurora. Quatro telas ilustram os dados, as validações e a decisão do gestor. Este material demonstra o formato da entrega, não uma análise de reunião real.",
        "objective": "Documentar como uma solicitação é registrada, conferida, aprovada e programada, identificando os responsáveis e os controles de cada etapa no cenário fictício.",
        "scope": {"in_scope": ["Cadastro da despesa e alocação no centro de custo.", "Conferência do comprovante e envio ao gestor.", "Aprovação ou devolução para ajuste.", "Programação do reembolso pelo financeiro."],
                  "out_of_scope": ["Conexão com banco ou ERP real.", "Efetivação do pagamento e baixa bancária.", "Definição da política de despesas da btime."]},
        "actors": [{"name": "Colaborador", "responsibility": "Registra a despesa, envia o comprovante e corrige pedidos devolvidos."},
                   {"name": "Gestor do projeto", "responsibility": "Confere a alocação e decide sobre a solicitação."},
                   {"name": "Financeiro", "responsibility": "Programa o reembolso após a aprovação."}],
        "systems": [{"name": "Portal de despesas fictício", "purpose": "Centralizar os registros e as decisões neste exemplo demonstrativo."}],
        "prerequisites": ["No cenário ilustrativo, o colaborador tem acesso ao projeto e ao centro de custo.", "O comprovante da despesa está disponível para anexação.", "Um gestor e o financeiro estão definidos como responsáveis."],
        "inputs": [{"name": "Categoria, data e valor da despesa", "source": "Colaborador", "required": "Obrigatório no cenário fictício"},
                   {"name": "Centro de custo", "source": "Projeto Aurora", "required": "Obrigatório"},
                   {"name": "Comprovante", "source": "Anexo do colaborador", "required": "Obrigatório para enviar"}],
        "outputs": [{"name": "Solicitação com decisão registrada", "destination": "Colaborador e financeiro"},
                    {"name": "Data programada para reembolso", "destination": "Fila do financeiro"}],
        "process_flow": flow,
        "business_rules": [{"rule": "Neste exemplo, categoria, centro de custo, valor e data são necessários para solicitar a aprovação.", "evidence_refs": [1]},
                           {"rule": "O comprovante deve estar anexado antes do envio ao gestor.", "evidence_refs": [2]},
                           {"rule": "O limite de R$ 500,00 é exclusivamente ilustrativo e não representa uma política corporativa real.", "evidence_refs": [2]},
                           {"rule": "O financeiro programa apenas solicitações aprovadas. Agendado não equivale a Pago.", "evidence_refs": [3, 4]}],
        "exceptions": [{"scenario": "Comprovante ausente", "handling": "Solicitar o anexo antes de enviar ao gestor.", "status": "Regra do cenário fictício"},
                       {"scenario": "Solicitação devolvida", "handling": "Corrigir os dados e reenviar para análise.", "status": "Caminho alternativo ilustrativo"},
                       {"scenario": "Despesa acima de R$ 500,00", "handling": "Definir a alçada de exceção antes de implantar uma automação.", "status": "A validar; exceção não demonstrada"}],
        "risks_and_controls": [{"risk": "Reembolso duplicado", "impact": "Pagamento repetido da mesma despesa", "control": "Proposta: conferir chave da despesa e histórico de pedidos antes do envio."},
                               {"risk": "Pagamento sem aprovação", "impact": "Descumprimento da alçada", "control": "Exigir decisão registrada antes da programação."}],
        "automation_opportunities": [{"opportunity": "Validar campos e presença do comprovante", "benefit": "Reduzir devoluções por dados incompletos.", "dependency": "Definir campos obrigatórios e formatos de anexo no processo real."},
                                     {"opportunity": "Integrar pedidos aprovados à fila financeira", "benefit": "Evitar redigitação dos dados já aprovados.", "dependency": "Confirmar API, permissões e identificadores do sistema financeiro."}],
        "open_questions": ["Quem aprova valores acima do limite fictício e como fica registrada a exceção?", "Como detectar comprovantes ou despesas repetidas?", "Como a confirmação bancária atualiza a situação para Pago?"],
        "preview_moments": [],
        "limitations": [DISCLAIMER, "As imagens são interfaces ilustrativas, não prints extraídos de uma gravação.", "Os horários do roteiro são ilustrativos. Não existe vídeo original nem transcrição neste exemplo.", "A paginação visual do Word ainda precisa ser conferida em um ambiente com renderizador DOCX disponível."],
    }
    return payload, steps, document


def build():
    STAGING.mkdir(parents=True, exist_ok=True)
    for index in range(1, 5):
        if not (STAGING / "evidence" / f"demo-tela-{index}.png").is_file():
            raise SystemExit("Gere primeiro as quatro telas com scripts/demo_reembolsos.cjs.")
    metadata_path = STAGING / "demo-job.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {"id": "demo-reembolsos-" + uuid4().hex[:8]}
    payload, steps, document = content()
    job = dict(payload, id=metadata["id"])
    (STAGING / "analise-visual.json").write_text(json.dumps(steps, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(job, steps, STAGING, Path("demo-sem-video"), document, [])
    create_package(STAGING)
    reader = PdfReader(STAGING / "documentacao-processo.pdf")
    assert sum(len(page.images) for page in reader.pages) == 4
    assert len(Document(STAGING / "documentacao-processo.docx").inline_shapes) == 4
    with zipfile.ZipFile(STAGING / "entrega-completa.zip") as archive:
        assert archive.testzip() is None
        assert not any(name.endswith(".mp4") for name in archive.namelist())
    metadata.update(title=payload["title"], pdf_pages=len(reader.pages), figures=4, demo=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False))


def publish():
    metadata = json.loads((STAGING / "demo-job.json").read_text(encoding="utf-8"))
    job_id = metadata["id"]
    if not re.fullmatch(r"demo-reembolsos-[0-9a-f]{8}", job_id):
        raise ValueError("ID de demonstração inválido.")
    target = (JOBS_DIR / job_id).resolve()
    assert target.is_relative_to(JOBS_DIR.resolve()) and STAGING.resolve().is_relative_to((ROOT / "cache").resolve())
    payload, steps, document = content()
    payload["source_path"] = str(target / "demo-sem-gravacao")
    result = {"demo": True, "demo_kind": "manual-fixture-v1", "source_count": 0, "evidence_count": 4,
              "transcript_segments": 0, "step_count": 4, "process_step_count": 4,
              "previews": [], "preview": {"created": False, "requested": False, "file": None, "ranges": []},
              "warnings": [DISCLAIMER], "deliverables": [name for name, _, _ in document_catalog(payload) if (STAGING / name).is_file()] + ["relatorio.html"]}
    database = Database(DATABASE)
    timestamp = now()
    # Never create a QUEUED record: the running worker must not see this demo as
    # a request for transcription, model inference or paid API processing.
    with database.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT result_json FROM jobs WHERE id=?", (job_id,)).fetchone()
        if existing:
            assert json.loads(existing[0]).get("demo_kind") == "manual-fixture-v1"
            print(json.dumps({"id": job_id, "url": f"http://127.0.0.1:8770/#job={job_id}", "already_exists": True}))
            return
        if target.exists():
            raise FileExistsError("A pasta de destino já existe; nenhum arquivo foi alterado.")
        shutil.copytree(STAGING, target, ignore=shutil.ignore_patterns("qa", "qa-page-*.png", "*.log"))
        db.execute("""INSERT INTO jobs
            (id,title,source_path,process_context,audience,detail_level,api_approved,api_budget_usd,
             status,stage,progress,created_at,updated_at,error,result_json,queued_at,owner_id,contexto_json)
            VALUES (?,?,?,?,?,?,0,?,'COMPLETED','Demonstração pronta para visualizar',100,?,?,NULL,?,?,NULL,?)""",
            (job_id, payload["title"], payload["source_path"], payload["process_context"], payload["audience"], payload["detail_level"],
             payload["api_budget_usd"], timestamp, timestamp, json.dumps(result, ensure_ascii=False), timestamp, json.dumps(payload["contexto"], ensure_ascii=False)))
        for message in (DISCLAIMER, "Quatro telas ilustrativas vinculadas às etapas do processo.", "PDF, Word, relatório e pacote preparados com os exportadores reais da plataforma."):
            db.execute("INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,'info',?)", (job_id, timestamp, message))
    print(json.dumps({"id": job_id, "url": f"http://127.0.0.1:8770/#job={job_id}", "files": len(list(target.glob('*')))}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    publish() if args.publish else build()
