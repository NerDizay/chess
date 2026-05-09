# CHESS

## Запуск API

1. Один раз создай виртуальное окружение через pyenv (если ещё не создано):

```bash
source ~/.pyenv/activate
pyenv virtualenv 3.14.0 chess_venv
```

2. Перед работой в каждой новой сессии терминала активируй окружение так:

```bash
source ~/.pyenv/activate
pyenv activate chess_venv
```

3. Установи зависимости:

```bash
python -m pip install -r deploy/requirements.txt
```

Файлы **`deploy/requirements.txt`** и **`deploy/requirements-dev.txt`** задают зависимости; метаданные и инструменты (Aerich и др.) — в **`deploy/pyproject.toml`**. Настройки pytest для запуска из корня репозитория — в **`pytest.ini`**.

Подсказки типов (Pylance / BasedPyright): в **`pyrightconfig.json`** по умолчанию указано pyenv-окружение **`chess_venv`** (`venvPath` + `venv`). Если у тебя другое имя venv или локальный **`.venv`** — измени значения в **`pyrightconfig.json`** или выбери интерпретатор вручную (**«Python: Select Interpreter»**).

4. Скопируй пример переменных окружения и при необходимости измени значения:

```bash
cp env.example .env
```

Для локальной разработки без PostgreSQL можно использовать SQLite, например:

```bash
DATABASE_URL=sqlite://./chess.db
DB_GENERATE_SCHEMAS=true
```

Для PostgreSQL укажи свой URL в `DATABASE_URL`. Миграции Aerich лежат в **`migrations/models/`**, конфиг — **`pyproject.toml`** в корне репозитория. При старте API вызывается `aerich upgrade` (через `Command` в `backend/database.py`). Локально, после изменения моделей: из корня проекта, с тем же `DATABASE_URL`, что в `.env`:

```bash
aerich migrate --name описание_изменения
aerich upgrade
```

5. Запусти сервер:

```bash
uvicorn backend.endpoints:app --reload --host 0.0.0.0 --port 8000
```

Открой документацию интерактивно: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Эндпоинты REST-слоя имеют префикс **`/api`** (например `GET /api/health`).

