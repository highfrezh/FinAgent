from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.llm_service import llm
from backend.services.pdf_parser import prepare_invoice_text
from backend.db.models.invoice import Invoice, InvoiceStatus
from backend.db.models.audit_log import AuditLog, AuditAction
from backend.schemas.invoice import InvoiceExtracted
from backend.core.logging import logger


# ── Prompt Template ──────────────────────────────────────────────────────────
EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a financial document AI assistant specialized in 
extracting structured data from invoices.

Extract the following fields from the invoice text provided:
- invoice_number: the invoice ID or number
- vendor_name: the company or person sending the invoice
- amount: the total amount due as a number only
- currency: the currency code (USD, EUR, GBP etc). Default to USD
- invoice_date: the invoice date in YYYY-MM-DD format
- due_date: the payment due date in YYYY-MM-DD format
- line_items: list of items with description, quantity, unit_price, total

Return ONLY a valid JSON object with these exact fields.
If a field cannot be found, use null.
Do not include any explanation or text outside the JSON.

Example output:
{{
  "invoice_number": "INV-2024-001",
  "vendor_name": "Acme Corporation",
  "amount": 5000.00,
  "currency": "USD",
  "invoice_date": "2024-01-15",
  "due_date": "2024-02-15",
  "line_items": [
    {{
      "description": "Software License",
      "quantity": 1,
      "unit_price": 5000.00,
      "total": 5000.00
    }}
  ]
}}"""),
    ("human", "Extract data from this invoice:\n\n{invoice_text}")
])


# ── Agent Class ───────────────────────────────────────────────────────────────
class IngestionAgent:

    def __init__(self):
        self.chain = EXTRACTION_PROMPT | llm | JsonOutputParser()
        logger.info("ingestion_agent.initialized")

    async def process(
        self,
        db: AsyncSession,
        file_bytes: bytes = None,
        filename: str = "",
        raw_text: str = None,
    ) -> Invoice:
        """
        Main method. Accepts PDF or text, extracts data, saves to database.
        Returns the saved Invoice object.
        """
        logger.info("ingestion_agent.started", filename=filename)

        # Step 1 — Extract text from PDF or raw input
        invoice_text = prepare_invoice_text(
            file_bytes=file_bytes,
            filename=filename,
            raw_text=raw_text
        )

        # Step 2 — Create invoice record in DB with PENDING status
        invoice = Invoice(
            raw_text=invoice_text,
            file_name=filename,
            status=InvoiceStatus.PENDING,
        )
        db.add(invoice)
        await db.flush()  # gets the ID without committing yet

        # Step 3 — Send text to AI for extraction
        logger.info("ingestion_agent.extracting", invoice_id=str(invoice.id))
        try:
            extracted_data = await self.chain.ainvoke({
                "invoice_text": invoice_text[:4000]  # limit tokens
            })

            # Step 4 — Parse and validate extracted data
            extracted = InvoiceExtracted(**extracted_data)

            # Step 5 — Update invoice with extracted fields
            invoice.invoice_number = extracted.invoice_number
            invoice.vendor_name = extracted.vendor_name
            invoice.amount = extracted.amount
            invoice.currency = extracted.currency or "USD"
            invoice.status = InvoiceStatus.PROCESSING

            # Parse dates safely
            if extracted.invoice_date:
                try:
                    invoice.invoice_date = datetime.strptime(
                        extracted.invoice_date, "%Y-%m-%d"
                    )
                except ValueError:
                    pass

            if extracted.due_date:
                try:
                    invoice.due_date = datetime.strptime(
                        extracted.due_date, "%Y-%m-%d"
                    )
                except ValueError:
                    pass

            if extracted.line_items:
                invoice.line_items = [
                    item.model_dump() for item in extracted.line_items
                ]

            invoice.processed_at = datetime.utcnow()

            # Step 6 — Write audit log
            audit = AuditLog(
                invoice_id=invoice.id,
                agent_name="ingestion_agent",
                action=AuditAction.INGESTED,
                reasoning=f"Successfully extracted invoice data. "
                          f"Vendor: {extracted.vendor_name}, "
                          f"Amount: {extracted.amount} {extracted.currency}",
                details={
                    "filename": filename,
                    "characters_extracted": len(invoice_text),
                    "fields_found": [
                        k for k, v in extracted.model_dump().items()
                        if v is not None
                    ]
                }
            )
            db.add(audit)

            logger.info(
                "ingestion_agent.completed",
                invoice_id=str(invoice.id),
                vendor=extracted.vendor_name,
                amount=extracted.amount,
            )

        except Exception as e:
            # If AI extraction fails — log the error and mark invoice
            invoice.status = InvoiceStatus.FLAGGED
            audit = AuditLog(
                invoice_id=invoice.id,
                agent_name="ingestion_agent",
                action=AuditAction.ERROR,
                reasoning=f"Extraction failed: {str(e)}",
                details={"error": str(e), "filename": filename}
            )
            db.add(audit)
            logger.error("ingestion_agent.failed", error=str(e))

        return invoice