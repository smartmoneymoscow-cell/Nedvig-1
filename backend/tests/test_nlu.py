"""NLU Agent tests — the most critical test file.

Tests the rule-based natural language understanding for real estate queries.
Each test case: input string → expected filters dict.
"""

import pytest
from app.ai.agent import AIAgent, CITY_ALIASES
from app.models.listing import PropertyType, DealType


@pytest.fixture
def agent():
    return AIAgent()


# ═══════════════════════════════════════
# ROOMS
# ═══════════════════════════════════════

class TestRoomParsing:
    """Test room count extraction from natural language."""

    @pytest.mark.parametrize("query,expected", [
        ("двушка в Москве", 2),
        ("двухкомнатная квартира", 2),
        ("2-комнатная", 2),
        ("2к квартира", 2),
        ("2 комнатная", 2),
        ("2х комнатная", 2),
    ])
    def test_two_rooms(self, agent, query, expected):
        filters, _ = agent.parse_query(query)
        assert filters.rooms_min == expected
        assert filters.rooms_max == expected

    @pytest.mark.parametrize("query,expected", [
        ("однушка", 1),
        ("однокомнатная", 1),
        ("1-комнатная", 1),
        ("1к", 1),
    ])
    def test_one_room(self, agent, query, expected):
        filters, _ = agent.parse_query(query)
        assert filters.rooms_min == expected

    @pytest.mark.parametrize("query,expected", [
        ("трёшка", 3),
        ("трешка", 3),
        ("трёхкомнатная", 3),
        ("3-комнатная", 3),
        ("3к", 3),
    ])
    def test_three_rooms(self, agent, query, expected):
        filters, _ = agent.parse_query(query)
        assert filters.rooms_min == expected

    @pytest.mark.parametrize("query", [
        ("студия"),
        ("студия в Москве"),
        ("студию снять"),
    ])
    def test_studio(self, agent, query):
        filters, _ = agent.parse_query(query)
        assert filters.rooms_min == 0
        assert filters.rooms_max == 0

    def test_four_rooms(self, agent):
        filters, _ = agent.parse_query("четырёхкомнатная квартира")
        assert filters.rooms_min == 4

    def test_five_rooms(self, agent):
        filters, _ = agent.parse_query("пятикомнатная квартира")
        assert filters.rooms_min == 5


# ═══════════════════════════════════════
# PRICE
# ═══════════════════════════════════════

class TestPriceParsing:
    """Test price extraction from natural language."""

    def test_price_max_mln(self, agent):
        filters, _ = agent.parse_query("до 10 млн")
        assert filters.price_max == 10_000_000

    def test_price_max_thousand(self, agent):
        filters, _ = agent.parse_query("до 500 тыс")
        assert filters.price_max == 500_000

    def test_price_range_mln(self, agent):
        filters, _ = agent.parse_query("от 5 до 15 млн")
        assert filters.price_min == 5_000_000
        assert filters.price_max == 15_000_000

    def test_price_max_raw_number(self, agent):
        filters, _ = agent.parse_query("до 5000000")
        assert filters.price_max == 5_000_000

    def test_price_implicit_max_mln(self, agent):
        """'5 млн' without 'до' should set price_max."""
        filters, _ = agent.parse_query("квартира 5 млн")
        assert filters.price_max == 5_000_000

    def test_price_min_only(self, agent):
        filters, _ = agent.parse_query("от 3 млн")
        assert filters.price_min == 3_000_000
        assert filters.price_max is None

    def test_price_with_spaces(self, agent):
        """Numbers with spaces: '10 000 000'."""
        filters, _ = agent.parse_query("до 10 000 тыс")
        assert filters.price_max == 10_000_000


# ═══════════════════════════════════════
# CITY
# ═══════════════════════════════════════

class TestCityParsing:
    """Test city extraction from natural language."""

    @pytest.mark.parametrize("query,expected", [
        ("в Москве", "Москва"),
        ("в москве", "Москва"),
        ("в мск", "Москва"),
        ("квартира москва", "Москва"),
    ])
    def test_moscow(self, agent, query, expected):
        filters, _ = agent.parse_query(query)
        assert filters.city == expected

    @pytest.mark.parametrize("query,expected", [
        ("в Питере", "Санкт-Петербург"),
        ("в СПб", "Санкт-Петербург"),
        ("в Петербурге", "Санкт-Петербург"),
        ("в спб", "Санкт-Петербург"),
    ])
    def test_spb(self, agent, query, expected):
        filters, _ = agent.parse_query(query)
        assert filters.city == expected

    def test_ekaterinburg(self, agent):
        filters, _ = agent.parse_query("в Екб")
        assert filters.city == "Екатеринбург"

    def test_novosibirsk(self, agent):
        filters, _ = agent.parse_query("в Нск")
        assert filters.city == "Новосибирск"

    def test_krasnodar(self, agent):
        filters, _ = agent.parse_query("в Краснодаре")
        assert filters.city == "Краснодар"

    def test_sochi(self, agent):
        filters, _ = agent.parse_query("дом в Сочи")
        assert filters.city == "Сочи"

    def test_city_not_mentioned(self, agent):
        filters, _ = agent.parse_query("квартира до 10 млн")
        assert filters.city is None


