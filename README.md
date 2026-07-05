# 🏠 Realty Platform — AI Агрегатор Недвижимости

Платформа для агрегации объявлений о недвижимости с разных источников и AI-агентом для поиска, аналитики и рекомендаций.

## Возможности

- 🤖 **AI-агент** — понимает естественный язык ("двушка в Москве до 10 млн")
- 🔍 **Умный поиск** — фильтры + полнотекстовый + семантический
- 📊 **Аналитика** — средние цены, цены за м², сравнение городов
- 🕷️ **Парсинг** — автоматический сбор с ЦИАН, Авито, Домклик
- 📱 **Современный UI** — чат с AI + карточки объявлений

## Стек

| Компонент | Технология |
|-----------|------------|
| Backend | Python 3.11 / FastAPI / SQLAlchemy 2.0 |
| БД | PostgreSQL 15 (основная) + Elasticsearch 8 (поиск) |
| AI | sentence-transformers / NLU pipeline |
| Парсинг | Scrapy + httpx + selectolax |
| Frontend | Next.js 14 / React 18 / TailwindCSS |
| Инфра | Docker Compose |

## Быстрый старт

### 1. Docker (рекомендуется)

```bash
cd realty-platform
docker-compose up -d
```

Сервисы:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Elasticsearch: http://localhost:9200

### 2. Запуск seed-данных

```bash
docker-compose exec backend python scripts/seed_data.py
```

### 3. Локальный запуск (без Docker)

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # настроить DATABASE_URL
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## API

### AI Agent
```bash
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "2-комнатная квартира в Москве до 15 млн"}'
```

### Listings
```bash
curl "http://localhost:8000/api/listings?city=Москва&deal_type=sale&rooms=2"
```

### Analytics
```bash
curl "http://localhost:8000/api/analytics?city=Москва"
```

### Compare Cities
```bash
curl "http://localhost:8000/api/analytics/compare?city1=Москва&city2=Санкт-Петербург"
```

## Архитектура

```
realty-platform/
├── backend/
│   ├── app/
│   │   ├── api/routes.py        # API endpoints
│   │   ├── ai/agent.py          # AI NLU agent
│   │   ├── models/
│   │   │   ├── database.py      # DB connection
│   │   │   └── listing.py       # Listing model
│   │   ├── scrapers/
│   │   │   ├── base.py          # Base scraper
│   │   │   └── cian_scraper.py  # CIAN implementation
│   │   ├── services/
│   │   │   └── search.py        # Search + analytics
│   │   ├── config.py            # Settings
│   │   └── main.py              # FastAPI app
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx           # Root layout
│   │   ├── page.tsx             # Main page (chat + listings)
│   │   └── globals.css          # Styles
│   └── package.json
├── scripts/
│   └── seed_data.py             # Demo data
├── docker-compose.yml
└── README.md
```

## Дорожная карта (MVP → Production)

- [x] Data model + PostgreSQL
- [x] FastAPI backend + endpoints
- [x] AI agent (rule-based NLU)
- [x] Search service (structured + text)
- [x] Frontend (chat + listings)
- [x] CIAN scraper example
- [x] Seed data
- [ ] Elasticsearch integration (full-text + geo)
- [ ] Embeddings (semantic search via sentence-transformers)
- [ ] More scrapers (Avito, DomClick, Яндекс.Недвижимость)
- [ ] Notification system (новые объекты по подписке)
- [ ] User accounts + saved searches
- [ ] Map view (Yandex/Leaflet)
- [ ] Price history + trends
- [ ] LLM integration (GigaChat / local LLM)
