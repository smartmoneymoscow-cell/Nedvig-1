"""AI Agent — parses natural language into search filters, generates responses."""

import re
import logging
from typing import Optional
from app.services.search import SearchFilters
from app.models.listing import PropertyType, DealType

log = logging.getLogger("realty")

# ─── Keyword mappings ────────────────────────────────────────────

PROPERTY_KEYWORDS = {
    "квартир": PropertyType.APARTMENT,
    "комнат": PropertyType.APARTMENT,
    "комната": PropertyType.APARTMENT,
    "студия": PropertyType.STUDIO,
    "студи": PropertyType.STUDIO,
    "дом": PropertyType.HOUSE,
    "коттедж": PropertyType.HOUSE,
    "таунхаус": PropertyType.HOUSE,
    "дача": PropertyType.HOUSE,
    "земля": PropertyType.LAND,
    "участок": PropertyType.LAND,
    "соток": PropertyType.LAND,
    "коммерческ": PropertyType.COMMERCIAL,
    "офис": PropertyType.COMMERCIAL,
    "магазин": PropertyType.COMMERCIAL,
    "склад": PropertyType.COMMERCIAL,
    "торгов": PropertyType.COMMERCIAL,
}

DEAL_KEYWORDS = {
    "аренда": DealType.RENT,
    "снять": DealType.RENT,
    "сниму": DealType.RENT,
    "арендовать": DealType.RENT,
    "сдаётся": DealType.RENT,
    "сдается": DealType.RENT,
    "продажа": DealType.SALE,
    "купить": DealType.SALE,
    "куплю": DealType.SALE,
    "прода": DealType.SALE,
    "покупка": DealType.SALE,
}

# ─── Room patterns (expanded) ────────────────────────────────────

ROOM_PATTERNS = [
    (r"(\d)\s*[-–]?\s*комн", lambda m: int(m.group(1))),
    (r"(\d)\s*[-–]?\s*к\b", lambda m: int(m.group(1))),
    (r"(\d)\s*[xх]\s*комн", lambda m: int(m.group(1))),
    (r"студия|студи", lambda m: 0),
    (r"однушк|одн[оё]к", lambda m: 1),
    (r"двушк|двухк", lambda m: 2),
    (r"трёшк|трешк|трёхк", lambda m: 3),
    (r"четыр", lambda m: 4),
    (r"пят", lambda m: 5),
]

# ─── Price patterns ──────────────────────────────────────────────

PRICE_PATTERNS = [
    (r"от\s+(\d+[\d\s]*)\s*(?:до)\s*(\d+[\d\s]*)\s*(тыс|млн|руб)", "range"),
    (r"от\s+(\d+[\d\s]*)\s*(тыс|млн|руб)", "min"),
    (r"до\s+(\d+[\d\s]*)\s*(тыс|млн|руб)", "max"),
    (r"(\d+)\s*млн", "max_mln"),
    (r"(\d+)\s*тыс", "max_thousand"),
    (r"до\s+(\d{4,})", "max_raw"),
    (r"от\s+(\d{4,})", "min_raw"),
]

# ─── City aliases (expanded) ─────────────────────────────────────

CITY_ALIASES = {
    "москва": "Москва", "москве": "Москва", "москвы": "Москва", "мск": "Москва",
    "питер": "Санкт-Петербург", "спб": "Санкт-Петербург", "петербург": "Санкт-Петербург",
    "петербурге": "Санкт-Петербург", "петербурга": "Санкт-Петербург",
    "новосибирск": "Новосибирск", "новосибирске": "Новосибирск", "нск": "Новосибирск",
    "екатеринбург": "Екатеринбург", "екатеринбурге": "Екатеринбург", "екб": "Екатеринбург",
    "казань": "Казань",
    "нижний": "Нижний Новгород",
    "краснодар": "Краснодар", "краснодаре": "Краснодар",
    "сочи": "Сочи",
    "владивосток": "Владивосток",
    "самара": "Самара",
    "уфа": "Уфа",
    "тюмень": "Тюмень",
    "ростов": "Ростов-на-Дону",
    "воронеж": "Воронеж",
    "пермь": "Пермь",
    "красноярск": "Красноярск",
}


def parse_price_value(value: str, unit: str) -> float:
    """Convert price string with unit to number."""
    num = float(value.replace(" ", "").replace(",", "."))
    if "млн" in unit:
        return num * 1_000_000
    elif "тыс" in unit:
        return num * 1_000
    return num


