# 📋 Nedvig-1 — План работ по приоритетам

> Конкретные задачи с файлами, изменениями и критериями приёмки. Без абстракций.

---

## 🔴 БЛОК 0: Немедленно (сегодня-завтра)

> Цель: устраниить уязвимости, которые эксплуатируются прямо сейчас.

### 0.1 Отозвать GitHub PAT
- **Что:** Зайти в GitHub → Settings → Developer settings → Personal access tokens → удалить токен `github…tQ85`
- **Почему:** Токен в открытом виде в истории чата — полный доступ к репозиторию
- **Критерий:** Старый токен не работает при `git push`

### 0.2 Закрыть CORS
- **Файл:** `backend/app/main.py` (строка ~25)
- **Файл:** `run_local.py` (строка ~487)
- **Было:**
  ```python
  allow_origins=["*"],
  allow_credentials=True,
  ```
- **Стало:**
  ```python
  allow_origins=[
      "https://nedvig.ru",
      "http://localhost:3000",  # dev
  ],
  allow_credentials=True,
  ```
- **Критерий:** Запрос с `Origin: https://evil.com` получает CORS-блок

### 0.3 Выключить DEBUG
- **Файл:** `backend/app/config.py` (строка 8)
- **Файл:** `run_local.py` (строка 19)
- **Было:** `DEBUG: bool = True` / `DEBUG = True`
- **Стало:** `DEBUG: bool = False` / `DEBUG = False`
- **Критерий:** Глобальный error handler не отдаёт `str(exc)`

### 0.4 Скрыть утечку ошибок
- **Файл:** `run_local.py` (строка ~503–510)
- **Было:**
  ```python
  content={"error": "Internal server error", "detail": str(exc) if DEBUG else "Contact support"},
  ```
- **Стало:**
  ```python
  content={"error": "Internal server error"},
  ```
  Плюс добавить `log.error(f"Unhandled: {exc}", exc_info=True)` для серверных логов.
- **Критерий:** Ответ 500 не содержит путей к файлам, имён таблиц, строк кода

### 0.5 Пароли из env в docker-compose
- **Файл:** `docker-compose.yml` (строки 7–9)
- **Было:**
  ```yaml
  POSTGRES_PASSWORD: ***
  ```
- **Стало:**
  ```yaml
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  ```
- **Файл:** Создать `.env.example`:
  ```bash
  POSTGRES_PASSWORD=changeme
  ES_URL=http://localhost:9200
  NEXT_PUBLIC_API_URL=http://localhost:8000
  ```
- **Критерий:** `docker-compose.yml` не содержит паролей в открытом виде

### 0.6 Создать .gitignore补充ения
- **Файл:** `.gitignore` — добавить:
  ```
  .env
  .env.local
  .env.production
  realty.db
  *.sqlite3
  ```
- **Критерий:** `git status` не показывает `.env` и базы данных

**⏱ Оценка: 1–2 часа**
**📦 Deliverable: 6 файлов изменены, 0 уязвимостей класса "мгновенный взлом"**

---

## 🟡 БЛОК 1: Очистка кодовой базы (неделя 1)

> Цель: одна правда, один источник, ноль дубликатов.

### 1.1 Определить canonical backend
- **Решение:** Оставить `backend/app/` как основу, удалить `run_local.py`
- **Почему:** Модульная структура масштабируется; `run_local.py` — 948 строк в одном файле
- **Действие:** Проверить, что все фичи из `run_local.py` перенесены в `backend/app/`:
  - [ ] `PriceHistory` модель → `backend/app/models/price_history.py`
  - [ ] `ScrapingJob` модель → `backend/app/models/scraping_job.py`
  - [ ] `Deduplicator` класс → `backend/app/services/dedup.py`
  - [ ] `AnalyticsService` (полная версия) → `backend/app/services/analytics.py`
  - [ ] `NLUAgent` (расширенная версия из run_local.py) → заменить `backend/app/ai/agent.py`
  - [ ] Seed data (28 записей) → `scripts/seed_data.py`
  - [ ] `/api/health` эндпоинт → `backend/app/api/routes.py`
  - [ ] `/api/admin/scrape`, `/api/admin/jobs` → `backend/app/api/routes.py`
  - [ ] Pydantic модели (ChatRequest, ChatResponse, etc.) → `backend/app/api/schemas.py`
