"""Deterministic Discovery context; browser and server share context-rules.json.

The structured context adds instructions, not a privacy guarantee. TODO: implement
and validate media-region masking separately before promising blurred outputs.
"""
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


RULES = json.loads((Path(__file__).parent / "static" / "context-rules.json").read_text(encoding="utf-8"))
LABELS = RULES["labels"]
ENTREGAVEIS_SUGERIDOS = RULES["suggestions"]
TOM = RULES["TOM"]
FOCO = RULES["FOCO"]
Solucao = Literal["rpa", "ia", "integracao", "flow", "indefinido"]
EtapaDestino = Literal["desenho", "doc_tecnica", "spec_rpa"]
Publico = Literal["rpa", "squad_ia", "dev_flow", "cliente", "comercial", "outro", "equipe", "gestao", "participantes", "alunos"]
Entregavel = Literal["fluxo_atual", "sistemas_telas", "campos_io", "regras_excecoes", "volume_tempo", "dores", "oportunidades", "prints_por_tela", "perguntas_abertas", "topicos", "decisoes", "proximos_passos", "aprendizados", "perguntas_respostas", "achados", "recomendacoes"]
Perfil = Literal["processo", "reuniao", "treinamento", "entrevista", "pesquisa", "personalizado"]


def is_general(context):
    return _mapping(context).get("perfil", "processo") != "processo"


def compile_general_guide(context):
    profile = RULES["profiles"][context["perfil"]]
    lines = [f'Perfil: {profile["label"]}', profile["focus"]]
    for key, label in (("processo", "Assunto"), ("cliente", "Área ou projeto"), ("objetivo", "Objetivo")):
        if value := _text(context.get(key)):
            lines.append(f"{label}: {value}")
    if audience := audience_label(context):
        lines.append(f"Quem vai ler: {audience}.")
    levels = {"resumido": "Sintético", "operacional": "Equilibrado", "detalhado": "Detalhado"}
    lines.append(f'Detalhamento: {levels.get(context.get("detalhamento", "operacional"), "Equilibrado")}.')
    blocks = ["\n".join(lines)]
    items = _ordered(context.get("entregaveis"), "entregaveis")
    if items:
        blocks.append("O que a análise precisa entregar:\n" + "\n".join(f'- {LABELS["entregaveis"][key]}' for key in items))
    if terms := context.get("sistemas"):
        blocks.append("Termos e ferramentas de referência: " + ", ".join(terms) + ".")
    cuts = ["Regras de corte:"]
    if subject := _text(context.get("processo")):
        cuts.append(RULES["cutKeep"].replace("{processo}", subject))
    cuts.append(RULES["cutDiscard"])
    blocks.append("\n".join(cuts))
    evidence = ["Regras de evidência:", *RULES["generalEvidence"]]
    if context.get("dadosSensiveis") is True:
        evidence.append(RULES["REGRA_DADOS_SENSIVEIS"])
    blocks.append("\n".join(evidence))
    if extra := _text(context.get("instrucoesExtras")):
        blocks.append("Instruções adicionais:\n" + extra)
    return "\n\n".join(blocks)


def _mapping(context):
    return context.model_dump() if isinstance(context, BaseModel) else context


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _ordered(values, group):
    return [key for key in LABELS[group] if key in (values or [])]


def audience_label(context):
    context = _mapping(context)
    return ", ".join(
        _text(context.get("publicoOutro")) if key == "outro" else LABELS["publico"][key]
        for key in _ordered(context.get("publico"), "publico")
        if key != "outro" or _text(context.get("publicoOutro"))
    )


def suggest_deliverables(context):
    context = _mapping(context)
    if is_general(context):
        return _ordered(RULES["profiles"][context["perfil"]]["suggestions"], "entregaveis")
    stage = context.get("etapaDestino")
    if stage not in ENTREGAVEIS_SUGERIDOS["base"]:
        return []
    items = set(ENTREGAVEIS_SUGERIDOS["base"][stage])
    for solution in context.get("solucoes", []):
        items.update(ENTREGAVEIS_SUGERIDOS["extra"].get(solution, []))
    return _ordered(items, "entregaveis")


def compile_guide(context):
    """Compile only explicit context fields; never append source-file metadata."""
    context = _mapping(context)
    if is_general(context):
        return compile_general_guide(context)
    blocks = []
    project = []
    for key, label in (("cliente", "Cliente"), ("processo", "Processo"), ("objetivo", "Por que está sendo mapeado")):
        if value := _text(context.get(key)):
            project.append(f"{label}: {value}")
    if project:
        blocks.append("\n".join(project))
    stage = context.get("etapaDestino")
    destination = []
    if stage in LABELS["etapas"]:
        destination.append(f'Este material alimenta a etapa "{LABELS["etapas"][stage]}" de um projeto da btime.')
    solutions = _ordered(context.get("solucoes"), "solucoes")
    if solutions:
        destination.append("Solução em vista: " + ", ".join(LABELS["solucoes"][key] for key in solutions) + ".")
    if audience := audience_label(context):
        destination.append(f"Quem vai ler: {audience}.")
    if stage in TOM:
        destination.append(TOM[stage])
    if destination:
        blocks.append("\n".join(destination))
    deliverables = _ordered(context.get("entregaveis"), "entregaveis")
    if deliverables:
        blocks.append("O que a análise precisa entregar:\n" + "\n".join(f'- {LABELS["entregaveis"][key]}' for key in deliverables))
    blocks.extend(FOCO[key] for key in solutions)
    systems = [_text(value) for value in context.get("sistemas", []) if _text(value)]
    if systems:
        blocks.append("Sistemas citados: " + ", ".join(systems) + ".")
    cuts = ["Regras de corte:"]
    if process := _text(context.get("processo")):
        cuts.append(RULES["cutKeep"].replace("{processo}", process))
    cuts.append(RULES["cutDiscard"])
    blocks.append("\n".join(cuts))
    evidence = ["Regras de evidência:", *RULES["evidence"]]
    if context.get("dadosSensiveis") is True:
        evidence.append(RULES["REGRA_DADOS_SENSIVEIS"])
    blocks.append("\n".join(evidence))
    if instructions := _text(context.get("instrucoesExtras")):
        blocks.append("Instruções adicionais:\n" + instructions)
    return "\n\n".join(blocks)


