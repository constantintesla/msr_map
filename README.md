# MSR Map — preshevkadastr.ru

Кадастровая игра на карте: три этапа (захват КТ, лут, схроны), роли **админ / командир / инженер**, live-карта, GPS, чат, QR-вход на объекты.

## Структура

```
msr_map/
├── backend/                 # FastAPI (REST + WebSocket)
├── frontend/                # React + Vite + Tailwind + Leaflet
├── kmz/                     # KML-пресет игры (автозагрузка при пустой БД)
├── nginx/                   # nginx.conf (HTTPS) и nginx.local.conf (HTTP)
├── docker-compose.yml       # прод: postgres + backend + frontend + nginx + certbot
├── docker-compose.local.yml # overlay: HTTP без SSL
├── docker-compose.ssl-external.yml  # overlay: внешний volume Let's Encrypt
├── start-dev.ps1            # локальная разработка (Windows)
├── start-prod.ps1           # Docker-деплой (Windows)
└── .github/workflows/ci.yml
```

## Роли

| Роль | Маршрут | Назначение |
|------|---------|------------|
| **admin** | `/#/admin` | Штаб: карта, этапы, счёт, настройки, экспорт |
| **commander** | `/#/command` | Командир стороны: карта, приказы, LPD-каналы, чат |
| **engineer** | `/#/engineer` | Полевой инженер: карта, захват/подрыв, GPS, чат |

После входа пользователь перенаправляется на домашний экран своей роли. Публичной карты без авторизации нет.

## Локальная разработка

Требования: **Python 3.12+**, **Node.js 20+**.

### Быстрый запуск (Windows)

```powershell
cd C:\projects\msr_map
.\start-dev.ps1
```

Остановка: `.\start-dev.ps1 -Stop`  
Только backend: `.\start-dev.ps1 -BackendOnly`  
Только frontend: `.\start-dev.ps1 -FrontendOnly`  
Без переустановки зависимостей: `.\start-dev.ps1 -SkipInstall`

### Backend (вручную)

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000/docs  
Health: http://localhost:8000/health

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: http://localhost:5173/#/login

### Тестовые учётные записи (seed)

| Роль | Логин | Пароль |
|------|-------|--------|
| Админ | `admin` | `admin` |
| Командир стороны A (ЛК) | `cmd_a` | `alfa` |
| Командир стороны B (СБГ) | `cmd_b` | `bravo` |
| Инженер A, слот 1 | `eng_a1` | `alfa01` |
| Инженер B, слот 1 | `eng_b1` | `bravo1` |
| Инженер A/B, слоты 2…N | `eng_a2` … `eng_bN` | случайный 6-символьный (см. админку → экспорт инженеров) |

По умолчанию создаётся **5 инженеров на сторону** (`engineers_per_side_a/b` в настройках штаба). Учётки `eng_*` синхронизируются при старте backend. Старые форматы (`ing_*`, `loot_*`, `post_*`) удаляются автоматически.

## Этапы игры

| Этап | Содержимое |
|------|------------|
| **1** | Захват контрольных точек (КТ), фаза разведки, слоты старта |
| **2** | Ящики с лутом (плёнка / прямой доступ), автовыдача целей после включения в админке |
| **3** | Схроны (пост / мертвяк): удержание 10 мин, подрыв, доставка |

Переключение этапов, старт/пауза/сброс — в админ-панели (`POST /api/admin/game/*`).

## Docker (production)

### Быстрый запуск (Windows)

```powershell
cd C:\projects\msr_map
.\start-prod.ps1
```

Скрипт создаёт `.env` из `.env.example` (с генерацией `SECRET_KEY`), поднимает стек через Docker Compose. Если SSL-сертификаты не найдены — автоматически включается **локальный HTTP-режим** (`http://localhost`).

Параметры:

| Флаг | Действие |
|------|----------|
| `-Stop` | Остановить стек |
| `-Local` | Принудительно HTTP без SSL |
| `-Rebuild` | Пересобрать образы backend/frontend |
| `-NoBuild` | Не собирать образы (только запуск) |

### Первичный выпуск SSL (Let's Encrypt)

До запуска nginx с HTTPS:

```bash
docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d preshevkadastr.ru -d www.preshevkadastr.ru \
  --email admin@preshevkadastr.ru --agree-tos --no-eff-email

docker compose up -d --build
```

Если сертификаты уже лежат во внешнем volume `msrv_b9_kadastr_certbot_conf`, `start-prod.ps1` подключит его через `docker-compose.ssl-external.yml`.

### Переменные окружения

**Корень репозитория** (`.env` для Docker):

| Переменная | Описание |
|------------|----------|
| `SECRET_KEY` | JWT-секрет (обязательно сменить) |
| `POSTGRES_PASSWORD` | Пароль PostgreSQL |
| `CORS_ORIGINS` | Опционально, origins через запятую |
| `PUBLIC_APP_URL` | Опционально, публичный URL приложения |

**Backend** (`backend/.env` для локальной разработки):

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DATABASE_URL` | SQLite (dev) / PostgreSQL (prod) | `sqlite:///./msr_map.db` |
| `SECRET_KEY` | JWT-секрет | dev-ключ (сменить!) |
| `JWT_ALGORITHM` | Алгоритм JWT | `HS256` |
| `JWT_EXPIRE_MINUTES` | Время жизни токена | `1440` |
| `HOLD_DEADMAN_SECONDS` | Таймаут dead-man ping удержания | `120` |
| `CACHE_HOLD_REQUIRED_SECONDS` | Минимальное удержание схрона (этап 3) | `600` |
| `CORS_ORIGINS` | Разрешённые origins | localhost, preshevkadastr |
| `PUBLIC_APP_URL` | Базовый URL для QR-ссылок | `https://preshevkadastr.ru` |

