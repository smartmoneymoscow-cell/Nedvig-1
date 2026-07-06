# 🏗 Nedvig-1 — План рефакторинга: монолит → микросервисы

> На основе аудита от 2026-07-06. Исходное состояние: монолитный FastAPI с дублированием, без auth, без тестов, парсеры не работают.

---

## 0. Текущее состояние → Целевое

```
СЕЙЧАС (монолит):                          ЦЕЛЬ (микросервисы):
┌──────────────────────┐                   ┌──────────────────────────────────────┐
│  run_local.py (948л) │                   │           API Gateway (Kong)          │
│  + backend/app/      │                   │  auth │ rate-limit │ routing │ TLS   │
│  + 3 файла скрейперов│        →          └──────────────┬───────────────────────┘
│  + demo/index.html   │                                  │
│  Всё в одном процессе│                   ┌──────────────┼──────────────┐
└──────────────────────┘                   │              │              │
                                  ┌────────▼───┐  ┌──────▼──────┐ ┌───▼──────────┐
                                  │  Ingestion │  │  Core API   │ │   Frontend   │
                                  │  Service   │  │  (search,   │ │  (Next.js)   │
                                  │  (scrapers)│  │  analytics, │ │              │
                                  └─────┬──────┘  │  agent)     │ └──────────────┘
                                        │         └──────┬──────┘
                                        │                │
                                  ┌─────▼────────────────▼──────┐
                                  │     Shared Infrastructure    │
                                  │  PostgreSQL │ Redis │ S3     │
                                  │  RabbitMQ   │ ES    │ pgvect │
                                  └──────────────────────────────┘
```

---

## Phase 0: Подготовка (Неделя 0) — СЕЙЧАС

### 0.1 Безопасность — немедленно

| Действие | Файл | Что делать |
|----------|------|------------|
| Отозвать PAT | GitHub Settings | Revoke `github…tQ85`, сгенерировать новый |
| CORS | `main.py`, `run_local.py` | `allow_origins=["https://nedvig.ru"]` вместо `["*"]` |
| DEBUG | `config.py`, `run_local.py` | `DEBUG: bool = False` по умолчанию |
| Error handler | `run_local.py` | Убрать `str(exc)` из ответа |
| .env.example | корень | Создать шаблон с комментариями |
| docker-compose | `docker-compose.yml` | `${POSTGRES_PASSWORD}` из env, не хардкод |

### 0.2 Удалить мёртвый код

```
Удалить:
  ├── backend/app/scrapers/real_scrapers.py      ← дубликат #1
  ├── backend/app/scrapers/production_scrapers.py ← дубликат #2
  └── (оставить base.py + cian_scraper.py как skeleton)

Решить судьбу run_local.py:
  Вариант А: Удалить, всё в backend/app/
  Вариант Б: Сделать run_local.py основой, удалить backend/app/
  → Рекомендую: Вариант А (модульная структура масштабируется лучше)
```

### 0.3 Единая точка входа

```python
# backend/app/config.py — финальный вариант
class Settings(BaseSettings):
    APP_NAME: str = "Realty Platform"
    DEBUG: bool = False                          # ← по умолчанию False
    
    DATABASE_URL: str                            # обязательное поле
    REDIS_URL: str = "redis://localhost:6379"
    ES_URL: str = "http://localhost:9200"
    
    CORS_ORIGINS: list[str] = ["https://nedvig.ru"]  # ← не ["*"]
    
    SECRET_KEY: str                              # для JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    
    SCRAPE_PROXY_LIST: list[str] = []            # прокси для скрейперов
    
    class Config:
        env_file = ".env"
```

---

## Phase 1: Разделение на сервисы (Недели 1–3)

### 1.1 Карта микросервисов

