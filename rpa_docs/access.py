"""Provider-independent resource ownership. Never infer identity from client input.

The account provider is still unavailable. A future authentication middleware
must validate a session before setting request.state.verified_identity. Tests
override current_access in-process; there is no HTTP development-user switch.
"""
from dataclasses import dataclass

from fastapi import HTTPException, Request

from .auth import AuthSettings, VerifiedIdentity


@dataclass(frozen=True)
class AccessScope:
    # NULL is a separate, explicitly unauthenticated local/legacy scope.
    # It is never a wildcard or an account assigned to the first person to log in.
    owner_id: str | None

    def __post_init__(self):
        if self.owner_id is not None and (not isinstance(self.owner_id, str) or not self.owner_id.strip()):
            raise ValueError("A verified account needs a non-empty owner identifier.")

    @property
    def is_local(self) -> bool:
        return self.owner_id is None


def current_access(request: Request) -> AccessScope:
    identity = getattr(request.state, "verified_identity", None)
    if identity is not None:
        if not isinstance(identity, VerifiedIdentity) or not isinstance(identity.user_id, str) or not identity.user_id.strip() or not isinstance(identity.session_id, str) or not identity.session_id.strip():
            raise HTTPException(401, "Não foi possível confirmar a identidade desta sessão.")
        return AccessScope(identity.user_id)
    if AuthSettings.from_environment().mode == "local":
        return AccessScope(None)
    # Required mode already stops at the auth middleware. Fail closed here too
    # if a future route/middleware change inadvertently bypasses that boundary.
    raise HTTPException(503, "A autenticação ainda não está disponível neste ambiente.")


def require_local_drive(access: AccessScope) -> None:
    if not access.is_local:
        raise HTTPException(503, "O Google Drive por usuário ainda não está configurado. Envie os arquivos pelo computador por enquanto; a conexão local não é compartilhada entre contas.")
