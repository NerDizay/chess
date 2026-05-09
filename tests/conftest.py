"""
Тестовое окружение: задаём переменные до импорта `backend.database` и `backend.endpoints`.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://:memory:")
os.environ.setdefault("DB_GENERATE_SCHEMAS", "true")
os.environ.setdefault(
    "JWT_SECRET",
    "test-jwt-secret-key-at-least-32-characters-long-for-hs256",
)
