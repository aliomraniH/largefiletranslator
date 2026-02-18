"""Phase 2: Assemble translated pages into a PDF with dynamic layout.

Uses a document plan (from Claude) for consistent headers, footers,
section organization, and professional styling. Measures actual content
sizes and flows elements top-to-bottom to prevent overlaps.
"""

import os
from fpdf import FPDF

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")

SUPPORTED_IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

PAGE_MARGIN_LEFT = 50
PAGE_MARGIN_RIGHT = 50
PAGE_MARGIN_TOP = 70
PAGE_MARGIN_BOTTOM = 50
ELEMENT_SPACING = 8
TABLE_FONT_SIZE = 8
TABLE_PADDING = 3
TABLE_LINE_HEIGHT = 11
TABLE_HEADER_BG = (230, 230, 240)
TABLE_BORDER_COLOR = (150, 150, 150)

HEADER_HEIGHT = 30
FOOTER_HEIGHT = 25
HEADER_LINE_COLOR = (70, 97, 238)
FOOTER_LINE_COLOR = (200, 200, 200)
SECTION_TITLE_COLOR = (26, 26, 46)
HEADER_TEXT_COLOR = (100, 100, 120)


class AssemblerPDF(FPDF):
    def __init__(self):
        super().__init__(unit="pt", format="letter")
        self.add_font("DejaVu", "", FONT_REGULAR)
        self.add_font("DejaVu", "B", FONT_BOLD)
        self.add_font("DejaVu", "I", FONT_REGULAR)
        self.set_auto_page_break(auto=False)
        self.set_margins(0, 0, 0)


def assemble_pdf(translated_pages: list[dict], output_path: str,
                 document_plan: dict | None = None) -> str:
    if not translated_pages:
        return output_path

    pdf = AssemblerPDF()
    plan = document_plan or {}

    annotations = {}
    for ann in plan.get("page_annotations", []):
        annotations[ann.get("source_page", 0)] = ann

    sections_by_page = {}
    for sec in plan.get("sections", []):
        sections_by_page[sec.get("source_page", 0)] = sec

    output_page_num = 0

    for page_data in translated_pages:
        page_w = page_data.get("width", 612.0)
        page_h = page_data.get("height", 792.0)
        content_w = page_w - PAGE_MARGIN_LEFT - PAGE_MARGIN_RIGHT
        source_page = page_data.get("page_num", 0)

        ann = annotations.get(source_page, {})
        show_header = ann.get("show_header", True) if plan else False
        show_footer = ann.get("show_footer", True)
        section_title = ann.get("section_title", "")

        section_start = sections_by_page.get(source_page)

        elements = _collect_elements(page_data)

        output_page_num = _render_page_elements(
            pdf, elements, page_w, page_h, content_w,
            source_page, output_page_num, plan,
            show_header, show_footer, section_title,
            section_start,
        )

    pdf.output(output_path)
    return output_path


def _collect_elements(page_data: dict) -> list:
    elements = []

    for block in page_data.get("text_blocks", []):
        text = block.get("text", "")
        if not text.strip():
            continue
        orig_y = block.get("bbox", [0, 0, 0, 0])[1]
        orig_x = block.get("bbox", [0, 0, 0, 0])[0]
        elements.append({
            "type": "text",
            "text": text,
            "font_size": block.get("font_size", 11),
            "is_bold": block.get("is_bold", False),
            "orig_y": orig_y,
            "orig_x": orig_x,
            "orig_bbox": block.get("bbox", [0, 0, 0, 0]),
        })

    for img in page_data.get("images", []):
        path = img.get("path", "")
        if not path or not os.path.exists(path):
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_IMG_EXTS:
            continue
        orig_w = img.get("width", 0)
        orig_h = img.get("height", 0)
        if orig_w <= 0 or orig_h <= 0:
            continue
        orig_y = img.get("bbox", [0, 0, 0, 0])[1]
        elements.append({
            "type": "image",
            "path": path,
            "orig_w": orig_w,
            "orig_h": orig_h,
            "orig_y": orig_y,
            "orig_bbox": img.get("bbox", [0, 0, 0, 0]),
        })

    for table in page_data.get("tables", []):
        rows = table.get("rows", [])
        if not rows:
            continue
        orig_y = table.get("bbox", [0, 0, 0, 0])[1]
        elements.append({
            "type": "table",
            "rows": rows,
            "col_count": table.get("col_count", 1),
            "row_count": table.get("row_count", 0),
            "orig_y": orig_y,
            "orig_bbox": table.get("bbox", [0, 0, 0, 0]),
        })

    elements.sort(key=lambda e: e["orig_y"])
    return elements


