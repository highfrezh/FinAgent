import fitz
import re
from pathlib import Path
from backend.core.logging import logger


def extract_text_from_pdf(file_bytes: bytes, filename: str = "") -> str:
    """
    Extract raw text from a PDF file.
    Returns the full text content of the PDF.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        full_text = ""

        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            full_text += f"\n--- Page {page_num + 1} ---\n"
            full_text += page_text

        doc.close()

        logger.info(
            "pdf.extracted",
            filename=filename,
            pages=len(doc),
            characters=len(full_text)
        )

        return full_text.strip()

    except Exception as e:
        logger.error("pdf.extraction_failed", filename=filename, error=str(e))
        raise ValueError(f"Could not extract text from PDF: {str(e)}")


def extract_text_from_string(text: str) -> str:
    """
    Clean and normalize raw invoice text input.
    Used when user submits plain text instead of PDF.
    """
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def prepare_invoice_text(
    file_bytes: bytes = None,
    filename: str = "",
    raw_text: str = None
) -> str:
    """
    Main entry point.
    Accepts either a PDF file or raw text and returns clean text.
    """
    if file_bytes:
        return extract_text_from_pdf(file_bytes, filename)
    elif raw_text:
        return extract_text_from_string(raw_text)
    else:
        raise ValueError("Must provide either file_bytes or raw_text")