```
services/
├── gateway/              # API Gateway (Kong / Nginx)
│   ├── kong.yml          # роутинг, rate-limit, auth
│   └── Dockerfile
│
├── core-api/             # Основной API (search, analytics, listings)
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── routes_listings.py
│   │   │   ├── routes_analytics.py
│   │   │   └── routes_health.py
│   │   ├── models/
│   │   │   ├── listing.py
│   │   │   └── price_history.py
│   │   ├── services/
│   │   │   ├── search_service.py
│   │   │   ├── analytics_service.py
│   │   │   └── dedup_service.py
│   │   └── config.py
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── agent-api/            # AI-агент (NLU + chat)
│   ├── app/
│   │   ├── main.py
│   │   ├── nlu/
│   │   │   ├── parser.py        # rule-based NLU
│   │   │   ├── entities.py      # извлечение сущностей
│   │   │   └── intents.py       # определение намерения
│   │   ├── response/
│   │   │   └── formatter.py     # генерация ответов
│   │   ├── llm/                 # (будущее) LLM integration
│   │   │   └── provider.py
│   │   └── config.py
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── ingestion/            # Сбор данных (скрейперы)
│   ├── app/
│   │   ├── main.py              # worker entry point
│   │   ├── scrapers/
│   │   │   ├── base.py
│   │   │   ├── cian.py
│   │   │   ├── avito.py
│   │   │   └── domclick.py
│   │   ├── pipeline/
│   │   │   ├── normalizer.py    # нормализация данных
│   │   │   ├── deduplicator.py  # дедупликация
│   │   │   └── writer.py        # запись в БД
│   │   ├── proxy/
│   │   │   └── manager.py       # ротация прокси
│   │   └── config.py
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── auth/                 # Аутентификация (опционально, можно через Gateway)
│   ├── app/
│   │   ├── main.py
│   │   ├── models/user.py
│   │   ├── jwt_service.py
│   │   └── config.py
│   ├── requirements.txt
│   └── Dockerfile
│
└── frontend/             # Next.js фронтенд (без изменений структуры)
    ├── app/
    ├── components/         # ← выделить компоненты
    ├── lib/
    │   ├── api.ts          # API client
    │   └── types.ts        # TypeScript типы
    ├── package.json
    └── Dockerfile
```

### 1.2 Межсервисное взаимодействие

```
┌──────────┐   HTTP/REST    ┌──────────┐
│ Frontend │ ──────────────→ │ Gateway  │
└──────────┘                 └────┬─────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
              ┌─────▼─────┐ ┌────▼────┐ ┌──────▼──────┐
              │ Core API  │ │Agent API│ │  Ingestion  │
              │ :8001     │ │ :8002   │ │  :8003      │
              └─────┬─────┘ └────┬────┘ └──────┬──────┘
                    │            │              │
                    │     ┌──────▼──────┐       │
                    │     │  Core API   │←──────┘ (запись через API)
                    │     │  (единая    │    или
                    │     │   точка     │
                    │     │   записи)   │
                    └────→│             │
                          └──────┬──────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
        ┌─────▼─────┐    ┌──────▼──────┐    ┌─────▼─────┐
        │PostgreSQL  │    │    Redis    │    │  S3/MinIO │
        │+ pgvector  │    │  (кеш)     │    │ (фото)    │
        └────────────┘    └─────────────┘    └───────────┘
```

### 1.3 Протоколы

| Взаимодействие | Протокол | Почему |
|---------------|----------|--------|
| Frontend → Gateway | HTTPS | Внешний трафик |
| Gateway → Services | HTTP/gRPC | Внутренний, быстрый |
| Ingestion → Core API | HTTP POST | Запись через API (не напрямую в БД) |
| Agent API → Core API | HTTP GET | Поиск данных для ответов |
| Services → Redis | Redis protocol | Кеш, pub/sub |
| Services → PostgreSQL | asyncpg | Постоянные соединения |
| Ingestion scheduler | RabbitMQ / Redis Queue | Фоновые задачи скрейпинга |

### 1.4 Единая база данных (пока без CQRS)

На первом этапе — **одна PostgreSQL** для всех сервисов. Каждый сервис работает со "своими" таблицами:

| Сервис | Таблицы |
|--------|---------|
| Core API | `listings`, `price_history`, `scraping_jobs` |
| Auth | `users`, `sessions` |
| Ingestion | пишет в `listings` через Core API |

**Почему не CQRS сразу?** Потому что объём данных мал (тысячи, не миллионы). Event sourcing и отдельные read/write базы — overengineering на этом этапе.

---

## Phase 2: Исправление багов и тесты (Недели 2–4)

### 2.1 Приоритетные баги

