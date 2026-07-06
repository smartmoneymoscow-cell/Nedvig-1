# 🔍 Nedvig-1 — Полный аудит проекта

> Дата: 2026-07-07 | Объём кода: ~60 файлов, ~4500 строк Python, ~800 строк TSX/HTML

---

## 1. Архитектура проекта

### 1.1 Общая схема

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend Layer                         │
│  ┌──────────────────┐  ┌──────────────────────────────┐  │
│  │ Next.js 14 (TSX) │  │ demo/index.html (vanilla JS) │  │
│  │ :3000             │  │ встроенный в backend          │  │
│  └────────┬─────────┘  └──────────────┬───────────────┘  │
│           │                            │                  │
├───────────┼────────────────────────────┼──────────────────┤
│           ▼                            ▼                  │
│  ┌────────────────────────────────────────────────────┐  │
│  │              FastAPI Backend (:8000)                 │  │
│  │                                                     │  │
│  │  ┌──────────┐ ┌──────────┐ ┌─────────────────────┐ │  │
│  │  │ API      │ │ Auth     │ │ AI Agent (NLU)       │ │  │
│  │  │ Routes   │ │ Routes   │ │ rule-based parsing   │ │  │
│  │  └────┬─────┘ └────┬─────┘ └──────────┬──────────┘ │  │
│  │       │             │                  │            │  │
│  │  ┌────▼─────────────▼──────────────────▼─────────┐ │  │
│  │  │           Services Layer                       │ │  │
│  │  │  SearchService | CacheService | AuthService    │ │  │
│  │  │  IngestionPipeline | ProxyManager              │ │  │
│  │  └────────────────────┬───────────────────────────┘ │  │
│  │                       │                             │  │
│  │  ┌────────────────────▼───────────────────────────┐ │  │
│  │  │           Models Layer (SQLAlchemy 2.0)         │ │  │
│  │  │  Listing | User | (PriceHistory в run_local)    │ │  │
│  │  └────────────────────┬───────────────────────────┘ │  │
│  └───────────────────────┼─────────────────────────────┘  │
│                          │                                │
├──────────────────────────┼────────────────────────────────┤
│                    Data Layer                              │
│  ┌───────────┐  ┌───────▼──────┐  ┌──────────────┐       │
│  │ PostgreSQL│  │  SQLite      │  │ Elasticsearch│       │
│  │ (prod)    │  │  (dev/Render)│  │ (unused)     │       │
│  └───────────┘  └──────────────┘  └──────────────┘       │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │              Scrapers Layer                        │    │
│  │  CianScraper | AvitoScraper | DomClickScraper     │    │
│  │  N1Scraper | ScraperRunner                         │    │
│  │  ⚠️ Все заблокированы IP дата-центра              │    │
│  └──────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────┘
```

### 1.2 Точки входа (ПРОБЛЕМА: их две)

| Файл | Строк | Что делает | Статус |
|------|-------|------------|--------|
| `backend/app/main.py` | ~90 | Модульный FastAPI, использует `backend/app/` | ✅ Canonical |
| `run_local.py` | ~948 | Монолитный FastAPI, дублирует ВСЁ | ⚠️ Дубликат |

**Проблема:** `run_local.py` содержит расширенную версию NLU, `PriceHistory`, `ScrapingJob`, `Deduplicator`, `AnalyticsService` — но не импортирует из `backend/app/`. Два разных приложения с разной логикой.

### 1.3 Технологический стек

| Компонент | Технология | Статус |
|-----------|-----------|--------|
| Backend Framework | FastAPI 0.115 | ✅ Работает |
| ORM | SQLAlchemy 2.0 (async) | ✅ Работает |
| Database | SQLite (dev) / PostgreSQL (prod) | ⚠️ Разные схемы |
| Search | Elasticsearch 8 | ❌ Подключён, но не используется |
| Cache | Redis | ❌ Код есть, не используется |
| AI/NLU | Rule-based regex | ✅ Работает, но ограничен |
| Embeddings | sentence-transformers | ❌ В requirements, не используется |
| Auth | JWT (python-jose + passlib) | ✅ Работает |
| Scraping | httpx + selectolax + cloudscraper | ❌ Все заблокированы |
| Frontend | Next.js 14 + TailwindCSS | ✅ Работает |
| Demo | Vanilla HTML/JS | ✅ Работает |
| Migrations | Alembic | ✅ Настроено |
| Containerization | Docker Compose | ✅ Работает |

---

## 2. Микросервисы

### 2.1 Текущее состояние: МОНОЛИТ

Проект **не является** микросервисным. Это монолитный FastAPI-приложение с модульной структурой внутри.

В `REFACTORING_PLAN.md` описан план разделения на 5 сервисов:
- **Gateway** (Kong) — роутинг, rate-limit, auth
- **Core API** — listings, analytics, search
- **Agent API** — NLU, чат
- **Ingestion** — скрейперы, нормализация
- **Auth** — пользователи, JWT

**Статус:** План существует, реализация = 0%.

### 2.2 Рекомендация

Для текущего масштаба (MVP, ~28 seed-записей) микросервисы — overengineering. Достаточно:
1. Один монолитный backend с чёткой модульной структурой
2. Отдельный worker для скрейпинга (background task или Celery)
3. Frontend как отдельный сервис (уже так и есть)

---

## 3. Скрайберы (Scrapers)

### 3.1 Реестр скрейперов

| Скрейпер | Файл | Источник | Статус |
|----------|------|----------|--------|
| `CianScraper` | `cian_scraper.py` | ЦИАН API | ❌ Cloudflare WAF блокирует |
| `AvitoScraper` | `avito_scraper.py` | Avito HTML | ❌ IP заблокирован |
| `DomClickScraper` | `domclick_scraper.py` | DomClick API | ❌ IP не из РФ / дата-центр |
| `N1Scraper` | `n1_scraper.py` | N1.ru HTML | ❌ IP заблокирован |

### 3.2 Архитектура скрейпинга

```
ScraperRunner.scrape_city()
    ├── DomClickScraper(proxy) ──→ asyncio.create_task()
    ├── CianScraper(proxy)    ──→ asyncio.create_task()
    ├── AvitoScraper(proxy)   ──→ asyncio.create_task()
    └── N1Scraper(proxy)      ──→ asyncio.create_task()
                                        │
                              ┌─────────▼──────────┐
                              │  _deduplicate()     │
                              │  source+id hash     │
                              │  content hash       │
                              └─────────┬──────────┘
                                        │
                              ┌─────────▼──────────┐
                              │  IngestionPipeline  │
                              │  normalize → validate│
                              │  → upsert to DB     │
                              └────────────────────┘
