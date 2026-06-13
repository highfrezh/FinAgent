from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.database import get_db
from backend.db.models.invoice import Invoice
from backend.agents.ingestion_agent import IngestionAgent
from backend.schemas.invoice import InvoiceUploadResponse, InvoiceListResponse
from backend.core.logging import logger

router = APIRouter()
ingestion_agent = IngestionAgent()


@router.post("/upload", response_model=InvoiceUploadResponse)
async def upload_invoice(
    file: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a PDF invoice for processing.
    The ingestion agent will extract all structured data automatically.
    """
    logger.info("api.invoice_upload", filename=file.filename if file else "none")

    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    # Read file bytes
    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    # Run ingestion agent
    invoice = await ingestion_agent.process(
        db=db,
        file_bytes=file_bytes,
        filename=file.filename,
    )

    return invoice


@router.post("/text", response_model=InvoiceUploadResponse)
async def upload_invoice_text(
    raw_text: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit raw invoice text for processing.
    Useful for testing without a PDF file.
    """
    if not raw_text or len(raw_text.strip()) == 0:
        raise HTTPException(status_code=400, detail="No text provided")

    invoice = await ingestion_agent.process(
        db=db,
        raw_text=raw_text,
    )

    return invoice


@router.get("/", response_model=InvoiceListResponse)
async def list_invoices(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    List all invoices with pagination.
    """
    # Get total count
    count_result = await db.execute(select(func.count(Invoice.id)))
    total = count_result.scalar()

    # Get invoices
    result = await db.execute(
        select(Invoice)
        .order_by(Invoice.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    invoices = result.scalars().all()

    return InvoiceListResponse(total=total, invoices=invoices)


@router.get("/{invoice_id}", response_model=InvoiceUploadResponse)
async def get_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single invoice by ID.
    """
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return invoice