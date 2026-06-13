import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, JSON, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from backend.db.base import Base


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    tax_id: Mapped[str] = mapped_column(String(100), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    average_invoice_amount: Mapped[float] = mapped_column(Float, default=0.0)
    total_invoices: Mapped[int] = mapped_column(default=0)
    total_spend: Mapped[float] = mapped_column(Float, default=0.0)

    payment_terms_days: Mapped[int] = mapped_column(default=30)
    categories: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="vendor"
    )

    def __repr__(self):
        return f"<Vendor {self.name} | verified={self.is_verified}>"