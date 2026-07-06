# 📊 Сравнение: Supabase vs Neon vs VPS

> Для Nedvig-1 (Realty AI Platform) — что выбрать вместо своего сервера?

---

## Таблица сравнения

| Критерий | **Supabase** | **Neon** | **VPS (Selectel/Hetzner)** |
|----------|-------------|----------|---------------------------|
| **Тип** | BaaS (Backend-as-a-Service) | Managed PostgreSQL | Полный сервер |
| **Цена (free)** | $0 (500MB DB, 2 проекта) | $0 (0.5GB DB, 100 проектов) | Нет free |
| **Цена (старт)** | $25/мес (Pro) | ~$5-10/мес (pay-as-you-go) | €4.5-15/мес |
| **PostgreSQL** | ✅ Встроен | ✅ Только PG | ✅ Установить самому |
| **pgvector** | ✅ Встроен | ✅ Встроен | ✅ Установить самому |
| **Auth** | ✅ Встроен (GoTrue) | ✅ Встроен (Neon Auth) | ❌ Свой (JWT) |
| **REST API** | ✅ PostgREST автоматически | ❌ Нет | ❌ Свой FastAPI |
| **Realtime** | ✅ WebSocket подписки | ❌ Нет | ❌ Свой |
| **File Storage** | ✅ S3-совместимый | ❌ Нет | ❌ S3/MinIO самому |
| **Edge Functions** | ✅ Deno serverless | ❌ Нет | ❌ Нет |
| **Скрейперы** | ❌ Нельзя запустить | ❌ Нельзя запустить | ✅ Docker + cron |
| **Playwright** | ❌ Нельзя | ❌ Нельзя | ✅ Можно |
| **FastAPI backend** | ❌ Нужен отдельно | ❌ Нужен отдельно | ✅ Всё на одном сервере |
| **Elasticsearch** | ❌ Нет | ❌ Нет | ✅ Docker |
| **Redis** | ❌ Нет (есть в Pro) | ❌ Нет | ✅ Docker |
| **Cron/планировщик** | ✅ pg_cron | ❌ Нет | ✅ systemd/cron |
| **География** | 🇺🇸 🇪🇺 🇦🇺 (нет РФ) | 🇺🇸 🇪🇺 🇦🇺 (нет РФ) | 🇷🇺 (Selectel) 🇪🇺 (Hetzner) |
| **Латентность из РФ** | ~150-300ms | ~150-300ms | ~5-30ms |
| **Масштабирование** | Автоматическое | Автоматическое (scale-to-zero) | Ручное |
| **Бэкапы** | ✅ Автоматические | ✅ Автоматические | ❌ Настроить самому |
| **SSL/TLS** | ✅ Автоматически | ✅ Автоматически | ✅ Let's Encrypt |
| **Dashboard** | ✅ Полноценный UI | ✅ Полноценный UI | ❌ Нет |
| **Vendor lock** | Средний (PostgreSQL стандартный) | Низкий (обычный PG) | Нет |

---

## Что может заменить для Nedvig-1?

### ✅ Supabase может заменить:

| Компонент Nedvig-1 | Supabase аналог |
|--------------------|----------------|
| PostgreSQL | ✅ Встроенный PostgreSQL |
| pgvector (семантический поиск) | ✅ pgvector расширение |
| Auth (JWT, регистрация) | ✅ GoTrue Auth (без кода!) |
| File Storage (фото квартир) | ✅ Supabase Storage |
| REST API для listings | ✅ PostgREST (автоматически) |
| Realtime (новые объявления) | ✅ Realtime subscriptions |

### ❌ Supabase НЕ может заменить:

| Компонент | Почему |
|-----------|--------|
| FastAPI backend (AI-агент, бизнес-логика) | Нужен Edge Functions или отдельный сервер |
| Скрейперы (парсинг ЦИАН/Авито) | Нельзя запустить headless Chrome |
| Elasticsearch | Нет в Supabase |
| Планировщик скрейпинга | pg_cron есть, но Playwright нет |

