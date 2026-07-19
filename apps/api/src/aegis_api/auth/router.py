"""Authentication HTTP routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from aegis_contracts import (
    AegisEnvironment,
    AegisSettings,
    ApiErrorEnvelopeV1,
    AuthErrorCode,
    AuthMethodV1,
    AuthSessionResponseV1,
    DevLoginRequestV1,
    PlatformRoleV1,
)
from aegis_contracts.errors import ContractValidationError
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_policy.authz import build_actor
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from aegis_api.auth.deps import CurrentActor, get_auth_service, require_actor
from aegis_api.auth.oidc import AuthOidcError, create_oidc_provider, create_pkce_pair
from aegis_api.auth.service import DEV_SEED_USERS, AuthService, AuthServiceError
from aegis_api.auth.tokens import generate_opaque_token
from aegis_api.db.session import get_db_session_maker

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class PasswordLoginRequestV1(BaseModel):
    """Username/password login body. The password is verified then discarded."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1, default=1)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class AccountSetupRequestV1(BaseModel):
    """First-run admin creation body (only accepted while no accounts exist)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1, default=1)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
    display_name: str = Field(alias="displayName", default="", max_length=256)

# Pending OIDC login state (nonce/PKCE verifier), keyed by the opaque `state`.
#
# Single-instance only: this store is process-local, so an OIDC callback must be
# routed back to the same API instance that served /login. Horizontal scaling
# requires a shared store (e.g. Redis); this limitation is recorded in
# docs/release/known-issues.md. Entries are bounded by both a TTL sweep (below)
# and a hard capacity cap so abandoned logins cannot grow memory without limit.
_OIDC_STATE: dict[str, dict[str, str]] = {}
_OIDC_STATE_TTL_SECONDS = 600
_OIDC_STATE_MAX_ENTRIES = 512


def _parse_oidc_created_at(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=UTC)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


def _prune_oidc_state(*, now: datetime) -> None:
    """Evict expired and over-capacity pending OIDC states.

    Uses the stored ``created_at`` to reject entries older than the TTL, then
    enforces the capacity cap by evicting the oldest entries first.
    """
    cutoff = now - timedelta(seconds=_OIDC_STATE_TTL_SECONDS)
    expired = [
        key
        for key, entry in _OIDC_STATE.items()
        if _parse_oidc_created_at(entry.get("created_at")) < cutoff
    ]
    for key in expired:
        _OIDC_STATE.pop(key, None)
    overflow = len(_OIDC_STATE) - _OIDC_STATE_MAX_ENTRIES
    if overflow > 0:
        oldest = sorted(
            _OIDC_STATE.items(),
            key=lambda item: _parse_oidc_created_at(item[1].get("created_at")),
        )
        for key, _entry in oldest[:overflow]:
            _OIDC_STATE.pop(key, None)


def _error_response(exc: AuthServiceError | AuthOidcError) -> JSONResponse:
    if isinstance(exc, AuthOidcError):
        code = exc.code.value
        message = exc.message
        status = 400
        details: dict[str, object] = {}
    else:
        code = exc.code.value
        message = exc.message
        status = exc.status_code
        details = exc.details
    envelope = ApiErrorEnvelopeV1(
        schema_version=1,
        code=code,
        message=message,
        details=details,
    )
    return JSONResponse(status_code=status, content=envelope.model_dump(by_alias=True))


def _set_session_cookies(
    response: Response,
    *,
    settings: AegisSettings,
    raw_token: str,
    csrf_token: str,
    max_age: int,
) -> None:
    secure = settings.AEGIS_ENV == AegisEnvironment.PRODUCTION
    response.set_cookie(
        key=settings.AEGIS_SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        key=settings.AEGIS_CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


def _clear_session_cookies(response: Response, *, settings: AegisSettings) -> None:
    response.delete_cookie(settings.AEGIS_SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(settings.AEGIS_CSRF_COOKIE_NAME, path="/")


@router.get("/session", response_model=AuthSessionResponseV1)
async def get_session(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponseV1 | JSONResponse:
    settings: AegisSettings = request.app.state.settings
    raw_token = request.cookies.get(settings.AEGIS_SESSION_COOKIE_NAME)
    if not raw_token:
        return auth_service.session_response(actor=None, session=None)
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            actor = await auth_service.resolve_actor_from_token(uow, raw_token=raw_token)
            session = await auth_service.get_session_info(uow, session_id=actor.session_id)
            return auth_service.session_response(actor=actor, session=session)
    except AuthServiceError:
        return auth_service.session_response(actor=None, session=None)


def _validation_error_response(exc: ContractValidationError) -> JSONResponse:
    envelope = ApiErrorEnvelopeV1(
        schema_version=1,
        code=str(exc.code.value) if hasattr(exc.code, "value") else str(exc.code),
        message=str(exc),
        details=dict(getattr(exc, "details", {}) or {}),
    )
    return JSONResponse(status_code=422, content=envelope.model_dump(by_alias=True))


@router.get("/setup-status")
async def setup_status(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> JSONResponse:
    """Public: report whether first-run admin setup is still available.

    ``setupRequired`` is true only while no password account exists. This gates the
    web first-run "create admin" screen; the endpoint reveals only initialization
    state, not any account detail.
    """
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            required = await auth_service.setup_required(uow)
    except AuthServiceError:
        required = False
    return JSONResponse(content={"schemaVersion": 1, "setupRequired": required})


@router.post("/setup", response_model=AuthSessionResponseV1)
async def setup_admin(
    request: Request,
    body: AccountSetupRequestV1,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    """Public first-run endpoint: create the initial admin and sign in.

    Self-disabling — succeeds only while the users table has no password account;
    once one exists it fails closed (409). This is the only unauthenticated path to
    create an account.
    """
    settings: AegisSettings = request.app.state.settings
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            actor, session, raw_token = await auth_service.bootstrap_admin(
                uow,
                username=body.username,
                password=body.password,
                display_name=body.display_name,
                request_id=request.headers.get("X-Request-Id"),
            )
            payload = auth_service.session_response(actor=actor, session=session)
            response = JSONResponse(content=payload.model_dump(by_alias=True))
            _set_session_cookies(
                response,
                settings=settings,
                raw_token=raw_token,
                csrf_token=session.csrf_token,
                max_age=settings.AEGIS_SESSION_TTL_SECONDS,
            )
            return response
    except ContractValidationError as exc:
        return _validation_error_response(exc)
    except AuthServiceError as exc:
        return _error_response(exc)


@router.post("/login", response_model=AuthSessionResponseV1)
async def password_login(
    request: Request,
    body: PasswordLoginRequestV1,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    """Public: verify a username/password and issue a session.

    Available in every environment (unlike ``/dev/login``). Wrong password and
    unknown username both fail closed with the same generic error and no
    enumeration signal. Coexists with the OIDC ``GET /login`` redirect.
    """
    settings: AegisSettings = request.app.state.settings
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            actor, session, raw_token = await auth_service.authenticate_password(
                uow,
                username=body.username,
                password=body.password,
                request_id=request.headers.get("X-Request-Id"),
            )
            payload = auth_service.session_response(actor=actor, session=session)
            response = JSONResponse(content=payload.model_dump(by_alias=True))
            _set_session_cookies(
                response,
                settings=settings,
                raw_token=raw_token,
                csrf_token=session.csrf_token,
                max_age=settings.AEGIS_SESSION_TTL_SECONDS,
            )
            return response
    except AuthServiceError as exc:
        return _error_response(exc)


@router.post("/dev/login", response_model=AuthSessionResponseV1)
async def dev_login(
    request: Request,
    body: DevLoginRequestV1,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    settings: AegisSettings = request.app.state.settings
    if settings.AEGIS_ENV == AegisEnvironment.PRODUCTION or not settings.AEGIS_DEV_AUTH_ENABLED:
        return _error_response(
            AuthServiceError(
                code=AuthErrorCode.DEV_AUTH_DISABLED,
                message="Development authentication is disabled",
                status_code=403,
            )
        )
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            user = await uow.auth.get_user(body.user_id)
            if user is None:
                raise AuthServiceError(
                    code=AuthErrorCode.INVALID_CREDENTIALS,
                    message="Unknown development user",
                    status_code=401,
                )
            actor, session, raw_token = await auth_service.create_session_for_user(
                uow,
                user=user,
                auth_method=AuthMethodV1.DEV,
                request_id=request.headers.get("X-Request-Id"),
            )
            payload = auth_service.session_response(actor=actor, session=session)
            response = JSONResponse(content=payload.model_dump(by_alias=True))
            _set_session_cookies(
                response,
                settings=settings,
                raw_token=raw_token,
                csrf_token=session.csrf_token,
                max_age=settings.AEGIS_SESSION_TTL_SECONDS,
            )
            return response
    except AuthServiceError as exc:
        return _error_response(exc)


@router.post("/logout", response_model=AuthSessionResponseV1)
async def logout(
    request: Request,
    actor: Annotated[CurrentActor, Depends(require_actor)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    settings: AegisSettings = request.app.state.settings
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            await auth_service.logout(
                uow,
                actor=actor,
                request_id=request.headers.get("X-Request-Id"),
            )
            payload = auth_service.session_response(actor=None, session=None)
            response = JSONResponse(content=payload.model_dump(by_alias=True))
            _clear_session_cookies(response, settings=settings)
            return response
    except AuthServiceError as exc:
        return _error_response(exc)


@router.post("/ws-ticket")
async def create_ws_ticket(
    request: Request,
    actor: Annotated[CurrentActor, Depends(require_actor)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> JSONResponse:
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            ticket = await auth_service.issue_ws_ticket(uow, actor=actor)
            return JSONResponse(
                content={
                    "schemaVersion": 1,
                    "ticket": ticket,
                    "expiresInSeconds": 300,
                }
            )
    except AuthServiceError as exc:
        return _error_response(exc)


@router.get("/login")
async def oidc_login(request: Request) -> Response:
    settings: AegisSettings = request.app.state.settings
    if not settings.AEGIS_OIDC_ENABLED:
        return _error_response(
            AuthServiceError(
                code=AuthErrorCode.OIDC_FAILED,
                message="OIDC login is not configured",
                status_code=400,
            )
        )
    provider = create_oidc_provider(settings)
    state = generate_opaque_token(nbytes=16)
    nonce = generate_opaque_token(nbytes=16)
    verifier, challenge = create_pkce_pair()
    now = datetime.now(tz=UTC)
    _OIDC_STATE[state] = {
        "nonce": nonce,
        "verifier": verifier,
        "created_at": now.isoformat(),
    }
    _prune_oidc_state(now=now)
    try:
        url = provider.build_authorize_url(
            state=state,
            nonce=nonce,
            code_challenge=challenge,
        )
    except AuthOidcError as exc:
        return _error_response(exc)
    return RedirectResponse(url=url, status_code=302)


@router.get("/callback")
async def oidc_callback(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    code: str | None = None,
    state: str | None = None,
) -> Response:
    settings: AegisSettings = request.app.state.settings
    if not settings.AEGIS_OIDC_ENABLED:
        return _error_response(
            AuthServiceError(
                code=AuthErrorCode.OIDC_FAILED,
                message="OIDC callback is not configured",
                status_code=400,
            )
        )
    # Sweep expired states first so an abandoned/expired login cannot complete.
    _prune_oidc_state(now=datetime.now(tz=UTC))
    if not code or not state or state not in _OIDC_STATE:
        return _error_response(
            AuthServiceError(
                code=AuthErrorCode.OIDC_FAILED,
                message="Invalid OIDC callback state",
                status_code=400,
            )
        )
    pending = _OIDC_STATE.pop(state)
    provider = create_oidc_provider(settings)
    try:
        claims = await provider.exchange_code(code=code, code_verifier=pending["verifier"])
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            user = await uow.auth.get_user_by_external_identity(
                issuer=claims.issuer,
                subject=claims.subject,
            )
            if user is None:
                # First-login provisioning maps OIDC subject into a pending operator
                # only when an admin has pre-created the user linkage.
                raise AuthServiceError(
                    code=AuthErrorCode.INVALID_CREDENTIALS,
                    message="No linked AEGIS user for OIDC identity",
                    status_code=401,
                )
            actor, session, raw_token = await auth_service.create_session_for_user(
                uow,
                user=user,
                auth_method=AuthMethodV1.OIDC,
                request_id=request.headers.get("X-Request-Id"),
            )
            response = RedirectResponse(
                url=f"{settings.AEGIS_WEB_BASE_URL}/",
                status_code=302,
            )
            _set_session_cookies(
                response,
                settings=settings,
                raw_token=raw_token,
                csrf_token=session.csrf_token,
                max_age=settings.AEGIS_SESSION_TTL_SECONDS,
            )
            _ = actor
            return response
    except (AuthOidcError, AuthServiceError) as exc:
        return _error_response(exc)


@router.get("/dev/users")
async def list_dev_users(request: Request) -> JSONResponse:
    settings: AegisSettings = request.app.state.settings
    if settings.AEGIS_ENV == AegisEnvironment.PRODUCTION or not settings.AEGIS_DEV_AUTH_ENABLED:
        return _error_response(
            AuthServiceError(
                code=AuthErrorCode.DEV_AUTH_DISABLED,
                message="Development authentication is disabled",
                status_code=403,
            )
        )
    return JSONResponse(
        content={
            "schemaVersion": 1,
            "users": [
                {
                    "userId": user_id,
                    "displayName": display_name,
                    "roles": [role.value for role in roles],
                }
                for user_id, display_name, roles in DEV_SEED_USERS
            ],
        }
    )


# Silence unused import for type checkers that do not see Depends usage.
_ = (PlatformRoleV1, build_actor)
