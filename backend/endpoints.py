from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from backend.auth.config import get_settings
from backend.auth.jwt_tokens import create_access_token
from backend.auth.cookie import clear_token_cookie, jwt_max_age_seconds, set_token_cookie
from backend.websocket import run_api_websocket
from backend.auth.google import get_oauth_client
from backend.database import close_database, init_database
from backend.auth.dependencies import JwtIdentity, require_jwt_identity
from backend.exceptions import GameForbiddenError, GameNotFoundError, UserNotFoundError
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, WebSocket
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from backend.repositories import GameDB, QueueWhoWantPlayRepository, UserRepository, purge_expired_anonymous_users
from backend.services import GameService, UserService
from backend.websocket.registry import ws_registry
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

_BACKEND_DIR = Path(__file__).resolve().parent
STATIC_DIR = _BACKEND_DIR.parent / "static"

API_PREFIX = "/api"
api_router = APIRouter(prefix=API_PREFIX)

user_repository = UserRepository()
user_svc = UserService(user_repository)
game_db = GameDB()
queue_repo = QueueWhoWantPlayRepository(game_db)
game_service = GameService(game_db, user_svc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_database()
    await purge_expired_anonymous_users()
    yield
    await close_database()


app = FastAPI(title="Chess API", lifespan=lifespan)

_auth_settings = get_settings()
app.add_middleware(SessionMiddleware, secret_key=_auth_settings.session_secret)
if _auth_settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(_auth_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(UserNotFoundError)
async def user_not_found_handler(_request: Request, exc: UserNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@api_router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@api_router.get("/matchmaking/waiting")
async def http_matchmaking_waiting(
    ident: JwtIdentity = Depends(require_jwt_identity),
) -> dict[str, int]:
    """Сколько других пользователей в очереди (сам запросивший не учитывается)."""
    n = await queue_repo.count_others_waiting(ident.user_id)
    return {"waiting_count": n}


class AnonymousAuthBody(BaseModel):
    name: str | None = Field(default=None, max_length=30)


class GamesSyncHttpBody(BaseModel):
    game_id: int
    client_version: int | None = None
    battle_field: dict[str, object] | None = None


@api_router.get("/games/active")
async def http_games_active(ident: JwtIdentity = Depends(require_jwt_identity)) -> dict[str, object | None]:
    """Текущая парная партия (для восстановления после F5 без полного тела WS)."""
    g = await game_service.active_game_dict(ident.user_id)
    return {"game": g}


@api_router.post("/games/sync")
async def http_games_sync(
    body: GamesSyncHttpBody,
    ident: JwtIdentity = Depends(require_jwt_identity),
) -> dict[str, object]:
    """Дельта позиции относительно кэша клиента (IndexedDB)."""
    try:
        return await game_service.sync_game(
            body.game_id,
            ident.user_id,
            body.client_version,
            body.battle_field,
        )
    except GameNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except GameForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@api_router.post("/auth/anonymous")
async def auth_anonymous(payload: AnonymousAuthBody) -> JSONResponse:
    settings = get_settings()
    user = await user_svc.create_anonymous_user(payload.name, settings.anonymous_ttl_hours)
    ttl = timedelta(hours=settings.anonymous_ttl_hours)
    token = create_access_token(
        user_id=user.id,
        name=user.name,
        expires_delta=ttl,
    )
    max_age = jwt_max_age_seconds(settings.anonymous_ttl_hours)
    response = JSONResponse(
        {
            "user_id": str(user.id),
            "name": user.name,
            "is_anonymous": True,
            "expires_at": user.anonymous_expires_at.isoformat()
            if user.anonymous_expires_at
            else None,
        }
    )
    set_token_cookie(response, token, max_age)
    return response


@api_router.get("/auth/google")
async def auth_google(request: Request):
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET).",
        )
    oauth = get_oauth_client()
    google = oauth.create_client("google")
    if google is None:
        raise HTTPException(status_code=503, detail="Google OAuth client not registered.")
    return await google.authorize_redirect(request, settings.google_redirect_uri)


@api_router.get("/auth/google/callback")
async def auth_google_callback(request: Request):
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")
    oauth = get_oauth_client()
    google = oauth.create_client("google")
    if google is None:
        raise HTTPException(status_code=503, detail="Google OAuth client not registered.")
    token = await google.authorize_access_token(request)
    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(status_code=400, detail="OAuth response missing userinfo.")
    google_sub = user_info["sub"]
    email = user_info.get("email") or ""
    name = user_info.get("name") or (email.split("@")[0] if email else "User")

    user = await user_svc.upsert_google_user(google_sub, email, name)

    expire = timedelta(hours=settings.jwt_expire_hours)
    jwt_token = create_access_token(
        user_id=user.id,
        name=user.name,
        expires_delta=expire,
    )
    max_age = jwt_max_age_seconds(settings.jwt_expire_hours)
    response = RedirectResponse(url=settings.frontend_after_login_url, status_code=302)
    set_token_cookie(response, jwt_token, max_age)
    return response


@api_router.post("/auth/logout")
async def auth_logout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    clear_token_cookie(response)
    return response


@api_router.websocket("/ws")
async def api_websocket(websocket: WebSocket) -> None:
    await run_api_websocket(websocket, game_service, queue_repo, ws_registry)


app.include_router(api_router)


@app.get("/", response_model=None)
async def root_page():
    """Vue-сборка в static/index.html; без сборки — 503 без тела-подсказки."""
    built = STATIC_DIR / "index.html"
    if built.is_file():
        return FileResponse(built)
    return HTMLResponse("", status_code=503)


# После API и точного GET `/`: файлы из `static/` (JS/CSS в `static/assets/`, SVG из `public/` в корне билда).
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=False), name="static")
