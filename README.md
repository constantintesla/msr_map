# MSR Map — preshevkadastr.ru

Кадастровая игра: удержание точек, детонация схронов, админ-панель с live-картой.

## Структура

```
msr_map/
├── backend/          # FastAPI (REST + WebSocket)
├── frontend/         # React + Vite + Tailwind + Leaflet
├── nginx/            # nginx.conf (HTTPS, proxy)
└── docker-compose.yml
```

## Локальная разработка

### Быстрый запуск (Windows)

```powershell
cd C:\projects\msr_map
.\start-dev.ps1
```

Остановка: `.\start-dev.ps1 -Stop`  
Только backend: `.\start-dev.ps1 -BackendOnly`  
Только frontend: `.\start-dev.ps1 -FrontendOnly`

### Backend (вручную)

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: http://localhost:5173

### Тестовые учётные записи (seed)

| Роль | Логин | Пароль |
|------|-------|--------|
| Админ | `admin` | `admin` |
| Сторона А, точка N | `ing_a1` … `ing_a7` | `alfa` |
| Сторона Б, точка N | `ing_b1` … `ing_b7` | `bravo` |
| Сторона А, схрон N | `schr_a1` … `schr_a10` | `alfa` |
| Сторона Б, схрон N | `schr_b1` … `schr_b10` | `bravo` |

Seed создаёт **7 точек** и **10 схронов** при первом запуске. Новые учётки добавляются при каждом старте backend, если их ещё нет.

## Docker (production)

```bash
# Первичный выпуск SSL-сертификата (до запуска nginx с SSL):
docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d preshevkadastr.ru -d www.preshevkadastr.ru \
  --email admin@preshevkadastr.ru --agree-tos --no-eff-email

docker compose up -d --build
```

Для dev без SSL можно временно использовать только backend + frontend локально.

## Переменные окружения (backend)

| Переменная           | Описание                          | По умолчанию              |
|----------------------|-----------------------------------|---------------------------|
| DATABASE_URL         | SQLite (dev) / PostgreSQL (prod)  | sqlite:///./msr_map.db    |
| SECRET_KEY           | JWT секрет                        | dev-secret-key-...        |
| HOLD_DEADMAN_SECONDS | Таймаут dead-man ping             | 120                       |
| CORS_ORIGINS         | Разрешённые origins               | localhost, preshevkadastr |

## API (кратко)

- `POST /api/auth/login` — JWT авторизация
- `GET /api/status` — публичный статус (polling)
- `POST /api/hold/confirm` — ping удержания
- `POST /api/hold/leave` — сброс удержания
- `POST /api/cache/detonate` — детонация схрона
- `POST /api/admin/kmz/import` — импорт KMZ
- `GET /api/admin/export/logs` — CSV gzip логов
- `WS /ws/admin?token=...` — live-карта админа

## Фронтенд маршруты (hash)

- `/#/login` — вход
- `/#/status` — публичная карта
- `/#/point/{id}` — удержание точки
- `/#/cache/{id}` — детонация схрона
- `/#/admin` — админ-панель

## KMZ / KML импорт

### Пресет из каталога `kmz/`

При первом запуске (пустая БД) автоматически загружаются:

| Файл | Содержимое |
|------|------------|
| `Задача1.kml` | **КТ1…КТ12** (общие) + **базы и старты** ЛК (синие) и СБГ (красные) |
| `Задача-2.kml` | **Ящики 1…10** — цели этапа 2 (лут за плёнкой) |
| `Задача-3 ЛК.kml` | Схроны **синих** (сторона A): Пост, Мертвяк |
| `Задача 3-СБГ.kml` | Схроны **красных** (сторона B): Пост, Мертвяк |

Перезагрузка вручную: кнопка **KML пресет** в админке или `POST /api/admin/kml/reload`.

Координаты KML (Lon,Lat,Alt) инвертируются в (Lat,Lon) для Leaflet.

### Ручной импорт

Placemarks с «Точка»/«Point»/«КТ» → точки; «Схрон»/«Пост»/«Мертвяк» → схроны.

## Публикация на GitHub

```bash
git init
git add .
git status   # убедитесь: нет .env, *.db, uploads/, node_modules/
git commit -m "Initial commit"
git remote add origin https://github.com/<user>/msr_map.git
git push -u origin main
```

CI (`.github/workflows/ci.yml`) запускает backend pytest и frontend build/test при push/PR.

## Безопасность (обязательно перед продакшеном)

| Риск | Рекомендация |
|------|--------------|
| Демо-пароли (`admin`, `alfa`, `bravo`) | Сменить или отключить seed-учётки |
| `SECRET_KEY` по умолчанию | Задать длинный случайный ключ в `.env` |
| `POSTGRES_PASSWORD` | Не использовать значения из примеров |
| `password_plain` в БД | Пароли инженеров хранятся открытым текстом для экспорта CSV — не для публичных инсталляций |
| JWT в query WebSocket (`?token=`) | Токен может попасть в логи прокси; для hardened-деплоя рассмотреть cookie/header |
| Загрузки медиа | Каталог `backend/uploads/` не коммитится; на проде — volume или S3 |

Файлы `.env`, `*.db`, `backend/uploads/` исключены в `.gitignore`.

## Лицензия

MIT — см. [LICENSE](LICENSE).