def _draw_header(pdf: AssemblerPDF, page_w: float, plan: dict, section_title: str):
    header_left = plan.get("header_left", "")
    header_right = plan.get("header_right", "")

    y_base = 20

    pdf.set_draw_color(*HEADER_LINE_COLOR)
    pdf.set_line_width(1.5)
    pdf.line(PAGE_MARGIN_LEFT, y_base + 22, page_w - PAGE_MARGIN_RIGHT, y_base + 22)

    pdf.set_font("DejaVu", "B", 7)
    pdf.set_text_color(*HEADER_TEXT_COLOR)

    if header_left:
        pdf.set_xy(PAGE_MARGIN_LEFT, y_base)
        pdf.cell(200, 10, header_left, align="L")

    if header_right:
        pdf.set_xy(page_w - PAGE_MARGIN_RIGHT - 200, y_base)
        pdf.cell(200, 10, header_right, align="R")

    if section_title:
        pdf.set_font("DejaVu", "I", 7)
        pdf.set_text_color(130, 130, 150)
        pdf.set_xy(PAGE_MARGIN_LEFT, y_base + 10)
        pdf.cell(page_w - PAGE_MARGIN_LEFT - PAGE_MARGIN_RIGHT, 10, section_title, align="L")

    pdf.set_text_color(0, 0, 0)


def _draw_footer(pdf: AssemblerPDF, page_w: float, page_h: float,
                 output_page_num: int, plan: dict):
    y_base = page_h - FOOTER_HEIGHT - 8

    pdf.set_draw_color(*FOOTER_LINE_COLOR)
    pdf.set_line_width(0.5)
    pdf.line(PAGE_MARGIN_LEFT, y_base, page_w - PAGE_MARGIN_RIGHT, y_base)

    doc_title = plan.get("document_title", "")

    pdf.set_font("DejaVu", "I", 7)
    pdf.set_text_color(150, 150, 150)

    if doc_title:
        pdf.set_xy(PAGE_MARGIN_LEFT, y_base + 4)
        short_title = doc_title[:60] + ("..." if len(doc_title) > 60 else "")
        pdf.cell(300, 10, short_title, align="L")

    pdf.set_xy(page_w - PAGE_MARGIN_RIGHT - 100, y_base + 4)
    pdf.cell(100, 10, f"Page {output_page_num}", align="R")

    pdf.set_text_color(0, 0, 0)


def _draw_section_divider(pdf: AssemblerPDF, section: dict,
                          page_w: float, cursor_y: float, content_w: float) -> float:
    sec_type = section.get("type", "body")
    sec_title = section.get("title", "")

    if not sec_title or sec_type == "cover":
        return cursor_y

    pdf.set_draw_color(*HEADER_LINE_COLOR)
    pdf.set_line_width(2)
    pdf.line(PAGE_MARGIN_LEFT, cursor_y, PAGE_MARGIN_LEFT + content_w * 0.3, cursor_y)

    cursor_y += 8

    pdf.set_font("DejaVu", "B", 16)
    pdf.set_text_color(*SECTION_TITLE_COLOR)
    pdf.set_xy(PAGE_MARGIN_LEFT, cursor_y)
    pdf.cell(content_w, 22, sec_title, align="L")

    cursor_y += 30

    pdf.set_draw_color(*FOOTER_LINE_COLOR)
    pdf.set_line_width(0.5)
    pdf.line(PAGE_MARGIN_LEFT, cursor_y, page_w - PAGE_MARGIN_RIGHT, cursor_y)

    cursor_y += 12

    pdf.set_text_color(0, 0, 0)
    return cursor_y