- **Удалить:** `run_local.py`
- **Критерий:** `uvicorn app.main:app` работает, все эндпоинты отвечают

### 1.2 Удалить дублирующие скрейперы
- **Удалить:** `backend/app/scrapers/real_scrapers.py` (дубликат #1, 350 строк)
- **Удалить:** `backend/app/scrapers/production_scrapers.py` (дубликат #2, 530 строк)
- **Оставить:** `backend/app/scrapers/base.py` + `backend/app/scrapers/cian_scraper.py`
- **Критерий:** `find . -name "*.py" | xargs grep "class.*Scraper"` показывает 2 класса, не 6

### 1.3 Объединить AI-агент
- **Файл:** `backend/app/ai/agent.py`
- **Взять из `run_local.py`** расширенный `NLUAgent`:
  - Больше паттернов комнат (`пят`, `четыр`, расширенные алиасы)
  - Больше городских алиасов (`москве`, `москвы`, `петербурге`, `екб`, `нск`)
  - Парсинг площади (`от 50м²`, `до 100м²`)
  - Парсинг этажа (`на 5 этаже`)
  - Сортировка (`дешевле`, `дороже`, `новые`)
  - `format_stats()` метод
- **Удалить:** старую версию `AIAgent`
- **Критерий:** Тест-кейсы проходят:
  ```
  "двушка в москве до 10 млн" → rooms=2, city=Москва, price_max=10000000
  "студия в питере в аренду" → property_type=studio, city=СПБ, deal_type=rent
  "3х комнатная квартира" → rooms=3
  "квартира от 50 до 80 м²" → area_min=50, area_max=80
  ```

### 1.4 Вынести Pydantic-схемы
- **Создать:** `backend/app/api/schemas.py`
- **Перенести:**
  ```python
  from pydantic import BaseModel, Field
  
  class ChatRequest(BaseModel):
      query: str = Field(..., min_length=1, max_length=500)
  
  class ChatResponse(BaseModel):
      response: str
      action: str
      filters: dict
      total: int
  
  class ListingResponse(BaseModel):
      total: int
      offset: int
      limit: int
      items: list[dict]
  
  class HealthResponse(BaseModel):
      status: str
      version: str
      uptime: float
      listings_count: int
  ```
- **Обновить:** `backend/app/api/routes.py` — использовать schemas вместо `body: dict`
- **Критерий:** `/docs` показывает правильные request/response модели

**⏱ Оценка: 4–6 часов**
**📦 Deliverable: ~1800 строк удалено, 1 canonical backend, 0 дубликатов**

---

## 🟡 БЛОК 2: Исправление багов (неделя 1–2)

> Цель: код делает то, что говорит.

### 2.1 Типы данных в модели Listing
- **Файл:** `backend/app/models/listing.py`
- **Изменения:**
  ```python
  # Было (баг: Decimal тип → Float колонка):
  price: Mapped[Decimal] = mapped_column(Float, nullable=False, index=True)
  
  # Стало:
  from sqlalchemy import Numeric
  price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, index=True)
  
  # Было (баг: datetime.utcnow — deprecated в SQLAlchemy 2.0):
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  
  # Стало:
  from sqlalchemy import func
  created_at: Mapped[datetime] = mapped_column(
      DateTime(timezone=True), server_default=func.now(), index=True
  )
  updated_at: Mapped[datetime] = mapped_column(
      DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
  )
  ```
- **Критерий:** Цена 18500000 хранится как `18500000.00`, не `18500000.0000000001`

### 2.2 Embedding: JSONB → pgvector
- **Файл:** `backend/app/models/listing.py`
- **Файл:** `backend/requirements.txt` — добавить `pgvector==0.3.0`
- **Изменения:**
  ```python
  from pgvector.sqlalchemy import Vector
  
  # Было:
  embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)
  
  # Стало:
  embedding: Mapped[list | None] = mapped_column(Vector(384), nullable=True)
  ```
- **Критерий:** В БД колонка `embedding` типа `vector(384)`, не `jsonb`

### 2.3 SearchService: убрать утечку ES-клиента
- **Файл:** `backend/app/services/search.py`
- **Было:** Новый `AsyncElasticsearch` на каждый вызов `SearchService.__init__`
- **Стало:**
  ```python
  # Singleton ES client
  _es_client: AsyncElasticsearch | None = None
  
  def get_es_client() -> AsyncElasticsearch:
      global _es_client
      if _es_client is None:
          _es_client = AsyncElasticsearch(settings.ES_URL)
      return _es_client
  
  class SearchService:
      def __init__(self, db: AsyncSession):
          self.db = db
          self.es = get_es_client()
      
      # Убрать close() — не закрываем singleton
  ```
- **Убрать:** `finally: await search.close()` из routes.py
- **Критерий:** Нет `ResourceWarning` в логах при 100+ запросах

### 2.4 Bare except → конкретные исключения
- **Файлы:** все скрейперы, routes.py
- **Было:**
  ```python
  except:
      pass
  except Exception as e:
  ```
- **Стало:**
  ```python
  except (httpx.HTTPError, asyncio.TimeoutError) as e:
      log.warning(f"Request failed: {e}")
  except (KeyError, ValueError, TypeError) as e:
      log.debug(f"Parse error: {e}")
  ```
- **Критий:** `grep -r "except:" --include="*.py"` возвращает 0 результатов

**⏱ Оценка: 3–4 часа**
**📦 Deliverable: 0 багов в типах данных, 0 утечек ресурсов, 0 bare except**

---

## 🟡 БЛОК 3: Тесты (неделя 2–3)

> Цель: ловить регрессии до деплоя.

### 3.1 Инфраструктура тестов
- **Создать:** `backend/tests/conftest.py`
  ```python
  import pytest
  import asyncio
  from httpx import AsyncClient, ASGITransport
  from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
  from app.main import app
  from app.models.database import Base, get_db
  
  TEST_DB = "postgresql+asyncpg://test:test@localhost:5432/realty_test"
  
  @pytest.fixture(scope="session")
  def event_loop():
      loop = asyncio.new_event_loop()
      yield loop
      loop.close()
  
  @pytest.fixture(scope="session")
  async def engine():
      eng = create_async_engine(TEST_DB)
      async with eng.begin() as conn:
          await conn.run_sync(Base.metadata.create_all)
      yield eng
      async with eng.begin() as conn:
          await conn.run_sync(Base.metadata.drop_all)
      await eng.dispose()
  
  @pytest.fixture
  async def db(engine):
      session = async_sessionmaker(engine, class_=AsyncSession)()
      yield session
      await session.rollback()
      await session.close()
  
  @pytest.fixture
  async def client(db):
      async def override_get_db():
          yield db
      app.dependency_overrides[get_db] = override_get_db
      transport = ASGITransport(app=app)
      async with AsyncClient(transport=transport, base_url="http://test") as c:
          yield c
      app.dependency_overrides.clear()
  ```
- **Создать:** `backend/tests/__init__.py`
- **Файл:** `backend/requirements.txt` — добавить:
  ```
  pytest==8.3.0
  pytest-asyncio==0.24.0
  httpx==0.27.0
  ```

### 3.2 Тесты NLU (unit) — самый важный блок
- **Создать:** `backend/tests/test_nlu.py`
- **Покрыть (~40 кейсов):**
  ```python
  # Комнаты
  ("двушка в Москве", {"rooms_min": 2, "rooms_max": 2, "city": "Москва"})
  ("3-комнатная", {"rooms_min": 3, "rooms_max": 3})
  ("3х комнатная", {"rooms_min": 3})
  ("студия", {"rooms_min": 0, "rooms_max": 0})
  ("однушка", {"rooms_min": 1})
  ("трёшка", {"rooms_min": 3})
  
  # Цена
  ("до 10 млн", {"price_max": 10_000_000})
  ("от 5 до 15 млн", {"price_min": 5_000_000, "price_max": 15_000_000})
  ("до 500000", {"price_max": 500_000})
  ("5 млн", {"price_max": 5_000_000})
  
  # Город
  ("в москве", {"city": "Москва"})
  ("в мск", {"city": "Москва"})
  ("в питере", {"city": "Санкт-Петербург"})
  ("в екб", {"city": "Екатеринбург"})
  
  # Тип недвижимости
  ("квартира", {"property_type": "apartment"})
  ("студия", {"property_type": "studio"})
  ("дом", {"property_type": "house"})
  ("участок", {"property_type": "land"})
  ("офис", {"property_type": "commercial"})
  
  # Тип сделки
  ("в аренду", {"deal_type": "rent"})
  ("купить", {"deal_type": "sale"})
  ("снять", {"deal_type": "rent"})
  
  # Action detection
  ("сравни цены в Москве и Питере", {"action": "compare"})
  ("аналитика по Краснодару", {"action": "analytics"})
  ("сколько объявлений", {"action": "stats"})
  
  # Комбо
  ("двушка в Москве до 15 млн в аренду", {
      "rooms_min": 2, "city": "Москва", "price_max": 15_000_000, "deal_type": "rent"
  })
  ```

### 3.3 Тесты API (integration)
- **Создать:** `backend/tests/test_api.py`
- **Тесты:**
  ```python
  # GET / — root info
  # GET /api/health — healthcheck
  # GET /api/listings — пустой список
  # GET /api/listings?city=Москва — фильтрация
  # GET /api/listings/{id} — 404 для несуществующего
  # POST /api/agent/chat — {"query": "двушка в Москве"}
  # POST /api/agent/chat — {"query": ""} → 400
  # GET /api/analytics — пустая аналитика
  # GET /api/stats — статистика
  ```

### 3.4 Seed-данные для тестов
- **Создать:** `backend/tests/fixtures.py`
  ```python
  SEED_LISTINGS = [
      {"city": "Москва", "rooms": 2, "price": 15_000_000, "deal_type": "sale", ...},
      {"city": "Москва", "rooms": 1, "price": 8_000_000, "deal_type": "sale", ...},
      {"city": "Санкт-Петербург", "rooms": 3, "price": 20_000_000, "deal_type": "sale", ...},
      # ... 10 записей для тестов
  ]
  ```

**⏱ Оценка: 6–8 часов**
**📦 Deliverable: 40+ NLU тестов, 10+ API тестов, `pytest` проходит за <10 сек**

---

## 🟡 БЛОК 4: Alembic миграции (неделя 3)

> Цель: управляемая схема БД вместо `create_all`.

### 4.1 Инициализация
- **Создать:** `backend/alembic.ini`
- **Создать:** `backend/alembic/env.py`
- **Создать:** `backend/alembic/versions/`
- **Команда:** `cd backend && alembic init alembic`

### 4.2 env.py — конфигурация
```python
# backend/alembic/env.py
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from app.config import get_settings
from app.models.database import Base

# Импортировать все модели чтобы Alembic их видел
from app.models.listing import Listing
from app.models.price_history import PriceHistory
from app.models.scraping_job import ScrapingJob

settings = get_settings()
target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=settings.DATABASE_URL, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

### 4.3 Первая миграция
```bash
cd backend
alembic revision --autogenerate -m "initial: listings, price_history, scraping_jobs"
alembic upgrade head
```

### 4.4 Обновить lifespan
```python
# backend/app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Было: await init_db()  ← create_all
    # Стало: ничего — миграции через Alembic
    yield
```

**⏱ Оценка: 2–3 часа**
**📦 Deliverable: `alembic upgrade head` создаёт таблицы, `alembic downgrade -1` откатывает**

---

## 🟢 БЛОК 5: Auth (неделя 4–5)

> Цель: пользователи, JWT, protected routes.

### 5.1 Модель User
- **Создать:** `backend/app/models/user.py`
- **Таблица `users`:** id, email (unique), hashed_password, name, role, is_active, created_at

### 5.2 Auth-сервис
- **Создать:** `backend/app/services/auth.py`
- **Функции:**
  - `hash_password(password: str) -> str` (bcrypt)
  - `verify_password(plain: str, hashed: str) -> bool`
  - `create_access_token(user_id: str) -> str` (JWT, 60 мин)
  - `create_refresh_token(user_id: str) -> str` (JWT, 7 дней)
  - `decode_token(token: str) -> dict` (верификация JWT)
  - `get_current_user(token: str) -> User` (dependency)

### 5.3 Auth API
- **Файл:** `backend/app/api/routes.py` — добавить:
  ```
  POST /api/auth/register  — регистрация
  POST /api/auth/login     — логин → access_token + refresh_token
  POST /api/auth/refresh   — обновление токена
  GET  /api/auth/me         — текущий пользователь
  ```

### 5.4 Protected routes
```python
# Dependency для защищённых эндпоинтов
async def require_user(token: str = Depends(oauth2_scheme)) -> User:
    ...

# Защищённые:
POST /api/saved-searches    → require_user
GET  /api/saved-searches    → require_user
POST /api/admin/scrape      → require_admin
GET  /api/admin/jobs        → require_admin
```

### 5.5 Обновить requirements.txt
```
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.12
```

**⏱ Оценка: 8–10 часов**
**📦 Deliverable: регистрация, логин, JWT, protected routes**

---

## 🟢 БЛОК 6: Ingestion Pipeline (неделя 5–7)

> Цель: рабочие скрейперы, которые реально собирают данные.

### 6.1 Прокси-менеджер
- **Создать:** `backend/app/services/proxy_manager.py`
- **Логика:** Ротация прокси, mark_blocked, cooldown, get_available

### 6.2 Один рабочий скрейпер — DomClick (самый доступный)
- **Файл:** `backend/app/scrapers/domclick_scraper.py`
- **Стратегия:** Direct API (`api.domclick.ru/research/v5/offers`)
- **Реализация:** из `real_scrapers.py` (там рабочая версия)
- **Тест:** Запустить `python -m app.scrapers.domclick_scraper` → получить 10+ объявлений

### 6.3 Нормализатор
- **Создать:** `backend/app/services/normalizer.py`
- **Задачи:**
  - Нормализация цен (всё в RUB)
  - Нормализация адресов (пробелы, регистр)
  - Валидация (пропускать записи без цены/адреса)
  - Извлечение rooms из title если не указано

### 6.4 Пайплайн ingestion
- **Создать:** `backend/app/services/ingestion.py`
- **Функция `ingest_listings(city, source, deal_type)`:**
  1. Скрейпить данные (scraper)
  2. Нормализовать (normalizer)
  3. Дедуплицировать (dedup service)
  4. Записать в БД (INSERT или UPDATE)
  5. Записать price_history если цена изменилась
  6. Логировать результат в scraping_jobs

### 6.5 CLI-скрипт для ручного запуска
- **Создать:** `scripts/scrape.py`
  ```bash
  python scripts/scrape.py --source domclick --city Москва --deal sale --limit 50
  ```

**⏱ Оценка: 12–15 часов**
**📦 Deliverable: DomClick скрейпер собирает реальные данные, пайплайн записывает в БД**

---

## 🟢 БЛОК 7: Elasticsearch (неделя 6–7)

> Цель: полнотекстовый поиск по описаниям.

### 7.1 ES индекс
- **Создать:** `backend/app/services/es_service.py`
- **Mapping:** address (text, russian), description (text, russian), city/price/rooms (keyword/float/integer)
- **Функции:**
  - `create_index()` — создание индекса с mapping
  - `index_listing(listing)` — индексация одного объявления
  - `search(filters, query_text)` — гибридный запрос (bool: filter + must)
  - `bulk_index(listings)` — массовая индексация

### 7.2 Индексация при ingestion
- В `ingestion.py` после записи в PostgreSQL → `es_service.index_listing()`

### 7.3 Поиск через ES
- **Файл:** `backend/app/services/search.py` — обновить
- **Логика:** Если `query_text` не пустой → ES, иначе → PostgreSQL
- **Fallback:** Если ES недоступен → PostgreSQL full-text (`func.lower(Listing.description).contains(...)`)

### 7.4 Индексация seed-данных
- `scripts/seed_data.py` → после записи в PG → bulk_index в ES

**⏱ Оценка: 8–10 часов**
**📦 Deliverable: поиск "свежий ремонт панорамные окна" находит релевантные квартиры**

---

## 🟢 БЛОК 8: Redis кеш (неделя 7)

> Цель: ускорить повторные запросы.

### 8.1 Кеш-сервис
- **Создать:** `backend/app/services/cache.py`
  ```python
  import redis.asyncio as redis
  import json
  
  class CacheService:
      def __init__(self, url: str):
          self.client = redis.from_url(url)
      
      async def get(self, key: str) -> dict | None:
          data = await self.client.get(key)
          return json.loads(data) if data else None
      
      async def set(self, key: str, value: dict, ttl: int = 300):
          await self.client.set(key, json.dumps(value), ex=ttl)
      
      async def invalidate(self, pattern: str):
          keys = await self.client.keys(pattern)
          if keys:
              await self.client.delete(*keys)
  ```

### 8.2 Кеш для аналитики и поиска
- **Аналитика:** TTL 10 минут (дорогой запрос)
- **Поиск:** TTL 5 минут (результаты меняются при ingestion)
- **Stats:** TTL 5 минут
- **Инвалидация:** После ingestion → `invalidate("analytics:*")`, `invalidate("search:*")`

**⏱ Оценка: 3–4 часа**
**📦 Deliverable: повторный `/api/analytics` отдаётся за <5мс из кеша**

---

## 🔵 БЛОК 9: Frontend (неделя 8–9)

> Цель: рабочий UI с фильтрами и API-интеграцией.

### 9.1 API Client
- **Создать:** `frontend/lib/api.ts`
- Обёртка над fetch с auth headers, error handling

### 9.2 TypeScript типы
- **Создать:** `frontend/lib/types.ts`
  ```typescript
  interface Listing {
    id: string;
    source: string;
    property_type: string;
    deal_type: string;
    price: number;
    area_m2: number | null;
    rooms: number | null;
    floor: number | null;
    address: string;
    city: string;
    description: string | null;
    images: string[];
  }
  ```

### 9.3 Компоненты
- `components/chat/ChatWindow.tsx` — окно чата
- `components/chat/SuggestionChips.tsx` — кнопки-подсказки
- `components/listings/ListingCard.tsx` — карточка объявления
- `components/listings/SearchFilters.tsx` — панель фильтров (город, тип, цена, комнаты)
- `components/analytics/StatsCards.tsx` — карточки статистики

### 9.4 Страницы
- `/chat` — AI-чат (основная)
- `/listings` — каталог с фильтрами
- `/listings/[id]` — детальная страница
- `/analytics` — дашборд

**⏱ Оценка: 12–15 часов**
**📦 Deliverable: рабочий UI, чат отвечает, карточки отображаются**

---

## 🔵 БЛОК 10: CI/CD (неделя 9–10)

> Цель: автоматический lint + test при push.

### 10.1 GitHub Actions
- **Создать:** `.github/workflows/ci.yml`
- **Jobs:** lint (ruff) → test (pytest) → build (docker compose build)

### 10.2 Docker production
- **Создать:** `docker-compose.prod.yml`
- Без volume mounts, без `--reload`, с nginx reverse proxy

### 10.3 Monitoring
- **Добавить:** `/metrics` эндпоинт (prometheus_client)
- **Метрики:** request_count, request_latency, scraper_items_total

**⏱ Оценка: 6–8 часов**
**📦 Deliverable: `git push` → автоматический lint + test, `docker-compose.prod.yml` для деплоя**

---

## Сводка

| Блок | Приоритет | Срок | Часы | Deliverable |
|------|-----------|------|------|-------------|
| **0** | 🔴 Критично | Сегодня | 1–2ч | Безопасность |
| **1** | 🟡 Важно | Неделя 1 | 4–6ч | Чистый код |
| **2** | 🟡 Важно | Неделя 1–2 | 3–4ч | Исправленные баги |
| **3** | 🟡 Важно | Неделя 2–3 | 6–8ч | Тесты |
| **4** | 🟡 Важно | Неделя 3 | 2–3ч | Миграции |
| **5** | 🟢 Нужно | Неделя 4–5 | 8–10ч | Auth |
| **6** | 🟢 Нужно | Неделя 5–7 | 12–15ч | Рабочий скрейпинг |
| **7** | 🟢 Нужно | Неделя 6–7 | 8–10ч | Elasticsearch |
| **8** | 🟢 Нужно | Неделя 7 | 3–4ч | Redis кеш |
| **9** | 🔵 Масштаб | Неделя 8–9 | 12–15ч | Frontend |
| **10** | 🔵 Масштаб | Неделя 9–10 | 6–8ч | CI/CD |
| | | **Итого** | **~65–85ч** | |

---

## Что делать прямо сейчас

```
1. Отозвать GitHub PAT                              ← 5 минут
2. Закрыть CORS в main.py и run_local.py            ← 2 минуты
3. DEBUG = False                                     ← 1 минута
4. Убрать str(exc) из error handler                  ← 2 минуты
5. Создать .env.example                              ← 5 минут
6. Удалить real_scrapers.py и production_scrapers.py ← 1 минута
```

Итого: **16 минут** до состояния "можно спать спокойно".
