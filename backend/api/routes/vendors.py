from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.database import get_db
from backend.db.models.vendor import Vendor
from backend.schemas.vendor import VendorCreate, VendorResponse, VendorUpdate
from backend.services.vendor_service import get_vendor_by_name, create_vendor
from backend.core.logging import logger

router = APIRouter()


@router.post("/", response_model=VendorResponse)
async def register_vendor(
    vendor_data: VendorCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new vendor in the system.
    """
    # Check if vendor already exists
    existing = await get_vendor_by_name(db, vendor_data.name)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Vendor '{vendor_data.name}' already exists"
        )

    vendor = await create_vendor(
        db=db,
        name=vendor_data.name,
        email=vendor_data.email,
        tax_id=vendor_data.tax_id,
        address=vendor_data.address,
        payment_terms_days=vendor_data.payment_terms_days or 30,
        categories=vendor_data.categories or [],
    )

    logger.info("api.vendor_registered", name=vendor.name)
    return vendor


@router.get("/", response_model=list[VendorResponse])
async def list_vendors(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    List all registered vendors.
    """
    result = await db.execute(
        select(Vendor)
        .order_by(Vendor.name)
        .offset(skip)
        .limit(limit)
    )
    vendors = result.scalars().all()
    return vendors


@router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
    vendor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single vendor by ID.
    """
    result = await db.execute(
        select(Vendor).where(Vendor.id == vendor_id)
    )
    vendor = result.scalar_one_or_none()

    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    return vendor


@router.patch("/{vendor_id}", response_model=VendorResponse)
async def update_vendor(
    vendor_id: str,
    vendor_data: VendorUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update vendor details.
    Use this to verify a vendor — set is_verified=true.
    """
    result = await db.execute(
        select(Vendor).where(Vendor.id == vendor_id)
    )
    vendor = result.scalar_one_or_none()

    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Only update fields that were actually provided
    update_data = vendor_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vendor, field, value)

    logger.info("api.vendor_updated", vendor_id=vendor_id, fields=list(update_data.keys()))
    return vendor


@router.delete("/{vendor_id}", response_model=VendorResponse)
async def deactivate_vendor(
    vendor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivate a vendor — does not delete them.
    Future invoices from this vendor will be flagged.
    """
    result = await db.execute(
        select(Vendor).where(Vendor.id == vendor_id)
    )
    vendor = result.scalar_one_or_none()

    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    vendor.is_active = False
    logger.info("api.vendor_deactivated", vendor_id=vendor_id, name=vendor.name)
    return vendor