# Realty Platform — Архитектура

## Обзор

Платформа агрегации недвижимости с AI-агентом для поиска и аналитики.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Источники   │────▶│   Scrapers   │────▶│   PostgreSQL    │
│  (сайты)     │     │  (Scrapy)    │     │   + ES index    │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                    ┌──────────────┐     ┌─────────▼────────┐
                    │   Frontend   │◀───▶│   FastAPI        │
                    │  (Next.js)   │     │   + AI Agent     │
                    └──────────────┘     └──────────────────┘
```

## Стек

- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic
- **Database**: PostgreSQL 15+ (основная) + Elasticsearch 8 (поиск)
- **AI**: sentence-transformers (embeddings) + LangChain (RAG pipeline)
- **Scraping**: Scrapy + httpx
- **Frontend**: Next.js 14 (App Router) + TailwindCSS + shadcn/ui
- **Infra**: Docker Compose

## Data Model

### Listing (объект недвижимости)
```
id              UUID
source          str          # cian, avito, domclick...
source_id       str          # ID на сайте-источнике
source_url      str          # Ссылка на оригинал
property_type   enum         # apartment, house, commercial, land
deal_type       enum         # sale, rent
price           Decimal
currency        str          # RUB, USD, EUR
area_m2         float
rooms           int|None
floor           int|None
floors_total    int|None
address         str
district        str|None
city            str
region          str|None
lat             float|None
lon             float|None
description     text
images          json[]       # URLs
features        json         # {parking, elevator, renovation...}
embedding       vector(384)  # для семантического поиска
created_at      timestamp
updated_at      timestamp
is_active       bool
```

### SearchQuery (история поиска — для рекомендаций)
```
id              UUID
query_text      str
filters         json
results_count   int
created_at      timestamp
```

## AI Agent

Агент понимает естественный язык:
- "2-комнатная квартира рядом с метро до 5 млн" → фильтры + семантический поиск
- "сравни цены на студии в Москве и Питере" → агрегация + сравнение
- "покажи что нового за неделю" → фильтр по дате + рекомендации

Pipeline:
1. NLU → извлечение параметров (rooms, price, location, type)
2. Structured search → PostgreSQL + ES filters
3. Semantic search → cosine similarity на embeddings
4. Reranking → комбинация score'ов
5. Response generation → форматированный ответ
