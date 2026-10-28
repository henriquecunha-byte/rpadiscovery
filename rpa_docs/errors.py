"""Safe public failures and deliberately minimal server diagnostics.

Provider messages, subprocess output and exception tracebacks can contain
credentials, request bodies or private paths. None belongs in job history,
downloadable warnings or browser responses.
"""
from __future__ import annotations

import logging
import re
import subprocess

from openai import APIConnectionError, APITimeoutError


LOGGER = logging.getLogger("rpa_docs.failures")
_OPERATIONS = frozenset({
    "guide_improvement", "prompt_suggestion", "visual_analysis", "document_synthesis",
    "job_processing", "transcription", "word_export", "pdf_export", "drive_status",
    "drive_connect", "drive_callback", "drive_files", "drive_import", "drive_upload",
})
MESSAGES = {
    "ai_configuration": "O serviço de IA não está configurado neste ambiente. Peça à pessoa responsável para verificar o provedor e a credencial no servidor.",
    "ai_credits": "O projeto ficou sem créditos de IA. Peça à pessoa responsável para verificar o saldo no Lovable e depois retome a análise.",
    "processing": "Não foi possível concluir o processamento. Os arquivos enviados foram preservados. Tente retomar a análise; se persistir, peça à pessoa responsável pelo ambiente para verificar a configuração.",
    "access": "O ambiente não conseguiu acessar um arquivo necessário. Os arquivos enviados foram preservados. Peça à pessoa responsável para revisar as permissões antes de retomar.",
    "missing_file": "Um arquivo necessário não está disponível no ambiente. Verifique as gravações e os arquivos de trabalho antes de retomar a análise.",
    "media": "Não foi possível ler ou preparar a gravação. Verifique se o vídeo abre corretamente e tente retomar a análise.",
    "prepare_video": "Não foi possível preparar uma das gravações. Verifique os vídeos enviados e tente retomar a análise.",
    "combine_videos": "Não foi possível consolidar as gravações. Verifique os vídeos e a disponibilidade de espaço antes de retomar.",
    "preview_segment": "Não foi possível montar um trecho do preview. Tente retomar a análise; se persistir, revise a gravação e os cortes solicitados.",
    "preview_finalize": "Não foi possível finalizar o preview. Verifique a disponibilidade de espaço e tente retomar a análise.",
    "transcription": "Transcrição indisponível. Peça à pessoa responsável pelo ambiente para verificar o modelo local, os arquivos e as dependências; depois tente novamente.",
    "word_export": "Documento Word indisponível. Peça à pessoa responsável pelo ambiente para verificar as dependências de exportação e tente gerar os documentos novamente.",
    "pdf_export": "Exportação em PDF indisponível. Peça à pessoa responsável pelo ambiente para verificar as dependências de exportação e tente gerar os documentos novamente.",
    "ai_credential": "O serviço de IA não aceitou a credencial configurada. Peça à pessoa responsável pelo ambiente para revisar a configuração.",
    "ai_permission": "O serviço de IA não autorizou esta operação. Peça à pessoa responsável pelo ambiente para revisar as permissões do projeto e do modelo.",
    "ai_limit": "O serviço de IA atingiu um limite de uso. Tente novamente mais tarde; se persistir, peça à pessoa responsável pelo ambiente para verificar os limites e a disponibilidade de uso.",
    "ai_timeout": "O serviço de IA demorou além do esperado. Tente novamente em instantes.",
    "ai_connection": "Não foi possível conectar ao serviço de IA. Verifique a conexão do ambiente e tente novamente.",
    "ai_unavailable": "O serviço de IA está temporariamente indisponível. Tente novamente em instantes.",
    "ai_request": "Não foi possível concluir a solicitação à IA. Revise as informações e tente novamente; se persistir, peça à pessoa responsável pelo ambiente para verificar a configuração.",
}


class PublicProcessingError(RuntimeError):
    """Internal allowlisted code; never wrap a provider's message here."""

    def __init__(self, code: str):
        self.code = code if code in MESSAGES else "processing"
        super().__init__(MESSAGES[self.code])


def ai_failure_code(error: Exception) -> str:
    if isinstance(error, PublicProcessingError) and error.code.startswith("ai_"):
        return error.code
    status = getattr(error, "status_code", None)
    if type(status) is int:
        if status in {401, 402, 403, 429}:
            return {401: "ai_credential", 402: "ai_credits", 403: "ai_permission", 429: "ai_limit"}[status]
        if status >= 500:
            return "ai_unavailable"
    if isinstance(error, (APITimeoutError, TimeoutError)):
        return "ai_timeout"
    if isinstance(error, (APIConnectionError, ConnectionError)):
        return "ai_connection"
    return "ai_request"


def public_failure(error: Exception, *, operation: str = "processing") -> str:
    """Map exceptions to fixed copy without invoking str/repr on the error."""
    if isinstance(error, PublicProcessingError):
        return MESSAGES.get(error.code, MESSAGES["processing"])
    if operation in MESSAGES and operation != "processing":
        return MESSAGES[operation]
    if isinstance(error, PermissionError):
        return MESSAGES["access"]
    if isinstance(error, FileNotFoundError):
        return MESSAGES["missing_file"]
    if isinstance(error, subprocess.SubprocessError):
        return MESSAGES["media"]
    return MESSAGES["processing"]


def log_failure(operation: str, error: Exception) -> None:
    """Log only the static operation, exception class and integer HTTP status.

    Never add exc_info, a traceback, request/response metadata, or the original
    exception as a formatting argument. Unknown status is represented by 0.
    """
    operation_name = operation if operation in _OPERATIONS else "unknown"
    error_type = type(error).__name__
    error_type = error_type if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", error_type) else "Exception"
    status = getattr(error, "status_code", None)
    status = status if type(status) is int and 100 <= status <= 599 else 0
    LOGGER.warning("operation=%s type=%s status=%d", operation_name, error_type, status)
