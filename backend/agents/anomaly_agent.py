from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from backend.db.models.invoice import Invoice, InvoiceStatus
from backend.db.models.vendor import Vendor
from backend.db.models.audit_log import AuditLog, AuditAction
from backend.core.logging import logger


class AnomalyAgent:

    # ── Thresholds ────────────────────────────────────────────────────────────
    AMOUNT_SPIKE_RATIO = 2.0        # 2x above vendor average
    VELOCITY_WINDOW_DAYS = 7        # check invoices in last 7 days
    VELOCITY_MAX_INVOICES = 5       # max invoices per vendor per week
    ROUND_NUMBER_THRESHOLD = 1000   # amounts divisible by this are suspicious
    NEW_VENDOR_LARGE_AMOUNT = 10000 # first invoice above this is suspicious
    DUPLICATE_AMOUNT_DAYS = 30      # same amount within this window

    async def process(
        self,
        db: AsyncSession,
        invoice: Invoice,
    ) -> list[str]:
        """
        Runs all anomaly checks against the invoice.
        Returns list of anomaly flags found.
        Updates invoice anomaly_flags and anomaly_score.
        """
        logger.info(
            "anomaly_agent.started",
            invoice_id=str(invoice.id),
            vendor=invoice.vendor_name,
            amount=invoice.amount
        )

        flags = []
        score = 0.0

        # Run all checks
        flags, score = await self._check_amount_spike(db, invoice, flags, score)
        flags, score = await self._check_velocity(db, invoice, flags, score)
        flags, score = await self._check_duplicate_amount(db, invoice, flags, score)
        flags, score = await self._check_round_number(invoice, flags, score)
        flags, score = await self._check_new_vendor_large_amount(db, invoice, flags, score)
        flags, score = await self._check_off_hours(invoice, flags, score)

        # Update invoice
        invoice.anomaly_flags = flags
        invoice.anomaly_score = min(score, 1.0)  # cap at 1.0

        # If anomaly score is high enough flag the invoice
        if score >= 0.5 and invoice.status == InvoiceStatus.VALID:
            invoice.status = InvoiceStatus.FLAGGED

        # Write audit log
        is_anomalous = len(flags) > 0
        audit = AuditLog(
            invoice_id=invoice.id,
            agent_name="anomaly_agent",
            action=AuditAction.ANOMALY_DETECTED if is_anomalous else AuditAction.VALIDATED,
            reasoning=(
                f"Anomaly detection complete. "
                f"Score: {invoice.anomaly_score:.2f}. "
                f"Flags: {flags if flags else 'none'}"
            ),
            details={
                "anomaly_score": invoice.anomaly_score,
                "flags": flags,
                "checks_run": 6,
            }
        )
        db.add(audit)

        logger.info(
            "anomaly_agent.completed",
            invoice_id=str(invoice.id),
            score=invoice.anomaly_score,
            flags=flags,
            is_anomalous=is_anomalous
        )

        return flags

    # ── Check 1: Amount Spike ─────────────────────────────────────────────────
    async def _check_amount_spike(
        self, db, invoice, flags, score
    ) -> tuple[list, float]:
        """Flag if amount is 2x above vendor average."""
        if not invoice.vendor_id or not invoice.amount:
            return flags, score

        result = await db.execute(
            select(Vendor).where(Vendor.id == invoice.vendor_id)
        )
        vendor = result.scalar_one_or_none()

        if vendor and vendor.average_invoice_amount > 0:
            ratio = invoice.amount / vendor.average_invoice_amount
            if ratio >= self.AMOUNT_SPIKE_RATIO:
                flags.append(f"AMOUNT_SPIKE_{ratio:.1f}X_ABOVE_AVERAGE")
                score += 0.3
                logger.warning(
                    "anomaly.amount_spike",
                    ratio=ratio,
                    amount=invoice.amount,
                    average=vendor.average_invoice_amount
                )

        return flags, score

    # ── Check 2: Velocity ─────────────────────────────────────────────────────
    async def _check_velocity(
        self, db, invoice, flags, score
    ) -> tuple[list, float]:
        """Flag if vendor submitted too many invoices in last 7 days."""
        if not invoice.vendor_name:
            return flags, score

        window_start = datetime.utcnow() - timedelta(days=self.VELOCITY_WINDOW_DAYS)

        result = await db.execute(
            select(func.count(Invoice.id)).where(
                and_(
                    func.lower(Invoice.vendor_name) == func.lower(invoice.vendor_name),
                    Invoice.created_at >= window_start,
                    Invoice.id != invoice.id
                )
            )
        )
        count = result.scalar() or 0

        if count >= self.VELOCITY_MAX_INVOICES:
            flags.append(f"HIGH_VELOCITY_{count}_INVOICES_IN_7_DAYS")
            score += 0.25
            logger.warning(
                "anomaly.high_velocity",
                vendor=invoice.vendor_name,
                count=count
            )

        return flags, score

    # ── Check 3: Duplicate Amount ─────────────────────────────────────────────
    async def _check_duplicate_amount(
        self, db, invoice, flags, score
    ) -> tuple[list, float]:
        """Flag if same amount from same vendor within 30 days."""
        if not invoice.vendor_name or not invoice.amount:
            return flags, score

        window_start = datetime.utcnow() - timedelta(days=self.DUPLICATE_AMOUNT_DAYS)

        result = await db.execute(
            select(func.count(Invoice.id)).where(
                and_(
                    func.lower(Invoice.vendor_name) == func.lower(invoice.vendor_name),
                    Invoice.amount == invoice.amount,
                    Invoice.created_at >= window_start,
                    Invoice.id != invoice.id,
                    Invoice.status != InvoiceStatus.FLAGGED
                )
            )
        )
        count = result.scalar() or 0

        if count > 0:
            flags.append(f"DUPLICATE_AMOUNT_WITHIN_30_DAYS")
            score += 0.35
            logger.warning(
                "anomaly.duplicate_amount",
                vendor=invoice.vendor_name,
                amount=invoice.amount,
                existing_count=count
            )

        return flags, score

    # ── Check 4: Round Number ─────────────────────────────────────────────────
    async def _check_round_number(
        self, invoice, flags, score
    ) -> tuple[list, float]:
        """Flag suspiciously round amounts like $10,000 or $5,000."""
        if not invoice.amount:
            return flags, score

        if (invoice.amount >= self.ROUND_NUMBER_THRESHOLD and
                invoice.amount % self.ROUND_NUMBER_THRESHOLD == 0):
            flags.append(f"SUSPICIOUSLY_ROUND_AMOUNT_{invoice.amount}")
            score += 0.1
            logger.warning(
                "anomaly.round_number",
                amount=invoice.amount
            )

        return flags, score

    # ── Check 5: New Vendor Large Amount ─────────────────────────────────────
    async def _check_new_vendor_large_amount(
        self, db, invoice, flags, score
    ) -> tuple[list, float]:
        """Flag if this is first invoice from vendor and amount is large."""
        if not invoice.vendor_name or not invoice.amount:
            return flags, score

        result = await db.execute(
            select(func.count(Invoice.id)).where(
                and_(
                    func.lower(Invoice.vendor_name) == func.lower(invoice.vendor_name),
                    Invoice.id != invoice.id
                )
            )
        )
        previous_count = result.scalar() or 0

        if previous_count == 0 and invoice.amount >= self.NEW_VENDOR_LARGE_AMOUNT:
            flags.append(f"NEW_VENDOR_LARGE_FIRST_INVOICE_{invoice.amount}")
            score += 0.4
            logger.warning(
                "anomaly.new_vendor_large_amount",
                vendor=invoice.vendor_name,
                amount=invoice.amount
            )

        return flags, score

    # ── Check 6: Off Hours Submission ────────────────────────────────────────
    async def _check_off_hours(
        self, invoice, flags, score
    ) -> tuple[list, float]:
        """Flag invoices submitted outside business hours or on weekends."""
        now = datetime.utcnow()
        hour = now.hour
        weekday = now.weekday()  # 0=Monday, 6=Sunday

        is_weekend = weekday >= 5
        is_off_hours = hour < 6 or hour > 22

        if is_weekend:
            flags.append("SUBMITTED_ON_WEEKEND")
            score += 0.1

        if is_off_hours:
            flags.append(f"SUBMITTED_OFF_HOURS_{hour:02d}:00_UTC")
            score += 0.1

        return flags, score