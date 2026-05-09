from authlib.integrations.starlette_client import OAuth

from .config import get_settings

_oauth: OAuth | None = None


def get_oauth_client() -> OAuth:
    global _oauth
    if _oauth is None:
        settings = get_settings()
        if not settings.google_client_id or not settings.google_client_secret:
            raise RuntimeError("Google OAuth credentials are missing.")
        _oauth = OAuth()
        _oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    return _oauth
