import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, Numeric, Boolean, DateTime, Enum, Index, func, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.database import Base


class PropertyType(str, enum.Enum):
    APARTMENT = "apartment"
    HOUSE = "house"
    COMMERCIAL = "commercial"
    LAND = "land"
    ROOM = "room"
    STUDIO = "studio"


class DealType(str, enum.Enum):
    SALE = "sale"
    RENT = "rent"


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Source
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Type
    property_type: Mapped[PropertyType] = mapped_column(Enum(PropertyType), nullable=False, index=True)
    deal_type: Mapped[DealType] = mapped_column(Enum(DealType), nullable=False, index=True)

    # Price
    price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")

    # Specs
    area_m2: Mapped[float] = mapped_column(Float, nullable=True)
    rooms: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floors_total: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Location
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    district: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Content
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    images: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    features: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)

    # Embedding for semantic search (stored as JSON array in MVP, migrate to pgvector later)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Meta
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Composite indexes for common queries
    __table_args__ = (
        Index("ix_listings_source_source_id", "source", "source_id", unique=True),
        Index("ix_listings_city_deal_type", "city", "deal_type"),
        Index("ix_listings_price_range", "price", "deal_type"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "source": self.source,
            "source_url": self.source_url,
            "property_type": self.property_type.value if self.property_type else None,
            "deal_type": self.deal_type.value if self.deal_type else None,
            "price": self.price,
            "currency": self.currency,
            "area_m2": self.area_m2,
            "rooms": self.rooms,
            "floor": self.floor,
            "floors_total": self.floors_total,
            "address": self.address,
            "district": self.district,
            "city": self.city,
            "region": self.region,
            "lat": self.lat,
            "lon": self.lon,
            "description": self.description,
            "images": self.images,
            "features": self.features,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
        }