Корень сайта [http://127.0.0.1:8000/](http://127.0.0.1:8000/) отдаёт собранный Vue (`static/index.html`). Если сборки ещё нет — ответ **503** с пустым телом.

В `.env` обязательно задай **`JWT_SECRET`** (см. `env.example`). Для тестов используется значение из `tests/conftest.py`.

### Какие команды считать эталоном

Чтобы README и фактический запуск не расходились:

- После `pyenv activate chess_venv` везде используй **`python`** (не `python3`): **`python -m pip`**, **`python -m pytest`** — как в блоках выше и в разделе «Запуск тестов».
- API локально: **`uvicorn backend.endpoints:app --reload --host 0.0.0.0 --port 8000`**. В контейнере `web` сервер поднимается тем же способом (`uvicorn` в **`deploy/Dockerfile`**, плюс `--proxy-headers` для nginx). При желании локально можно вызвать эквивалент **`python -m uvicorn backend.endpoints:app --reload --host 0.0.0.0 --port 8000`**.
- **Нестандартно (только внутри Docker):** в **`deploy/docker-compose.yml`** у сервиса `web` в **healthcheck** вызывается **`python -c "..."`** с `urllib` — это проверка `GET /api/health` без установки `curl` в образ; пользовательскую команду из README это не заменяет.

## Фронтенд (Vue 3 + Vite)

Исходники в каталоге **`frontend/`**. Сборка складывается в **`static/`** (`index.html` и `assets/*`). CSS и JS из Vue-проекта попадают в `static/assets/` после каждого билда.

**Сборка под продакшен:**

```bash
cd frontend
npm install
npm run build
```

После этого перезапускать uvicorn не обязательно — раздаются уже новые файлы из `static/`.

**Разработка с hot-reload:** в одном терминале API на порту 8000, во втором:

```bash
cd frontend
npm run dev
```

Открывай [http://127.0.0.1:5173](http://127.0.0.1:5173) — Vite проксирует запросы с префиксом **`/api`** на бэкенд (см. `frontend/vite.config.js`). Запросы к статике и модулям Vite обслуживает сам dev-сервер.

Интерфейс — один адрес **`/`** (без **`#`** в URL и без **vue-router**): корневой **`App.vue`** подставляет нужное представление из **`frontend/src/views/`** (вход / игра) по состоянию и cookie.

### SVG-фигуры на доске

Графика фигур лежит в **`frontend/public/`** и раздаётся Vite как статика с корня сайта. Имена файлов совпадают с типом и цветом фигуры из API: **`{white|black}_{king|queen|rook|bishop|knight|pawn}.svg`** (например `white_king.svg`, `black_pawn.svg`). В коде доски URL собирается в **`frontend/src/components/ChessBoard.vue`** в функции **`pieceSvgSrc`** как **`/${color}_${name}.svg`**.

Если перенесёшь SVG в подпапку (например **`frontend/public/pieces/`**), измени префикс в **`pieceSvgSrc`** на путь вида **`/pieces/${color}_${piece.name}.svg`** (и положи файлы в `public/pieces/` с теми же именами).

Каталог **`static/`** — результат `npm run build`; в **`.gitignore`** он исключён (билд получают локально или в Docker при сборке образа).

## Docker (Compose + nginx)

Нужны **Docker** и **Docker Compose v2**.

1. Создай `.env` из примера и задай как минимум **`JWT_SECRET`** (остальное можно по умолчанию):

```bash
cp env.example .env
# отредактируй JWT_SECRET и при необходимости Google OAuth
```

2. Запуск «продакшн»-стека (nginx + web + PostgreSQL): образ **`web`** собирается из **`deploy/Dockerfile`**.

**Сборка статики при деплое:** в Dockerfile есть стадия **`frontend`** (`node:22-alpine`): `npm ci`, затем **`npm run build`** — Vite кладёт SPA в **`static/`**, финальный образ копирует её в контейнер (`COPY --from=frontend …`). Отдельной команды «собрать статику» в compose не требуется: всё выполняется при **`docker compose … build`**.

```bash
docker compose -f deploy/docker-compose.yml up --build
```

В образе **`python -m pip install`** может собирать **asyncpg** из исходников (для свежего Python не всегда есть готовые wheels на PyPI). В **`deploy/Dockerfile`** на этот шаг ставятся компилятор и **`libpq-dev`**, затем они удаляются; локально у вас обычно всё ставится без этого.

**Локальная разработка без nginx:** только PostgreSQL в Docker, API и Vite на хосте:

```bash
docker compose -f deploy/docker-compose.dev.yml up -d
```

В `.env` выставь **`DATABASE_URL=postgres://postgres:postgres@localhost:5432/chess`** (порт **5432** проброшен наружу; volume **`postgres_dev_data`** отделён от продакшн-volume **`postgres_data`**). Затем **`uvicorn backend.endpoints:app …`** и во втором терминале **`cd frontend && npm run dev`**. Запросы к **`/api`** с дев-сервера Vite идут через **proxy** в **`frontend/vite.config.js`** на тот же origin — **CORS обычно не нужен**. Если фронт открыт с другого origin (без proxy), задай в `.env` **`CORS_ORIGINS`** — через запятую список origin (см. **`env.example`**).

3. В браузере: приложение и API через nginx — **[http://localhost](http://localhost)** (порт задаётся переменной **`HTTP_PORT`**, по умолчанию **80**). Документация API: [http://localhost/docs](http://localhost/docs).

Сервисы в **`deploy/docker-compose.yml`**:

| Сервис | Роль |
|--------|------|
| **db** | PostgreSQL 16, данные в volume `postgres_data` |
| **web** | FastAPI (uvicorn), фронт собирается стадией Node в **`deploy/Dockerfile`** |
| **nginx** | Прокси на `web:8000`, конфиг **`deploy/nginx.conf`** смонтирован только для чтения |

Для Docker в compose переопределены **`DATABASE_URL`** (хост `db`) и **`DB_GENERATE_SCHEMAS=true`** (создание таблиц при старте; для продакшена лучше миграции Aerich). По умолчанию **`GOOGLE_REDIRECT_URI`** и **`FRONTEND_AFTER_LOGIN_URL`** указывают на `http://localhost/...`; для продакшена задай их в `.env`.

**Перезагрузка nginx после правки `deploy/nginx.conf`:**

```bash
docker compose -f deploy/docker-compose.yml exec nginx nginx -t && docker compose -f deploy/docker-compose.yml exec nginx nginx -s reload
```

**Полный перезапуск nginx:** `docker compose -f deploy/docker-compose.yml restart nginx`.

Файлы: **`deploy/Dockerfile`**, **`deploy/Dockerfile.dockerignore`**, **`deploy/docker-compose.yml`** (полный стек), **`deploy/docker-compose.dev.yml`** (только БД для dev), **`deploy/nginx.conf`**. Контекст сборки — корень репозитория (`build.context: ..` в compose).

## Аутентификация

- **JWT** в cookie (`COOKIE_NAME`, по умолчанию `access_token`): в токене поля **`sub`** (UUID пользователя) и **`name`**. Для проверки запросов пользователя можно не ходить в БД — достаточно валидного JWT (эндпоинты игр всё же проверяют, что пользователь ещё есть в БД, чтобы не создавать игры «по поддельному» токену).
- Идентификатор пользователя в БД — **UUID v7**, генерируется пакетом **[uuid-utils](https://pypi.org/project/uuid-utils/)** (реализация на Rust; через `uuid_utils.compat` возвращаются обычные `uuid.UUID` для ORM и JWT).
- **Анонимный режим**: `POST /api/auth/anonymous` — создаёт пользователя с флагом анонима и время жизни **`ANONYMOUS_TTL_HOURS`**; при старте приложения удаляются просроченные анонимные аккаунты (история не гарантируется).
- **Google**: в Google Cloud Console создай OAuth Client (тип Web), укажи redirect URI как **`GOOGLE_REDIRECT_URI`** (например `http://127.0.0.1:8000/api/auth/google/callback` или через nginx `http://localhost/api/auth/google/callback`). Затем задай `GOOGLE_CLIENT_ID` и `GOOGLE_CLIENT_SECRET`. Эндпоинты: `GET /api/auth/google` → редирект на Google, `GET /api/auth/google/callback` → установка cookie и редирект на **`FRONTEND_AFTER_LOGIN_URL`**.
- **Выход**: `POST /api/auth/logout` — сбрасывает cookie.
- **Текущий пользователь / партии**: WebSocket **`/api/ws`** — после установки соединения пользователь определяется **один раз** по cookie JWT из handshake; поле **`id`** в JSON сообщений нужно только чтобы сопоставить ответ с запросом в браузере. Действия: `auth.me`, `games.create`, `games.get` (+ `game_id`). После **`POST /api/auth/anonymous`** клиент должен открыть новый WS (cookie обновилась).

HTTP сохранены: **`GET /api/health`**, **`POST /api/auth/anonymous`**, **`POST /api/auth/logout`**, редиректы Google OAuth.

## Запуск тестов

Сначала активируй то же окружение (`source ~/.pyenv/activate`, затем `pyenv activate chess_venv`), затем:

```bash
python -m pip install -r deploy/requirements-dev.txt
python -m pytest -v
```

Через `tests/conftest.py` задаются также `JWT_SECRET`, `DATABASE_URL` и `DB_GENERATE_SCHEMAS` (SQLite в памяти для pytest).
