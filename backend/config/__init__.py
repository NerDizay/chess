"""Настройки, не читаемые из .env (секреты и окружение — в `backend/auth/config.py`)."""

from backend.config.game_play import game_play_config

__all__ = ["game_play_config"]