| # | Баг | Файл | Исправление |
|---|-----|------|-------------|
| 1 | `price: Decimal` → `Float` в БД | `listing.py` | `mapped_column(Numeric(15,2))` |
| 2 | `created_at: str` вместо `DateTime` | `run_local.py` | `DateTime(timezone=True)` |
| 3 | `asyncio.sleep()` в sync-методе | `real_scrapers.py` | `await asyncio.sleep()` или `time.sleep()` |
| 4 | Bare `except:` повсюду | все скрейперы | `except (httpx.HTTPError, asyncio.TimeoutError) as e:` |
| 5 | Новый ES client на каждый запрос | `search.py` | Singleton + connection pool |
| 6 | `SearchService` не используется ES | `search.py` | Либо использовать, либо убрать |
| 7 | `embedding: JSONB` вместо `vector` | `listing.py` | `from pgvector.sqlalchemy import Vector` |

### 2.2 Тесты — минимальный набор

```
tests/
├── conftest.py                # fixtures: test DB, test client
│
├── unit/
│   ├── test_nlu_parser.py     # ← самый важный, ~50 кейсов
│   │   ├── test_parse_rooms
│   │   ├── test_parse_price
│   │   ├── test_parse_city
│   │   ├── test_parse_deal_type
│   │   └── test_parse_property_type
│   ├── test_dedup.py
│   └── test_normalizer.py
│
├── integration/
│   ├── test_api_listings.py   # CRUD через HTTP
│   ├── test_api_analytics.py
│   ├── test_api_agent.py
│   └── test_search_service.py # SQL-запросы
│
└── e2e/
    └── test_chat_flow.py      # полный сценарий: запрос → ответ
```

**Минимальный targe: покрытие NLU 80%, API 60%.**

### 2.3 NLU — текущие проблемы и исправления

```python
# СЕЙЧАС: "двушка" → rooms=2 ✓, но "2-комнатная" → rooms=2 только если 
# паттерн совпадает. "2х комнатная" — пропускается.

# ИСПРАВЛЕНИЕ: расширить паттерны
ROOM_PATTERNS = [
    (r"(\d)\s*[-–]?\s*комн", lambda m: int(m.group(1))),
    (r"(\d)\s*[-–]?\s*к\b", lambda m: int(m.group(1))),
    (r"(\d)\s*[xх]\s*комн", lambda m: int(m.group(1))),      # ← новое
    (r"студия|студи", lambda m: 0),
    (r"однушк|одн[оё]к", lambda m: 1),                        # ← расширено
    (r"двушк|двухк", lambda m: 2),                            # ← расширено
    (r"трёшк|трешк|трёхк", lambda m: 3),                     # ← расширено
    (r"четыр", lambda m: 4),
    (r"пят", lambda m: 5),
]

# СЕЙЧАС: "5 млн" без "до" → price_max не парсится
# ИСПРАВЛЕНИЕ: добавить fallback-паттерн
# (уже есть в run_local.py, но не в backend/app/ai/agent.py)
```

---

## Phase 3: Инфраструктура (Недели 3–5)

### 3.1 Docker Compose — полный стек

```yaml
# docker-compose.dev.yml
version: "3.9"

services:
  # ─── Shared Infrastructure ──────────────
  postgres:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: realty
      POSTGRES_USER: realty
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U realty"]
      interval: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=true               # ← ВКЛЮЧИТЬ
      - ELASTIC_PASSWORD=${ES_PASSWORD}
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports: ["9200:9200"]
    volumes:
      - esdata:/usr/share/elasticsearch/data

  rabbitmq:
    image: rabbitmq:3-management-alpine
    ports: ["5672:5672", "15672:15672"]
    environment:
      RABBITMQ_DEFAULT_USER: realty
      RABBITMQ_DEFAULT_PASS: ${RABBIT_PASSWORD}

  # ─── Application Services ───────────────
  gateway:
    image: kong:3.4
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/kong.yml
    volumes:
      - ./infra/kong.yml:/kong/kong.yml
    ports: ["8000:8000", "8443:8443"]
    depends_on: [core-api, agent-api]

  core-api:
    build: ./services/core-api
    ports: ["8001:8001"]
    environment:
      DATABASE_URL: postgresql+asyncpg://realty:${POSTGRES_PASSWORD}@postgres:5432/realty
      REDIS_URL: redis://redis:6379
      ES_URL: http://elasticsearch:9200
      ES_PASSWORD: ${ES_PASSWORD}
      SECRET_KEY: ${SECRET_KEY}
      CORS_ORIGINS: ${CORS_ORIGINS}
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_started }
    volumes:
      - ./services/core-api:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

  agent-api:
    build: ./services/agent-api
    ports: ["8002:8002"]
    environment:
      CORE_API_URL: http://core-api:8001
      SECRET_KEY: ${SECRET_KEY}
    depends_on: [core-api]
    volumes:
      - ./services/agent-api:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload

  ingestion:
    build: ./services/ingestion
    environment:
      CORE_API_URL: http://core-api:8001
      RABBITMQ_URL: amqp://realty:${RABBIT_PASSWORD}@rabbitmq:5672
      PROXY_LIST: ${PROXY_LIST}
    depends_on: [core-api, rabbitmq]
    volumes:
      - ./services/ingestion:/app
    command: python -m app.worker

  frontend:
    build: ./services/frontend
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    depends_on: [gateway]
    volumes:
      - ./services/frontend:/app
      - /app/node_modules

  # ─── Monitoring (Phase 5) ───────────────
  # prometheus:
  # grafana:

volumes:
  pgdata:
  esdata:
```

