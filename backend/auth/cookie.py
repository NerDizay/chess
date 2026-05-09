from datetime import timedelta

from fastapi import Response

from .config import get_settings


def set_token_cookie(response: Response, token: str, max_age_seconds: int) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def clear_token_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.cookie_name, path="/")


def jwt_max_age_seconds(expires_hours: int) -> int:
    return int(timedelta(hours=expires_hours).total_seconds())
