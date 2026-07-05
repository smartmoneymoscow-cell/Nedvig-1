"""
Local server — runs backend (FastAPI + SQLite) + serves frontend HTML.
No Docker, no PostgreSQL needed.
"""

import uuid
import json
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, Enum, Index, select, func, desc, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pydantic import BaseModel
from typing import Optional
import enum
import re

# ═══════════════════════════════════════════════════════
# Database (SQLite)
# ═══════════════════════════════════════════════════════

DB_URL = "sqlite+aiosqlite:///./realty.db"
engine = create_async_engine(DB_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class PropertyType(str, enum.Enum):
    apartment = "apartment"
    house = "house"
    commercial = "commercial"
    land = "land"
    room = "room"
    studio = "studio"


class DealType(str, enum.Enum):
    sale = "sale"
    rent = "rent"


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(500))
    property_type: Mapped[str] = mapped_column(String(20))
    deal_type: Mapped[str] = mapped_column(String(10))
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    area_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    floor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    floors_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    address: Mapped[str] = mapped_column(String(500))
    district: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    city: Mapped[str] = mapped_column(String(100))
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    images: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    features: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    created_at: Mapped[str] = mapped_column(String(30), default=lambda: datetime.utcnow().isoformat())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id, "source": self.source, "source_url": self.source_url,
            "property_type": self.property_type, "deal_type": self.deal_type,
            "price": self.price, "currency": self.currency, "area_m2": self.area_m2,
            "rooms": self.rooms, "floor": self.floor, "floors_total": self.floors_total,
            "address": self.address, "district": self.district, "city": self.city,
            "description": self.description, "created_at": self.created_at, "is_active": self.is_active,
        }


# ═══════════════════════════════════════════════════════
# AI Agent (NLU)
# ═══════════════════════════════════════════════════════

ROOM_PATTERNS = [
    (r"(\d)\s*[-–]?\s*комн", lambda m: int(m.group(1))),
    (r"(\d)\s*[-–]?\s*к\b", lambda m: int(m.group(1))),
    (r"студия|студи", lambda m: 0),
    (r"однушк", lambda m: 1),
    (r"двушк", lambda m: 2),
    (r"трёшк|трешк", lambda m: 3),
]

CITY_ALIASES = {
    "москва": "Москва", "москве": "Москва", "москвы": "Москва", "мск": "Москва",
    "питер": "Санкт-Петербург", "спб": "Санкт-Петербург", "петербург": "Санкт-Петербург", "петербурге": "Санкт-Петербург",
    "новосибирск": "Новосибирск", "новосибирске": "Новосибирск",
    "екатеринбург": "Екатеринбург", "екатеринбурге": "Екатеринбург",
    "казань": "Казань", "краснодар": "Краснодар", "краснодаре": "Краснодар",
    "сочи": "Сочи", "владивосток": "Владивосток",
}

PTYPE_KW = {
    "квартир": "apartment", "комнат": "apartment", "комната": "apartment",
    "студия": "studio", "студи": "studio",
    "дом": "house", "коттедж": "house", "таунхаус": "house",
    "земля": "land", "участок": "land",
    "коммерческ": "commercial", "офис": "commercial", "магазин": "commercial",
}

DEAL_KW = {
    "аренда": "rent", "снять": "rent", "сниму": "rent", "арендовать": "rent",
    "продажа": "sale", "купить": "sale", "куплю": "sale", "прода": "sale",
}