# ═══════════════════════════════════════
# PROPERTY TYPE
# ═══════════════════════════════════════

class TestPropertyTypeParsing:

    def test_apartment(self, agent):
        filters, _ = agent.parse_query("квартира в Москве")
        assert filters.property_type == PropertyType.APARTMENT

    def test_studio(self, agent):
        filters, _ = agent.parse_query("студия")
        assert filters.property_type == PropertyType.STUDIO

    def test_house(self, agent):
        filters, _ = agent.parse_query("дом в Сочи")
        assert filters.property_type == PropertyType.HOUSE

    def test_land(self, agent):
        filters, _ = agent.parse_query("участок 10 соток")
        assert filters.property_type == PropertyType.LAND

    def test_commercial(self, agent):
        filters, _ = agent.parse_query("офис в аренду")
        assert filters.property_type == PropertyType.COMMERCIAL


# ═══════════════════════════════════════
# DEAL TYPE
# ═══════════════════════════════════════

class TestDealTypeParsing:

    @pytest.mark.parametrize("query", [
        "купить квартиру",
        "продажа",
        "в продаже",
        "покупка",
    ])
    def test_sale(self, agent, query):
        filters, _ = agent.parse_query(query)
        assert filters.deal_type == DealType.SALE

    @pytest.mark.parametrize("query", [
        "снять квартиру",
        "в аренду",
        "аренда",
        "сниму",
        "студию снять",
    ])
    def test_rent(self, agent, query):
        filters, _ = agent.parse_query(query)
        assert filters.deal_type == DealType.RENT


# ═══════════════════════════════════════
# ACTION DETECTION
# ═══════════════════════════════════════

class TestActionDetection:

    def test_search_default(self, agent):
        _, action = agent.parse_query("квартира в Москве")
        assert action == "search"

    def test_compare(self, agent):
        _, action = agent.parse_query("сравни цены в Москве и Питере")
        assert action == "compare"

    def test_analytics(self, agent):
        _, action = agent.parse_query("аналитика по Краснодару")
        assert action == "analytics"

    def test_stats(self, agent):
        _, action = agent.parse_query("сколько объявлений")
        assert action == "stats"

    def test_recommend(self, agent):
        _, action = agent.parse_query("посоветуй квартиру")
        assert action == "recommend"


# ═══════════════════════════════════════
# AREA
# ═══════════════════════════════════════

class TestAreaParsing:

    def test_area_min(self, agent):
        filters, _ = agent.parse_query("от 50 м²")
        assert filters.area_min == 50.0

    def test_area_max(self, agent):
        filters, _ = agent.parse_query("до 100 м²")
        assert filters.area_max == 100.0

    def test_area_range(self, agent):
        filters, _ = agent.parse_query("от 50 до 100 м²")
        assert filters.area_min == 50.0
        assert filters.area_max == 100.0


# ═══════════════════════════════════════
# COMBO — real-world queries
# ═══════════════════════════════════════

class TestCombinedQueries:
    """Test realistic multi-parameter queries."""

    def test_typical_buy_query(self, agent):
        filters, action = agent.parse_query("двушка в Москве до 15 млн")
        assert action == "search"
        assert filters.rooms_min == 2
        assert filters.city == "Москва"
        assert filters.price_max == 15_000_000
        # Note: "двушка" sets rooms, not property_type
        assert filters.property_type is None

    def test_rent_studio(self, agent):
        filters, action = agent.parse_query("студия в Питере в аренду")
        assert filters.rooms_min == 0
        assert filters.city == "Санкт-Петербург"
        assert filters.deal_type == DealType.RENT
        assert filters.property_type == PropertyType.STUDIO

    def test_house_in_sochi(self, agent):
        filters, action = agent.parse_query("дом в Сочи до 30 млн")
        assert filters.property_type == PropertyType.HOUSE
        assert filters.city == "Сочи"
        assert filters.price_max == 30_000_000

    def test_compare_cities(self, agent):
        _, action = agent.parse_query("сравни цены в Москве и Питере")
        assert action == "compare"

    def test_analytics_with_city(self, agent):
        filters, action = agent.parse_query("аналитика по Краснодару")
        assert action == "analytics"
        assert filters.city == "Краснодар"

    def test_three_room_in_ekb(self, agent):
        filters, _ = agent.parse_query("трёшка в Екб до 10 млн")
        assert filters.rooms_min == 3
        assert filters.city == "Екатеринбург"
        assert filters.price_max == 10_000_000


# ═══════════════════════════════════════
# CITY ALIASES — completeness
# ═══════════════════════════════════════

class TestCityAliases:
    """Verify all expected city aliases exist."""

    def test_all_major_cities_have_aliases(self):
        expected_cities = {
            "Москва", "Санкт-Петербург", "Новосибирск",
            "Екатеринбург", "Казань", "Краснодар", "Сочи",
        }
        actual_cities = set(CITY_ALIASES.values())
        for city in expected_cities:
            assert city in actual_cities, f"Missing city: {city}"

    def test_no_duplicate_aliases(self):
        aliases = list(CITY_ALIASES.keys())
        assert len(aliases) == len(set(aliases)), "Duplicate aliases found"
