"""Authentication boundary prepared for a future, server-verified provider.

No Supabase client, remote request, credential parsing, or authenticated session
exists here yet. Local mode deliberately leaves the existing API open. Required
mode stays closed until provider verification AND resource authorization exist.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Literal, Mapping, Protocol
from urllib.parse import unquote

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


AuthMode = Literal["local", "required"]
AuthStatus = Literal["not_configured", "integration_pending"]
SESSION_COOKIE = "btime_rpa_session"
UNAVAILABLE_MESSAGE = (
    "O login e a recuperação de senha ainda não estão disponíveis. "
    "A integração com o Supabase precisa ser concluída."
)
PUBLIC_AUTH_ENDPOINTS = frozenset({
    ("GET", "/api/auth/config"),
    ("GET", "/api/auth/session"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/recover"),
    ("POST", "/api/auth/logout"),
})


@dataclass(frozen=True)
class AuthSettings:
    mode: AuthMode
    status: AuthStatus
    invalid_mode: bool = False

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> AuthSettings:
        environment = os.environ if environment is None else environment
        value = environment.get("AUTH_MODE", "local").strip()
        valid = value in {"local", "required"}
        mode: AuthMode = "local" if value == "local" else "required"
        # Presence is only a preparation stage: never an authentication signal.
        configured = bool(environment.get("SUPABASE_URL", "").strip()) and bool(
            environment.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
        )
        return cls(mode, "integration_pending" if configured else "not_configured", not valid)

    @property
    def message(self) -> str:
        if self.invalid_mode:
            return "AUTH_MODE inválido. A API está bloqueada; use local ou required. " + UNAVAILABLE_MESSAGE
        if self.mode == "local":
            return "Modo local sem proteção de acesso. " + UNAVAILABLE_MESSAGE
        return "A API está bloqueada porque a autenticação é obrigatória. " + UNAVAILABLE_MESSAGE

    def public_config(self) -> dict:
        return {
            "mode": self.mode,
            "provider": "supabase",
            "status": self.status,
            "enabled": False,
            "can_continue_local": self.mode == "local",
            "message": self.message,
        }


@dataclass(frozen=True)
class VerifiedIdentity:
    """Only a future provider validating JWTs on the server may produce this."""
    user_id: str
    session_id: str


class AuthNotConfigured(RuntimeError):
    pass


class AuthProvider(Protocol):
    """Future integration must also enforce resource ownership outside this API."""

    async def verify_access_token(self, access_token: str) -> VerifiedIdentity: ...

    async def login(self, email: str, password: str) -> VerifiedIdentity: ...

    async def recover(self, email: str) -> None: ...

    async def revoke_session(self, access_token: str) -> None: ...


class PendingSupabaseProvider:
    """An unavailable adapter; environment values cannot activate it."""

    async def verify_access_token(self, access_token: str) -> VerifiedIdentity:
        raise AuthNotConfigured(UNAVAILABLE_MESSAGE)

    async def login(self, email: str, password: str) -> VerifiedIdentity:
        raise AuthNotConfigured(UNAVAILABLE_MESSAGE)

    async def recover(self, email: str) -> None:
        raise AuthNotConfigured(UNAVAILABLE_MESSAGE)

    async def revoke_session(self, access_token: str) -> None:
        raise AuthNotConfigured(UNAVAILABLE_MESSAGE)


def unavailable(settings: AuthSettings | None = None) -> JSONResponse:
    return JSONResponse(
        {"detail": settings.message if settings else UNAVAILABLE_MESSAGE, "code": "auth_not_configured"},
        status_code=503,
        headers={"Cache-Control": "no-store"},
    )


class AuthBoundaryMiddleware:
    """Gate every API operation before FastAPI reads bodies or dispatches routes."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            settings = AuthSettings.from_environment()
            path = scope.get("path", "")  # ASGI already decodes percent-encoded paths.
            # Match the router when the app is mounted behind a proxy prefix.
            root_path = scope.get("root_path", "")
            if root_path and path.startswith(root_path + "/"):
                path = path[len(root_path):]
            # Also reject double-encoded API delimiters; allowlisting remains exact.
            api_path = unquote(path)
            is_api = api_path == "/api" or api_path.startswith("/api/")
            public = (scope.get("method"), path) in PUBLIC_AUTH_ENDPOINTS
            if settings.mode == "required" and is_api and not public:
                await unavailable(settings)(scope, receive, send)
                return
        await self.app(scope, receive, send)


router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.get("/config")
async def auth_config():
    return JSONResponse(AuthSettings.from_environment().public_config(), headers={"Cache-Control": "no-store"})


@router.get("/session")
async def auth_session():
    settings = AuthSettings.from_environment()
    return JSONResponse({
        "authenticated": False, "user": None,
        "mode": settings.mode, "provider": "supabase", "status": settings.status,
    }, headers={"Cache-Control": "no-store"})


@router.post("/login")
async def auth_login():
    # Do not bind a body or read credentials while the provider is unavailable.
    return unavailable()


@router.post("/recover")
async def auth_recover():
    return unavailable()


@router.post("/logout")
async def auth_logout():
    # This only clears our reserved browser cookie. No provider session exists
    # and this response makes no claim about revoking a Supabase session.
    response = JSONResponse({"authenticated": False, "user": None}, headers={"Cache-Control": "no-store"})
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")
    return response


def install_auth(app: FastAPI) -> None:
    app.include_router(router)
    app.add_middleware(AuthBoundaryMiddleware)
