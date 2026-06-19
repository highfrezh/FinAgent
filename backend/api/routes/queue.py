from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.database import get_db
from backend.db.models.invoice import Invoice, InvoiceStatus
from backend.db.models.audit_log import AuditLog, AuditAction
from backend.db.models.vendor import Vendor
from backend.schemas.queue import (
    QueueListResponse, QueueItem,
    ApprovalRequest, RejectionRequest,
    QueueActionResponse
)
from backend.services.vendor_service import update_vendor_stats
from backend.core.logging import logger

router = APIRouter()


@router.get("/", response_model=QueueListResponse)
async def get_queue(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all invoices waiting for human review.
    These are invoices flagged by agents that need approval.
    """
    count_result = await db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.status == InvoiceStatus.FLAGGED)
    )
    total = count_result.scalar()

    result = await db.execute(
        select(Invoice)
        .where(Invoice.status == InvoiceStatus.FLAGGED)
        .order_by(Invoice.anomaly_score.desc())
        .offset(skip)
        .limit(limit)
    )
    invoices = result.scalars().all()

    return QueueListResponse(
        total=total,
        items=invoices
    )


@router.get("/{invoice_id}", response_model=QueueItem)
async def get_queue_item(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single flagged invoice with full details.
    Shows AI reasoning so reviewer can make informed decision.
    """
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != InvoiceStatus.FLAGGED:
        raise HTTPException(
            status_code=400,
            detail=f"Invoice is not in queue. Current status: {invoice.status}"
        )

    return invoice


@router.post("/{invoice_id}/approve", response_model=QueueActionResponse)
async def approve_invoice(
    invoice_id: str,
    request: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a flagged invoice.
    Records who approved it and updates vendor statistics.
    """
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != InvoiceStatus.FLAGGED:
        raise HTTPException(
            status_code=400,
            detail=f"Invoice cannot be approved. Current status: {invoice.status}"
        )

    # Update invoice status
    invoice.status = InvoiceStatus.APPROVED

    # Update vendor stats since we are approving the payment
    if invoice.vendor_id and invoice.amount:
        vendor_result = await db.execute(
            select(Vendor).where(Vendor.id == invoice.vendor_id)
        )
        vendor = vendor_result.scalar_one_or_none()
        if vendor:
            await update_vendor_stats(db, vendor, invoice.amount)

    # Write audit log
    audit = AuditLog(
        invoice_id=invoice.id,
        agent_name="human",
        action=AuditAction.HUMAN_APPROVED,
        reasoning=request.comment or "Approved by reviewer",
        details={
            "approved_by": request.approved_by,
            "comment": request.comment,
            "previous_status": "flagged",
            "anomaly_score": invoice.anomaly_score,
            "anomaly_flags": invoice.anomaly_flags,
        },
        performed_by=request.approved_by
    )
    db.add(audit)

    logger.info(
        "queue.approved",
        invoice_id=invoice_id,
        approved_by=request.approved_by,
        amount=invoice.amount,
        vendor=invoice.vendor_name
    )

    return QueueActionResponse(
        invoice_id=invoice_id,
        action="approved",
        performed_by=request.approved_by,
        comment=request.comment,
        new_status="approved",
        actioned_at=datetime.utcnow()
    )


@router.post("/{invoice_id}/reject", response_model=QueueActionResponse)
async def reject_invoice(
    invoice_id: str,
    request: RejectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a flagged invoice.
    Records who rejected it and the reason why.
    Invoice is permanently marked rejected — cannot be resubmitted.
    """
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != InvoiceStatus.FLAGGED:
        raise HTTPException(
            status_code=400,
            detail=f"Invoice cannot be rejected. Current status: {invoice.status}"
        )

    # Update invoice status
    invoice.status = InvoiceStatus.REJECTED

    # Write audit log
    audit = AuditLog(
        invoice_id=invoice.id,
        agent_name="human",
        action=AuditAction.HUMAN_REJECTED,
        reasoning=request.reason,
        details={
            "rejected_by": request.rejected_by,
            "reason": request.reason,
            "previous_status": "flagged",
            "anomaly_score": invoice.anomaly_score,
            "anomaly_flags": invoice.anomaly_flags,
        },
        performed_by=request.rejected_by
    )
    db.add(audit)

    logger.info(
        "queue.rejected",
        invoice_id=invoice_id,
        rejected_by=request.rejected_by,
        reason=request.reason,
        vendor=invoice.vendor_name
    )

    return QueueActionResponse(
        invoice_id=invoice_id,
        action="rejected",
        performed_by=request.rejected_by,
        comment=request.reason,
        new_status="rejected",
        actioned_at=datetime.utcnow()
    )


@router.get("/stats/summary")
async def get_queue_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    Get queue statistics — how many invoices are pending review.
    """
    flagged_result = await db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.status == InvoiceStatus.FLAGGED)
    )
    approved_result = await db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.status == InvoiceStatus.APPROVED)
    )
    rejected_result = await db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.status == InvoiceStatus.REJECTED)
    )

    amount_result = await db.execute(
        select(func.sum(Invoice.amount))
        .where(Invoice.status == InvoiceStatus.FLAGGED)
    )

    return {
        "pending_review": flagged_result.scalar() or 0,
        "approved_today": approved_result.scalar() or 0,
        "rejected_today": rejected_result.scalar() or 0,
        "total_amount_pending": float(amount_result.scalar() or 0),
    }