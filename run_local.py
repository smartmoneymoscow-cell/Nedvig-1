"""
Realty AI Platform — Production Backend
FastAPI + SQLite + AI Agent + Scrapers
"""

import uuid
import json
import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, select, func, desc, asc, or_, and_
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

DB_URL = "sqlite+aiosqlite:///./realty.db"
DEBUG = True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("realty")


# ═══════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════

engine = create_async_engine(DB_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class PropertyType(str, Enum):
    apartment = "apartment"
    house = "house"
    commercial = "commercial"
    land = "land"
    room = "room"
    studio = "studio"


class DealType(str, Enum):
    sale = "sale"
    rent = "rent"


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[str] = mapped_column(String(50), index=True)
    source_id: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(500))
    source_hash: Mapped[str] = mapped_column(String(64), index=True)

    property_type: Mapped[str] = mapped_column(String(20), index=True)
    deal_type: Mapped[str] = mapped_column(String(10), index=True)

    price: Mapped[float] = mapped_column(Float, index=True)
    price_per_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")

    area_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    floor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    floors_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    address: Mapped[str] = mapped_column(String(500))
    district: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    city: Mapped[str] = mapped_column(String(100), index=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    metro_station: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    metro_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    images: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    features: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    author_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[str] = mapped_column(String(30), default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Mapped[str] = mapped_column(String(30), default=lambda: datetime.now(timezone.utc).isoformat())
    scraped_at: Mapped[str] = mapped_column(String(30), default=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "source_url": self.source_url,
            "property_type": self.property_type,
            "deal_type": self.deal_type,
            "price": self.price,
            "price_per_m2": self.price_per_m2,
            "currency": self.currency,
            "area_m2": self.area_m2,
            "rooms": self.rooms,
            "floor": self.floor,
            "floors_total": self.floors_total,
            "address": self.address,
            "district": self.district,
            "city": self.city,
            "lat": self.lat,
            "lon": self.lon,
            "metro_station": self.metro_station,
            "metro_minutes": self.metro_minutes,
            "title": self.title,
            "description": self.description,
            "images": json.loads(self.images) if self.images else [],
            "features": json.loads(self.features) if self.features else {},
            "author_type": self.author_type,
            "created_at": self.created_at,
            "is_active": self.is_active,
        }


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id: Mapped[str] = mapped_column(String(36), index=True)
    price: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[str] = mapped_column(String(30), default=lambda: datetime.now(timezone.utc).isoformat())


class ScrapingJob(Base):
    __tablename__ = "scraping_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[str] = mapped_column(String(50))
    city: Mapped[str] = mapped_column(String(100))
    deal_type: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    finished_at: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[str] = mapped_column(String(30), default=lambda: datetime.now(timezone.utc).isoformat())


# ═══════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════

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

class StatsResponse(BaseModel):
    total: int
    by_city: dict
    by_source: dict
    by_type: dict
    by_deal: dict

class HealthResponse(BaseModel):
    status: str
    version: str
    uptime: float
    listings_count: int


# ═══════════════════════════════════════════════════════════════
# AI AGENT — Natural Language Understanding
# ═══════════════════════════════════════════════════════════════

ROOM_PATTERNS = [
    (r"(\d)\s*[-–]?\s*комн", lambda m: int(m.group(1))),
    (r"(\d)\s*[-–]?\s*к\b", lambda m: int(m.group(1))),
    (r"студия|студи", lambda m: 0),
    (r"однушк", lambda m: 1),
    (r"двушк", lambda m: 2),
    (r"трёшк|трешк", lambda m: 3),
    (r"четыр", lambda m: 4),
    (r"пят", lambda m: 5),
]

CITY_ALIASES = {
    "москва": "Москва", "москве": "Москва", "москвы": "Москва", "мск": "Москва",
    "питер": "Санкт-Петербург", "спб": "Санкт-Петербург", "петербург": "Санкт-Петербург",
    "петербурге": "Санкт-Петербург", "петербурга": "Санкт-Петербург",
    "новосибирск": "Новосибирск", "новосибирске": "Новосибирск", "нск": "Новосибирск",
    "екатеринбург": "Екатеринбург", "екатеринбурге": "Екатеринбург", "екб": "Екатеринбург",
    "казань": "Казань", "краснодар": "Краснодар", "краснодаре": "Краснодар",
    "сочи": "Сочи", "владивосток": "Владивосток", "самара": "Самара",
    "уфа": "Уфа", "тюмень": "Тюмень", "ростов": "Ростов-на-Дону",
    "воронеж": "Воронеж", "пермь": "Пермь", "красноярск": "Красноярск",
}

PTYPE_KW = {
    "квартир": "apartment", "комнат": "apartment", "комната": "apartment",
    "студия": "studio", "студи": "studio",
    "дом": "house", "коттедж": "house", "таунхаус": "house", "дача": "house",
    "земля": "land", "участок": "land", "соток": "land",
    "коммерческ": "commercial", "офис": "commercial", "магазин": "commercial",
    "склад": "commercial", "торгов": "commercial",
    "комната": "room", "комнату": "room",
}

DEAL_KW = {
    "аренда": "rent", "снять": "rent", "сниму": "rent", "арендовать": "rent",
    "сдаётся": "rent", "сдается": "rent",
    "продажа": "sale", "купить": "sale", "куплю": "sale", "прода": "sale",
    "покупка": "sale",
}


class NLUAgent:
    """Natural Language Understanding for real estate queries."""

    def parse(self, text: str) -> dict:
        ql = text.lower().strip()
        f = {}

        # Detect action
        if re.search(r"сравн|разниц|сопостав", ql):
            f["action"] = "compare"
        elif re.search(r"аналитик|статистик|средн|динамик|тренд|цены на", ql):
            f["action"] = "analytics"
        elif re.search(r"рекоменд|подбер|посовет|что нового|новинк", ql):
            f["action"] = "recommend"
        elif re.search(r"сколько|количеств|объявлен", ql):
            f["action"] = "stats"
        else:
            f["action"] = "search"

        # Property type
        for kw, pt in PTYPE_KW.items():
            if kw in ql:
                f["property_type"] = pt
                break

        # Deal type
        for kw, dt in DEAL_KW.items():
            if kw in ql:
                f["deal_type"] = dt
                break

        # Rooms
        for pat, ext in ROOM_PATTERNS:
            m = re.search(pat, ql)
            if m:
                f["rooms"] = ext(m)
                break

        # Price — multiple patterns
        # "от 5 до 10 млн"
        m = re.search(r"от\s+(\d+[\d\s]*)\s*(?:до)\s*(\d+[\d\s]*)\s*(тыс|млн|руб)", ql)
        if m:
            f["price_min"] = self._parse_price(m.group(1), m.group(3))
            f["price_max"] = self._parse_price(m.group(2), m.group(3))
        else:
            # "до 10 млн"
            m = re.search(r"до\s+(\d+[\d\s]*)\s*(тыс|млн|руб)", ql)
            if m:
                f["price_max"] = self._parse_price(m.group(1), m.group(2))
            else:
                # "10 млн" (without до)
                m = re.search(r"(\d+)\s*млн", ql)
                if m and "от" not in ql:
                    f["price_max"] = int(m.group(1)) * 1_000_000
                else:
                    # "до 5000000"
                    m = re.search(r"до\s+(\d{4,})", ql)
                    if m:
                        f["price_max"] = int(m.group(1))

        # Area
        m = re.search(r"от\s+(\d+)\s*м[²2]", ql)
        if m:
            f["area_min"] = float(m.group(1))
        m = re.search(r"до\s+(\d+)\s*м[²2]", ql)
        if m:
            f["area_max"] = float(m.group(1))

        # Floor
        m = re.search(r"(\d+)\s*этаж", ql)
        if m:
            f["floor_min"] = int(m.group(1))
            f["floor_max"] = int(m.group(1))

        # City
        for alias, city in sorted(CITY_ALIASES.items(), key=lambda x: -len(x[0])):
            if alias in ql:
                f["city"] = city
                break

        # District
        m = re.search(r"(\w+)\s+район", ql)
        if m:
            f["district"] = m.group(1)

        # Metro
        m = re.search(r"(?:метро|рядом с метро|у метро)\s+(\w+)", ql)
        if m:
            f["metro"] = m.group(1)

        # Sorting
        if re.search(r"дешев|самая маленькая цен|подешевле", ql):
            f["sort_by"] = "price"
            f["sort_order"] = "asc"
        elif re.search(r"дорог|самая большая цен|подороже", ql):
            f["sort_by"] = "price"
            f["sort_order"] = "desc"
        elif re.search(r"нов|последн|свеж", ql):
            f["sort_by"] = "created_at"
            f["sort_order"] = "desc"
        elif re.search(r"площад|больше метр|просторн", ql):
            f["sort_by"] = "area_m2"
            f["sort_order"] = "desc"

        return f

    def _parse_price(self, value: str, unit: str) -> float:
        num = float(value.replace(" ", "").replace(",", "."))
        if "млн" in unit:
            return num * 1_000_000
        elif "тыс" in unit:
            return num * 1_000
        return num

    def format_response(self, action: str, data: dict, filters: dict) -> str:
        if action == "search" or action == "recommend":
            return self._format_search(data, filters)
        elif action == "analytics":
            return self._format_analytics(data)
        elif action == "compare":
            return self._format_compare(data)
        elif action == "stats":
            return self._format_stats(data)
        return str(data)

    def _format_search(self, data: dict, filters: dict) -> str:
        items = data.get("items", [])
        total = data.get("total", 0)

        if not items:
            return "😕 Ничего не найдено. Попробуйте изменить параметры поиска."

        lines = [f"🏠 Найдено **{total}** объявлений:\n"]
        for i, item in enumerate(items[:10], 1):
            price = f"{item['price']:,.0f} ₽".replace(",", " ")
            if item.get("deal_type") == "rent":
                price += "/мес"

            rooms_str = "Студия" if item.get("property_type") == "studio" else (
                f"{item['rooms']}к" if item.get("rooms") is not None else item.get("property_type", "")
            )
            area = f", {item['area_m2']}м²" if item.get("area_m2") else ""
            floor = f", этаж {item['floor']}/{item['floors_total']}" if item.get("floor") else ""
            metro = f", 🚇 {item['metro_station']}" if item.get("metro_station") else ""

            lines.append(f"**{i}.** {rooms_str}{area}{floor} — **{price}**")
            lines.append(f"   📍 {item.get('city', '')}, {item.get('address', '')}{metro}")

        if total > 10:
            lines.append(f"\n... и ещё {total - 10} объявлений. Уточните запрос для сужения.")

        return "\n".join(lines)

    def _format_analytics(self, data: dict) -> str:
        analytics = data.get("analytics", [])
        city = data.get("city", "все города")

        if not analytics:
            return "📊 Нет данных для аналитики."

        lines = [f"📊 **Аналитика по {city or 'всем городам'}:**\n"]

        for item in analytics:
            deal = "Продажа" if item["deal_type"] == "sale" else "Аренда"
            ptype = item.get("property_type", "—")
            count = item.get("count", 0)
            avg = f"{item['avg_price']:,.0f}".replace(",", " ") if item.get("avg_price") else "—"
            per_m2 = f"{item['avg_price_per_m2']:,.0f}".replace(",", " ") if item.get("avg_price_per_m2") else "—"

            lines.append(f"**{deal} / {ptype}** ({count} шт.)")
            lines.append(f"  Средняя цена: {avg} ₽")
            lines.append(f"  За м²: {per_m2} ₽")
            if item.get("min_price") and item.get("max_price"):
                lines.append(f"  Диапазон: {item['min_price']:,.0f} – {item['max_price']:,.0f} ₽".replace(",", " "))
            lines.append("")

        return "\n".join(lines)

    def _format_compare(self, data: dict) -> str:
        comparison = data.get("comparison", {})
        if not comparison:
            return "📊 Нет данных для сравнения."

        lines = ["📊 **Сравнение:**\n"]
        for city, info in comparison.items():
            lines.append(f"**{city}** — {info.get('total', 0)} объявлений")
            for a in info.get("analytics", []):
                avg = f"{a['avg_price']:,.0f}".replace(",", " ") if a.get("avg_price") else "—"
                per_m2 = f"{a['avg_price_per_m2']:,.0f}".replace(",", " ") if a.get("avg_price_per_m2") else "—"
                lines.append(f"  {a.get('property_type', '—')}: ср. {avg} ₽ ({per_m2} ₽/м²)")
            lines.append("")

        return "\n".join(lines)

    def _format_stats(self, data: dict) -> str:
        total = data.get("total", 0)
        by_city = data.get("by_city", {})
        by_source = data.get("by_source", {})

        lines = [f"📈 **Статистика платформы:**\n"]
        lines.append(f"Всего объявлений: **{total}**\n")
        lines.append("**По городам:**")
        for city, count in sorted(by_city.items(), key=lambda x: -x[1]):
            lines.append(f"  {city}: {count}")
        lines.append("\n**По источникам:**")
        for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
            lines.append(f"  {source}: {count}")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# DEDUPLICATION
# ═══════════════════════════════════════════════════════════════

class Deduplicator:
    """Cross-source deduplication."""

    @staticmethod
    def make_hash(source: str, source_id: str, price: float, address: str) -> str:
        content = f"{source}:{source_id}:{price}:{address}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @staticmethod
    def make_content_hash(city: str, address: str, area: float, rooms: int, price: float) -> str:
        content = f"{city}:{address}:{area}:{rooms}:{price}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @classmethod
    async def is_duplicate(cls, session: AsyncSession, source_hash: str) -> bool:
        result = await session.execute(
            select(Listing.id).where(Listing.source_hash == source_hash).limit(1)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def upsert(cls, session: AsyncSession, item_data: dict) -> tuple[str, bool]:
        """Insert or update listing. Returns (id, is_new)."""
        source_hash = cls.make_hash(
            item_data["source"], item_data["source_id"],
            item_data["price"], item_data["address"]
        )

        existing = await session.execute(
            select(Listing).where(Listing.source_hash == source_hash).limit(1)
        )
        existing = existing.scalar_one_or_none()

        if existing:
            # Update if price changed
            if existing.price != item_data["price"]:
                # Record price history
                session.add(PriceHistory(listing_id=existing.id, price=existing.price))
                existing.price = item_data["price"]
                existing.price_per_m2 = item_data["price"] / item_data.get("area_m2", 1) if item_data.get("area_m2") else None
                existing.updated_at = datetime.now(timezone.utc).isoformat()
            return existing.id, False

        # New listing
        listing_id = str(uuid.uuid4())
        price_per_m2 = item_data["price"] / item_data["area_m2"] if item_data.get("area_m2") else None

        listing = Listing(
            id=listing_id,
            source=item_data["source"],
            source_id=item_data["source_id"],
            source_url=item_data.get("source_url", ""),
            source_hash=source_hash,
            property_type=item_data.get("property_type", "apartment"),
            deal_type=item_data.get("deal_type", "sale"),
            price=item_data["price"],
            price_per_m2=price_per_m2,
            currency=item_data.get("currency", "RUB"),
            area_m2=item_data.get("area_m2"),
            rooms=item_data.get("rooms"),
            floor=item_data.get("floor"),
            floors_total=item_data.get("floors_total"),
            address=item_data.get("address", ""),
            district=item_data.get("district"),
            city=item_data.get("city", ""),
            region=item_data.get("region"),
            lat=item_data.get("lat"),
            lon=item_data.get("lon"),
            metro_station=item_data.get("metro_station"),
            metro_minutes=item_data.get("metro_minutes"),
            title=item_data.get("title"),
            description=item_data.get("description"),
            images=json.dumps(item_data.get("images", [])),
            features=json.dumps(item_data.get("features", {})),
            author_type=item_data.get("author_type"),
        )
        session.add(listing)
        return listing_id, True


# ═══════════════════════════════════════════════════════════════
# SEED DATA
# ═══════════════════════════════════════════════════════════════

SEED = [
    {"city":"Москва","district":"Центральный","address":"ул. Тверская, 15","rooms":2,"area_m2":65,"floor":5,"floors_total":12,"price":18500000,"deal_type":"sale","property_type":"apartment","description":"Уютная 2-комнатная квартира в центре Москвы. Свежий ремонт, панорамные окна.","source":"cian","metro_station":"Тверская","metro_minutes":3},
    {"city":"Москва","district":"Арбат","address":"ул. Арбат, 25","rooms":3,"area_m2":95,"floor":8,"floors_total":15,"price":35000000,"deal_type":"sale","property_type":"apartment","description":"Просторная трёшка в историческом центре. Высокие потолки, паркет.","source":"avito","metro_station":"Арбатская","metro_minutes":5},
    {"city":"Москва","district":"Пресненский","address":"Пресненская наб., 12","rooms":1,"area_m2":42,"floor":22,"floors_total":55,"price":12000000,"deal_type":"sale","property_type":"apartment","description":"Квартира в Москва-Сити. Вид на город, мебель включена.","source":"cian","metro_station":"Деловой центр","metro_minutes":7},
    {"city":"Москва","district":"Хамовники","address":"ул. Льва Толстого, 7","rooms":4,"area_m2":150,"floor":3,"floors_total":6,"price":65000000,"deal_type":"sale","property_type":"apartment","description":"Элитная 4-комнатная квартира. Дизайнерский ремонт, камин.","source":"domclick","metro_station":"Парк Культуры","metro_minutes":10},
    {"city":"Москва","district":"Таганский","address":"ул. Марксисткая, 3","rooms":2,"area_m2":58,"floor":9,"floors_total":17,"price":75000,"deal_type":"rent","property_type":"apartment","description":"Сдаётся 2-комнатная квартира. Все удобства, техника.","source":"cian","metro_station":"Марксисткая","metro_minutes":2},
    {"city":"Москва","district":"Басманный","address":"ул. Покровка, 22","rooms":1,"area_m2":38,"floor":4,"floors_total":9,"price":55000,"deal_type":"rent","property_type":"apartment","description":"Однокомнатная квартира рядом с метро. Свежий ремонт.","source":"avito","metro_station":"Красные Ворота","metro_minutes":4},
    {"city":"Москва","district":"Якиманка","address":"ул. Большая Полянка, 44","rooms":0,"area_m2":28,"floor":11,"floors_total":20,"price":45000,"deal_type":"rent","property_type":"studio","description":"Студия с панорамным видом. Полностью меблирована.","source":"cian","metro_station":"Полянка","metro_minutes":5},
    {"city":"Москва","district":"Раменки","address":"ул. Раменки, 18","rooms":3,"area_m2":85,"floor":12,"floors_total":25,"price":22000000,"deal_type":"sale","property_type":"apartment","description":"Просторная трёшка в новостройке. Паркинг включён.","source":"domclick","metro_station":"Раменки","metro_minutes":8},
    {"city":"Москва","district":"Дорогомилово","address":"Кутузовский пр., 12","rooms":3,"area_m2":110,"floor":18,"floors_total":35,"price":45000000,"deal_type":"sale","property_type":"apartment","description":"Пентхаус с террасой. Вид на Москву-реку, консьерж-сервис.","source":"cian","metro_station":"Кутузовская","metro_minutes":6},
    {"city":"Санкт-Петербург","district":"Адмиралтейский","address":"Невский пр., 78","rooms":2,"area_m2":70,"floor":4,"floors_total":5,"price":15000000,"deal_type":"sale","property_type":"apartment","description":"Квартира на Невском. Исторический дом, лепнина, высокие потолки.","source":"cian","metro_station":"Гостиный двор","metro_minutes":4},
    {"city":"Санкт-Петербург","district":"Петроградский","address":"Каменноостровский пр., 40","rooms":1,"area_m2":45,"floor":6,"floors_total":8,"price":9500000,"deal_type":"sale","property_type":"apartment","description":"Однушка на Петроградке. Рядом метро и парк.","source":"avito","metro_station":"Петроградская","metro_minutes":3},
    {"city":"Санкт-Петербург","district":"Василеостровский","address":"Средний пр. В.О., 28","rooms":3,"area_m2":90,"floor":3,"floors_total":4,"price":20000000,"deal_type":"sale","property_type":"apartment","description":"Трёшка на Васильевском острове. Вид на Неву.","source":"cian","metro_station":"Василеостровская","metro_minutes":7},
    {"city":"Санкт-Петербург","district":"Центральный","address":"ул. Рубинштейна, 15","rooms":2,"area_m2":62,"floor":5,"floors_total":6,"price":65000,"deal_type":"rent","property_type":"apartment","description":"На улице ресторанов. Отличное состояние.","source":"cian","metro_station":"Владимирская","metro_minutes":5},
    {"city":"Санкт-Петербург","district":"Московский","address":"Московский пр., 100","rooms":0,"area_m2":30,"floor":10,"floors_total":18,"price":35000,"deal_type":"rent","property_type":"studio","description":"Студия у метро.","source":"avito","metro_station":"Московская","metro_minutes":2},
    {"city":"Краснодар","district":"Центральный","address":"ул. Красная, 170","rooms":2,"area_m2":60,"floor":7,"floors_total":16,"price":8500000,"deal_type":"sale","property_type":"apartment","description":"Двушка в центре Краснодара. Новостройка, чистовая отделка.","source":"cian"},
    {"city":"Краснодар","district":"Западный","address":"ул. Западная, 45","rooms":3,"area_m2":88,"floor":3,"floors_total":9,"price":11000000,"deal_type":"sale","property_type":"apartment","description":"Просторная трёшка с видом на парк. Два санузла.","source":"domclick"},
    {"city":"Краснодар","district":"Прикубанский","address":"ул. Ставропольская, 200","rooms":1,"area_m2":40,"floor":5,"floors_total":10,"price":5500000,"deal_type":"sale","property_type":"apartment","description":"Однокомнатная квартира. Тихий двор, детская площадка.","source":"avito"},
    {"city":"Краснодар","district":"Фестивальный","address":"ул. Кубанская, 10","rooms":4,"area_m2":120,"floor":2,"floors_total":3,"price":18000000,"deal_type":"sale","property_type":"house","description":"Частный дом с участком 6 соток. Гараж, баня, бассейн.","source":"cian"},
    {"city":"Сочи","district":"Центральный","address":"ул. Навагинская, 12","rooms":2,"area_m2":55,"floor":8,"floors_total":14,"price":12000000,"deal_type":"sale","property_type":"apartment","description":"Квартира с видом на море. 5 минут до пляжа.","source":"cian"},
    {"city":"Сочи","district":"Хостинский","address":"ул. Черноморская, 5","rooms":1,"area_m2":35,"floor":4,"floors_total":5,"price":40000,"deal_type":"rent","property_type":"apartment","description":"Сдаётся на лето. Вид на море, кондиционер, Wi-Fi.","source":"avito"},
    {"city":"Сочи","district":"Адлер","address":"ул. Ленина, 215","rooms":0,"area_m2":25,"floor":9,"floors_total":12,"price":6000000,"deal_type":"sale","property_type":"studio","description":"Студия у олимпийского парка. С мебелью.","source":"cian"},
    {"city":"Екатеринбург","district":"Ленинский","address":"ул. Малышева, 36","rooms":2,"area_m2":55,"floor":10,"floors_total":20,"price":7500000,"deal_type":"sale","property_type":"apartment","description":"Двушка в центре Екб. Панорамные окна, вид на город.","source":"domclick"},
    {"city":"Екатеринбург","district":"Октябрьский","address":"ул. 8 Марта, 50","rooms":1,"area_m2":38,"floor":3,"floors_total":5,"price":35000,"deal_type":"rent","property_type":"apartment","description":"Однушка. Рядом ТЦ и парк.","source":"avito"},
    {"city":"Новосибирск","district":"Центральный","address":"Красный пр., 25","rooms":2,"area_m2":60,"floor":6,"floors_total":9,"price":6500000,"deal_type":"sale","property_type":"apartment","description":"Квартира на Красном проспекте. Свежий ремонт.","source":"cian"},
    {"city":"Новосибирск","district":"Советский","address":"ул. Ипподромская, 42","rooms":3,"area_m2":80,"floor":4,"floors_total":10,"price":9000000,"deal_type":"sale","property_type":"apartment","description":"Трёшка в тихом районе. Рядом Академгородок.","source":"domclick"},
    {"city":"Москва","district":"Пресненский","address":"Пресненская наб., 8","rooms":None,"area_m2":200,"floor":15,"floors_total":55,"price":500000,"deal_type":"rent","property_type":"commercial","description":"Офис класса А в Москва-Сити. Панорамное остекление.","source":"cian"},
    {"city":"Санкт-Петербург","district":"Невский","address":"Невский пр., 100","rooms":None,"area_m2":80,"floor":1,"floors_total":5,"price":150000,"deal_type":"rent","property_type":"commercial","description":"Торговое помещение на Невском. Высокий трафик.","source":"avito"},
    {"city":"Краснодар","district":"Пашковский","address":"ст. Пашковская","rooms":None,"area_m2":1500,"floor":None,"floors_total":None,"price":3500000,"deal_type":"sale","property_type":"land","description":"Участок 15 соток. Все коммуникации, асфальтированный подъезд.","source":"domclick"},
]


async def seed_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        count = (await session.execute(select(func.count(Listing.id)))).scalar()
        if count > 0:
            log.info(f"Database already has {count} listings")
            return
        for d in SEED:
            source_hash = Deduplicator.make_hash(d["source"], f"seed_{hash(d['address'])}", d["price"], d["address"])
            session.add(Listing(
                source=d["source"],
                source_id=f"seed_{hash(d['address'])}",
                source_url=f"https://example.com/{hash(d['address'])}",
                source_hash=source_hash,
                property_type=d["property_type"],
                deal_type=d["deal_type"],
                price=d["price"],
                price_per_m2=d["price"] / d["area_m2"] if d.get("area_m2") else None,
                area_m2=d.get("area_m2"),
                rooms=d.get("rooms"),
                floor=d.get("floor"),
                floors_total=d.get("floors_total"),
                address=d["address"],
                district=d.get("district"),
                city=d["city"],
                description=d.get("description"),
                metro_station=d.get("metro_station"),
                metro_minutes=d.get("metro_minutes"),
            ))
        await session.commit()
        log.info(f"✅ Seeded {len(SEED)} listings")


# ═══════════════════════════════════════════════════════════════
# ANALYTICS SERVICE
# ═══════════════════════════════════════════════════════════════

class AnalyticsService:

    @staticmethod
    async def get_analytics(session: AsyncSession, city: Optional[str] = None) -> dict:
        q = select(Listing).where(Listing.is_active == True)
        if city:
            q = q.where(Listing.city == city)
        result = await session.execute(q)
        items = [l.to_dict() for l in result.scalars().all()]

        # Group by deal_type + property_type
        groups = {}
        for item in items:
            key = (item["deal_type"], item["property_type"])
            if key not in groups:
                groups[key] = []
            groups[key].append(item)

        analytics = []
        for (deal, ptype), group in sorted(groups.items()):
            prices = [i["price"] for i in group]
            areas = [i["area_m2"] for i in group if i.get("area_m2")]
            per_m2 = [i["price"] / i["area_m2"] for i in group if i.get("area_m2")]

            analytics.append({
                "deal_type": deal,
                "property_type": ptype,
                "count": len(group),
                "avg_price": sum(prices) / len(prices) if prices else 0,
                "min_price": min(prices) if prices else 0,
                "max_price": max(prices) if prices else 0,
                "avg_area": sum(areas) / len(areas) if areas else 0,
                "avg_price_per_m2": sum(per_m2) / len(per_m2) if per_m2 else 0,
            })

        return {"city": city, "analytics": analytics}

    @staticmethod
    async def compare_cities(session: AsyncSession, city1: str, city2: str) -> dict:
        result = {}
        for city in [city1, city2]:
            q = select(Listing).where(Listing.is_active == True, Listing.city == city)
            items = (await session.execute(q)).scalars().all()
            items_dict = [l.to_dict() for l in items]

            sale = [i for i in items_dict if i["deal_type"] == "sale"]
            avg_price = sum(i["price"] for i in sale) / len(sale) if sale else 0
            per_m2 = [i["price"] / i["area_m2"] for i in sale if i.get("area_m2")]
            avg_m2 = sum(per_m2) / len(per_m2) if per_m2 else 0

            result[city] = {
                "total": len(items_dict),
                "analytics": [{
                    "property_type": "apartment",
                    "avg_price": avg_price,
                    "avg_price_per_m2": avg_m2,
                }]
            }
        return {"comparison": result}


# ═══════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════

START_TIME = datetime.now(timezone.utc)
nlu = NLUAgent()
analytics_service = AnalyticsService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_db()
    log.info("✅ Database ready")
    yield


app = FastAPI(
    title="Realty AI Platform",
    version="2.0.0",
    description="AI-powered real estate aggregation platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Error Handler ─────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc) if DEBUG else "Contact support"},
    )


# ─── Health & Info ─────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
async def health():
    async with async_session() as session:
        count = (await session.execute(select(func.count(Listing.id)).where(Listing.is_active == True))).scalar()
    uptime = (datetime.now(timezone.utc) - START_TIME).total_seconds()
    return HealthResponse(status="ok", version="2.0.0", uptime=uptime, listings_count=count)


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    async with async_session() as session:
        total = (await session.execute(select(func.count(Listing.id)).where(Listing.is_active == True))).scalar()
        by_city = dict((await session.execute(
            select(Listing.city, func.count(Listing.id)).where(Listing.is_active == True).group_by(Listing.city)
        )).all())
        by_source = dict((await session.execute(
            select(Listing.source, func.count(Listing.id)).where(Listing.is_active == True).group_by(Listing.source)
        )).all())
        by_type = dict((await session.execute(
            select(Listing.property_type, func.count(Listing.id)).where(Listing.is_active == True).group_by(Listing.property_type)
        )).all())
        by_deal = dict((await session.execute(
            select(Listing.deal_type, func.count(Listing.id)).where(Listing.is_active == True).group_by(Listing.deal_type)
        )).all())
    return StatsResponse(total=total, by_city=by_city, by_source=by_source, by_type=by_type, by_deal=by_deal)


# ─── Frontend ──────────────────────────────────────────

@app.get("/")
async def frontend():
    return FileResponse("demo/index.html", media_type="text/html")


# ─── AI Agent Chat ─────────────────────────────────────

@app.post("/api/agent/chat", response_model=ChatResponse)
async def agent_chat(body: ChatRequest):
    filters = nlu.parse(body.query)
    action = filters.pop("action", "search")

    async with async_session() as session:
        if action == "analytics":
            data = await analytics_service.get_analytics(session, filters.get("city"))
            response = nlu.format_response("analytics", data, filters)
            return ChatResponse(response=response, action=action, filters=filters, total=data.get("total", 0))

        elif action == "compare":
            cities = []
            ql = body.query.lower()
            for alias, name in sorted(CITY_ALIASES.items(), key=lambda x: -len(x[0])):
                if alias in ql and name not in cities:
                    cities.append(name)
            if len(cities) >= 2:
                data = await analytics_service.compare_cities(session, cities[0], cities[1])
                response = nlu.format_response("compare", data, filters)
                return ChatResponse(response=response, action=action, filters=filters, total=0)
            else:
                return ChatResponse(
                    response="📊 Укажите два города для сравнения. Например: 'сравни цены в Москве и Питере'",
                    action=action, filters=filters, total=0,
                )

        elif action == "stats":
            total = (await session.execute(select(func.count(Listing.id)).where(Listing.is_active == True))).scalar()
            by_city = dict((await session.execute(
                select(Listing.city, func.count(Listing.id)).where(Listing.is_active == True).group_by(Listing.city)
            )).all())
            by_source = dict((await session.execute(
                select(Listing.source, func.count(Listing.id)).where(Listing.is_active == True).group_by(Listing.source)
            )).all())
            data = {"total": total, "by_city": by_city, "by_source": by_source}
            response = nlu.format_response("stats", data, filters)
            return ChatResponse(response=response, action=action, filters=filters, total=total)

        else:  # search / recommend
            q = select(Listing).where(Listing.is_active == True)

            if filters.get("city"):
                q = q.where(Listing.city == filters["city"])
            if filters.get("deal_type"):
                q = q.where(Listing.deal_type == filters["deal_type"])
            if filters.get("property_type"):
                q = q.where(Listing.property_type == filters["property_type"])
            if filters.get("rooms") is not None:
                q = q.where(Listing.rooms == filters["rooms"])
            if filters.get("price_max"):
                q = q.where(Listing.price <= filters["price_max"])
            if filters.get("price_min"):
                q = q.where(Listing.price >= filters["price_min"])
            if filters.get("district"):
                q = q.where(Listing.district.contains(filters["district"]))
            if filters.get("metro"):
                q = q.where(Listing.metro_station.contains(filters["metro"]))
            if filters.get("area_min"):
                q = q.where(Listing.area_m2 >= filters["area_min"])
            if filters.get("area_max"):
                q = q.where(Listing.area_m2 <= filters["area_max"])

            # Sorting
            sort_col = getattr(Listing, filters.get("sort_by", "created_at"), Listing.created_at)
            sort_order = asc(sort_col) if filters.get("sort_order") == "asc" else desc(sort_col)
            q = q.order_by(sort_order)

            result = await session.execute(q)
            items = [l.to_dict() for l in result.scalars().all()]

            data = {"items": items, "total": len(items)}
            response = nlu.format_response("search", data, filters)
            return ChatResponse(response=response, action=action, filters=filters, total=len(items))


# ─── Listings ──────────────────────────────────────────

@app.get("/api/listings")
async def get_listings(
    city: Optional[str] = None,
    deal_type: Optional[str] = None,
    property_type: Optional[str] = None,
    rooms: Optional[int] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    area_min: Optional[float] = None,
    area_max: Optional[float] = None,
    district: Optional[str] = None,
    metro: Optional[str] = None,
    sort_by: str = Query("created_at", pattern="^(created_at|price|area_m2|price_per_m2)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    async with async_session() as session:
        q = select(Listing).where(Listing.is_active == True)

        if city:
            q = q.where(Listing.city == city)
        if deal_type:
            q = q.where(Listing.deal_type == deal_type)
        if property_type:
            q = q.where(Listing.property_type == property_type)
        if rooms is not None:
            q = q.where(Listing.rooms == rooms)
        if price_max:
            q = q.where(Listing.price <= price_max)
        if price_min:
            q = q.where(Listing.price >= price_min)
        if area_min:
            q = q.where(Listing.area_m2 >= area_min)
        if area_max:
            q = q.where(Listing.area_m2 <= area_max)
        if district:
            q = q.where(Listing.district.contains(district))
        if metro:
            q = q.where(Listing.metro_station.contains(metro))

        count_q = select(func.count()).select_from(q.subquery())
        total = (await session.execute(count_q)).scalar()

        sort_col = getattr(Listing, sort_by, Listing.created_at)
        order = asc(sort_col) if sort_order == "asc" else desc(sort_col)
        q = q.order_by(order).offset(offset).limit(limit)

        result = await session.execute(q)
        items = [l.to_dict() for l in result.scalars().all()]

    return {"total": total, "offset": offset, "limit": limit, "items": items}


@app.get("/api/listings/{listing_id}")
async def get_listing(listing_id: str):
    async with async_session() as session:
        result = await session.execute(
            select(Listing).where(Listing.id == listing_id, Listing.is_active == True)
        )
        listing = result.scalar_one_or_none()
        if not listing:
            raise HTTPException(404, "Listing not found")
        return listing.to_dict()


# ─── Analytics ─────────────────────────────────────────

@app.get("/api/analytics")
async def get_analytics(city: Optional[str] = None):
    async with async_session() as session:
        return await analytics_service.get_analytics(session, city)


@app.get("/api/analytics/compare")
async def compare_cities(
    city1: str = Query(..., description="First city"),
    city2: str = Query(..., description="Second city"),
):
    async with async_session() as session:
        return await analytics_service.compare_cities(session, city1, city2)


# ─── Scraping Jobs ─────────────────────────────────────

@app.post("/api/admin/scrape")
async def trigger_scrape(body: dict):
    """Trigger a scraping job (stub for now)."""
    return {
        "message": "Scraping job queued",
        "source": body.get("source", "all"),
        "city": body.get("city", "Москва"),
        "status": "queued",
    }


@app.get("/api/admin/jobs")
async def get_jobs(limit: int = 20):
    async with async_session() as session:
        result = await session.execute(
            select(ScrapingJob).order_by(desc(ScrapingJob.created_at)).limit(limit)
        )
        jobs = result.scalars().all()
        return [{"id": j.id, "source": j.source, "city": j.city, "status": j.status,
                 "items_found": j.items_found, "items_new": j.items_new,
                 "created_at": j.created_at} for j in jobs]


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