def _render_page_elements(pdf: AssemblerPDF, elements: list,
                          page_w: float, page_h: float, content_w: float,
                          source_page: int, output_page_num: int,
                          plan: dict, show_header: bool, show_footer: bool,
                          section_title: str, section_start: dict | None) -> int:

    output_page_num += 1
    pdf.add_page(format=(page_w, page_h))

    if show_header and plan:
        _draw_header(pdf, page_w, plan, section_title)

    top_y = PAGE_MARGIN_TOP if show_header else 40
    bottom_y = page_h - PAGE_MARGIN_BOTTOM - (FOOTER_HEIGHT if show_footer else 10)

    cursor_y = top_y

    if section_start:
        cursor_y = _draw_section_divider(pdf, section_start, page_w, cursor_y, content_w)

    for elem in elements:
        if elem["type"] == "text":
            needed = _measure_text_height(pdf, elem, content_w)
            if cursor_y + needed > bottom_y and cursor_y > top_y + 20:
                if show_footer:
                    _draw_footer(pdf, page_w, page_h, output_page_num, plan)
                output_page_num += 1
                pdf.add_page(format=(page_w, page_h))
                if show_header and plan:
                    _draw_header(pdf, page_w, plan, section_title)
                cursor_y = top_y

            cursor_y = _draw_text(pdf, elem, PAGE_MARGIN_LEFT, cursor_y, content_w)
            cursor_y += ELEMENT_SPACING

        elif elem["type"] == "image":
            avail_h = bottom_y - cursor_y
            img_w, img_h = _fit_image_size(elem["orig_w"], elem["orig_h"], content_w, avail_h)

            if img_h <= 0:
                continue

            if cursor_y + img_h > bottom_y and cursor_y > top_y + 20:
                if show_footer:
                    _draw_footer(pdf, page_w, page_h, output_page_num, plan)
                output_page_num += 1
                pdf.add_page(format=(page_w, page_h))
                if show_header and plan:
                    _draw_header(pdf, page_w, plan, section_title)
                cursor_y = top_y
                avail_h = bottom_y - cursor_y
                img_w, img_h = _fit_image_size(elem["orig_w"], elem["orig_h"], content_w, avail_h)

            img_x = PAGE_MARGIN_LEFT + (content_w - img_w) / 2
            try:
                pdf.image(elem["path"], x=img_x, y=cursor_y, w=img_w, h=img_h)
                cursor_y += img_h + ELEMENT_SPACING
            except Exception:
                pass

        elif elem["type"] == "table":
            table_h = _measure_table_height(pdf, elem, content_w)

            if cursor_y + table_h > bottom_y and cursor_y > top_y + 20:
                if show_footer:
                    _draw_footer(pdf, page_w, page_h, output_page_num, plan)
                output_page_num += 1
                pdf.add_page(format=(page_w, page_h))
                if show_header and plan:
                    _draw_header(pdf, page_w, plan, section_title)
                cursor_y = top_y

            cursor_y = _draw_table(
                pdf, elem, PAGE_MARGIN_LEFT, cursor_y, content_w,
                bottom_y, output_page_num, page_w, page_h,
                plan, show_header, show_footer, section_title,
            )
            cursor_y += ELEMENT_SPACING

    if show_footer:
        _draw_footer(pdf, page_w, page_h, output_page_num, plan)

    return output_page_num


def _measure_text_height(pdf: AssemblerPDF, elem: dict, content_w: float) -> float:
    font_size = max(6, min(elem.get("font_size", 11), 36))
    style = "B" if elem.get("is_bold") else ""
    pdf.set_font("DejaVu", style, font_size)
    line_h = font_size * 1.3
    try:
        lines = pdf.multi_cell(
            w=content_w, h=line_h, text=elem["text"],
            border=0, align="L", dry_run=True, output="LINES"
        )
        return len(lines) * line_h
    except Exception:
        return line_h * 3


def _draw_text(pdf: AssemblerPDF, elem: dict, x: float, y: float, content_w: float) -> float:
    font_size = max(6, min(elem.get("font_size", 11), 36))
    style = "B" if elem.get("is_bold") else ""
    pdf.set_font("DejaVu", style, font_size)
    pdf.set_text_color(0, 0, 0)
    line_h = font_size * 1.3

    pdf.set_xy(x, y)
    try:
        pdf.multi_cell(w=content_w, h=line_h, text=elem["text"], border=0, align="L")
    except Exception:
        safe = elem["text"].encode("latin-1", errors="replace").decode("latin-1")
        pdf.set_xy(x, y)
        try:
            pdf.multi_cell(w=content_w, h=line_h, text=safe, border=0, align="L")
        except Exception:
            pass

    return pdf.get_y()