class AIAgent:
    """Rule-based NLU agent with expanded Russian language support."""

    def parse_query(self, text: str) -> tuple[SearchFilters, str]:
        """Parse natural language query into SearchFilters and action type."""
        text_lower = text.lower().strip()
        filters = SearchFilters(query_text=text)
        action = "search"

        # ── Detect action ────────────────────────────────────
        if re.search(r"сравн|разниц|сопостав", text_lower):
            action = "compare"
        elif re.search(r"аналитик|статистик|средн|динамик|тренд|цены на", text_lower):
            action = "analytics"
        elif re.search(r"рекоменд|подбер|посовет|что нового|новинк", text_lower):
            action = "recommend"
        elif re.search(r"сколько|количеств|объявлен", text_lower):
            action = "stats"

        # ── Parse property type ──────────────────────────────
        for keyword, ptype in PROPERTY_KEYWORDS.items():
            if keyword in text_lower:
                filters.property_type = ptype
                break

        # ── Parse deal type ──────────────────────────────────
        for keyword, dtype in DEAL_KEYWORDS.items():
            if keyword in text_lower:
                filters.deal_type = dtype
                break

        # ── Parse rooms ──────────────────────────────────────
        for pattern, extractor in ROOM_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                filters.rooms_min = extractor(match)
                filters.rooms_max = extractor(match)
                break

        # ── Parse price ──────────────────────────────────────
        # "от X до Y млн"
        m = re.search(r"от\s+(\d+[\d\s]*)\s*до\s*(\d+[\d\s]*)\s*(тыс|млн|руб)", text_lower)
        if m:
            filters.price_min = parse_price_value(m.group(1), m.group(3))
            filters.price_max = parse_price_value(m.group(2), m.group(3))
        else:
            # "до X млн"
            m = re.search(r"до\s+(\d+[\d\s]*)\s*(тыс|млн|руб)", text_lower)
            if m:
                filters.price_max = parse_price_value(m.group(1), m.group(2))
            else:
                # "X млн" (without до)
                m = re.search(r"(\d+)\s*млн", text_lower)
                if m and "от" not in text_lower:
                    filters.price_max = float(m.group(1)) * 1_000_000
                else:
                    # "до 5000000"
                    m = re.search(r"до\s+(\d{4,})", text_lower)
                    if m:
                        filters.price_max = float(m.group(1))
                    else:
                        # "от X тыс"
                        m = re.search(r"от\s+(\d+[\d\s]*)\s*(тыс|млн|руб)", text_lower)
                        if m:
                            filters.price_min = parse_price_value(m.group(1), m.group(2))

        # ── Parse area ───────────────────────────────────────
        m = re.search(r"от\s+(\d+)\s*м[²2]", text_lower)
        if m:
            filters.area_min = float(m.group(1))
        m = re.search(r"до\s+(\d+)\s*м[²2]", text_lower)
        if m:
            filters.area_max = float(m.group(1))

        # ── Parse floor ──────────────────────────────────────
        m = re.search(r"на\s+(\d+)\s*этаж", text_lower)
        if m:
            filters.floor_min = int(m.group(1))
            filters.floor_max = int(m.group(1))

        # ── Parse city (longest match first) ─────────────────
        for alias, city_name in sorted(CITY_ALIASES.items(), key=lambda x: -len(x[0])):
            if alias in text_lower:
                filters.city = city_name
                break

        # ── Parse district ───────────────────────────────────
        m = re.search(r"(\w+)\s+район", text_lower)
        if m:
            filters.district = m.group(1)

        return filters, action

    def format_response(self, action: str, data: dict, filters: SearchFilters) -> str:
        """Generate human-readable response."""
        if action == "search" or action == "recommend":
            return self._format_search(data, filters)
        elif action == "analytics":
            return self._format_analytics(data)
        elif action == "compare":
            return self._format_compare(data)
        elif action == "stats":
            return self._format_stats(data)
        return str(data)

    def _format_search(self, data: dict, filters: SearchFilters) -> str:
        items = data.get("items", [])
        total = data.get("total", 0)

        if not items:
            return "😕 Ничего не найдено. Попробуйте изменить параметры поиска."

        lines = [f"🏠 Найдено **{total}** объявлений:\n"]
        for i, item in enumerate(items[:10], 1):
            price = f"{item['price']:,.0f} ₽".replace(",", " ")
            if item.get("deal_type") == "rent":
                price += "/мес"

            rooms = "Студия" if item.get("property_type") == "studio" else (
                f"{item['rooms']}к" if item.get("rooms") is not None else item.get("property_type", "")
            )
            area = f", {item['area_m2']}м²" if item.get("area_m2") else ""
            floor = f", этаж {item['floor']}/{item['floors_total']}" if item.get("floor") else ""
            metro = f", 🚇 {item['metro_station']}" if item.get("metro_station") else ""

            lines.append(f"**{i}.** {rooms}{area}{floor} — **{price}**")
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
            lines.append(f"**{city}** — {info.get('total_listings', info.get('total', 0))} объявлений")
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
