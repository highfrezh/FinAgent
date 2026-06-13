import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, JSON, Enum, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from backend.db.base import Base
import enum


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    VALID = "valid"
    FLAGGED = "flagged"
    REJECTED = "rejected"
    APPROVED = "approved"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=True)

    invoice_number: Mapped[str] = mapped_column(String(100), nullable=True)
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True
    )
    amount: Mapped[float] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    invoice_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    due_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    line_items: Mapped[dict] = mapped_column(JSON, default=list)

    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus), default=InvoiceStatus.PENDING
    )
    validation_result: Mapped[dict] = mapped_column(JSON, nullable=True)
    anomaly_flags: Mapped[dict] = mapped_column(JSON, default=list)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)

    embedding: Mapped[list] = mapped_column(Vector(1536), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="invoices")
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="invoice"
    )

    def __repr__(self):
        return f"<Invoice {self.invoice_number} | {self.vendor_name} | ${self.amount} | {self.status}>"