"""Generate translated PDF output using fpdf2."""

import os
from fpdf import FPDF

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")


class TranslatedPDF(FPDF):
    """Custom PDF class for translated documents."""

    def __init__(self):
        super().__init__()
        self.add_font("DejaVu", "", FONT_REGULAR)
        self.add_font("DejaVu", "B", FONT_BOLD)
        self.add_font("DejaVu", "I", FONT_REGULAR)

    def header(self):
        self.set_font("DejaVu", "I", 8)
        self.cell(0, 5, "Translated by LargeFileTranslator (Claude API)", align="R")
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def create_translated_pdf(translated_pages: list[dict], output_path: str) -> str:
    """Create a PDF file from translated page content.

    Args:
        translated_pages: List of {"page": int, "text": str} dicts.
        output_path: Path to write the output PDF.

    Returns:
        The output file path.
    """
    pdf = TranslatedPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    for page_data in translated_pages:
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 10)
        pdf.cell(0, 8, f"Page {page_data['page']}", ln=True)
        pdf.ln(2)

        pdf.set_font("DejaVu", "", 11)
        text = page_data["text"]
        if text:
            pdf.multi_cell(0, 6, text)
        else:
            pdf.set_font("DejaVu", "I", 10)
            pdf.cell(0, 8, "(empty page)", ln=True)

    pdf.output(output_path)
    return output_path