```

### 3.3 Проблемы скрейперов

1. **IP блокировка** — все сайты блокируют IP дата-центров. Нужны резидентные прокси ($50-100/мес)
2. **Нет retry логики** — при ошибке скрейпер просто пропускает страницу
3. **Нет мониторинга** — нет логирования успешных/неудачных запросов
4. **Нет rate limiting** — между запросами фиксированная задержка, нет адаптивной
5. **CianScraper использует cloudscraper** (синхронный) — работает через `run_in_executor`, но это костыль
6. **AvitoScraper** — HTML-парсинг через CSS-селекторы, которые могут измениться в любой момент
7. **ProxyManager** — код есть, но не интегрирован со скрейперами (ScraperRunner передаёт прокси, но скрейперы не используют их последовательно)

---

## 4. Ошибки и избыточности кода

### 4.1 Критическое дублирование

| Что | Где дублируется | Строк | Проблема |
|-----|-----------------|-------|----------|
| Listing model | `backend/app/models/listing.py` + `run_local.py` | 60 + 80 | Разные схемы (Enum vs String, Numeric vs Float) |
| NLU Agent | `backend/app/ai/agent.py` + `run_local.py` | 180 + 120 | `run_local.py` имеет расширенные паттерны |
| SearchService | `backend/app/services/search.py` + `run_local.py` | 120 + 60 | `run_local.py` не использует ES |
| Deduplicator | `backend/app/services/ingestion.py` + `run_local.py` | 40 + 30 | Разные поля (source_hash vs hash) |
| AnalyticsService | `run_local.py` | 60 | Не вынесен в `backend/app/services/` |
| Seed data | `scripts/seed_data.py` + `run_local.py` | 80 + 100 | Разные наборы данных |
| City aliases | `backend/app/ai/agent.py` + `run_local.py` | 30 + 30 | Идентичны, но скопированы |
| Price patterns | `backend/app/ai/agent.py` + `run_local.py` | 20 + 20 | Дублированы |

**Итого: ~800 строк дублированного кода.**

### 4.2 Конкретные ошибки в коде

#### Ошибка 1: Несовпадение модели Listing

```python
# backend/app/models/listing.py — ИСПОЛЬЗУЕТ Enum
property_type: Mapped[PropertyType] = mapped_column(
    Enum(PropertyType, values_callable=lambda x: [e.value for e in x])
)
price: Mapped[float] = mapped_column(Numeric(15, 2))

