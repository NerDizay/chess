from dataclasses import dataclass

from environs import Env


@dataclass(frozen=True)
class Settings:
    jwt_secret: str
    jwt_expire_hours: int
    cookie_name: str
    cookie_secure: bool
    cookie_samesite: str
    session_secret: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    frontend_after_login_url: str
    anonymous_ttl_hours: int
    cors_origins: tuple[str, ...]


def get_settings() -> Settings:
    env = Env()
    env.read_env()
    jwt_secret = env.str("JWT_SECRET")
    cors_raw = env.str("CORS_ORIGINS", "")
    cors_origins = tuple(s.strip() for s in cors_raw.split(",") if s.strip())
    return Settings(
        jwt_secret=jwt_secret,
        jwt_expire_hours=env.int("JWT_EXPIRE_HOURS", 24 * 7),
        cookie_name=env.str("COOKIE_NAME", "access_token"),
        cookie_secure=env.bool("COOKIE_SECURE", False),
        cookie_samesite=env.str("COOKIE_SAMESITE", "lax"),
        session_secret=env.str("SESSION_SECRET", jwt_secret),
        google_client_id=env.str("GOOGLE_CLIENT_ID", ""),
        google_client_secret=env.str("GOOGLE_CLIENT_SECRET", ""),
        google_redirect_uri=env.str(
            "GOOGLE_REDIRECT_URI",
            "http://127.0.0.1:8000/api/auth/google/callback",
        ),
        frontend_after_login_url=env.str("FRONTEND_AFTER_LOGIN_URL", "/"),
        anonymous_ttl_hours=env.int("ANONYMOUS_TTL_HOURS", 24),
        cors_origins=cors_origins,
    )
