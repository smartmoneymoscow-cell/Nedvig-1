"""AI Agent — parses natural language into search filters, generates responses."""

import re
from typing import Optional
from app.services.search import SearchFilters
from app.models.listing import PropertyType, DealType

# Keyword mappings for Russian real estate queries
PROPERTY_KEYWORDS = {
    "квартира": PropertyType.APARTMENT,
    "кв": PropertyType.APARTMENT,
    "комнат": PropertyType.APARTMENT,
    "комната": PropertyType.APARTMENT,
    "студия": PropertyType.STUDIO,
    "студи": PropertyType.STUDIO,
    "дом": PropertyType.HOUSE,
    "коттедж": PropertyType.HOUSE,
    "таунхаус": PropertyType.HOUSE,
    "земля": PropertyType.LAND,
    "участок": PropertyType.LAND,
    "коммерческ": PropertyType.COMMERCIAL,
    "офис": PropertyType.COMMERCIAL,
    "магазин": PropertyType.COMMERCIAL,
    "кладовк": PropertyType.ROOM,
    "комната": PropertyType.ROOM,
}

DEAL_KEYWORDS = {
    "аренда": DealType.RENT,
    "снять": DealType.RENT,
    "сниму": DealType.RENT,
    "арендовать": DealType.RENT,
    "продажа": DealType.SALE,
    "купить": DealType.SALE,
    "куплю": DealType.SALE,
    "прода": DealType.SALE,
}

ROOM_PATTERNS = [
    (r"(\d+)\s*[-–]?\s*комн", lambda m: int(m.group(1))),
    (r"(\d)\s*[-–]?\s*к\b", lambda m: int(m.group(1))),
    (r"студия", lambda m: 0),
    (r"однушк", lambda m: 1),
    (r"двушк", lambda m: 2),
    (r"трёшк|трешк", lambda m: 3),
    (r"четырёхкомн|четырехкомн", lambda m: 4),
]

PRICE_PATTERNS = [
    # "до 5 млн", "от 3 до 7 млн"
    (r"от\s+(\d+[\d\s]*)\s*(тыс|млн|руб)", "min"),
    (r"до\s+(\d+[\d\s]*)\s*(тыс|млн|руб)", "max"),
    (r"(\d+[\d\s]*)\s*[-–]\s*(\d+[\d\s]*)\s*(тыс|млн|руб)", "range"),
    # "5млн", "300тыс"
    (r"(\d+)\s*млн", "max_mln"),
    (r"(\d+)\s*тыс", "max_thousand"),
    # "5000000" raw number
    (r"до\s+(\d{4,})", "max_raw"),
    (r"от\s+(\d{4,})", "min_raw"),
]

