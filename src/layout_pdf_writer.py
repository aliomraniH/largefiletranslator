"""Reconstruct PDF from translated layout data with images, tables, and positioned text."""

import os
from fpdf import FPDF

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")

SUPPORTED_IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

TABLE_FONT_SIZE = 8
TABLE_PADDING = 3
TABLE_LINE_HEIGHT = 10


class LayoutPDF(FPDF):
    def __init__(self, page_width, page_height):
        super().__init__(unit="pt", format=(page_width, page_height))
        self.add_font("DejaVu", "", FONT_REGULAR)
        self.add_font("DejaVu", "B", FONT_BOLD)
        self.add_font("DejaVu", "I", FONT_REGULAR)
        self.set_auto_page_break(auto=False)
        self.set_margins(0, 0, 0)


def create_layout_pdf(translated_pages: list[dict], output_path: str) -> str:
    if not translated_pages:
        return output_path

    first = translated_pages[0]
    pdf = LayoutPDF(first["width"], first["height"])

    for page_data in translated_pages:
        w = page_data["width"]
        h = page_data["height"]

        pdf.add_page(format=(w, h))

        _render_images(pdf, page_data.get("images", []))
        _render_text_blocks(pdf, page_data.get("text_blocks", []), w)
        _render_tables(pdf, page_data.get("tables", []), w)

        _render_page_footer(pdf, page_data["page_num"], w, h)

    pdf.output(output_path)
    return output_path


def _render_images(pdf: LayoutPDF, images: list):
    for img in images:
        path = img.get("path", "")
        if not path or not os.path.exists(path):
            continue

        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_IMG_EXTS:
            continue

        bbox = img["bbox"]
        x, y = bbox[0], bbox[1]
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        if w <= 0 or h <= 0:
            continue

        try:
            pdf.image(path, x=x, y=y, w=w, h=h)
        except Exception:
            pass


def _render_text_blocks(pdf: LayoutPDF, blocks: list, page_width: float):
    for block in blocks:
        bbox = block["bbox"]
        x, y = bbox[0], bbox[1]
        block_w = bbox[2] - bbox[0]

        if block_w <= 0:
            block_w = page_width - x - 10

        text = block.get("text", "")
        if not text.strip():
            continue

        font_size = block.get("font_size", 11)
        is_bold = block.get("is_bold", False)

        font_size = max(6, min(font_size, 36))

        style = "B" if is_bold else ""
        pdf.set_font("DejaVu", style, font_size)

        pdf.set_xy(x, y)

        line_height = font_size * 1.3

        try:
            pdf.multi_cell(w=block_w, h=line_height, text=text, border=0, align="L")
        except Exception:
            safe_text = text.encode("latin-1", errors="replace").decode("latin-1")
            try:
                pdf.set_xy(x, y)
                pdf.multi_cell(w=block_w, h=line_height, text=safe_text, border=0, align="L")
            except Exception:
                pass


def _render_tables(pdf: LayoutPDF, tables: list, page_width: float):
    for table in tables:
        bbox = table["bbox"]
        rows = table.get("rows", [])
        if not rows:
            continue

        table_x = bbox[0]
        table_y = bbox[1]
        table_w = bbox[2] - bbox[0]
        table_h = bbox[3] - bbox[1]

        col_count = table.get("col_count", 1)
        row_count = len(rows)

        if col_count <= 0:
            col_count = 1
        if table_w <= 0:
            table_w = page_width - table_x - 10

        col_w = table_w / col_count

        pdf.set_font("DejaVu", "", TABLE_FONT_SIZE)
        pdf.set_draw_color(120, 120, 120)
        pdf.set_line_width(0.5)

        row_heights = _calculate_row_heights(pdf, rows, col_w, col_count, table_h, row_count)

        current_y = table_y
        for row_idx, row in enumerate(rows):
            current_x = table_x
            cells = row.get("cells", [])
            rh = row_heights[row_idx]

            for cell_idx in range(col_count):
                pdf.rect(current_x, current_y, col_w, rh)

                if cell_idx < len(cells):
                    cell_text = cells[cell_idx].get("text", "")
                    if cell_text.strip():
                        _render_cell_text(pdf, cell_text, current_x, current_y, col_w, rh)

                current_x += col_w
            current_y += rh


def _calculate_row_heights(pdf: LayoutPDF, rows: list, col_w: float, col_count: int,
                           table_h: float, row_count: int) -> list:
    base_row_h = table_h / max(row_count, 1)
    min_row_h = max(TABLE_LINE_HEIGHT + TABLE_PADDING * 2, 14)

    row_heights = []
    for row in rows:
        cells = row.get("cells", [])
        max_cell_h = min_row_h

        for cell_idx in range(min(col_count, len(cells))):
            cell_text = cells[cell_idx].get("text", "")
            if cell_text.strip():
                text_w = col_w - TABLE_PADDING * 2
                if text_w <= 0:
                    text_w = 50

                pdf.set_font("DejaVu", "", TABLE_FONT_SIZE)
                try:
                    lines = pdf.multi_cell(
                        w=text_w, h=TABLE_LINE_HEIGHT, text=cell_text,
                        border=0, align="L", dry_run=True, output="LINES"
                    )
                    needed_h = len(lines) * TABLE_LINE_HEIGHT + TABLE_PADDING * 2
                except Exception:
                    needed_h = TABLE_LINE_HEIGHT + TABLE_PADDING * 2

                max_cell_h = max(max_cell_h, needed_h)

        row_heights.append(max(max_cell_h, base_row_h))

    total = sum(row_heights)
    if total > 0 and abs(total - table_h) > 5:
        scale = table_h / total
        if 0.5 < scale < 2.0:
            row_heights = [h * scale for h in row_heights]
            row_heights = [max(h, min_row_h) for h in row_heights]

    return row_heights


def _render_cell_text(pdf: LayoutPDF, text: str, x: float, y: float, col_w: float, row_h: float):
    text_w = col_w - TABLE_PADDING * 2
    if text_w <= 0:
        return

    pdf.set_font("DejaVu", "", TABLE_FONT_SIZE)
    pdf.set_xy(x + TABLE_PADDING, y + TABLE_PADDING)

    try:
        pdf.multi_cell(w=text_w, h=TABLE_LINE_HEIGHT, text=text, border=0, align="L")
    except Exception:
        safe_text = text.encode("latin-1", errors="replace").decode("latin-1")
        try:
            pdf.set_xy(x + TABLE_PADDING, y + TABLE_PADDING)
            pdf.multi_cell(w=text_w, h=TABLE_LINE_HEIGHT, text=safe_text, border=0, align="L")
        except Exception:
            pass


def _render_page_footer(pdf: LayoutPDF, page_num: int, width: float, height: float):
    pdf.set_font("DejaVu", "I", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.set_xy(10, height - 15)
    pdf.cell(width - 20, 10, f"Translated by LargeFileTranslator (Claude AI) - Page {page_num}", align="R")
    pdf.set_text_color(0, 0, 0)