### 3.2 Gateway (Kong) — конфигурация

```yaml
# infra/kong.yml
_format_version: "3.0"

services:
  - name: core-api
    url: http://core-api:8001
    routes:
      - name: core-routes
        paths: ["/api/listings", "/api/analytics", "/api/stats", "/api/health"]
    plugins:
      - name: rate-limiting
        config:
          minute: 60
          policy: redis
          redis_host: redis
      - name: cors
        config:
          origins: ["https://nedvig.ru", "http://localhost:3000"]

  - name: agent-api
    url: http://agent-api:8002
    routes:
      - name: agent-routes
        paths: ["/api/agent"]
    plugins:
      - name: rate-limiting
        config:
          minute: 20          # AI-запросы дороже
          policy: redis
          redis_host: redis
      - name: cors
        config:
          origins: ["https://nedvig.ru", "http://localhost:3000"]

  - name: admin-api
    url: http://core-api:8001
    routes:
      - name: admin-routes
        paths: ["/api/admin"]
    plugins:
      - name: key-auth         # ← только с API key
      - name: rate-limiting
        config:
          minute: 30
```

### 3.3 Миграции (Alembic)

```bash
# Инициализация
cd services/core-api
alembic init alembic

# Первая миграция
alembic revision --autogenerate -m "initial: listings, price_history, scraping_jobs"

# Применение
alembic upgrade head

# Откат
alembic downgrade -1
```

```python
# alembic/env.py — ключевые настройки
from app.models import Base
target_metadata = Base.metadata

# alembic.ini
# sqlalchemy.url = postgresql+asyncpg://realty:***@localhost:5432/realty
```

---

## Phase 4: Auth и пользователи (Недели 4–6)

### 4.1 Модель пользователя

```python
# services/core-api/app/models/user.py
class User(Base):
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="user")  # user | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SavedSearch(Base):
    __tablename__ = "saved_searches"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    filters: Mapped[dict] = mapped_column(JSONB)
    is_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_frequency: Mapped[str] = mapped_column(String(20), default="daily")  # instant | daily | weekly
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
```

### 4.2 JWT auth flow

```
Регистрация:  POST /api/auth/register  → { email, password, name }
Логин:        POST /api/auth/login     → { email, password } → { access_token, refresh_token }
Обновление:   POST /api/auth/refresh   → { refresh_token } → { access_token }

Защищённые:
  GET  /api/saved-searches     (нужен JWT)
  POST /api/saved-searches     (нужен JWT)
  POST /api/agent/chat         (опционально, можно и без auth)
```

### 4.3 Изоляция данных

```
Анонимный пользователь:
  - Поиск: ✓
  - Аналитика: ✓
  - AI-чат: ✓ (с rate limit 20/мин)
  - Сохранение поисков: ✗
  - Уведомления: ✗

Авторизованный:
  - Всё анонимного +
  - Сохранение поисков: ✓
  - Email/Telegram уведомления: ✓
  - История чата: ✓

Админ:
  - Всё +
  - /api/admin/* эндпоинты
  - Управление скрейпингом
  - Просмотр логов
```

---

## Phase 5: Ingestion Pipeline (Недели 5–8)

### 5.1 Решение проблемы парсинга

