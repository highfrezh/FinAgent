from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.db.models.vendor import Vendor
from backend.core.logging import logger


async def get_vendor_by_name(db: AsyncSession, name: str) -> Vendor | None:
    """
    Find a vendor by name — case insensitive search.
    """
    result = await db.execute(
        select(Vendor).where(
            func.lower(Vendor.name) == func.lower(name)
        )
    )
    return result.scalar_one_or_none()


async def get_vendor_by_id(db: AsyncSession, vendor_id: str) -> Vendor | None:
    """
    Find a vendor by their UUID.
    """
    result = await db.execute(
        select(Vendor).where(Vendor.id == vendor_id)
    )
    return result.scalar_one_or_none()


async def create_vendor(db: AsyncSession, name: str, **kwargs) -> Vendor:
    """
    Create a new vendor in the registry.
    """
    vendor = Vendor(name=name, **kwargs)
    db.add(vendor)
    await db.flush()
    logger.info("vendor.created", name=name, id=str(vendor.id))
    return vendor


async def update_vendor_stats(
    db: AsyncSession,
    vendor: Vendor,
    invoice_amount: float
) -> Vendor:
    """
    Update vendor statistics after a new invoice is processed.
    Recalculates average invoice amount, total invoices, total spend.
    """
    vendor.total_invoices += 1
    vendor.total_spend += invoice_amount

    # Recalculate rolling average
    vendor.average_invoice_amount = vendor.total_spend / vendor.total_invoices

    logger.info(
        "vendor.stats_updated",
        vendor=vendor.name,
        total_invoices=vendor.total_invoices,
        average=vendor.average_invoice_amount
    )
    return vendor


async def check_duplicate_invoice(
    db: AsyncSession,
    invoice_number: str,
    vendor_name: str,
    exclude_invoice_id: str = None
) -> bool:
    """
    Check if an invoice number already exists for this vendor.
    Returns True if duplicate found.
    """
    from backend.db.models.invoice import Invoice

    query = select(Invoice).where(
        Invoice.invoice_number == invoice_number,
        func.lower(Invoice.vendor_name) == func.lower(vendor_name)
    )

    if exclude_invoice_id:
        query = query.where(Invoice.id != exclude_invoice_id)

    result = await db.execute(query)
    existing = result.scalar_one_or_none()

    return existing is not None