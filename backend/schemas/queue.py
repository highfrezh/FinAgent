from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class QueueItem(BaseModel):
    id: UUID
    invoice_number: Optional[str]
    vendor_name: Optional[str]
    amount: Optional[float]
    currency: Optional[str]
    status: str
    validation_result: Optional[dict]
    anomaly_flags: Optional[list]
    anomaly_score: Optional[float]
    created_at: datetime
    file_name: Optional[str]

    class Config:
        from_attributes = True


class QueueListResponse(BaseModel):
    total: int
    items: list[QueueItem]


class ApprovalRequest(BaseModel):
    approved_by: str
    comment: Optional[str] = None


class RejectionRequest(BaseModel):
    rejected_by: str
    reason: str


class QueueActionResponse(BaseModel):
    invoice_id: str
    action: str
    performed_by: str
    comment: Optional[str]
    new_status: str
    actioned_at: datetime