from __future__ import annotations

import io
import shutil
from pathlib import Path

from docx import Document
from fastapi import HTTPException

TESSERACT_INSTALL_HINT = (
    "Tesseract OCR is not installed. Run: brew install tesseract poppler"
)
POPPLER_INSTALL_HINT = (
    "Poppler is not installed (required for PDF OCR). Run: brew install poppler"
)


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from DOCX file")
    return text


def extract_text_from_pdf(file_bytes: bytes) -> str:
    if not _tesseract_available():
        raise HTTPException(status_code=503, detail=TESSERACT_INSTALL_HINT)

    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="OCR dependencies missing. Run: pip install pytesseract pdf2image Pillow",
        ) from exc

    try:
        images = convert_from_bytes(file_bytes)
    except Exception as exc:
        message = str(exc).lower()
        if "poppler" in message or "pdftoppm" in message:
            raise HTTPException(status_code=503, detail=POPPLER_INSTALL_HINT) from exc
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {exc}") from exc

    if not images:
        raise HTTPException(status_code=400, detail="PDF has no pages to process")

    page_texts: list[str] = []
    for i, image in enumerate(images, start=1):
        try:
            page_text = pytesseract.image_to_string(image)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"OCR failed on page {i}. {TESSERACT_INSTALL_HINT}",
            ) from exc
        if page_text.strip():
            page_texts.append(page_text.strip())

    full_text = "\n\n".join(page_texts)
    if not full_text.strip():
        raise HTTPException(
            status_code=400,
            detail="OCR produced no text. Try a clearer PDF or DOCX upload.",
        )
    return full_text


def extract_text(file_bytes: bytes, file_type: str) -> str:
    if file_type == "pdf":
        return extract_text_from_pdf(file_bytes)
    if file_type == "docx":
        return extract_text_from_docx(file_bytes)
    raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF or DOCX.")


def detect_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")