# run_local.py — ИСПОЛЬЗУЕТ String/Float
property_type: Mapped[str] = mapped_column(String(20))
price: Mapped[float] = mapped_column(Float)
```

**Последствие:** Данные, записанные через `run_local.py`, несовместимы с `backend/app/`.

#### Ошибка 2: IngestionPipeline создаёт несуществующие поля

```python
# backend/app/services/ingestion.py, строка ~100
listing = Listing(
    source_hash=source_hash,        # ❌ Нет в модели Listing (backend/app/)
    price_per_m2=...,               # ❌ Нет в модели Listing (backend/app/)
    title=...,                      # ❌ Нет в модели Listing (backend/app/)
)
```

Модель `Listing` в `backend/app/models/listing.py` не имеет полей `source_hash`, `price_per_m2`, `title`.

#### Ошибка 3: SearchService.close() — no-op

```python
# backend/app/services/search.py
async def close(self):
    """No-op — singleton ES client stays open."""
    pass
```

При этом в `routes.py`:
```python
finally:
    await search.close()  # Вызывается на каждый запрос, но ничего не делает
```

#### Ошибка 4: Потенциальная SQL-инъекция через city name

```python
# backend/app/services/search.py
if filters.district:
    query = query.where(func.lower(Listing.district).contains(filters.district.lower()))
