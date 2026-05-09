"""Идентификаторы пользователей: UUID v7 через uuid-utils (Rust), типы совместимы с uuid.UUID."""

from uuid import UUID

from uuid_utils.compat import uuid7


def new_user_uuid() -> UUID:
    return uuid7()
