from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.agents.reporting_agent import ReportingAgent
from backend.schemas.report import FinanceReport
from backend.core.logging import logger

router = APIRouter()
reporting_agent = ReportingAgent()


@router.get("/monthly", response_model=FinanceReport)
async def get_monthly_report(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a complete finance report.
    Includes spend summary, vendor breakdown,
    anomaly analysis, upcoming payments and AI narrative.

    - days: number of days to include in report (default 30, max 365)
    """
    logger.info("api.report_requested", days=days)

    report = await reporting_agent.generate_report(db=db, days=days)

    return report