class DiscoveryContextDraft(BaseModel):
    """Validated partial context used while editing or requesting AI wording."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    # Missing profile keeps the historical process contract, without inference.
    perfil: Perfil = "processo"
    # Absent in historical requests: keep their individual video previews.
    modoEntrega: Literal["documentacao", "documentacao_previews"] = "documentacao_previews"
    detalhamento: Literal["resumido", "operacional", "detalhado"] = "operacional"

    cliente: str = Field(default="", max_length=80)
    processo: str = Field(default="", max_length=100)
    objetivo: str = Field(default="", max_length=400)
    solucoes: list[Solucao] = Field(default_factory=lambda: ["indefinido"], max_length=5)
    etapaDestino: EtapaDestino | None = None
    etapaDestinoTocado: StrictBool = False
    publico: list[Publico] = Field(default_factory=list, max_length=10)
    publicoOutro: str = Field(default="", max_length=60)
    entregaveis: list[Entregavel] = Field(default_factory=list, max_length=16)
    entregaveisTocado: StrictBool = False
    sistemas: list[str] = Field(default_factory=list, max_length=15)
    dadosSensiveis: StrictBool = False
    instrucoesExtras: str = Field(default="", max_length=1500)
    guia: str = Field(default="", max_length=8000)
    guiaEditado: StrictBool = False

    @model_validator(mode="before")
    @classmethod
    def ignore_unedited_client_guide(cls, value):
        if isinstance(value, dict) and value.get("guiaEditado", False) is False:
            # This field is server-derived, even if the caller sends stale text.
            value = {**value, "guia": ""}
        return value

    @field_validator("solucoes", "publico", "entregaveis")
    @classmethod
    def unique_choices(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Não repita as opções selecionadas.")
        return value

    @field_validator("solucoes")
    @classmethod
    def exclusive_undefined(cls, value):
        if "indefinido" in value and len(value) > 1:
            raise ValueError('"Ainda não definido" deve ser selecionado sozinho.')
        return value

    @field_validator("sistemas")
    @classmethod
    def valid_system_tags(cls, value):
        values = [item.strip() for item in value]
        if any(not item or len(item) > 80 for item in values):
            raise ValueError("Cada sistema deve ter entre 1 e 80 caracteres.")
        if len({item.casefold() for item in values}) != len(values):
            raise ValueError("Não repita os sistemas.")
        return values

    @model_validator(mode="after")
    def compile_unedited_guide(self):
        if not self.guiaEditado:
            self.guia = compile_guide(self)
        if len(self.guia) > 8000:
            raise ValueError("O guia deve ter no máximo 8.000 caracteres.")
        return self


class DiscoveryContexto(DiscoveryContextDraft):
    """Complete context accepted for a queued analysis."""
    cliente: str = Field(default="", max_length=80)
    processo: str = Field(min_length=1, max_length=100)
    solucoes: list[Solucao] = Field(default_factory=list, max_length=5)
    etapaDestino: EtapaDestino | None = None
    publico: list[Publico] = Field(min_length=1, max_length=10)
    entregaveis: list[Entregavel] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def validate_completed_context(self):
        if self.perfil == "processo":
            if not self.cliente or not self.solucoes or not self.etapaDestino:
                raise ValueError("Informe cliente, solução e etapa para documentar um processo.")
            allowed = set(LABELS["entregaveis"]) - set(RULES["profiles"]["personalizado"]["available"])
        else:
            allowed = set(RULES["profiles"][self.perfil]["available"])
        if not set(self.entregaveis) <= allowed:
            raise ValueError("Os itens selecionados não pertencem ao perfil escolhido.")
        if "outro" in self.publico and not self.publicoOutro:
            raise ValueError("Diga quem é o público.")
        if self.guiaEditado and not self.guia:
            raise ValueError("O guia não pode ficar vazio.")
        return self


def legacy_fields(context):
    """Keep the existing processing contract without changing pipeline logic."""
    context = _mapping(context)
    return {
        "title": context["processo"],
        "process_context": context["guia"],
        "audience": audience_label(context) or "Equipe",
        "detail_level": context.get("detalhamento", "operacional") if is_general(context) else "resumido" if context.get("etapaDestino") == "desenho" else "operacional",
    }


# Explicit aliases mirror the browser compiler's public contract.
compileGuide = compile_guide
suggestDeliverables = suggest_deliverables
