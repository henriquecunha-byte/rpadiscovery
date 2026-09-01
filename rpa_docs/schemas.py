from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    source_path: str = Field(min_length=1)
    process_context: str = Field(default="", max_length=8000)
    audience: str = Field(default="Equipe de RPA", max_length=160)
    detail_level: str = Field(default="operacional", pattern="^(resumido|operacional|detalhado)$")
    api_approved: bool = False
    api_budget_usd: float = Field(default=1.0, ge=0.1, le=50.0)


class PromptSuggestion(BaseModel):
    title: str = Field(default="", max_length=120)
    process_context: str = Field(default="", max_length=8000)
    audience: str = Field(default="Equipe de RPA", max_length=160)
    detail_level: str = Field(default="operacional", pattern="^(resumido|operacional|detalhado)$")
    sources: list[str] = Field(default_factory=list, max_length=100)


class DriveUpload(BaseModel):
    folder: str = Field(default="", max_length=1000)


class DriveImport(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    file_ids: list[str] = Field(min_length=1, max_length=100)
    process_context: str = Field(default="", max_length=8000)
    audience: str = Field(default="Equipe de RPA", max_length=160)
    detail_level: str = Field(default="operacional", pattern="^(resumido|operacional|detalhado)$")
    api_approved: bool = False
    api_budget_usd: float = Field(default=1.0, ge=0.1, le=50.0)