**Стратегия:** Прокси + retry + мониторинг блокировок.

```python
# services/ingestion/app/proxy/manager.py
class ProxyManager:
    """Ротация резидентных прокси."""
    
    def __init__(self, proxies: list[str]):
        self.proxies = proxies
        self._blocked: dict[str, datetime] = {}  # proxy → until
        self._index = 0
    
    def get(self, source: str) -> str | None:
        """Получить рабочий прокси для источника."""
        now = datetime.utcnow()
        available = [
            p for p in self.proxies 
            if p not in self._blocked or self._blocked[p] < now
        ]
        if not available:
            # Разблокировать все (cooldown прошёл)
            self._blocked.clear()
            available = self.proxies
        
        proxy = available[self._index % len(available)]
        self._index += 1
        return proxy
    
    def mark_blocked(self, proxy: str, cooldown_minutes: int = 30):
        self._blocked[proxy] = datetime.utcnow() + timedelta(minutes=cooldown_minutes)
```

### 5.2 Пайплайн обработки

```
                    ┌─────────────┐
                    │  Scheduler  │ (APScheduler / Celery Beat)
                    │  "каждые 2ч"│
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Scraper   │ (CIAN / Avito / DomClick)
                    │  ScrapedItem│
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Normalizer  │ (адреса, цены, типы)
                    │  CleanItem  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Deduplicator│ (source_hash + content_hash)
                    │  new/update │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼────┐ ┌────▼─────┐
        │  Writer   │ │Embedder│ │Indexer   │
        │ (PostgreSQL)│ │(pgvec) │ │(ES)      │
        └───────────┘ └────────┘ └──────────┘
              │
        ┌─────▼─────┐
        │  Alert    │ (если цена изменилась → уведомление)
        │  Checker  │
        └───────────┘
```

### 5.3 Расписание скрейпинга

```python
# services/ingestion/app/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# Основные города — каждые 2 часа
scheduler.add_job(
    scrape_city, 
    CronTrigger(hour="*/2", minute=0),
    args=["Москва", "sale"],
    id="moscow_sale",
    max_instances=1,
)

# Второстепенные — каждые 6 часов
scheduler.add_job(
    scrape_city,
    CronTrigger(hour="*/6", minute=30),
    args=["Краснодар", "sale"],
    id="krasnodar_sale",
    max_instances=1,
)
```

### 5.4 Мониторинг скрейпинга

```python
# services/ingestion/app/models.py
@dataclass
class ScrapeResult:
    source: str
    city: str
    deal_type: str
    status: str           # success | partial | blocked | error
    items_found: int
    items_new: int
    items_updated: int
    items_skipped: int    # дубли / битые
    duration_sec: float
    errors: list[str]
    proxy_used: str
    timestamp: datetime
```

---

## Phase 6: Поиск и аналитика (Недели 6–8)

### 6.1 Elasticsearch интеграция

```python
# services/core-api/app/services/es_service.py
class ElasticsearchService:
    INDEX = "listings"
    
    MAPPING = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "source": {"type": "keyword"},
                "property_type": {"type": "keyword"},
                "deal_type": {"type": "keyword"},
                "price": {"type": "float"},
                "area_m2": {"type": "float"},
                "rooms": {"type": "integer"},
                "city": {"type": "keyword"},
                "district": {"type": "keyword"},
                "address": {"type": "text", "analyzer": "russian"},
                "description": {"type": "text", "analyzer": "russian"},
                "metro_station": {"type": "keyword"},
                "location": {"type": "geo_point"},  # lat/lon
                "created_at": {"type": "date"},
            }
        }
    }
    
    async def search(self, filters: SearchFilters, query_text: str = None) -> dict:
        """Гибридный поиск: структурные фильтры + полнотекстовый."""
        must = []
        filter_clauses = []
        
        if query_text:
            must.append({
                "multi_match": {
                    "query": query_text,
                    "fields": ["description^2", "address", "title"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            })
        
        if filters.city:
            filter_clauses.append({"term": {"city": filters.city}})
        if filters.deal_type:
            filter_clauses.append({"term": {"deal_type": filters.deal_type}})
        if filters.property_type:
            filter_clauses.append({"term": {"property_type": filters.property_type}})
        if filters.price_max:
            filter_clauses.append({"range": {"price": {"lte": filters.price_max}}})
        if filters.price_min:
            filter_clauses.append({"range": {"price": {"gte": filters.price_min}}})
        
        body = {
            "query": {
                "bool": {
                    "must": must,
                    "filter": filter_clauses,
                }
            },
            "sort": [
                {"_score": "desc"},
                {"created_at": "desc"},
            ],
            "size": filters.limit or 20,
            "from": filters.offset or 0,
        }
        
        return await self.client.search(index=self.INDEX, body=body)
```