def _fit_image_size(orig_w: float, orig_h: float, max_w: float, max_h: float) -> tuple:
    if orig_w <= 0 or orig_h <= 0:
        return 0, 0

    ratio = orig_w / orig_h
    w = min(orig_w, max_w)
    h = w / ratio

    if h > max_h and max_h > 30:
        h = max_h
        w = h * ratio
        if w > max_w:
            w = max_w
            h = w / ratio

    return w, h


def _measure_table_height(pdf: AssemblerPDF, elem: dict, content_w: float) -> float:
    rows = elem.get("rows", [])
    col_count = max(elem.get("col_count", 1), 1)
    col_w = content_w / col_count
    total = 0.0

    for row in rows:
        rh = _measure_row_height(pdf, row, col_w, col_count)
        total += rh

    return total


def _measure_row_height(pdf: AssemblerPDF, row: dict, col_w: float, col_count: int) -> float:
    cells = row.get("cells", [])
    min_h = TABLE_LINE_HEIGHT + TABLE_PADDING * 2
    max_h = min_h

    pdf.set_font("DejaVu", "", TABLE_FONT_SIZE)
    text_w = col_w - TABLE_PADDING * 2
    if text_w <= 0:
        text_w = 30

    for ci in range(min(col_count, len(cells))):
        cell_text = cells[ci].get("text", "")
        if not cell_text.strip():
            continue
        try:
            lines = pdf.multi_cell(
                w=text_w, h=TABLE_LINE_HEIGHT, text=cell_text,
                border=0, align="L", dry_run=True, output="LINES"
            )
            needed = len(lines) * TABLE_LINE_HEIGHT + TABLE_PADDING * 2
        except Exception:
            needed = min_h
        max_h = max(max_h, needed)

    return max_h


def _draw_table(pdf: AssemblerPDF, elem: dict, x: float, y: float,
                content_w: float, max_y: float,
                output_page_num: int, page_w: float, page_h: float,
                plan: dict, show_header: bool, show_footer: bool,
                section_title: str) -> float:
    rows = elem.get("rows", [])
    col_count = max(elem.get("col_count", 1), 1)
    col_w = content_w / col_count
    cursor_y = y

    header_row = rows[0] if rows else None

    pdf.set_draw_color(*TABLE_BORDER_COLOR)
    pdf.set_line_width(0.5)

    for row_idx, row in enumerate(rows):
        rh = _measure_row_height(pdf, row, col_w, col_count)

        if cursor_y + rh > max_y and cursor_y > PAGE_MARGIN_TOP + 20:
            if show_footer:
                _draw_footer(pdf, page_w, page_h, output_page_num, plan)
            pdf.add_page(format=(page_w, page_h))
            if show_header and plan:
                _draw_header(pdf, page_w, plan, section_title)
            cursor_y = PAGE_MARGIN_TOP
            pdf.set_draw_color(*TABLE_BORDER_COLOR)
            pdf.set_line_width(0.5)

            if header_row and row_idx > 0:
                hh = _measure_row_height(pdf, header_row, col_w, col_count)
                cursor_y = _draw_table_row(pdf, header_row, x, cursor_y, col_w, col_count, hh, is_header=True)

        cursor_y = _draw_table_row(pdf, row, x, cursor_y, col_w, col_count, rh, is_header=(row_idx == 0))

    return cursor_y


def _draw_table_row(pdf: AssemblerPDF, row: dict, x: float, y: float,
                    col_w: float, col_count: int, rh: float, is_header: bool) -> float:
    cells = row.get("cells", [])
    cx = x

    if is_header:
        pdf.set_fill_color(*TABLE_HEADER_BG)

    for ci in range(col_count):
        if is_header:
            pdf.rect(cx, y, col_w, rh, style="DF")
        else:
            pdf.rect(cx, y, col_w, rh)

        if ci < len(cells):
            cell_text = cells[ci].get("text", "")
            if cell_text.strip():
                if is_header:
                    pdf.set_font("DejaVu", "B", TABLE_FONT_SIZE)
                else:
                    pdf.set_font("DejaVu", "", TABLE_FONT_SIZE)
                pdf.set_text_color(0, 0, 0)
                pdf.set_xy(cx + TABLE_PADDING, y + TABLE_PADDING)
                tw = col_w - TABLE_PADDING * 2
                if tw > 0:
                    try:
                        pdf.multi_cell(w=tw, h=TABLE_LINE_HEIGHT, text=cell_text, border=0, align="L")
                    except Exception:
                        pass
        cx += col_w

    return y + rh