CITY_ALIASES = {
    "москва": "Москва",
    "мск": "Москва",
    "питер": "Санкт-Петербург",
    "спб": "Санкт-Петербург",
    "петербург": "Санкт-Петербург",
    "новосибирск": "Новосибирск",
    "екатеринбург": "Екатеринбург",
    "казань": "Казань",
    "нижний": "Нижний Новгород",
    "краснодар": "Краснодар",
    "сочи": "Сочи",
    "владивосток": "Владивосток",
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
    """Simple rule-based NLU agent. Can be upgraded to LLM later."""

    def parse_query(self, text: str) -> tuple[SearchFilters, str]:
        """Parse natural language query into SearchFilters and action type."""
        text_lower = text.lower().strip()
        filters = SearchFilters(query_text=text)
        action = "search"  # search | analytics | compare | recommend

        # Detect action
        if any(w in text_lower for w in ["сравн", "сравни", "разниц"]):
            action = "compare"
        elif any(w in text_lower for w in ["аналитик", "статистик", "средн", "цены на", "динамик"]):
            action = "analytics"
        elif any(w in text_lower for w in ["рекоменд", "подбер", "посовет", "что нового"]):
            action = "recommend"

        # Parse property type
        for keyword, ptype in PROPERTY_KEYWORDS.items():
            if keyword in text_lower:
                filters.property_type = ptype
                break

        # Parse deal type
        for keyword, dtype in DEAL_KEYWORDS.items():
            if keyword in text_lower:
                filters.deal_type = dtype
                break

        # Parse rooms
        for pattern, extractor in ROOM_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                filters.rooms_min = extractor(match)
                filters.rooms_max = extractor(match)
                break

        # Parse price
        for pattern, ptype in PRICE_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                groups = match.groups()
                if ptype == "min":
                    filters.price_min = parse_price_value(groups[0], groups[1])
                elif ptype == "max":
                    filters.price_max = parse_price_value(groups[0], groups[1])
                elif ptype == "range":
                    filters.price_min = parse_price_value(groups[0], groups[2])
                    filters.price_max = parse_price_value(groups[1], groups[2])
                elif ptype == "max_mln":
                    filters.price_max = float(groups[0]) * 1_000_000
                elif ptype == "max_thousand":
                    filters.price_max = float(groups[0]) * 1_000
                elif ptype == "max_raw":
                    filters.price_max = float(groups[0])
                elif ptype == "min_raw":
                    filters.price_min = float(groups[0])
                break

        # Parse city
        for alias, city_name in CITY_ALIASES.items():
            if alias in text_lower:
                filters.city = city_name
                break

        # Parse district
        district_match = re.search(r"(?:в\s+)?(\w+\s+район)", text_lower)
        if district_match:
            filters.district = district_match.group(1)

        return filters, action

    def format_response(self, action: str, data: dict, filters: SearchFilters) -> str:
        """Generate human-readable response."""
        if action == "search":
            return self._format_search(data, filters)
        elif action == "analytics":
            return self._format_analytics(data)
        elif action == "compare":
            return self._format_compare(data)
        elif action == "recommend":
            return self._format_search(data, filters)
        return str(data)

    def _format_search(self, data: dict, filters: SearchFilters) -> str:
        items = data.get("items", [])
        total = data.get("total", 0)

        if not items:
            return f"😕 Ничего не найдено. Попробуйте изменить параметры поиска."

        lines = [f"🏠 Найдено **{total}** объявлений:\n"]
        for i, item in enumerate(items[:10], 1):
            price = f"{item['price']:,.0f} {item.get('currency', 'RUB')}".replace(",", " ")
            rooms = f"{item['rooms']}к" if item.get('rooms') else "студия"
            area = f", {item['area_m2']}м²" if item.get('area_m2') else ""
            floor = f", этаж {item['floor']}/{item['floors_total']}" if item.get('floor') else ""

            lines.append(
                f"**{i}.** {rooms}{area}{floor} — **{price}**\n"
                f"   📍 {item.get('city', '')}, {item.get('address', '')}\n"
                f"   🔗 {item.get('source_url', '')}"
            )

        if total > 10:
            lines.append(f"\n... и ещё {total - 10} объявлений. Уточните запрос для сужения.")

        return "\n".join(lines)

    def _format_analytics(self, data: dict) -> str:
        analytics = data.get("analytics", [])
        if not analytics:
            return "📊 Нет данных для аналитики."

        city = data.get("city", "все города")
        lines = [f"📊 Аналитика по {city or 'всем городам'}:\n"]

        for item in analytics:
            deal = "Продажа" if item["deal_type"] == "sale" else "Аренда"
            ptype = item["property_type"] or "—"
            avg = f"{item['avg_price']:,.0f}".replace(",", " ") if item.get('avg_price') else "—"
            per_m2 = f"{item['avg_price_per_m2']:,.0f}".replace(",", " ") if item.get('avg_price_per_m2') else "—"

            lines.append(
                f"**{deal} / {ptype}** ({item['count']} шт.)\n"
                f"  Средняя цена: {avg} ₽\n"
                f"  За м²: {per_m2} ₽\n"
                f"  Диапазон: {item.get('min_price', 0):,.0f} – {item.get('max_price', 0):,.0f} ₽"
            )

        return "\n".join(lines)

    def _format_compare(self, data: dict) -> str:
        comparison = data.get("comparison", {})
        if not comparison:
            return "📊 Нет данных для сравнения."

        lines = ["📊 Сравнение:\n"]
        for city, info in comparison.items():
            lines.append(f"**{city}** — {info['total_listings']} объявлений")
            for a in info.get("analytics", []):
                avg = f"{a['avg_price']:,.0f}".replace(",", " ") if a.get('avg_price') else "—"
                per_m2 = f"{a['avg_price_per_m2']:,.0f}".replace(",", " ") if a.get('avg_price_per_m2') else "—"
                lines.append(f"  {a['property_type']}: ср. {avg} ₽ ({per_m2} ₽/м²)")
            lines.append("")

        return "\n".join(lines)
