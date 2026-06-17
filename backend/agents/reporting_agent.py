from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text

from backend.db.models.invoice import Invoice, InvoiceStatus
from backend.db.models.audit_log import AuditLog, AuditAction
from backend.schemas.report import (
    FinanceReport, StatusSummary, VendorSpend,
    MonthlySpend, AnomalySummary, UpcomingPayment
)
from backend.services.llm_service import llm
from backend.core.logging import logger


class ReportingAgent:

    async def generate_report(
        self,
        db: AsyncSession,
        days: int = 30,
    ) -> FinanceReport:
        """
        Generates a complete finance report for the specified period.
        """
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=days)

        logger.info(
            "reporting_agent.started",
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            days=days
        )

        # Run all data collection in parallel sections
        status_summary = await self._get_status_summary(db, period_start)
        top_vendors = await self._get_top_vendors(db, period_start)
        monthly_spend = await self._get_monthly_spend(db, period_start)
        anomaly_summary = await self._get_anomaly_summary(db, period_start)
        upcoming_payments = await self._get_upcoming_payments(db)
        total_spend = sum(v.total_spend for v in top_vendors)

        # Generate LLM narrative
        narrative, recommendations = await self._generate_narrative(
            status_summary=status_summary,
            top_vendors=top_vendors,
            anomaly_summary=anomaly_summary,
            upcoming_payments=upcoming_payments,
            total_spend=total_spend,
            days=days
        )

        report = FinanceReport(
            generated_at=datetime.utcnow(),
            period_start=period_start,
            period_end=period_end,
            status_summary=status_summary,
            total_spend=total_spend,
            top_vendors=top_vendors,
            monthly_spend=monthly_spend,
            anomaly_summary=anomaly_summary,
            upcoming_payments=upcoming_payments,
            narrative=narrative,
            recommendations=recommendations
        )

        # Write audit log
        audit = AuditLog(
            invoice_id=None,
            agent_name="reporting_agent",
            action=AuditAction.REPORT_GENERATED,
            reasoning=f"Generated {days}-day finance report. "
                      f"Total spend: ${total_spend:,.2f}. "
                      f"Invoices: {status_summary.total_invoices}",
            details={
                "days": days,
                "total_spend": total_spend,
                "total_invoices": status_summary.total_invoices,
                "anomalies": anomaly_summary.total_anomalies
            }
        )
        db.add(audit)
        await db.flush()

        logger.info(
            "reporting_agent.completed",
            total_spend=total_spend,
            total_invoices=status_summary.total_invoices,
            anomalies=anomaly_summary.total_anomalies
        )

        return report

    # ── Status Summary ────────────────────────────────────────────────────────
    async def _get_status_summary(
        self, db: AsyncSession, period_start: datetime
    ) -> StatusSummary:

        result = await db.execute(
            select(Invoice.status, func.count(Invoice.id))
            .where(Invoice.created_at >= period_start)
            .group_by(Invoice.status)
        )
        rows = result.all()

        counts = {row[0]: row[1] for row in rows}

        return StatusSummary(
            total_invoices=sum(counts.values()),
            valid=counts.get(InvoiceStatus.VALID, 0),
            flagged=counts.get(InvoiceStatus.FLAGGED, 0),
            rejected=counts.get(InvoiceStatus.REJECTED, 0),
            approved=counts.get(InvoiceStatus.APPROVED, 0),
            pending=counts.get(InvoiceStatus.PENDING, 0),
            processing=counts.get(InvoiceStatus.PROCESSING, 0),
        )

    # ── Top Vendors ───────────────────────────────────────────────────────────
    async def _get_top_vendors(
    self, db: AsyncSession, period_start: datetime
    ) -> list[VendorSpend]:

        result = await db.execute(
            select(
                Invoice.vendor_name,
                func.sum(Invoice.amount).label("total_spend"),
                func.count(Invoice.id).label("invoice_count"),
                func.avg(Invoice.amount).label("average_amount"),
            )
            .where(
                and_(
                    Invoice.created_at >= period_start,
                    Invoice.vendor_name.isnot(None),
                    Invoice.amount.isnot(None)
                )
            )
            .group_by(Invoice.vendor_name)
            .order_by(func.sum(Invoice.amount).desc())
            .limit(10)
        )
        rows = result.all()

        # Get flagged counts separately
        flagged_result = await db.execute(
            select(
                Invoice.vendor_name,
                func.count(Invoice.id).label("flagged_count")
            )
            .where(
                and_(
                    Invoice.created_at >= period_start,
                    Invoice.vendor_name.isnot(None),
                    Invoice.status == InvoiceStatus.FLAGGED
                )
            )
            .group_by(Invoice.vendor_name)
        )
        flagged_map = {
            row.vendor_name: row.flagged_count
            for row in flagged_result.all()
        }

        return [
            VendorSpend(
                vendor_name=row.vendor_name,
                total_spend=float(row.total_spend or 0),
                invoice_count=row.invoice_count,
                average_amount=float(row.average_amount or 0),
                flagged_count=flagged_map.get(row.vendor_name, 0)
            )
            for row in rows
        ]
    # ── Monthly Spend ─────────────────────────────────────────────────────────
    async def _get_monthly_spend(
        self, db: AsyncSession, period_start: datetime
    ) -> list[MonthlySpend]:

        result = await db.execute(
            text("""
                SELECT 
                    to_char(created_at, 'YYYY-MM') as month,
                    SUM(amount) as total_spend,
                    COUNT(id) as invoice_count,
                    COUNT(CASE WHEN status = 'FLAGGED' THEN 1 END) as flagged_count
                FROM invoices
                WHERE created_at >= :period_start
                AND amount IS NOT NULL
                GROUP BY to_char(created_at, 'YYYY-MM')
                ORDER BY to_char(created_at, 'YYYY-MM')
            """),
            {"period_start": period_start}
        )
        rows = result.all()

        return [
            MonthlySpend(
                month=row.month,
                total_spend=float(row.total_spend or 0),
                invoice_count=row.invoice_count,
                flagged_count=int(row.flagged_count or 0)
            )
            for row in rows
        ]
    # ── Anomaly Summary ───────────────────────────────────────────────────────
    async def _get_anomaly_summary(
        self, db: AsyncSession, period_start: datetime
    ) -> AnomalySummary:

        result = await db.execute(
            select(Invoice.anomaly_flags)
            .where(
                and_(
                    Invoice.created_at >= period_start,
                    Invoice.anomaly_flags.isnot(None)
                )
            )
        )
        all_flags = result.scalars().all()

        high_velocity = 0
        duplicate_amount = 0
        amount_spike = 0
        round_number = 0
        off_hours = 0
        total = 0

        for flags_list in all_flags:
            if not flags_list:
                continue
            for flag in flags_list:
                total += 1
                if "HIGH_VELOCITY" in flag:
                    high_velocity += 1
                elif "DUPLICATE_AMOUNT" in flag:
                    duplicate_amount += 1
                elif "AMOUNT_SPIKE" in flag:
                    amount_spike += 1
                elif "ROUND_AMOUNT" in flag:
                    round_number += 1
                elif "OFF_HOURS" in flag or "WEEKEND" in flag:
                    off_hours += 1

        return AnomalySummary(
            total_anomalies=total,
            high_velocity_count=high_velocity,
            duplicate_amount_count=duplicate_amount,
            amount_spike_count=amount_spike,
            round_number_count=round_number,
            off_hours_count=off_hours
        )

    # ── Upcoming Payments ─────────────────────────────────────────────────────
    async def _get_upcoming_payments(
        self, db: AsyncSession
    ) -> list[UpcomingPayment]:

        now = datetime.utcnow()
        thirty_days = now + timedelta(days=30)

        result = await db.execute(
            select(Invoice)
            .where(
                and_(
                    Invoice.due_date >= now,
                    Invoice.due_date <= thirty_days,
                    Invoice.status == InvoiceStatus.VALID,
                    Invoice.amount.isnot(None)
                )
            )
            .order_by(Invoice.due_date)
        )
        invoices = result.scalars().all()

        return [
            UpcomingPayment(
                invoice_id=str(inv.id),
                vendor_name=inv.vendor_name or "Unknown",
                amount=inv.amount,
                currency=inv.currency or "USD",
                due_date=inv.due_date,
                days_until_due=(inv.due_date - now).days
            )
            for inv in invoices
        ]

    # ── LLM Narrative ─────────────────────────────────────────────────────────
    async def _generate_narrative(
        self,
        status_summary: StatusSummary,
        top_vendors: list[VendorSpend],
        anomaly_summary: AnomalySummary,
        upcoming_payments: list[UpcomingPayment],
        total_spend: float,
        days: int
    ) -> tuple[str, list[str]]:

        # Build context for LLM
        vendor_text = "\n".join([
            f"- {v.vendor_name}: ${v.total_spend:,.2f} "
            f"({v.invoice_count} invoices, {v.flagged_count} flagged)"
            for v in top_vendors[:5]
        ])

        upcoming_text = "\n".join([
            f"- {p.vendor_name}: ${p.amount:,.2f} due in {p.days_until_due} days"
            for p in upcoming_payments[:5]
        ])

        prompt = f"""You are a senior financial analyst. 
Generate a concise executive summary and action items based on this data:

PERIOD: Last {days} days
TOTAL SPEND: ${total_spend:,.2f}
INVOICES: {status_summary.total_invoices} total, 
          {status_summary.valid} valid, 
          {status_summary.flagged} flagged,
          {status_summary.approved} approved

TOP VENDORS:
{vendor_text if vendor_text else "No vendor data"}

ANOMALIES DETECTED: {anomaly_summary.total_anomalies} total
- High velocity submissions: {anomaly_summary.high_velocity_count}
- Duplicate amounts: {anomaly_summary.duplicate_amount_count}
- Amount spikes: {anomaly_summary.amount_spike_count}

UPCOMING PAYMENTS (next 30 days):
{upcoming_text if upcoming_text else "No upcoming payments"}

Return a JSON object with exactly these two fields:
{{
  "narrative": "2-3 paragraph executive summary",
  "recommendations": ["action item 1", "action item 2", "action item 3"]
}}

Return ONLY the JSON. No explanation outside it."""

        try:
            from langchain_core.messages import HumanMessage
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # Clean up response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            import json
            parsed = json.loads(content)
            narrative = parsed.get("narrative", "Report generated successfully.")
            recommendations = parsed.get("recommendations", [])

        except Exception as e:
            logger.error("reporting_agent.narrative_failed", error=str(e))
            narrative = (
                f"Finance report for the last {days} days. "
                f"Total spend: ${total_spend:,.2f} across "
                f"{status_summary.total_invoices} invoices. "
                f"{status_summary.flagged} invoices flagged for review."
            )
            recommendations = [
                "Review all flagged invoices",
                "Verify vendors with high anomaly scores",
                "Ensure upcoming payments are approved"
            ]

        return narrative, recommendations