def parse_query(text: str) -> dict:
    ql = text.lower()
    f = {}

    # Action
    if re.search(r"сравн|разниц", ql):
        f["action"] = "compare"
    elif re.search(r"аналитик|статистик|средн", ql):
        f["action"] = "analytics"
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

    # Price
    m = re.search(r"от\s+(\d+)\s*до\s+(\d+)\s*млн", ql)
    if m:
        f["price_min"] = int(m.group(1)) * 1_000_000
        f["price_max"] = int(m.group(2)) * 1_000_000
    else:
        m = re.search(r"до\s+(\d+)\s*млн", ql)
        if m:
            f["price_max"] = int(m.group(1)) * 1_000_000
        else:
            m = re.search(r"до\s+(\d+)\s*тыс", ql)
            if m:
                f["price_max"] = int(m.group(1)) * 1_000
            else:
                m = re.search(r"до\s+(\d{4,})", ql)
                if m:
                    f["price_max"] = int(m.group(1))

    # City
    for alias, city in CITY_ALIASES.items():
        if alias in ql:
            f["city"] = city
            break

    return f


# ═══════════════════════════════════════════════════════
# Seed Data
# ═══════════════════════════════════════════════════════

SEED = [
    {"city":"Москва","district":"Центральный","address":"ул. Тверская, 15","rooms":2,"area_m2":65,"floor":5,"floors_total":12,"price":18500000,"deal_type":"sale","property_type":"apartment","description":"Уютная 2-комнатная квартира в центре Москвы. Свежий ремонт, панорамные окна.","source":"cian"},
    {"city":"Москва","district":"Арбат","address":"ул. Арбат, 25","rooms":3,"area_m2":95,"floor":8,"floors_total":15,"price":35000000,"deal_type":"sale","property_type":"apartment","description":"Просторная трёшка в историческом центре. Высокие потолки, паркет.","source":"avito"},
    {"city":"Москва","district":"Пресненский","address":"Пресненская наб., 12","rooms":1,"area_m2":42,"floor":22,"floors_total":55,"price":12000000,"deal_type":"sale","property_type":"apartment","description":"Квартира в Москва-Сити. Вид на город, мебель включена.","source":"cian"},
    {"city":"Москва","district":"Хамовники","address":"ул. Льва Толстого, 7","rooms":4,"area_m2":150,"floor":3,"floors_total":6,"price":65000000,"deal_type":"sale","property_type":"apartment","description":"Элитная 4-комнатная квартира. Дизайнерский ремонт, камин.","source":"domclick"},
    {"city":"Москва","district":"Таганский","address":"ул. Марксисткая, 3","rooms":2,"area_m2":58,"floor":9,"floors_total":17,"price":75000,"deal_type":"rent","property_type":"apartment","description":"Сдаётся 2-комнатная квартира. Все удобства, техника.","source":"cian"},
    {"city":"Москва","district":"Басманный","address":"ул. Покровка, 22","rooms":1,"area_m2":38,"floor":4,"floors_total":9,"price":55000,"deal_type":"rent","property_type":"apartment","description":"Однокомнатная квартира рядом с метро. Свежий ремонт.","source":"avito"},
    {"city":"Москва","district":"Якиманка","address":"ул. Большая Полянка, 44","rooms":0,"area_m2":28,"floor":11,"floors_total":20,"price":45000,"deal_type":"rent","property_type":"studio","description":"Студия с панорамным видом. Полностью меблирована.","source":"cian"},
    {"city":"Москва","district":"Раменки","address":"ул. Раменки, 18","rooms":3,"area_m2":85,"floor":12,"floors_total":25,"price":22000000,"deal_type":"sale","property_type":"apartment","description":"Просторная трёшка в новостройке. Паркинг включён.","source":"domclick"},
    {"city":"Москва","district":"Дорогомилово","address":"Кутузовский пр., 12","rooms":3,"area_m2":110,"floor":18,"floors_total":35,"price":45000000,"deal_type":"sale","property_type":"apartment","description":"Пентхаус с террасой. Вид на Москву-реку, консьерж-сервис.","source":"cian"},
    {"city":"Санкт-Петербург","district":"Адмиралтейский","address":"Невский пр., 78","rooms":2,"area_m2":70,"floor":4,"floors_total":5,"price":15000000,"deal_type":"sale","property_type":"apartment","description":"Квартира на Невском. Исторический дом, лепнина, высокие потолки.","source":"cian"},
    {"city":"Санкт-Петербург","district":"Петроградский","address":"Каменноостровский пр., 40","rooms":1,"area_m2":45,"floor":6,"floors_total":8,"price":9500000,"deal_type":"sale","property_type":"apartment","description":"Однушка на Петроградке. Рядом метро и парк.","source":"avito"},
    {"city":"Санкт-Петербург","district":"Василеостровский","address":"Средний пр. В.О., 28","rooms":3,"area_m2":90,"floor":3,"floors_total":4,"price":20000000,"deal_type":"sale","property_type":"apartment","description":"Трёшка на Васильевском острове. Вид на Неву.","source":"cian"},
    {"city":"Санкт-Петербург","district":"Центральный","address":"ул. Рубинштейна, 15","rooms":2,"area_m2":62,"floor":5,"floors_total":6,"price":65000,"deal_type":"rent","property_type":"apartment","description":"Сдаётся квартира на улице ресторанов. Отличное состояние.","source":"cian"},
    {"city":"Санкт-Петербург","district":"Московский","address":"Московский пр., 100","rooms":0,"area_m2":30,"floor":10,"floors_total":18,"price":35000,"deal_type":"rent","property_type":"studio","description":"Студия у метро. Подходит для одного.","source":"avito"},
    {"city":"Краснодар","district":"Центральный","address":"ул. Красная, 170","rooms":2,"area_m2":60,"floor":7,"floors_total":16,"price":8500000,"deal_type":"sale","property_type":"apartment","description":"Двушка в центре Краснодара. Новостройка, чистовая отделка.","source":"cian"},
    {"city":"Краснодар","district":"Западный","address":"ул. Западная, 45","rooms":3,"area_m2":88,"floor":3,"floors_total":9,"price":11000000,"deal_type":"sale","property_type":"apartment","description":"Просторная трёшка с видом на парк. Два санузла.","source":"domclick"},
    {"city":"Краснодар","district":"Прикубанский","address":"ул. Ставропольская, 200","rooms":1,"area_m2":40,"floor":5,"floors_total":10,"price":5500000,"deal_type":"sale","property_type":"apartment","description":"Однокомнатная квартира. Тихий двор, детская площадка.","source":"avito"},
    {"city":"Краснодар","district":"Фестивальный","address":"ул. Кубанская, 10","rooms":4,"area_m2":120,"floor":2,"floors_total":3,"price":18000000,"deal_type":"sale","property_type":"house","description":"Частный дом с участком 6 соток. Гараж, баня, бассейн.","source":"cian"},
    {"city":"Сочи","district":"Центральный","address":"ул. Навагинская, 12","rooms":2,"area_m2":55,"floor":8,"floors_total":14,"price":12000000,"deal_type":"sale","property_type":"apartment","description":"Квартира с видом на море. 5 минут до пляжа.","source":"cian"},
    {"city":"Сочи","district":"Хостинский","address":"ул. Черноморская, 5","rooms":1,"area_m2":35,"floor":4,"floors_total":5,"price":40000,"deal_type":"rent","property_type":"apartment","description":"Сдаётся на лето. Вид на море, кондиционер, Wi-Fi.","source":"avito"},
    {"city":"Сочи","district":"Адлер","address":"ул. Ленина, 215","rooms":0,"area_m2":25,"floor":9,"floors_total":12,"price":6000000,"deal_type":"sale","property_type":"studio","description":"Студия в 3 минутах от олимпийского парка. С мебелью.","source":"cian"},
    {"city":"Екатеринбург","district":"Ленинский","address":"ул. Малышева, 36","rooms":2,"area_m2":55,"floor":10,"floors_total":20,"price":7500000,"deal_type":"sale","property_type":"apartment","description":"Двушка в центре Екб. Панорамные окна, вид на город.","source":"domclick"},
    {"city":"Екатеринбург","district":"Октябрьский","address":"ул. 8 Марта, 50","rooms":1,"area_m2":38,"floor":3,"floors_total":5,"price":35000,"deal_type":"rent","property_type":"apartment","description":"Сдаётся однушка. Рядом ТЦ и парк.","source":"avito"},
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
            return
        for d in SEED:
            session.add(Listing(
                source=d["source"], source_id=f"seed_{hash(d['address'])}",
                source_url=f"https://example.com/{hash(d['address'])}",
                property_type=d["property_type"], deal_type=d["deal_type"],
                price=d["price"], area_m2=d.get("area_m2"), rooms=d.get("rooms"),
                floor=d.get("floor"), floors_total=d.get("floors_total"),
                address=d["address"], district=d.get("district"), city=d["city"],
                description=d.get("description"),
            ))
        await session.commit()
        print(f"✅ Seeded {len(SEED)} listings")


# ═══════════════════════════════════════════════════════
# FastAPI App
# ═══════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_db()
    print("✅ Database ready")
    yield

app = FastAPI(title="Realty AI", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Serve frontend
@app.get("/")
async def frontend():
    return FileResponse("demo/index.html", media_type="text/html")


# ─── API ───────────────────────────────────────────────

@app.post("/api/agent/chat")
async def agent_chat(body: dict):
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(400, "Query required")

    f = parse_query(query)
    action = f.pop("action", "search")

    async with async_session() as session:
        q = select(Listing).where(Listing.is_active == True)

        if f.get("city"):
            q = q.where(Listing.city == f["city"])
        if f.get("deal_type"):
            q = q.where(Listing.deal_type == f["deal_type"])
        if f.get("property_type"):
            q = q.where(Listing.property_type == f["property_type"])
        if f.get("rooms") is not None:
            q = q.where(Listing.rooms == f["rooms"])
        if f.get("price_max"):
            q = q.where(Listing.price <= f["price_max"])
        if f.get("price_min"):
            q = q.where(Listing.price >= f["price_min"])
        if f.get("district"):
            q = q.where(Listing.district.contains(f["district"]))

        if action == "analytics":
            return await _analytics(session, f.get("city"))
        elif action == "compare":
            return await _compare(query)

        result = await session.execute(q.order_by(desc(Listing.created_at)))
        items = [l.to_dict() for l in result.scalars().all()]

    # Format response
    if not items:
        response = "😕 Ничего не найдено. Попробуйте изменить параметры."
    else:
        lines = [f"🏠 Найдено **{len(items)}** объявлений:\n"]
        for i, l in enumerate(items[:10], 1):
            price = f"{l['price']:,.0f} ₽".replace(",", " ")
            rooms = f"{l['rooms']}к" if l.get("rooms") is not None else ("Студия" if l["property_type"] == "studio" else l["property_type"])
            area = f", {l['area_m2']}м²" if l.get("area_m2") else ""
            floor = f", этаж {l['floor']}/{l['floors_total']}" if l.get("floor") else ""
            lines.append(f"**{i}.** {rooms}{area}{floor} — **{price}**")
            lines.append(f"   📍 {l['city']}, {l['address']}")
            lines.append(f"   🔗 {l['source_url']}\n")
        if len(items) > 10:
            lines.append(f"... и ещё {len(items) - 10} объявлений.")
        response = "\n".join(lines)

    return {"response": response, "filters": f, "total": len(items)}


async def _analytics(session, city=None):
    q = select(Listing).where(Listing.is_active == True)
    if city:
        q = q.where(Listing.city == city)
    result = await session.execute(q)
    items = [l.to_dict() for l in result.scalars().all()]

    sale = [l for l in items if l["deal_type"] == "sale" and l["property_type"] in ("apartment", "studio")]
    rent = [l for l in items if l["deal_type"] == "rent" and l["property_type"] in ("apartment", "studio")]

    def avg(arr, key):
        vals = [l[key] for l in arr if l.get(key)]
        return sum(vals) / len(vals) if vals else 0

    lines = [f"📊 **Аналитика {city or 'все города'}:**\n"]
    if sale:
        lines.append(f"**Продажа квартир** ({len(sale)} шт.)")
        lines.append(f"  Средняя цена: {avg(sale, 'price'):,.0f} ₽".replace(",", " "))
        m2 = [l["price"]/l["area_m2"] for l in sale if l.get("area_m2")]
        if m2: lines.append(f"  За м²: {sum(m2)/len(m2):,.0f} ₽".replace(",", " "))
        prices = [l["price"] for l in sale]
        lines.append(f"  Диапазон: {min(prices):,.0f} – {max(prices):,.0f} ₽\n".replace(",", " "))
    if rent:
        lines.append(f"**Аренда квартир** ({len(rent)} шт.)")
        lines.append(f"  Средняя: {avg(rent, 'price'):,.0f} ₽/мес".replace(",", " "))

    return {"response": "\n".join(lines), "filters": {"city": city}, "total": len(items)}


async def _compare(query):
    ql = query.lower()
    cities = []
    for alias, name in CITY_ALIASES.items():
        if alias in ql and name not in cities:
            cities.append(name)
    if len(cities) < 2:
        return {"response": "📊 Укажите два города. Например: 'сравни цены в Москве и Питере'", "filters": {}, "total": 0}

    lines = ["📊 **Сравнение:**\n"]
    async with async_session() as session:
        for city in cities[:2]:
            result = await session.execute(select(Listing).where(Listing.city == city, Listing.is_active == True))
            items = [l.to_dict() for l in result.scalars().all()]
            sale = [l for l in items if l["deal_type"] == "sale" and l["property_type"] in ("apartment", "studio")]
            avg_p = sum(l["price"] for l in sale) / len(sale) if sale else 0
            m2 = [l["price"]/l["area_m2"] for l in sale if l.get("area_m2")]
            avg_m2 = sum(m2) / len(m2) if m2 else 0
            lines.append(f"**{city}** — {len(items)} объявлений")
            lines.append(f"  Продажа: ср. {avg_p:,.0f} ₽ ({avg_m2:,.0f} ₽/м²)\n".replace(",", " "))

    return {"response": "\n".join(lines), "filters": {}, "total": 0}


@app.get("/api/listings")
async def get_listings(
    city: Optional[str] = None, deal_type: Optional[str] = None,
    property_type: Optional[str] = None, rooms: Optional[int] = None,
    price_min: Optional[float] = None, price_max: Optional[float] = None,
    offset: int = 0, limit: int = 50,
):
    async with async_session() as session:
        q = select(Listing).where(Listing.is_active == True)
        if city: q = q.where(Listing.city == city)
        if deal_type: q = q.where(Listing.deal_type == deal_type)
        if property_type: q = q.where(Listing.property_type == property_type)
        if rooms is not None: q = q.where(Listing.rooms == rooms)
        if price_max: q = q.where(Listing.price <= price_max)
        if price_min: q = q.where(Listing.price >= price_min)

        count_q = select(func.count()).select_from(q.subquery())
        total = (await session.execute(count_q)).scalar()
        result = await session.execute(q.order_by(desc(Listing.created_at)).offset(offset).limit(limit))
        items = [l.to_dict() for l in result.scalars().all()]

    return {"total": total, "items": items}


@app.get("/api/stats")
async def get_stats():
    async with async_session() as session:
        total = (await session.execute(select(func.count(Listing.id)).where(Listing.is_active == True))).scalar()
        by_city = (await session.execute(
            select(Listing.city, func.count(Listing.id)).where(Listing.is_active == True).group_by(Listing.city)
        )).all()
        by_source = (await session.execute(
            select(Listing.source, func.count(Listing.id)).where(Listing.is_active == True).group_by(Listing.source)
        )).all()
    return {"total": total, "by_city": dict(by_city), "by_source": dict(by_source)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