```

`contains()` в SQLAlchemy безопасен (параметризованный запрос), но `func.lower()` + `contains()` может вести себя неожиданно с Unicode.

#### Ошибка 5: Деление на ноль в аналитике

```python
# run_local.py, AnalyticsService
"avg_price_per_m2": sum(per_m2) / len(per_m2) if per_m2 else 0,
```

Если `per_m2` пуст — вернёт 0, но если `area_m2 = 0` — будет `ZeroDivisionError` при вычислении `price / area_m2`.

#### Ошибка 6: Неправильный парсинг цены в NLU

```python
# backend/app/ai/agent.py
m = re.search(r"от\s+(\d+[\d\s]*)\s*до\s*(\d+[\d\s]*)\s*(тыс|млн|руб)", text_lower)
```

Паттерн `(тыс|млн|руб)` не матчит "рублей", "руб", "тысяч". Запрос "от 5 до 10 рублей" не распарсится.

#### Ошибка 7: Демо-файл хардкодит API URL

```html
<!-- demo/index.html -->
<script>
const API = 'http://localhost:8001';  // ← Захардкожен порт 8001
```

А `backend/app/main.py` слушает порт 8000. Демо не подключится к backend без ручного изменения.

---

## 5. Архитектурные проблемы

### 5.1 Две точки входа — два «истинных» источника

`run_local.py` (948 строк) и `backend/app/main.py` (90 строк) — это **два разных приложения** с разной логикой, разными моделями, разными NLU-агентами. Это главная архитектурная проблема проекта.

**Решение:** Выбрать одно. Рекомендую `backend/app/` как canonical, перенести недостающие фичи из `run_local.py`, удалить `run_local.py`.

### 5.2 Elasticsearch подключён, но не используется

В `config.py` есть `ES_URL`, в `requirements.txt` есть `elasticsearch`, в `search.py` есть `get_es_client()` — но **ни один эндпоинт не использует ES**. SearchService делает всё через PostgreSQL.

**Решение:** Либо реально интегрировать ES (full-text поиск по описаниям), либо удалить все ES-зависимости.

### 5.3 Redis кеш — код есть, не используется

`CacheService` в `backend/app/services/cache.py` — полная реализация с TTL, invalidate_pattern и т.д. Но **ни один эндпоинт не вызывает CacheService**.

**Решение:** Либо интегрировать (кешировать аналитику, результаты поиска), либо удалить.

### 5.4 Нет background worker для скрейпинга

Скрейпинг запускается через `POST /api/admin/scrape` — синхронно, блокирует HTTP-запрос. Для production нужен фоновый worker (Celery, APScheduler, или хотя бы `asyncio.create_task`).

### 5.5 Нет очереди сообщений

Для ingestion pipeline нужна очередь (RabbitMQ, Redis Queue, или хотя бы SQLite-based job queue). Сейчас — синхронный вызов.

### 5.6 Два фронтенда

| Файл | Тип | Где запускается |
|------|-----|-----------------|
| `frontend/app/page.tsx` | Next.js 14 (React) | `:3000` |
| `demo/index.html` | Vanilla HTML/JS | Встроен в backend (`/`) |

Два фронтенда с одинаковой функциональностью — избыточность.

---

## 6. Риски безопасности

### 6.1 КРИТИЧЕСКИЕ

| # | Уязвимость | Файл | Описание |
|---|-----------|------|----------|
| **S1** | CORS `allow_origins=["*"]` | `run_local.py:487` | Любой сайт может делать запросы к API |
| **S2** | `DEBUG = True` в production | `run_local.py:19` | Error handler отдаёт `str(exc)` — утечка внутренних деталей |
| **S3** | Хардкоженный `SECRET_KEY` | `config.py:14` | `"change-me-in-production"` — можно подделать JWT |
| **S4** | Нет rate limiting | все routes | Можно DDoSить API и AI-агент |
| **S5** | Admin-эндпоинты без auth | `routes.py:130` | `/api/admin/scrape` доступен без аутентификации |
| **S6** | Пароль в docker-compose | `docker-compose.yml:8` | `${POSTGRES_PASSWORD}` не замаскирован |

### 6.2 ВЫСОКИЕ

| # | Уязвимость | Файл | Описание |
|---|-----------|------|----------|
| **S7** | Нет валидации входных данных | `routes.py:30` | `body: dict` вместо Pydantic-схем |
| **S8** | Нет авторизации на listings | `routes.py` | Все listings публичные, включая source_url |
| **S9** | Нет HTTPS | `docker-compose.yml` | Трафик между сервисами не шифруется |
| **S10** | Нет CSP headers | `main.py` | Нет Content-Security-Policy |

### 6.3 СРЕДНИЕ

| # | Уязвимость | Описание |
|---|-----------|----------|
| **S11** | Нет лимита на размер ответа | `/api/listings?limit=200` может вернуть много данных |
| **S12** | Нет аудита действий | Нет логирования кто что искал |
| **S13** | JWT без blacklist | Нельзя отозвать токен до истечения |

### 6.4 План решения

```
Немедленно (сегодня):
  1. Заменить CORS на конкретные origins
  2. DEBUG = False
  3. Сгенерировать случайный SECRET_KEY
  4. Добавить Depends(require_admin) на /api/admin/*

На этой неделе:
  5. Добавить slowapi (rate limiting)
  6. Заменить body: dict на Pydantic-схемы
  7. Добавить HTTPS (nginx reverse proxy или Render TLS)

В ближайший спринт:
  8. Redis-based JWT blacklist
  9. CSP headers
  10. Аудит-лог
```

---

## 7. Баги в коде

### 7.1 Критические

| # | Баг | Файл | Строка | Описание |
|---|-----|------|--------|----------|
| **B1** | Несовпадение моделей | `models/listing.py` vs `run_local.py` | - | Разные типы полей (Enum vs String) |
| **B2** | IngestionPipeline → несуществующие поля | `services/ingestion.py` | ~100 | `source_hash`, `price_per_m2`, `title` отсутствуют в Listing |
| **B3** | Деление на ноль | `run_local.py` | AnalyticsService | `price / area_m2` когда `area_m2 = 0` |
| **B4** | Stats считает все listings | `routes.py` /stats | ~160 | Нет фильтра `is_active == True` (проверено — есть, но дублировано) |

### 7.2 Средние

| # | Баг | Описание |
|---|-----|----------|
| **B5** | `created_at` как String в `run_local.py` | Должен быть `DateTime(timezone=True)` |
| **B6** | `images` как String в `run_local.py` | `str(item.images)` вместо `json.dumps()` |
| **B7** | `features` как String в `run_local.py` | Аналогично |
| **B8** | Demo API URL = `localhost:8001` | Backend слушает `8000` |
| **B9** | Нет валидации UUID в `get_listing` | `UUID(listing_id)` без try/except → 500 вместо 400 |
| **B10** | `rooms_min=rooms_max` при парсинге | "двушка" → rooms_min=2, rooms_max=2 (ищет только точно 2 комнаты) |

### 7.3 Минорные

| # | Баг | Описание |
|---|-----|----------|
| **B11** | PRICE_PATTERNS не используется | В `agent.py` определён, но парсинг идёт через отдельные regex |
| **B12** | `format_price` не форматирует тыс. | `18500000` → `18 500 000 ₽` вместо `18,5 млн ₽` |
| **B13** | `embedding: JSON` в миграции | Должен быть `Vector(384)` для pgvector |

---

## 8. Покрытие тестами

### 8.1 Существующие тесты

| Файл | Тестов | Что тестирует |
|------|--------|---------------|
| `test_nlu.py` | ~35 | NLU: комнаты, цена, город, тип, deal, action, area, combo |
| `test_api.py` | ~12 | API: root, health, listings, agent chat, analytics, stats |
| `conftest.py` | - | Fixtures: SQLite test DB, async client |

### 8.2 Что покрыто ✅

- NLU парсинг: комнаты (0-5), цена (млн/тыс/raw), города (алиасы), тип недвижимости, тип сделки, action detection, площадь, комбинированные запросы
- API: GET/POST эндпоинты, пустые ответы, фильтрация, пагинация, 404

### 8.3 Что НЕ покрыто ❌

| Область | Пробел |
|---------|--------|
| **Auth** | 0 тестов для register/login/refresh/me |
| **Scrapers** | 0 тестов (ни unit, ни integration) |
| **IngestionPipeline** | 0 тестов |
| **Deduplicator** | 0 тестов |
| **SearchService** | 0 тестов (ES fallback, фильтры) |
| **CacheService** | 0 тестов |
| **ProxyManager** | 0 тестов |
| **Error handling** | Нет тестов на 500, 400, 422 |
| **Edge cases** | Нет тестов на пустой город, отрицательную цену, SQL-инъекцию |
| **Performance** | Нет нагрузочных тестов |
| **E2E** | Нет полных сценариев (зарегистрировался → поискал → сохранил) |

### 8.4 Оценка покрытия

```
NLU Agent:        ████████░░  80%  (хорошо)
API Endpoints:    ████░░░░░░  40%  (слабо)
Auth:             ░░░░░░░░░░   0%  (нет)
Scrapers:         ░░░░░░░░░░   0%  (нет)
Services:         ██░░░░░░░░  15%  (минимально)
Overall:          ███░░░░░░░  ~30%
```

---

## 9. UX веб-интерфейса

### 9.1 Два фронтенда

| | Next.js (`frontend/`) | Demo (`demo/index.html`) |
|---|---|---|
| Страницы | 1 (chat + listings) | 3 (chat, listings, analytics) |
| Стилизация | TailwindCSS | Custom CSS |
| Чат | ✅ | ✅ |
| Listings grid | ✅ | ✅ |
| Аналитика | ❌ | ✅ |
| Фильтры | Базовые | Базовые |
| Мобильная версия | ❌ | Адаптивная (media queries) |
| Детальная страница | ❌ | ❌ |
| Карта | ❌ | ❌ |
| Авторизация | ❌ | ❌ |

### 9.2 Что хорошо 👍

1. **AI-чат** — интуитивный ввод на естественном языке
2. **Подсказки** (suggestion chips) — быстрый старт
3. **Карточки объявлений** — чистый дизайн с ценой, метражом, адресом
4. **Аналитика** — статистика по городам с визуализацией
5. **Современный CSS** — градиенты, тени, скругления, анимации

### 9.3 Что плохо 👎

1. **Нет детальной страницы объявления** — карточка ведёт на `source_url` (внешний сайт)
2. **Нет карты** — для недвижимости это критично (Яндекс.Карты / Leaflet)
3. **Нет фильтра по цене (range slider)** — только через AI-чат
4. **Нет фильтра по площади** — только через AI-чат
5. **Нет сортировки** — только через AI-чат
6. **Нет пагинации в UI** — infinite scroll или "показать ещё"
7. **Нет истории поиска** — при перезагрузке всё теряется
8. **Нет избранного** — нельзя сохранить объявление
9. **Нет сравнения** — нельзя выбрать 2-3 объекта и сравнить
10. **Нет уведомлений** — о новых объявлениях по подписке
11. **Нет авторизации в UI** — кнопки login/register отсутствуют
12. **Плохой mobile UX** — sidebar занимает 260px, на телефоне не работает
13. **Нет loading skeleton** — только "⏳ Ищу..."
14. **Нет error states** — при ошибке просто текст
15. **Нет dark mode** — только светлая тема

### 9.4 Как сделать лучше

#### Немедленно (MVP fix)
1. Сделать sidebar сворачиваемым на мобильных
2. Добавить loading skeleton для карточек
3. Добавить error boundary с кнопкой "повторить"
4. Добавить фильтры (город, тип, цена range, комнаты) в listings view
5. Добавить "Показать ещё" кнопку

#### На этой неделе
6. Детальная страница `/listings/[id]` с галереей фото
7. Интеграция Яндекс.Карт для отображения на карте
8. Фильтры с range slider для цены и площади
9. Infinite scroll или пагинация
10. Сохранение поиска в localStorage

#### В ближайший спринт
11. Авторизация (login/register forms)
12. Избранное (сохранённые объявления)
13. Сравнение объектов (2-3 квартиры side-by-side)
14. Push-уведомления о новых объявлениях
15. Dark mode

### 9.5 Референсы для интерфейса

| Сервис | Что взять | Ссылка |
|--------|-----------|--------|
| **CIAN** | Фильтры, карта, карточки, UX поиска | cian.ru |
| **Авито** | Grid layout, фильтры, мобильный UI | avito.ru |
| **DomClick** | Карта + список, ипотечный калькулятор | domclick.ru |
| **Яндекс.Недвижимость** | AI-подбор, карта, аналитика | realty.ya.ru |
| **Rightmove** (UK) | Чистый UI, карта, saved searches | rightmove.co.uk |
| **Zillow** (US) | Zestimate (AI-оценка), карта, тренды цен | zillow.com |
| **Redfin** (US) | Современный UI, данные в реальном времени | redfin.com |

**Главный референс:** CIAN + Яндекс.Недвижимость — лучшие UX для российского рынка.

---

## 10. Деплой на Render

### 10.1 Проблема

Пользователь сообщает, что деплой на `https://dashboard.render.com/project/prj-d95prt28qa3s7390kddg` вызвал ошибки.

### 10.2 Анализ возможных причин

#### Проблема 1: Нет `render.yaml` или `Dockerfile` для Render

Render требует конфигурацию. В репозитории:
- `backend/Dockerfile` — есть ✅
- `frontend/Dockerfile` — есть ✅
- `render.yaml` — **нет** ❌
- `Procfile` — **нет** ❌

#### Проблема 2: Backend не запускается без PostgreSQL

`config.py` по умолчанию использует SQLite:
```python
DATABASE_URL: str = "sqlite+aiosqlite:///./realty.db"
```

На Render нет SQLite (ephemeral filesystem). Нужен PostgreSQL.

#### Проблема 3: Alembic миграции не запускаются

`backend/app/main.py` вызывает `init_db()` (create_all), но миграции не применяются автоматически.

#### Проблема 4: Порт

Render использует переменную `PORT`. `uvicorn` по умолчанию слушает 8000, но Render может ожидать другой порт.

#### Проблема 5: Зависимости

`requirements.txt` включает `sentence-transformers` и `numpy` — тяжёлые пакеты, могут не установиться на бесплатном тарифе Render (512MB RAM).

#### Проблема 6: Redis и ES недоступны

На бесплатном Render нет Redis и Elasticsearch. Код `search.py` и `cache.py` пытаются подключиться и падают.

### 10.3 План запуска на Render

#### Шаг 1: Создать `render.yaml`

```yaml
services:
  - type: web
    name: nedvig-backend
    runtime: python
    region: frankfurt
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: nedvig-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: DEBUG
        value: "false"
      - key: CORS_ORIGINS
        value: "https://nedvig-frontend.onrender.com"
      - key: ES_URL
        value: ""  # отключить ES
      - key: REDIS_URL
        value: ""  # отключить Redis
    healthCheckPath: /api/health

databases:
  - name: nedvig-db
    plan: free
    databaseName: realty_db
    user: realty
```

#### Шаг 2: Исправить код для работы без ES/Redis

В `backend/app/services/search.py` — ES клиент должен быть опциональным:
```python
def get_es_client():
    if not settings.ES_URL:
        return None
    # ... existing code
```

В `backend/app/services/cache.py` — Redis должен быть опциональным:
```python
def get_redis():
    if not settings.REDIS_URL:
        return None
    # ... existing code
```

#### Шаг 3: Убрать тяжёлые зависимости для Render free

`requirements.txt` — вынести AI-зависимости в опциональные:
```
# Core (обязательные)
fastapi==0.115.0
uvicorn==0.30.0
sqlalchemy==2.0.35
asyncpg==0.29.0
pydantic==2.9.0
pydantic-settings==2.5.0

# AI (опциональные, для Render free — закомментировать)
# sentence-transformers==3.1.0
# numpy==1.26.4
```

#### Шаг 4: Обновить Dockerfile для Render

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render передаёт PORT через env
EXPOSE $PORT

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

#### Шаг 5: Добавить health check

Убедиться, что `/api/health` работает без Redis/ES:
```python
@app.get("/api/health")
async def health():
    checks = {"status": "ok"}
    # DB check — обязательно
    # Redis check — опционально (unavailable, не error)
    # ES check — опционально (unavailable, не error)
    return checks
```

### 10.4 Быстрый старт (минимальный деплой)

```bash
# 1. Создать PostgreSQL database на Render (free tier)
# 2. Создать Web Service:
#    - Runtime: Python
#    - Build: pip install -r requirements.txt
#    - Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
#    - Env vars: DATABASE_URL, SECRET_KEY, DEBUG=false
# 3. Деплоить
```

---

## Сводная таблица приоритетов

| # | Задача | Приоритет | Время |
|---|--------|-----------|-------|
| 1 | Удалить `run_local.py`, оставить `backend/app/` | 🔴 Критично | 2ч |
| 2 | Закрыть CORS, DEBUG=False, SECRET_KEY | 🔴 Критично | 30мин |
| 3 | Добавить auth на admin-эндпоинты | 🔴 Критично | 1ч |
| 4 | Исправить модели (source_hash, price_per_m2) | 🔴 Критично | 2ч |
| 5 | Создать render.yaml + исправить для Render | 🟡 Важно | 3ч |
| 6 | Добавить тесты auth + scrapers | 🟡 Важно | 6ч |
| 7 | Убрать ES/Redis код или интегрировать | 🟡 Важно | 4ч |
| 8 | Детальная страница listing | 🟡 Важно | 4ч |
| 9 | Фильтры в UI (range sliders) | 🟡 Важно | 6ч |
| 10 | Мобильная адаптация | 🟡 Важно | 4ч |
| 11 | Карта (Яндекс/Leaflet) | 🟢 Нужно | 8ч |
| 12 | Rate limiting | 🟢 Нужно | 2ч |
| 13 | Background worker для скрейпинга | 🟢 Нужно | 6ч |
| 14 | Рабочие скрейперы (прокси) | 🟢 Нужно | 12ч |
| 15 | Избранное + сравнение | 🔵 Масштаб | 8ч |

---

## Итого

**Сильные стороны:**
- Хорошая модульная структура backend
- Рабочий NLU с распознаванием русского языка
- Красивый demo UI
- Docker Compose для локальной разработки
- Alembic миграции

**Слабые стороны:**
- Дублирование кода (~800 строк)
- Скрейперы не работают (IP блокировка)
- ES и Redis подключены, но не используются
- Нет тестов для auth, scrapers, services
- Два фронтенда вместо одного
- Несколько критических уязвимостей безопасности

**Общая оценка: 6/10** — хороший MVP, но требует значительной доработки перед production.
