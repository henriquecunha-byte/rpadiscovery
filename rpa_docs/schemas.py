from pydantic import BaseModel, ConfigDict, Field, model_validator

from .context_model import DiscoveryContextDraft, DiscoveryContexto, legacy_fields


class InputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)


class ContextJobInput(InputModel):
    contexto: DiscoveryContexto | None = None

    @model_validator(mode="before")
    @classmethod
    def derive_context_fields(cls, value):
        if isinstance(value, dict) and value.get("contexto") is not None:
            context = DiscoveryContexto.model_validate(value["contexto"])
            return {**value, **legacy_fields(context), "contexto": context}
        return value

    @model_validator(mode="after")
    def validate_legacy_title(self):
        if self.contexto is None and len(self.title) < 2:
            raise ValueError("O nome da análise deve ter pelo menos 2 caracteres.")
        return self


class JobCreate(ContextJobInput):
    title: str = Field(min_length=1, max_length=120)
    source_path: str = Field(min_length=1)
    process_context: str = Field(default="", max_length=8000)
    audience: str = Field(default="Equipe", max_length=320)
    detail_level: str = Field(default="operacional", pattern="^(resumido|operacional|detalhado)$")
    api_approved: bool = False
    api_budget_usd: float = Field(default=1.0, ge=0.1, le=50.0)


class PromptSuggestion(InputModel):
    contexto: DiscoveryContextDraft | None = None
    title: str = Field(default="", max_length=120)
    process_context: str = Field(default="", max_length=8000)
    audience: str = Field(default="Equipe", max_length=320)
    detail_level: str = Field(default="operacional", pattern="^(resumido|operacional|detalhado)$")
    sources: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def derive_context_fields(cls, value):
        if isinstance(value, dict) and value.get("contexto") is not None:
            context = DiscoveryContextDraft.model_validate(value["contexto"])
            return {**value, **legacy_fields(context), "contexto": context}
        return value


class DriveUpload(InputModel):
    folder: str = Field(default="", max_length=1000)
    include_assets: bool = False


class DriveImport(ContextJobInput):
    title: str = Field(min_length=1, max_length=120)
    file_ids: list[str] = Field(min_length=1, max_length=100)
    process_context: str = Field(default="", max_length=8000)
    audience: str = Field(default="Equipe", max_length=320)
    detail_level: str = Field(default="operacional", pattern="^(resumido|operacional|detalhado)$")
    api_approved: bool = False
    api_budget_usd: float = Field(default=1.0, ge=0.1, le=50.0)
