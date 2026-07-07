"""Tests for ingestion pipeline and normalizer."""

import pytest
from app.services.ingestion import Normalizer, Deduplicator
from app.scrapers.base import ScrapedItem


class TestNormalizer:
    """Unit tests for data normalization."""

    def test_normalize_price_rub(self):
        assert Normalizer.normalize_price(100, "RUB") == 100

    def test_normalize_price_usd(self):
        assert Normalizer.normalize_price(100, "USD") == 9000

    def test_normalize_price_eur(self):
        assert Normalizer.normalize_price(100, "EUR") == 10000

    def test_normalize_price_negative(self):
        assert Normalizer.normalize_price(-100, "RUB") == 100

    def test_normalize_price_zero(self):
        assert Normalizer.normalize_price(0, "RUB") == 0

    def test_normalize_address_whitespace(self):
        assert Normalizer.normalize_address("  ул.   Пушкина  ") == "ул. Пушкина"

    def test_normalize_address_commas(self):
        assert Normalizer.normalize_address(", Москва, ") == "Москва"

    def test_normalize_address_empty(self):
        assert Normalizer.normalize_address("") == ""

    def test_normalize_city_lowercase(self):
        assert Normalizer.normalize_city("москва") == "Москва"

    def test_normalize_city_english(self):
        assert Normalizer.normalize_city("moscow") == "Москва"

    def test_normalize_city_slang(self):
        assert Normalizer.normalize_city("спб") == "Санкт-Петербург"
        assert Normalizer.normalize_city("питер") == "Санкт-Петербург"

    def test_normalize_city_unknown(self):
        assert Normalizer.normalize_city("Неизвестный") == "Неизвестный"

    def test_validate_valid_item(self):
        item = ScrapedItem(
            source="test", source_id="1", source_url="http://",
            property_type="apartment", deal_type="sale",
            price=100, address="addr", city="Москва",
        )
        assert Normalizer.validate(item) is True

    def test_validate_no_price(self):
        item = ScrapedItem(
            source="test", source_id="1", source_url="http://",
            property_type="apartment", deal_type="sale",
            price=0, address="addr", city="Москва",
        )
        assert Normalizer.validate(item) is False

    def test_validate_negative_price(self):
        item = ScrapedItem(
            source="test", source_id="1", source_url="http://",
            property_type="apartment", deal_type="sale",
            price=-100, address="addr", city="Москва",
        )
        assert Normalizer.validate(item) is False

    def test_validate_no_city(self):
        item = ScrapedItem(
            source="test", source_id="1", source_url="http://",
            property_type="apartment", deal_type="sale",
            price=100, address="addr", city="",
        )
        assert Normalizer.validate(item) is False

    def test_validate_no_address_no_description(self):
        item = ScrapedItem(
            source="test", source_id="1", source_url="http://",
            property_type="apartment", deal_type="sale",
            price=100, address="", city="Москва",
        )
        assert Normalizer.validate(item) is False


class TestDeduplicator:
    """Unit tests for deduplication logic."""

    def test_source_hash_deterministic(self):
        h1 = Deduplicator.make_source_hash("cian", "123", 100, "addr")
        h2 = Deduplicator.make_source_hash("cian", "123", 100, "addr")
        assert h1 == h2

    def test_source_hash_different_source_id(self):
        h1 = Deduplicator.make_source_hash("cian", "123", 100, "addr")
        h2 = Deduplicator.make_source_hash("cian", "124", 100, "addr")
        assert h1 != h2

    def test_source_hash_different_source(self):
        h1 = Deduplicator.make_source_hash("cian", "123", 100, "addr")
        h2 = Deduplicator.make_source_hash("avito", "123", 100, "addr")
        assert h1 != h2

    def test_content_hash_deterministic(self):
        h1 = Deduplicator.make_content_hash("Москва", "addr", 50.0, 2, 5000000)
        h2 = Deduplicator.make_content_hash("Москва", "addr", 50.0, 2, 5000000)
        assert h1 == h2

    def test_content_hash_different_price(self):
        h1 = Deduplicator.make_content_hash("Москва", "addr", 50.0, 2, 5000000)
        h2 = Deduplicator.make_content_hash("Москва", "addr", 50.0, 2, 6000000)
        assert h1 != h2

    def test_content_hash_different_city(self):
        h1 = Deduplicator.make_content_hash("Москва", "addr", 50.0, 2, 5000000)
        h2 = Deduplicator.make_content_hash("Питер", "addr", 50.0, 2, 5000000)
        assert h1 != h2

    def test_hash_length(self):
        h = Deduplicator.make_source_hash("cian", "123", 100, "addr")
        assert len(h) == 16