### 6.2 Семантический поиск (pgvector)

```python
# services/core-api/app/services/semantic_search.py
from sentence_transformers import SentenceTransformer

class SemanticSearchService:
    def __init__(self):
        self.model = SentenceTransformer(
            'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
        )
    
    async def search(self, query: str, city: str = None, limit: int = 20) -> list:
        """Семантический поиск через pgvector."""
        embedding = self.model.encode(query).tolist()
        
        # cosine distance через pgvector
        stmt = (
            select(Listing)
            .where(Listing.is_active == True)
            .where(Listing.embedding.isnot(None))
        )
        if city:
            stmt = stmt.where(Listing.city == city)
        
        stmt = stmt.order_by(
            Listing.embedding.cosine_distance(embedding)
        ).limit(limit)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def generate_embedding(self, listing: Listing) -> list[float]:
        """Генерация embedding для нового объявления."""
        text = f"{listing.title or ''} {listing.description or ''} {listing.address} {listing.city}"
        return self.model.encode(text).tolist()
```

### 6.3 Гибридный скоринг

```python
async def hybrid_search(self, filters, query_text, limit=20):
    """Комбинация трёх типов поиска."""
    
    # 1. Структурный (PostgreSQL) — точные фильтры
    structured = await self.pg_search(filters, limit=limit*2)
    
    # 2. Полнотекстовый (Elasticsearch) — fuzzy match
    text_results = await self.es_search(filters, query_text, limit=limit*2) if query_text else []
    
    # 3. Семантический (pgvector) — смысловое сходство
    semantic = await self.semantic_search(query_text, filters.city, limit=limit*2) if query_text else []
    
    # Скоринг и мёрдж
    scores = {}
    for item in structured:
        scores[item.id] = scores.get(item.id, 0) + 0.4  # structural weight
    
    for item in text_results:
        scores[item.id] = scores.get(item.id, 0) + 0.35  # text weight
    
    for item in semantic:
        scores[item.id] = scores.get(item.id, 0) + 0.25  # semantic weight
    
    # Сортировка по combined score
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:limit]
    
    # Возвращаем в порядке ранжирования
    id_to_item = {i.id: i for i in structured + text_results + semantic}
    return [id_to_item[listing_id] for listing_id, _ in ranked]
```

---

## Phase 7: Frontend (Недели 7–9)

### 7.1 Структура компонентов

```
services/frontend/
├── app/
│   ├── layout.tsx              # Root layout
│   ├── page.tsx                # → redirect to /chat
│   ├── chat/
│   │   └── page.tsx            # AI Chat (основная страница)
│   ├── listings/
│   │   ├── page.tsx            # Каталог с фильтрами
│   │   └── [id]/
│   │       └── page.tsx        # Детальная страница
│   ├── analytics/
│   │   └── page.tsx            # Дашборд аналитики
│   └── auth/
│       ├── login/page.tsx
│       └── register/page.tsx
│
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   ├── Header.tsx
│   │   └── MobileNav.tsx
│   │
│   ├── chat/
│   │   ├── ChatWindow.tsx      # Основной компонент чата
│   │   ├── MessageBubble.tsx
│   │   ├── SuggestionChips.tsx # Кнопки-подсказки
│   │   └── FilterChips.tsx     # Извлечённые фильтры
│   │
│   ├── listings/
│   │   ├── ListingCard.tsx
│   │   ├── ListingGrid.tsx
│   │   ├── SearchFilters.tsx   # Панель фильтров
│   │   ├── PriceTag.tsx
│   │   └── ImageGallery.tsx
│   │
│   ├── analytics/
│   │   ├── PriceChart.tsx
│   │   ├── CityComparison.tsx
│   │   └── StatsCards.tsx
│   │
│   └── ui/                     # Базовые UI компоненты
│       ├── Button.tsx
│       ├── Input.tsx
│       ├── Select.tsx
│       └── Card.tsx
│
├── lib/
│   ├── api.ts                  # API client (fetch wrapper)
│   ├── types.ts                # TypeScript типы
│   ├── hooks/                  # Custom hooks
│   │   ├── useChat.ts
│   │   ├── useListings.ts
│   │   └── useAuth.ts
│   └── utils.ts
│
├── package.json
└── Dockerfile
```

