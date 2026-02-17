"""PDF text extraction using PyMuPDF."""

import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """Extract text from each page of a PDF file.

    Returns a list of dicts: [{"page": 1, "text": "..."}, ...]
    """
    doc = fitz.open(pdf_path)
    pages = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text()
        pages.append({"page": page_num + 1, "text": text.strip()})
    doc.close()
    return pages


def get_pdf_page_count(pdf_path: str) -> int:
    """Return the number of pages in a PDF."""
    doc = fitz.open(pdf_path)
    count = len(doc)
    doc.close()
    return count
