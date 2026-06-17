from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class VendorSpend(BaseModel):
    vendor_name: str
    total_spend: float
    invoice_count: int
    average_amount: float
    flagged_count: int


class MonthlySpend(BaseModel):
    month: str
    total_spend: float
    invoice_count: int
    flagged_count: int


class StatusSummary(BaseModel):
    total_invoices: int
    valid: int
    flagged: int
    rejected: int
    approved: int
    pending: int
    processing: int


class AnomalySummary(BaseModel):
    total_anomalies: int
    high_velocity_count: int
    duplicate_amount_count: int
    amount_spike_count: int
    round_number_count: int
    off_hours_count: int


class UpcomingPayment(BaseModel):
    invoice_id: str
    vendor_name: str
    amount: float
    currency: str
    due_date: datetime
    days_until_due: int


class FinanceReport(BaseModel):
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    status_summary: StatusSummary
    total_spend: float
    top_vendors: list[VendorSpend]
    monthly_spend: list[MonthlySpend]
    anomaly_summary: AnomalySummary
    upcoming_payments: list[UpcomingPayment]
    narrative: str
    recommendations: list[str]