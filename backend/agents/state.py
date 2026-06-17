from typing import TypedDict, Optional
from uuid import UUID


class InvoiceState(TypedDict):
    """
    The state object that flows through the entire agent graph.
    Every agent reads from and writes to this object.
    """
    # Invoice identification
    invoice_id: Optional[str]
    file_bytes: Optional[bytes]
    filename: Optional[str]
    raw_text: Optional[str]

    # Extracted data
    vendor_name: Optional[str]
    invoice_number: Optional[str]
    amount: Optional[float]
    currency: Optional[str]

    # Processing results
    ingestion_complete: bool
    validation_complete: bool
    anomaly_complete: bool

    # Decisions
    is_valid: bool
    is_anomalous: bool
    requires_human_review: bool

    # Flags and reasoning
    validation_flags: list[str]
    anomaly_flags: list[str]
    reasoning: list[str]

    # Error tracking
    error: Optional[str]
    current_agent: Optional[str]