### ✅ Neon может заменить:

| Компонент Nedvig-1 | Neon аналог |
|--------------------|-------------|
| PostgreSQL | ✅ Managed PostgreSQL |
| pgvector | ✅ Поддерживается |
| Scale-to-zero | ✅ Бесплатно когда не используется |

### ❌ Neon НЕ может заменить:

| Компонент | Почему |
|-----------|--------|
| Всё кроме БД | Neon — это ТОЛЬКО PostgreSQL |

---

## Рекомендация для Nedvig-1

### Вариант А: Supabase + VPS (оптимальный)

```
┌─────────────────────────────────────────────────┐
│                Supabase ($0-25/мес)              │
│  PostgreSQL │ Auth │ Storage │ REST API │ Realtime│
└────────────────────────┬────────────────────────┘
                         │
┌────────────────────────▼────────────────────────┐
│           VPS — Hetzner (€4.5/мес)              │
│  FastAPI │ Scrapy/Playwright │ Elasticsearch     │
│  AI Agent │ Scrapers │ Redis                     │
└─────────────────────────────────────────────────┘
```

**Итого: ~$5-30/мес**
- Supabase Free: PostgreSQL + Auth + Storage
- VPS: скрейперы + FastAPI + AI

### Вариант Б: VPS only (простой)

```
┌─────────────────────────────────────────────────┐
│           VPS — Selectel (400₽/мес)             │
│  PostgreSQL │ FastAPI │ Scrapers │ Elasticsearch │
│  Auth (JWT) │ Redis │ AI Agent │ Nginx           │
└─────────────────────────────────────────────────┘
```

**Итого: ~400-800₽/мес**
- Всё на одном сервере
- Проще в управлении
- Данные в РФ

### Вариант В: Neon + VPS (для БД)

```
┌─────────────────────────────────────────────────┐
│              Neon (free/~$5/мес)                 │
│  PostgreSQL │ pgvector │ Autoscaling             │
└────────────────────────┬────────────────────────┘
                         │
┌────────────────────────▼────────────────────────┐
│           VPS — Hetzner (€4.5/мес)              │
│  FastAPI │ Scrapers │ Redis │ AI Agent           │
└─────────────────────────────────────────────────┘
```

**Итого: ~$5-15/мес**
- Neon: managed PG с scale-to-zero
- VPS: приложение

---

## Для Nedvig-1 — лучший вариант: **Вариант А (Supabase + VPS)**

Причины:
1. **Auth бесплатно** — не нужно писать и поддерживать свой JWT
2. **Storage бесплатно** — фотографии квартир
3. **PostgreSQL + pgvector** — семантический поиск без настройки
4. **Realtime** — push-уведомления о новых объявлениях
5. **VPS** — скрейперы и AI-агент (нельзя в Supabase)

---

## Миграция на Supabase (пошагово)

### Шаг 1: Создать проект
1. Зайти на supabase.com → New Project
2. Выбратьрегион (EU closest to Russia)
3. Получить `SUPABASE_URL` и `SUPABASE_KEY`

### Шаг 2: Подключить к Nedvig-1
```python
# backend/app/config.py
SUPABASE_URL: str = ""
SUPABASE_KEY: str = ""
DATABASE_URL: str = ""  # Supabase connection string
```

### Шаг 3: Миграция данных
```bash
# Экспорт из SQLite
sqlite3 realty.db ".dump listings" > listings.sql

# Импорт в Supabase (через их SQL editor или psql)
psql $SUPABASE_URL -f listings.sql
```

### Шаг 4: Использовать Supabase Auth
```python
# Вместо своего JWT — Supabase Auth
from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Регистрация
supabase.auth.sign_up({"email": "...", "password": "..."})

# Логин
supabase.auth.sign_in_with_password({"email": "...", "password": "..."})
```