### 7.2 API Client

```typescript
// services/frontend/lib/api.ts
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
    };

    const res = await fetch(`${API}${path}`, { ...options, headers });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ message: res.statusText }));
      throw new Error(error.message || `HTTP ${res.status}`);
    }
    return res.json();
  }

  // Agent
  chat(query: string) {
    return this.request<{ response: string; action: string; filters: object; total: number }>(
      '/api/agent/chat',
      { method: 'POST', body: JSON.stringify({ query }) }
    );
  }

  // Listings
  getListings(params: Record<string, string>) {
    const qs = new URLSearchParams(params).toString();
    return this.request<{ total: number; items: Listing[] }>(`/api/listings?${qs}`);
  }

  getListing(id: string) {
    return this.request<Listing>(`/api/listings/${id}`);
  }

  // Analytics
  getAnalytics(city?: string) {
    return this.request<{ analytics: AnalyticsItem[] }>(
      `/api/analytics${city ? `?city=${city}` : ''}`
    );
  }

  // Auth
  login(email: string, password: string) {
    return this.request<{ access_token: string; refresh_token: string }>(
      '/api/auth/login',
      { method: 'POST', body: JSON.stringify({ email, password }) }
    );
  }
}

export const api = new ApiClient();
```

---

## Phase 8: Мониторинг и CI/CD (Недели 9–11)

### 8.1 Метрики (Prometheus)

```python
# services/core-api/app/middleware.py
from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    'api_requests_total', 
    'Total requests', 
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'api_request_duration_seconds',
    'Request latency',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")
```

### 8.2 CI/CD (GitHub Actions)

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install ruff
      - run: ruff check .

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg15
        env:
          POSTGRES_DB: realty_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r services/core-api/requirements.txt
      - run: pip install pytest pytest-asyncio httpx
      - run: pytest services/core-api/tests/ -v
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/realty_test

  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose -f docker-compose.prod.yml build
```

---

## Сводная дорожная карта

```
Неделя  Phase                           Deliverables
──────  ──────────────────────────────  ────────────────────────────────────
  0     Безопасность + очистка          CORS закрыт, DEBUG=False, 
                                         мёртвый код удалён, .env.example

  1-3   Разделение на сервисы           4 сервиса в Docker Compose,
                                         Kong gateway, единая БД

  2-4   Баги + тесты                    Типы данных исправлены,
                                         80% NLU покрыто тестами,
                                         API integration tests

  3-5   Инфраструктура                  Alembic мigrations,
                                         RabbitMQ для ingestion,
                                         Redis кеш

  4-6   Auth                            JWT, пользователи,
                                         saved searches, admin API

  5-8   Ingestion Pipeline              Прокси-ротация, 3 рабочих скрейпера,
                                         дедупликация, мониторинг блокировок

  6-8   Поиск + аналитика              Elasticsearch интеграция,
                                         pgvector семантика,
                                         гибридный скоринг

  7-9   Frontend                        Компоненты, API client,
                                         фильтры, карта

  9-11  Мониторинг + CI/CD              Prometheus, Grafana,
                                         GitHub Actions,
                                         docker-compose.prod.yml
```

---

## Приоритеты по импакту

```
🔴 Критично (сделать немедленно):
   1. Закрыть CORS
   2. DEBUG=False
   3. Отозвать GitHub PAT
   4. Удалить дублированный код

🟡 Важно (недели 1-4):
   5. Разделить на сервисы
   6. Добавить тесты (NLU + API)
   7. Alembic миграции
   8. Исправить типы данных

🟢 Значимо (недели 4-8):
   9. Auth + пользователи
   10. Рабочие скрейперы (прокси)
   11. Elasticsearch
   12. Redis кеш

🔵 Масштабирование (недели 8+):
   13. Семантический поиск
   14. Карта (Yandex Maps)
   15. Уведомления
   16. LLM интеграция
```
