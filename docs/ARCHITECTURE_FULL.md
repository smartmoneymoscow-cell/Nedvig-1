# 🏗️ Realty Platform — Полный план архитектуры

## Содержание

1. [Обзор системы](#1-обзор-системы)
2. [Принципы проектирования](#2-принципы-проектирования)
3. [Модульная архитектура](#3-модульная-архитектура)
4. [Схема данных](#4-схема-данных)
5. [Слой ingestion (сбор данных)](#5-слой-ingestion)
6. [Слой хранения](#6-слой-хранения)
7. [Слой поиска и аналитики](#7-слой-поиска-и-аналитики)
8. [AI-слой](#8-ai-слой)
9. [API-слой](#9-api-слой)
10. [Фронтенд](#10-фронтенд)
11. [Инфраструктура и деплой](#11-инфраструктура)
12. [Безопасность](#12-безопасность)
13. [Масштабирование](#13-масштабирование)
14. [Дорожная карта](#14-дорожная-карта)

---

## 1. Обзор системы

### Что делает платформа

```
Пользователь (риелтор/покупатель)
        │
        ▼
┌───────────────────────────────────────────────────┐
│                   Frontend (Next.js)              │
│  Чат с AI │ Каталог │ Аналитика │ Карта │ Уведомл │
└───────────────────────┬───────────────────────────┘
                        │ REST / WebSocket
                        ▼
┌───────────────────────────────────────────────────┐
│               API Gateway (FastAPI)                │
│  /agent/chat │ /listings │ /analytics │ /alerts   │
└───┬──────────┬──────────┬───────────┬─────────────┘
    │          │          │           │
    ▼          ▼          ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐
│  AI    │ │ Search │ │  Data  │ │ Notification│
│ Engine │ │ Engine │ │  API   │ │   Service   │
└───┬────┘ └───┬────┘ └───┬────┘ └──────┬─────┘
    │          │          │              │
    ▼          ▼          ▼              ▼
┌───────────────────────────────────────────────────┐
│              PostgreSQL + pgvector                 │
│         (основное хранилище + embeddings)          │
├───────────────────────────────────────────────────┤
│              Elasticsearch 8.x                     │
│         (полнотекстовый + геопоиск)                │
├───────────────────────────────────────────────────┤
│              Redis                                 │
│         (кеш, очереди, pub/sub)                    │
└───────────────────────────────────────────────────┘
                        ▲
                        │
┌───────────────────────────────────────────────────┐
│             Ingestion Pipeline                     │
│  Scrapy │ HTTP-парсеры │ API-адаптеры │ Webhooks  │
│                                                     │
│  Источники: ЦИАН │ Авито │ Домклик │ Яндекс.Недв │
└───────────────────────────────────────────────────┘
```

### Ключевые метрики

| Метрика | MVP | Production |
|---------|-----|-----------|
| Объектов в базе | 100–1K | 100K–1M |
| Источников | 1–2 | 5–10 |
| Запросов/сек | 10 | 500+ |
| Время поиска | <500ms | <100ms |
| Время индексации нового объекта | 1ч | 5мин |

---

## 2. Принципы проектирования

### 2.1 Разделение ответственности (Separation of Concerns)

Каждый слой делает ОДНУ вещь хорошо:

```
Ingestion  → только сбор и нормализация данных
Storage    → только хранение и базовые CRUD
Search     → только поиск и фильтрация
AI         → только понимание языка и рекомендации
API        → только маршрутизация и валидация
Frontend   → только отображение и взаимодействие
```

### 2.2 Устойчивость к сбоям (Fault Tolerance)

- Скрейпер одного сайта упал → остальные работают
- Elasticsearch недоступен → fallback на PostgreSQL full-text
- AI-модель не отвечает → fallback на rule-based NLU
- Redis упал → кеш обходится, работает медленнее

### 2.3 Идемпотентность

- Повторный скрейп того же объекта → UPDATE, не дубль
- Повторный поиск → тот же результат (кеш)
- Повторная индексация → не ломает embeddings

### 2.4 Конфигурация через окружение

```
# .env — всё в одном месте
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
ES_URL=http://...
EMBEDDING_MODEL=sentence-transformers/...
SCRAPE_INTERVAL=3600
AI_FALLBACK=rule-based
```

---

## 3. Модульная архитектура

### 3.1 Структура проекта

```
realty-platform/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app + lifespan
│   │   ├── config.py                  # Pydantic Settings
│   │   │
│   │   ├── api/                       # API-слой
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                # Dependency injection
│   │   │   ├── routes/
│   │   │   │   ├── agent.py           # POST /api/agent/chat
│   │   │   │   ├── listings.py        # GET /api/listings
│   │   │   │   ├── analytics.py       # GET /api/analytics
│   │   │   │   ├── alerts.py          # CRUD /api/alerts
│   │   │   │   └── admin.py           # Admin endpoints
│   │   │   └── middleware.py          # Rate limit, auth, logging
│   │   │
│   │   ├── models/                    # Data models
│   │   │   ├── __init__.py
│   │   │   ├── database.py            # SQLAlchemy engine + session
│   │   │   ├── listing.py             # Listing model
│   │   │   ├── user.py                # User model (future)
│   │   │   ├── alert.py               # Saved search alerts
│   │   │   └── enums.py               # PropertyType, DealType...
│   │   │
│   │   ├── services/                  # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── search.py              # Search orchestrator
│   │   │   ├── analytics.py           # Analytics service
│   │   │   ├── listing.py             # Listing CRUD
│   │   │   └── dedup.py               # Deduplication service
│   │   │
│   │   ├── ai/                        # AI Engine
│   │   │   ├── __init__.py
│   │   │   ├── nlu.py                 # Natural Language Understanding
│   │   │   ├── embeddings.py          # Embedding generation
│   │   │   ├── reranker.py            # Result reranking
│   │   │   ├── recommender.py         # Recommendations
│   │   │   └── prompts.py             # LLM prompts (future)
│   │   │
│   │   ├── ingestion/                 # Data collection
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # BaseScraper interface
│   │   │   ├── pipeline.py            # Ingestion pipeline
│   │   │   ├── normalizer.py          # Data normalization
│   │   │   ├── scrapers/
│   │   │   │   ├── cian.py
│   │   │   │   ├── avito.py
│   │   │   │   ├── domclick.py
│   │   │   │   └── yandex_realty.py
│   │   │   └── scheduler.py           # Scrapy scheduler
│   │   │
│   │   ├── search/                    # Search engines
│   │   │   ├── __init__.py
│   │   │   ├── pg_search.py           # PostgreSQL full-text
│   │   │   ├── es_search.py           # Elasticsearch
│   │   │   ├── semantic.py            # Vector similarity
│   │   │   └── hybrid.py              # Combined search
│   │   │
│   │   └── notifications/             # Alert system
│   │       ├── __init__.py
│   │       ├── matcher.py             # Alert → new listing matching
│   │       ├── sender.py              # Notification delivery
│   │       └── templates.py           # Message templates
│   │
│   ├── alembic/                       # DB migrations
│   │   ├── env.py
│   │   └── versions/
│   │
│   ├── tests/
│   │   ├── test_api.py
│   │   ├── test_search.py
│   │   ├── test_ai.py
│   │   └── test_scrapers.py
│   │
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx                 # Root layout
│   │   ├── page.tsx                   # Main page
│   │   ├── chat/
│   │   │   └── page.tsx               # AI Chat page
│   │   ├── listings/
│   │   │   ├── page.tsx               # Listings catalog
│   │   │   └── [id]/page.tsx          # Single listing
│   │   ├── analytics/
│   │   │   └── page.tsx               # Analytics dashboard
│   │   └── map/
│   │       └── page.tsx               # Map view
│   │
│   ├── components/
│   │   ├── ChatWindow.tsx
│   │   ├── ListingCard.tsx
│   │   ├── SearchFilters.tsx
│   │   ├── PriceChart.tsx
│   │   ├── CityComparison.tsx
│   │   └── MapView.tsx
│   │
│   ├── lib/
│   │   ├── api.ts                     # API client
│   │   ├── types.ts                   # TypeScript types
│   │   └── utils.ts
│   │
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   └── Dockerfile
│
├── infra/
│   ├── docker-compose.yml             # Local dev
│   ├── docker-compose.prod.yml        # Production
│   ├── nginx.conf                     # Reverse proxy
│   └── monitoring/
│       ├── prometheus.yml
│       └── grafana/
│
├── scripts/
│   ├── seed_data.py                   # Demo data
│   ├── migrate.py                     # DB migrations
│   └── benchmark.py                   # Performance tests
│
└── docs/
    ├── ARCHITECTURE_FULL.md           # Этот файл
    ├── API.md                         # API reference
    └── DEPLOY.md                      # Deployment guide
```

### 3.2 Зависимости между модулями

```
api ──────► services ──────► models
  │            │
  │            ├──► search ──► [pg_search, es_search, semantic]
  │            │
  │            └──► ai ──► [nlu, embeddings, reranker]
  │
  └──► ingestion ──► [scrapers, normalizer, pipeline]

notifications ──► services (для matching)
              ──► sender (для delivery)
```

**Правило:** Никаких циклических зависимостей. API не знает про внутренности search. Search не знает про API.

---

## 4. Схема данных

### 4.1 Listing (объект недвижимости)

```sql
CREATE TABLE listings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Источник
    source          VARCHAR(50) NOT NULL,          -- 'cian', 'avito', 'domclick'
    source_id       VARCHAR(200) NOT NULL,         -- ID на сайте-источнике
    source_url      VARCHAR(500) NOT NULL,         -- Ссылка на оригинал
    source_hash     VARCHAR(64) NOT NULL,          -- SHA256(content) для дедупликации

    -- Тип недвижимости
    property_type   VARCHAR(20) NOT NULL,          -- apartment, house, commercial, land, room, studio
    deal_type       VARCHAR(10) NOT NULL,          -- sale, rent

    -- Цена
    price           NUMERIC(15,2) NOT NULL,
    price_per_m2    NUMERIC(12,2),                 -- Авто-вычисляемое
    currency        VARCHAR(3) DEFAULT 'RUB',

    -- Характеристики
    area_total      NUMERIC(10,2),                 -- Общая площадь
    area_living     NUMERIC(10,2),                 -- Жилая
    area_kitchen    NUMERIC(10,2),                 -- Кухня
    rooms           INTEGER,                       -- NULL = не применимо (land, commercial)
    rooms_type      VARCHAR(20),                   -- 'studio', 'free_layout', 'room'
    floor           INTEGER,
    floors_total    INTEGER,
    ceiling_height  NUMERIC(3,2),                  -- Высота потолков (м)

    -- Расположение
    address         VARCHAR(500) NOT NULL,
    district        VARCHAR(200),
    microdistrict   VARCHAR(200),
    city            VARCHAR(100) NOT NULL,
    region          VARCHAR(100),
    country         VARCHAR(50) DEFAULT 'Russia',
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    metro_station   VARCHAR(200),                  -- Ближайшее метро
    metro_distance  INTEGER,                       -- Минут до метро

    -- Описание
    title           VARCHAR(500),
    description     TEXT,
    images          JSONB DEFAULT '[]',            -- [{url, width, height}]
    features        JSONB DEFAULT '{}',            -- {parking, elevator, renovation...}

    -- Статус
    is_active       BOOLEAN DEFAULT TRUE,
    is_verified     BOOLEAN DEFAULT FALSE,         -- Проверено модератором

    -- Embedding для семантического поиска (pgvector)
    embedding       vector(384),                   -- MiniLM-L12-v2

    -- Метаданные
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    scraped_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,                   -- Когда объявление истекает

    -- Уникальность
    UNIQUE(source, source_id)
);

-- Индексы
CREATE INDEX idx_listings_city ON listings(city);
CREATE INDEX idx_listings_deal_type ON listings(deal_type);
CREATE INDEX idx_listings_property_type ON listings(property_type);
CREATE INDEX idx_listings_price ON listings(price);
CREATE INDEX idx_listings_rooms ON listings(rooms);
CREATE INDEX idx_listings_created ON listings(created_at DESC);
CREATE INDEX idx_listings_active ON listings(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_listings_city_deal ON listings(city, deal_type);
CREATE INDEX idx_listings_geo ON listings(lat, lon) WHERE lat IS NOT NULL;
CREATE INDEX idx_listings_embedding ON listings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- GIN-индекс для полнотекстового поиска по PostgreSQL
CREATE INDEX idx_listings_fts ON listings USING gin(
    to_tsvector('russian', coalesce(title,'') || ' ' || coalesce(description,'') || ' ' || coalesce(address,''))
);
```

### 4.2 PriceHistory (история цен)

```sql
CREATE TABLE price_history (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id  UUID REFERENCES listings(id) ON DELETE CASCADE,
    price       NUMERIC(15,2) NOT NULL,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_price_history_listing ON price_history(listing_id, recorded_at DESC);
```

### 4.3 SearchAlert (подписка на уведомления)

```sql
CREATE TABLE search_alerts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID,                              -- NULL = anonymous
    name        VARCHAR(200) NOT NULL,
    filters     JSONB NOT NULL,                    -- {city, deal_type, property_type, price_max, rooms...}
    is_active   BOOLEAN DEFAULT TRUE,
    frequency   VARCHAR(20) DEFAULT 'instant',     -- instant, hourly, daily
    channel     VARCHAR(20) DEFAULT 'email',       -- email, telegram, webhook
    channel_target VARCHAR(500),                   -- email addr, chat_id, URL
    last_sent   TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.4 ScrapingJob (задания на скрейпинг)

```sql
CREATE TABLE scraping_jobs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source      VARCHAR(50) NOT NULL,
    city        VARCHAR(100),
    deal_type   VARCHAR(10),
    status      VARCHAR(20) DEFAULT 'pending',     -- pending, running, completed, failed
    items_found INTEGER DEFAULT 0,
    items_new   INTEGER DEFAULT 0,
    items_updated INTEGER DEFAULT 0,
    error       TEXT,
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.5 ER-диаграмма

```
┌──────────────┐       ┌──────────────────┐
│   listings   │       │  price_history   │
├──────────────┤       ├──────────────────┤
│ id (PK)      │──┐    │ id (PK)          │
│ source       │  │    │ listing_id (FK)  │──┐
│ source_id    │  │    │ price            │  │
│ source_url   │  │    │ recorded_at      │  │
│ property_type│  │    └──────────────────┘  │
│ deal_type    │  │                           │
│ price        │  │    ┌──────────────────┐  │
│ area_total   │  │    │  search_alerts   │  │
│ rooms        │  │    ├──────────────────┤  │
│ floor        │  │    │ id (PK)          │  │
│ address      │  │    │ user_id          │  │
│ city         │  │    │ filters (JSONB)  │  │
│ lat, lon     │  │    │ frequency        │  │
│ description  │  │    │ channel          │  │
│ embedding    │  │    └──────────────────┘  │
│ is_active    │  │                           │
│ created_at   │  │    ┌──────────────────┐  │
│ ...          │  │    │  scraping_jobs   │  │
└──────────────┘  │    ├──────────────────┤  │
                  │    │ id (PK)          │  │
                  │    │ source           │  │
                  │    │ status           │  │
                  │    │ items_found      │  │
                  │    │ created_at       │  │
                  │    └──────────────────┘  │
                  │                           │
                  └───────────────────────────┘
```

---

## 5. Слой Ingestion (сбор данных)

### 5.1 Архитектура пайплайна

```
┌─────────────────────────────────────────────────────────┐
│                    Scheduler (APScheduler)               │
│  Каждый N часов запускает скрейперы по расписанию        │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│                    Scraper Layer                         │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  CIAN    │  │  AVITO   │  │ DOMCLICK │  │ YANDEX  │ │
│  │ Scraper  │  │ Scraper  │  │ Scraper  │  │  Realty │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│       │              │              │              │      │
│       └──────────────┴──────────────┴──────────────┘      │
│                          │                                │
│                    ScrapedItem[]                          │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Normalizer                             │
│                                                          │
│  1. Нормализация цен (→ RUB)                            │
│  2. Нормализация адресов (→ единый формат)              │
│  3. Геокодирование (address → lat/lon)                  │
│  4. Извлечение features из текста                       │
│  5. Валидация (пропускаем битые записи)                  │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Deduplicator                           │
│                                                          │
│  1. Проверка UNIQUE(source, source_id)                  │
│  2. Проверка source_hash (контент не изменился?)        │
│  3. Cross-source дедупликация (same apartment, diff src)│
│     → fuzzy match по (city, address, area, rooms, price)│
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Writer                                 │
│                                                          │
│  1. INSERT новый / UPDATE существующий                  │
│  2. Запись в price_history если цена изменилась          │
│  3. Генерация embedding (async, в фоне)                 │
│  4. Индексация в Elasticsearch                          │
│  5. Проверка search_alerts → отправка уведомлений       │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Интерфейс скрейпера

```python
class BaseScraper(ABC):
    SOURCE_NAME: str
    BASE_URL: str

    @abstractmethod
    async def scrape_listings(
        self,
        city: str,
        deal_type: str = "sale",
        max_pages: int = 10,
    ) -> list[ScrapedItem]:
        """Возвращает нормализованные объекты."""
        pass

    @abstractmethod
    async def scrape_detail(self, url: str) -> ScrapedItem | None:
        """Скрейпит детальную страницу одного объекта."""
        pass
```

### 5.3 Расписание скрейпинга

| Источник | Частота | Города | Приоритет |
|----------|---------|--------|-----------|
| ЦИАН | Каждые 2ч | Топ-10 городов | Высокий |
| Авито | Каждые 3ч | Топ-10 городов | Высокий |
| Домклик | Каждые 6ч | Топ-5 городов | Средний |
| Яндекс.Недв | Каждые 6ч | Топ-5 городов | Средний |

### 5.4 Обработка ошибок

```python
# Каждый скрейпер оборачивается в retry
@retry(max_attempts=3, backoff=exponential(base=2, max=60))
async def safe_scrape(scraper, city, deal_type):
    try:
        return await scraper.scrape_listings(city, deal_type)
    except ScraperBlocked:
        # IP заблокирован → помечаем, переключаем на прокси
        await mark_blocked(scraper.SOURCE_NAME, city)
        raise
    except ScraperChanged:
        # Структура сайта изменила → алерт разработчику
        await alert_dev(f"{scraper.SOURCE_NAME} structure changed")
        raise
```

---

## 6. Слой хранения

### 6.1 Выбор БД

| Тип данных | БД | Почему |
|------------|-----|--------|
| Основные данные | PostgreSQL 15 | ACID, JSONB, расширения |
| Векторные embeddings | pgvector (расширение PG) | Не нужна отдельная БД |
| Полнотекстовый поиск | Elasticsearch 8 | Fuzzy, агрегации, скоринг |
| Кеш | Redis | TTL, pub/sub для уведомлений |
| Файлы (изображения) | S3 / MinIO | Object storage |

### 6.2 Почему не MongoDB?

- Нужна сложная аналитика (aggregations в SQL мощнее)
- Нужны JOIN-ы (listings + price_history + alerts)
- Нужна полнотекстовая индексация (PG + ES лучше)
- Нужна геолокация (PostGIS мощнее, чем GeoJSON в Mongo)

### 6.3 Стратегия миграций

```bash
# Alembic для автоматических миграций
alembic revision --autogenerate -m "add_embedding_column"
alembic upgrade head
alembic downgrade -1  # откат
```

---

## 7. Слой поиска и аналитики

### 7.1 Архитектура поиска

```
Запрос пользователя
        │
        ▼
┌─────────────────────┐
│   Hybrid Search     │
│   Orchestrator      │
└───┬────────┬────────┘
    │        │
    ▼        ▼
┌────────┐ ┌────────────┐
│Structur│ │  Semantic   │
│ Search │ │  Search     │
│(PG/ES) │ │(pgvector)   │
└───┬────┘ └─────┬──────┘
    │            │
    ▼            ▼
┌─────────────────────┐
│    Reranker         │
│  (combines scores)  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Result Formatter   │
│  (grouping, facets) │
└─────────────────────┘
```

### 7.2 Structured Search (PostgreSQL)

```python
# Фильтры → SQL WHERE
query = select(Listing).where(Listing.is_active == True)

if filters.city:
    query = query.where(Listing.city == filters.city)
if filters.price_max:
    query = query.where(Listing.price <= filters.price_max)
if filters.rooms:
    query = query.where(Listing.rooms == filters.rooms)
# ... и так далее
```

### 7.3 Full-Text Search (Elasticsearch)

```json
{
  "query": {
    "bool": {
      "must": [
        { "match": { "description": "свежий ремонт панорамные окна" } }
      ],
      "filter": [
        { "term": { "city": "Москва" } },
        { "range": { "price": { "lte": 15000000 } } }
      ]
    }
  },
  "sort": [
    { "_score": "desc" },
    { "created_at": "desc" }
  ]
}
```

### 7.4 Semantic Search (pgvector)

```python
# Запрос → embedding → cosine similarity
query_embedding = model.encode("двушка рядом с метро с ремонтом")

results = await session.execute(
    select(Listing)
    .where(Listing.is_active == True)
    .order_by(Listing.embedding.cosine_distance(query_embedding))
    .limit(20)
)
```

### 7.5 Hybrid Scoring

```python
def hybrid_score(structural_score, semantic_score, text_score):
    """
    Комбинирует три типа скоров:
    - structural: точное совпадение фильтров (0 или 1)
    - semantic: cosine similarity (0..1)
    - text: Elasticsearch _score (нормализованный 0..1)
    """
    return (
        0.4 * structural_score +
        0.35 * semantic_score +
        0.25 * text_score
    )
```

### 7.6 Аналитика

```sql
-- Средняя цена по городам и типам
SELECT
    city,
    property_type,
    deal_type,
    COUNT(*) as count,
    AVG(price) as avg_price,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) as median_price,
    AVG(price / NULLIF(area_total, 0)) as avg_price_per_m2
FROM listings
WHERE is_active = TRUE
GROUP BY city, property_type, deal_type;

-- Динамика цен (за месяц)
SELECT
    date_trunc('week', ph.recorded_at) as week,
    AVG(ph.price) as avg_price,
    COUNT(DISTINCT ph.listing_id) as listings
FROM price_history ph
JOIN listings l ON l.id = ph.listing_id
WHERE l.city = 'Москва' AND l.property_type = 'apartment'
GROUP BY week
ORDER BY week;
```

---

## 8. AI-слой

### 8.1 Архитектура AI Engine

```
Пользовательский ввод
        │
        ▼
┌─────────────────────────────────────┐
│        NLU (Natural Language        │
│           Understanding)            │
│                                      │
│  "двушка в Москве до 10 млн"       │
│         │                            │
│         ▼                            │
│  {                                  │
│    rooms: 2,                        │
│    city: "Москва",                  │
│    price_max: 10000000,             │
│    property_type: "apartment",      │
│    intent: "search"                 │
│  }                                  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│        Query Router                 │
│                                      │
│  intent: search  → Search Engine    │
│  intent: compare → Analytics        │
│  intent: stats   → Analytics        │
│  intent: recommend → Recommender    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│        Response Generator           │
│                                      │
│  Форматирует результат в текст     │
│  с эмодзи, структурой, ссылками     │
└─────────────────────────────────────┘
```

### 8.2 NLU Pipeline (этапы развития)

| Этап | Подход | Когда |
|------|--------|-------|
| MVP | Rule-based (regex + словари) | Сейчас |
| v2 | Fine-tuned classifier (BERT-tiny) | Месяц 2 |
| v3 | LLM (GigaChat / local) | Месяц 4+ |

### 8.3 Embedding Strategy

```python
# Модель: paraphrase-multilingual-MiniLM-L12-v2
# Размерность: 384
# Поддержка: русский + английский
# Скорость: ~1000 запросов/сек на CPU

from sentence_transformers import SentenceTransformer

model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

def generate_embedding(listing: Listing) -> list[float]:
    """Генерирует embedding из текста объявления."""
    text = f"{listing.title or ''} {listing.description or ''} {listing.address} {listing.city}"
    return model.encode(text).tolist()
```

### 8.4 Рекомендательная система

```python
# Collaborative filtering + content-based
class Recommender:
    async def get_recommendations(self, user_id: str, limit: int = 10):
        # 1. История поиска пользователя → извлечь preferences
        prefs = await self.get_user_preferences(user_id)

        # 2. Найти похожие объекты (content-based)
        similar = await self.semantic_search(prefs.to_query(), limit=50)

        # 3. Отранжировать по:
        #    - совпадение с preferences (вес 0.4)
        #    - свежесть объявления (вес 0.3)
        #    - популярность (views) (вес 0.2)
        #    - разнообразие (не все из одного дома) (вес 0.1)

        return self.rerank(similar, prefs, limit)
```

---

## 9. API-слой

### 9.1 Endpoints

```
# ─── AI Agent ─────────────────────────
POST   /api/agent/chat              # Нatural language query

# ─── Listings ─────────────────────────
GET    /api/listings                 # Search with filters
GET    /api/listings/{id}            # Single listing
GET    /api/listings/{id}/history    # Price history

# ─── Analytics ────────────────────────
GET    /api/analytics                # Overview analytics
GET    /api/analytics/compare        # Compare cities
GET    /api/analytics/trends         # Price trends over time

# ─── Alerts ───────────────────────────
POST   /api/alerts                   # Create alert
GET    /api/alerts                   # List user's alerts
DELETE /api/alerts/{id}              # Delete alert

# ─── Admin ────────────────────────────
POST   /api/admin/scrape             # Trigger scraping
GET    /api/admin/jobs               # Scraping job status
GET    /api/admin/stats              # System stats
```

### 9.2 API Response Format

```json
// Успешный ответ
{
  "success": true,
  "data": { ... },
  "meta": {
    "total": 142,
    "offset": 0,
    "limit": 20,
    "took_ms": 45
  }
}

// Ошибка
{
  "success": false,
  "error": {
    "code": "INVALID_FILTER",
    "message": "price_max must be positive"
  }
}
```

### 9.3 Rate Limiting

```
# Лимиты по умолчанию
- Анонимный: 30 запросов/минуту
- Авторизованный: 120 запросов/минуту
- Admin: без лимита
- AI Chat: 10 запросов/минуту (дорогой endpoint)
```

### 9.4 WebSocket для real-time (будущее)

```
# Подписка на новые объявления
WS /ws/listings?city=Москва&deal_type=sale

# Клиент получает:
{
  "event": "new_listing",
  "data": { "id": "...", "price": 15000000, ... }
}
```

---

## 10. Фронтенд

### 10.1 Структура страниц

```
/                     → Главная (AI Chat + быстрый поиск)
/listings             → Каталог объявлений (фильтры + карточки)
/listings/[id]        → Детальная страница объявления
/analytics            → Дашборд аналитики
/map                  → Карта с объявлениями
/alerts               → Управление подписками
```

### 10.2 Компоненты

```
components/
├── layout/
│   ├── Sidebar.tsx           # Навигация
│   ├── Header.tsx            # Верхняя панель
│   └── MobileNav.tsx         # Мобильное меню
│
├── chat/
│   ├── ChatWindow.tsx        # Окно чата
│   ├── MessageBubble.tsx     # Сообщение
│   ├── Suggestions.tsx       # Кнопки-подсказки
│   └── FilterChips.tsx       # Извлечённые фильтры
│
├── listings/
│   ├── ListingCard.tsx       # Карточка объявления
│   ├── ListingGrid.tsx       # Сетка карточек
│   ├── ListingDetail.tsx     # Детальный вид
│   ├── SearchFilters.tsx     # Панель фильтров
│   ├── PriceTag.tsx          # Отображение цены
│   └── ImageGallery.tsx      # Галерея фото
│
├── analytics/
│   ├── PriceChart.tsx        # График цен
│   ├── CityComparison.tsx    # Сравнение городов
│   ├── StatsCards.tsx        # Карточки статистики
│   └── DistributionChart.tsx # Распределение по типам
│
└── map/
    ├── MapView.tsx           # Яндекс.Карта / Leaflet
    ├── MapMarker.tsx         # Маркер на карте
    └── MapCluster.tsx        # Кластеризация
```

### 10.3 State Management

```typescript
// SWR для кешированных запросов
import useSWR from 'swr';

function useListings(filters: SearchFilters) {
  return useSWR(
    ['/api/listings', filters],
    ([url, filters]) => fetcher(url, filters),
    { revalidateOnFocus: false, dedupingInterval: 5000 }
  );
}

// React Context для чата
const ChatContext = createContext<{
  messages: Message[];
  sendMessage: (text: string) => Promise<void>;
  loading: boolean;
}>(null);
```

### 10.4 Адаптивность

```
Mobile-first:
- < 640px  → 1 колонка, скрытый sidebar
- 640-1024 → 2 колонки, collapsed sidebar
- > 1024   → 3 колонки, полный sidebar
- > 1440   → 4 колонки, карта рядом
```

---

## 11. Инфраструктура и деплой

### 11.1 Docker Compose (разработка)

```yaml
version: "3.9"

services:
  postgres:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: realty
      POSTGRES_USER: realty
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports: ["5432:5432"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports: ["9200:9200"]

  backend:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [postgres, redis, elasticsearch]
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --reload

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [backend]

  # Celery worker для фоновых задач (скрейпинг, embeddings)
  worker:
    build: ./backend
    command: celery -A app.celery worker -l info
    depends_on: [postgres, redis]

  # Celery beat для расписания
  beat:
    build: ./backend
    command: celery -A app.celery beat -l info
    depends_on: [redis]

volumes:
  pgdata:
```

### 11.2 Production (Docker Compose + Nginx)

```yaml
# docker-compose.prod.yml
version: "3.9"

services:
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./infra/nginx.conf:/etc/nginx/nginx.conf
      - ./infra/certs:/etc/nginx/certs
    depends_on: [backend, frontend]

  backend:
    image: realty-backend:latest
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: "1"
          memory: 1G
    environment:
      DATABASE_URL: postgresql+asyncpg://...
      REDIS_URL: redis://...
      ES_URL: http://...

  frontend:
    image: realty-frontend:latest
    deploy:
      replicas: 2

  postgres:
    image: pgvector/pgvector:pg15
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 4G
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru

  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
    volumes:
      - esdata:/usr/share/elasticsearch/data
```

### 11.3 Мониторинг

```
Prometheus → собирает метрики
Grafana → визуализация

Метрики:
- api_request_duration_seconds (гистограмма)
- api_requests_total (счётчик)
- scraper_items_total (по источникам)
- search_query_duration_seconds
- ai_chat_duration_seconds
- db_connection_pool_size
- redis_memory_used_bytes
```

### 11.4 CI/CD Pipeline

```
Push → GitHub Actions:
  1. Lint (ruff, eslint)
  2. Test (pytest, jest)
  3. Build Docker images
  4. Push to registry
  5. Deploy to staging
  6. Smoke tests
  7. Deploy to production (manual approval)
```

---

## 12. Безопасность

### 12.1 Уровни защиты

```
┌─────────────────────────────────────────┐
│  Level 1: Network                       │
│  - Nginx reverse proxy                  │
│  - Rate limiting (per IP)               │
│  - DDoS protection (Cloudflare)         │
├─────────────────────────────────────────┤
│  Level 2: API                           │
│  - Input validation (Pydantic)          │
│  - SQL injection prevention (SQLAlchemy)│
│  - CORS policy                          │
├─────────────────────────────────────────┤
│  Level 3: Auth (future)                 │
│  - JWT tokens                           │
│  - OAuth2 (Google, Yandex)              │
│  - Role-based access (user/admin)       │
├─────────────────────────────────────────┤
│  Level 4: Data                          │
│  - Encryption at rest (PG)              │
│  - Encryption in transit (TLS)          │
│  - No PII stored (until auth added)     │
└─────────────────────────────────────────┘
```

### 12.2 Защита скрейпинга

```
- Ротация User-Agent
- Прокси-пулы (резидентные прокси)
- Respectful delays (1-3 сек между запросами)
- robots.txt compliance
- Exponential backoff при блокировках
- Мониторинг блокировок
```

---

## 13. Масштабирование

### 13.1 Горизонтальное масштабирование

```
Текущий (MVP):
  1 backend, 1 frontend, 1 PG, 1 ES, 1 Redis

Средний (10K пользователей):
  3 backend, 2 frontend, 1 PG (replica), 1 ES, 1 Redis

Большой (100K+ пользователей):
  5+ backend, 3+ frontend, PG cluster, ES cluster, Redis Sentinel
```

### 13.2 Стратегия кеширования

```
L1: In-memory (Python dict) — TTL 30сек
    → для hot queries (популярные города)

L2: Redis — TTL 5мин
    → для search results, analytics

L3: CDN (Cloudflare) — TTL 1час
    → для статики (изображения, CSS, JS)

L4: Browser cache — через Cache-Control headers
```

### 13.3 Параллелизация скрейпинга

```
# Celery + Redis для распределённых задач
# Каждый город × источник = отдельная задача

10 городов × 4 источника = 40 задач
С 8 воркерами → ~5 минут на полный цикл
```

---

## 14. Дорожная карта

### Phase 1: MVP (Недели 1-2) ✅ Текущий

- [x] Data model (Listing)
- [x] FastAPI backend
- [x] SQLite → PostgreSQL
- [x] Rule-based NLU
- [x] Basic search (structured)
- [x] Frontend (chat + listings)
- [x] Seed data
- [ ] CIAN scraper (real)

### Phase 2: Search & Scraping (Недели 3-4)

- [ ] Elasticsearch интеграция
- [ ] Full-text search
- [ ] Авито scraper
- [ ] Домклик scraper
- [ ] Дедупликация
- [ ] Нормализация адресов
- [ ] Фильтры на фронте

### Phase 3: AI & Analytics (Недели 5-6)

- [ ] pgvector embeddings
- [ ] Semantic search
- [ ] Hybrid scoring (structured + semantic + text)
- [ ] Аналитика (графики, тренды)
- [ ] Сравнение городов
- [ ] Price history tracking

### Phase 4: Alerts & UX (Недели 7-8)

- [ ] Search alerts (подписки)
- [ ] Email / Telegram уведомления
- [ ] Map view (Yandex Maps)
- [ ] User accounts (JWT)
- [ ] Saved searches
- [ ] Recommendations

### Phase 5: Scale & Polish (Недели 9-12)

- [ ] Docker → production
- [ ] Nginx + TLS
- [ ] Мониторинг (Prometheus + Grafana)
- [ ] CI/CD pipeline
- [ ] Performance optimization
- [ ] LLM integration (GigaChat)
- [ ] Mobile PWA

### Phase 6: Growth (Месяц 4+)

- [ ] Больше источников (10+)
- [ ] Больше городов (50+)
- [ ] Коммерческая недвижимость
- [ ] Ипотечный калькулятор
- [ ] Юридические проверки
- [ ] Партнёрская программа
- [ ] Мобильное приложение (React Native)
