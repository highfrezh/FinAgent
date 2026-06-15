from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class VendorCreate(BaseModel):
    name: str
    email: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    payment_terms_days: Optional[int] = 30
    categories: Optional[list[str]] = []


class VendorResponse(BaseModel):
    id: UUID
    name: str
    email: Optional[str]
    tax_id: Optional[str]
    is_active: bool
    is_verified: bool
    average_invoice_amount: float
    total_invoices: int
    total_spend: float
    payment_terms_days: int
    categories: list
    created_at: datetime

    class Config:
        from_attributes = True


class VendorUpdate(BaseModel):
    email: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    payment_terms_days: Optional[int] = None
    categories: Optional[list[str]] = None


class ValidationResult(BaseModel):
    is_valid: bool
    vendor_found: bool
    vendor_verified: bool
    flags: list[str] = []
    reasoning: str