"""Tests for AI agent NLU parsing and response formatting."""

import pytest
from app.ai.agent import AIAgent
from app.services.search import SearchFilters
from app.models.listing import PropertyType, DealType


class TestAIAgentParsing:
    """Unit tests for natural language understanding."""

    def setup_method(self):
        self.agent = AIAgent()

    # --- Action detection ---

    def test_search_default(self):
        _, action = self.agent.parse_query("привет")
        assert action == "search"

    def test_analytics(self):
        _, action = self.agent.parse_query("средние цены в Москве")
        assert action == "analytics"

    def test_analytics_statistics(self):
        _, action = self.agent.parse_query("статистика по Краснодару")
        assert action == "analytics"

    def test_compare(self):
        _, action = self.agent.parse_query("сравни Москву и Питер")
        assert action == "compare"

    def test_stats(self):
        _, action = self.agent.parse_query("сколько объявлений")
        assert action == "stats"

    # --- Property type ---

    def test_apartment(self):
        filters, _ = self.agent.parse_query("квартира в Москве")
        assert filters.property_type == PropertyType.APARTMENT

    def test_studio(self):
        filters, _ = self.agent.parse_query("студия в Питере")
        assert filters.property_type == PropertyType.STUDIO

    def test_house(self):
        filters, _ = self.agent.parse_query("дом в Краснодаре")
        assert filters.property_type == PropertyType.HOUSE

    def test_land(self):
        filters, _ = self.agent.parse_query("земельный участок")
        assert filters.property_type == PropertyType.LAND

    def test_commercial(self):
        filters, _ = self.agent.parse_query("офис в Москве")
        assert filters.property_type == PropertyType.COMMERCIAL

    # --- Deal type ---

    def test_sale(self):
        filters, _ = self.agent.parse_query("купить квартиру")
        assert filters.deal_type == DealType.SALE

    def test_rent(self):
        filters, _ = self.agent.parse_query("снять квартиру")
        assert filters.deal_type == DealType.RENT

    def test_rent_arenda(self):
        filters, _ = self.agent.parse_query("аренда студии")
        assert filters.deal_type == DealType.RENT

    # --- Rooms ---

    def test_rooms_digit(self):
        filters, _ = self.agent.parse_query("3-комнатная квартира")
        assert filters.rooms_min == 3
        assert filters.rooms_max == 3

    def test_rooms_studio(self):
        filters, _ = self.agent.parse_query("студия")
        assert filters.rooms_min == 0

    def test_rooms_odnushka(self):
        filters, _ = self.agent.parse_query("однушка в Москве")
        assert filters.rooms_min == 1

    def test_rooms_dvushka(self):
        filters, _ = self.agent.parse_query("двушка до 10 млн")
        assert filters.rooms_min == 2

    def test_rooms_treshka(self):
        filters, _ = self.agent.parse_query("трёшка в Питере")
        assert filters.rooms_min == 3

    # --- Price ---

    def test_price_max_mln(self):
        filters, _ = self.agent.parse_query("до 10 млн")
        assert filters.price_max == 10_000_000

    def test_price_range_mln(self):
        filters, _ = self.agent.parse_query("от 5 до 15 млн")
        assert filters.price_min == 5_000_000
        assert filters.price_max == 15_000_000

    def test_price_max_raw(self):
        filters, _ = self.agent.parse_query("до 5000000")
        assert filters.price_max == 5_000_000

    def test_price_mln_without_do(self):
        filters, _ = self.agent.parse_query("10 млн")
        assert filters.price_max == 10_000_000

    # --- City ---

    def test_city_moscow(self):
        filters, _ = self.agent.parse_query("квартира в Москве")
        assert filters.city == "Москва"

    def test_city_piter(self):
        filters, _ = self.agent.parse_query("студия в Питере")
        assert filters.city == "Санкт-Петербург"

    def test_city_spb(self):
        filters, _ = self.agent.parse_query("квартира в СПБ")
        assert filters.city == "Санкт-Петербург"

    def test_city_msk(self):
        filters, _ = self.agent.parse_query("квартира в МСК")
        assert filters.city == "Москва"

    def test_city_krasnodar(self):
        filters, _ = self.agent.parse_query("дом в Краснодаре")
        assert filters.city == "Краснодар"

    # --- Area ---

    def test_area_range(self):
        filters, _ = self.agent.parse_query("от 50 до 100 м²")
        assert filters.area_min == 50
        assert filters.area_max == 100

    def test_area_min(self):
        filters, _ = self.agent.parse_query("от 30 м²")
        assert filters.area_min == 30

    def test_area_max(self):
        filters, _ = self.agent.parse_query("до 80 м²")
        assert filters.area_max == 80

    # --- Floor ---

    def test_floor(self):
        filters, _ = self.agent.parse_query("на 5 этаже")
        assert filters.floor_min == 5
        assert filters.floor_max == 5

    # --- Combined ---

    def test_combined_query(self):
        filters, action = self.agent.parse_query("2-комнатная квартира в Москве до 10 млн")
        assert action == "search"
        assert filters.city == "Москва"
        assert filters.rooms_min == 2
        assert filters.price_max == 10_000_000
        assert filters.property_type == PropertyType.APARTMENT

    def test_rent_studio_piter(self):
        filters, action = self.agent.parse_query("студия в аренду в Питере")
        assert filters.deal_type == DealType.RENT
        assert filters.property_type == PropertyType.STUDIO
        assert filters.city == "Санкт-Петербург"


