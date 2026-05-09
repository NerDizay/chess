# Сборка Vue → static/, затем образ с FastAPI
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# asyncpg (и др. нативные пакеты) для Python 3.14 часто ставятся из исходников — нужны gcc и заголовки libpq.
# После pip dev-пакеты снимаем, runtime остаётся libpq5.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libpq-dev \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/requirements.txt requirements.txt
# Как при локальной установке в README: python -m pip
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && apt-get update \
    && apt-get purge -y gcc libc6-dev libpq-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . .
COPY --from=frontend /app/static ./static

EXPOSE 8000

# Одна строка JSON — иначе часть сборщиков Docker ошибочно трактует следующие строки как новые инструкции
CMD ["uvicorn", "backend.endpoints:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
