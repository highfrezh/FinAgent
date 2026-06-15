from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.invoice import Invoice, InvoiceStatus
from backend.db.models.audit_log import AuditLog, AuditAction
from backend.schemas.vendor import ValidationResult
from backend.services.vendor_service import (
    get_vendor_by_name,
    update_vendor_stats,
    check_duplicate_invoice
)
from backend.core.logging import logger


class ValidationAgent:

    async def process(
        self,
        db: AsyncSession,
        invoice: Invoice,
    ) -> ValidationResult:
        """
        Validates an invoice against business rules.
        Updates invoice status and writes audit log.
        """
        logger.info(
            "validation_agent.started",
            invoice_id=str(invoice.id),
            vendor=invoice.vendor_name
        )

        flags = []
        vendor_found = False
        vendor_verified = False

        # ── Rule 1: Vendor must exist in registry ────────────────────────────
        vendor = None
        if invoice.vendor_name:
            vendor = await get_vendor_by_name(db, invoice.vendor_name)
            if vendor:
                vendor_found = True
                vendor_verified = vendor.is_verified
                invoice.vendor_id = vendor.id

                if not vendor.is_verified:
                    flags.append("VENDOR_NOT_VERIFIED")

                if not vendor.is_active:
                    flags.append("VENDOR_INACTIVE")

            else:
                flags.append("VENDOR_NOT_FOUND")
        else:
            flags.append("VENDOR_NAME_MISSING")

        # ── Rule 2: Amount must be present and positive ───────────────────────
        if invoice.amount is None:
            flags.append("AMOUNT_MISSING")
        elif invoice.amount <= 0:
            flags.append("AMOUNT_INVALID")

        # ── Rule 3: Invoice number must be present ────────────────────────────
        if not invoice.invoice_number:
            flags.append("INVOICE_NUMBER_MISSING")

        # ── Rule 4: Check for duplicate invoice ───────────────────────────────
        if invoice.invoice_number and invoice.vendor_name:
            is_duplicate = await check_duplicate_invoice(
                db=db,
                invoice_number=invoice.invoice_number,
                vendor_name=invoice.vendor_name,
                exclude_invoice_id=str(invoice.id)
            )
            if is_duplicate:
                flags.append("DUPLICATE_INVOICE")

        # ── Rule 5: Due date must be in the future ────────────────────────────
        if invoice.due_date and invoice.due_date < datetime.utcnow():
            flags.append("DUE_DATE_EXPIRED")

        # ── Rule 6: Amount vs vendor average ─────────────────────────────────
        if vendor and vendor.average_invoice_amount > 0 and invoice.amount:
            ratio = invoice.amount / vendor.average_invoice_amount
            if ratio > 3:
                flags.append(f"AMOUNT_3X_ABOVE_VENDOR_AVERAGE")

        # ── Determine final status ────────────────────────────────────────────
        critical_flags = {
            "VENDOR_NOT_FOUND",
            "AMOUNT_MISSING",
            "AMOUNT_INVALID",
            "DUPLICATE_INVOICE",
            "VENDOR_INACTIVE"
        }

        has_critical = any(f in critical_flags for f in flags)
        is_valid = not has_critical

        # Update invoice status
        if is_valid:
            invoice.status = InvoiceStatus.VALID
            if vendor and invoice.amount:
                await update_vendor_stats(db, vendor, invoice.amount)
        else:
            invoice.status = InvoiceStatus.FLAGGED

        # Build reasoning message
        if is_valid:
            reasoning = (
                f"Invoice passed validation. "
                f"Vendor '{invoice.vendor_name}' found and active. "
                f"Amount {invoice.amount} {invoice.currency} is acceptable. "
                f"No duplicates detected."
            )
            if flags:
                reasoning += f" Minor flags: {', '.join(flags)}"
        else:
            reasoning = (
                f"Invoice failed validation. "
                f"Critical flags: {', '.join(f for f in flags if f in critical_flags)}. "
                f"All flags: {', '.join(flags)}"
            )

        # Build result
        result = ValidationResult(
            is_valid=is_valid,
            vendor_found=vendor_found,
            vendor_verified=vendor_verified,
            flags=flags,
            reasoning=reasoning
        )

        # Save validation result to invoice
        invoice.validation_result = {
            "is_valid": is_valid,
            "vendor_found": vendor_found,
            "vendor_verified": vendor_verified,
            "flags": flags,
            "reasoning": reasoning,
            "validated_at": datetime.utcnow().isoformat()
        }

        # Write audit log
        audit = AuditLog(
            invoice_id=invoice.id,
            agent_name="validation_agent",
            action=AuditAction.VALIDATED if is_valid else AuditAction.FLAGGED,
            reasoning=reasoning,
            details={
                "flags": flags,
                "vendor_found": vendor_found,
                "vendor_verified": vendor_verified,
                "rules_checked": 6
            }
        )
        db.add(audit)

        logger.info(
            "validation_agent.completed",
            invoice_id=str(invoice.id),
            is_valid=is_valid,
            flags=flags
        )

        return result