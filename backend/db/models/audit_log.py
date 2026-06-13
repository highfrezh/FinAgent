import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from backend.db.base import Base
import enum


class AuditAction(str, enum.Enum):
    INGESTED = "ingested"
    VALIDATED = "validated"
    FLAGGED = "flagged"
    ANOMALY_DETECTED = "anomaly_detected"
    HUMAN_APPROVED = "human_approved"
    HUMAN_REJECTED = "human_rejected"
    REPORT_GENERATED = "report_generated"
    ERROR = "error"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True
    )

    agent_name: Mapped[str] = mapped_column(String(100))
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction))
    reasoning: Mapped[str] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    performed_by: Mapped[str] = mapped_column(String(100), default="system")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.agent_name} → {self.action} @ {self.created_at}>"