class TestAIAgentFormatting:
    """Unit tests for response formatting."""

    def setup_method(self):
        self.agent = AIAgent()

    def test_format_search_empty(self):
        result = self.agent.format_response(
            "search", {"items": [], "total": 0}, SearchFilters()
        )
        assert "Ничего не найдено" in result

    def test_format_search_with_items(self):
        data = {
            "total": 2,
            "items": [
                {
                    "price": 5000000, "property_type": "apartment",
                    "deal_type": "sale", "rooms": 2, "area_m2": 50,
                    "floor": 5, "floors_total": 10, "city": "Москва",
                    "address": "ул. Пушкина", "metro_station": "",
                },
                {
                    "price": 8000000, "property_type": "apartment",
                    "deal_type": "sale", "rooms": 3, "area_m2": 80,
                    "floor": 3, "floors_total": 9, "city": "Москва",
                    "address": "ул. Лермонтова", "metro_station": "",
                },
            ],
        }
        result = self.agent.format_response("search", data, SearchFilters())
        assert "Найдено" in result
        assert "5 000 000" in result

    def test_format_analytics_empty(self):
        result = self.agent.format_response("analytics", {"analytics": []}, SearchFilters())
        assert "Нет данных" in result

    def test_format_stats(self):
        data = {
            "total": 100,
            "by_city": {"Москва": 50, "Питер": 30},
            "by_source": {"cian": 40, "domclick": 60},
        }
        result = self.agent.format_response("stats", data, SearchFilters())
        assert "100" in result
        assert "Москва" in result
        assert "cian" in result

    def test_format_compare_empty(self):
        result = self.agent.format_response("compare", {"comparison": {}}, SearchFilters())
        assert "Нет данных" in result

    def test_format_compare_with_data(self):
        data = {
            "comparison": {
                "Москва": {
                    "total_listings": 50,
                    "analytics": [
                        {"property_type": "apartment", "avg_price": 10000000, "avg_price_per_m2": 200000}
                    ],
                },
                "Санкт-Петербург": {
                    "total_listings": 30,
                    "analytics": [
                        {"property_type": "apartment", "avg_price": 7000000, "avg_price_per_m2": 150000}
                    ],
                },
            }
        }
        result = self.agent.format_response("compare", data, SearchFilters())
        assert "Москва" in result
        assert "Санкт-Петербург" in result