## API (кратко)

Полная схема: http://localhost:8000/docs

### Авторизация и статус

- `POST /api/auth/login` — JWT
- `GET /api/status` — публичный статус игры (polling)

### Удержание

- `GET /api/hold/point/{point_id}` — состояние удержания точки
- `POST /api/hold/confirm` / `leave` — ping / сброс точки
- `POST /api/hold/cache/confirm` / `leave` — ping / сброс схрона

### Точки и схроны (инженер)

- `POST /api/point/begin-capture` — начать захват КТ
- `POST /api/point/post-film-report` — отчёт с плёнкой (этап 1)
- `POST /api/point/detonate` — подрыв точки
- `POST /api/cache/breach-code` / `unlock-code` — ввод кодов
- `POST /api/cache/detonate` — подрыв схрона
- `POST /api/cache/film-report` / `deliver-report` / `deliver` — лут и доставка

### Командир и инженер

- `GET /api/commander/status` / `feed` / `engineers` / `orders`
- `POST /api/commander/orders` — полевой приказ
- `PATCH /api/commander/engineers/{id}/lpd-channel` — LPD-канал
- `GET /api/engineer/profile` / `orders/active`
- `POST /api/engineer/orders/{id}/dismiss`

### GPS, чат, QR

- `POST /api/location/ping` — координаты инженера
- `GET /api/location/engineers` — позиции на карте
- `GET/POST /api/chat/messages` — чат (текст + медиа)
- `GET /api/public/qr/{token}` — разрешение QR-токена объекта

### Админка

- `GET /api/admin/status` — расширенный статус
- `POST /api/admin/game/start|pause|reset|stage/{n}` — управление игрой
- `GET/PATCH /api/admin/settings` — настройки (радиус захвата, GPS-калибровка, пул инженеров)
- `POST /api/admin/kmz/import` / `kml/reload` — импорт KML
- `GET /api/admin/export/logs` / `export/engineers` — CSV gzip
- CRUD `/api/admin/map/points|caches|landmarks` — редактор карты
- Этапы 1–3: `/api/admin/stage1/*`, `/api/admin/stage2/*`, `/api/admin/stage3/*`

### Карта и WebSocket

- `GET /api/map/grid` / `grid/image` — подложка сетки
- `WS /ws/admin?token=...` — live-карта штаба
- `WS /ws/commander?token=...` — live-лента командира
- `WS /ws/engineer?token=...` — приказы и события инженера

## Фронтенд маршруты (hash)

| Маршрут | Доступ | Описание |
|---------|--------|----------|
| `/#/login` | все | Вход |
| `/#/admin` | admin | Админ-панель |
| `/#/command` | commander | Панель командира |
| `/#/engineer` | engineer | Главный экран инженера |
| `/#/point/{id}` | engineer | Захват / подрыв точки |
| `/#/g/{token}` | engineer | Вход по QR на объект |
| `/#/cache/{id}` | — | редирект на `/#/engineer` |
| `/#/status` | — | редирект на домашний экран роли |

## KMZ / KML импорт

### Пресет из каталога `kmz/`

При первом запуске (пустая БД) автоматически загружаются:

| Файл | Содержимое |
|------|------------|
| `Задача1.kml` | **КТ1…КТ12** (общие) + **базы и старты** ЛК (синие) и СБГ (красные) |
| `Задача-2.kml` | **Ящики 1…10** — цели этапа 2 (лут) |
| `Задача-3 ЛК.kml` | Схроны **синих** (сторона A): пост, мертвяк |
| `Задача 3-СБГ.kml` | Схроны **красных** (сторона B): пост, мертвяк |

Перезагрузка вручную: кнопка **KML пресет** в админке или `POST /api/admin/kml/reload`.

Координаты KML (Lon,Lat,Alt) инвертируются в (Lat,Lon) для Leaflet.

### Ручной импорт

`POST /api/admin/kmz/import` — загрузка KMZ/KML. Placemarks с «Точка»/«Point»/«КТ» → точки; «Схрон»/«Пост»/«Мертвяк» → схроны.

## CI

GitHub Actions (`.github/workflows/ci.yml`) при push/PR в `main`/`master`:

- **backend** — `pytest` (Python 3.12)
- **frontend** — `npm run build` + `npm test` (Vitest, Node 20)

## Безопасность (обязательно перед продакшеном)

| Риск | Рекомендация |
|------|--------------|
| Демо-пароли (`admin`, `alfa`, `alfa01`, `bravo1`) | Сменить или отключить seed-учётки |
| `SECRET_KEY` по умолчанию | Задать длинный случайный ключ в `.env` |
| `POSTGRES_PASSWORD` | Не использовать значения из примеров |
| `password_plain` в БД | Пароли инженеров хранятся открытым текстом для экспорта CSV — не для публичных инсталляций |
| JWT в query WebSocket (`?token=`) | Токен может попасть в логи прокси; для hardened-деплоя рассмотреть cookie/header |
| Загрузки медиа | Каталог `backend/uploads/` не коммитится; на проде — volume или S3 |

Файлы `.env`, `*.db`, `backend/uploads/` исключены в `.gitignore`.

## Лицензия

MIT — см. [LICENSE](LICENSE).
