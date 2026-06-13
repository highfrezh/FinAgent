from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    total: float


class InvoiceExtracted(BaseModel):
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = "USD"
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    line_items: Optional[list[LineItem]] = []


class InvoiceUploadResponse(BaseModel):
    id: UUID
    invoice_number: Optional[str]
    vendor_name: Optional[str]
    amount: Optional[float]
    currency: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    total: int
    invoices: list[InvoiceUploadResponse]