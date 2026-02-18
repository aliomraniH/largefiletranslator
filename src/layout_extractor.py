"""Extract detailed page layout from PDF: text blocks, images, tables with positions."""

import os
import fitz
import pdfplumber


def extract_page_layout(pdf_path: str, temp_dir: str) -> dict:
    """Extract full layout data from every page of a PDF.

    Returns a dict with page dimensions, text blocks, images, and detected tables.
    """
    fitz_doc = fitz.open(pdf_path)
    plumber_pdf = pdfplumber.open(pdf_path)
    pages = []

    img_dir = os.path.join(temp_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    for page_idx in range(len(fitz_doc)):
        fitz_page = fitz_doc.load_page(page_idx)
        plumber_page = plumber_pdf.pages[page_idx] if page_idx < len(plumber_pdf.pages) else None
        page_data = _extract_single_page(fitz_doc, fitz_page, plumber_page, page_idx, img_dir)
        pages.append(page_data)

    fitz_doc.close()
    plumber_pdf.close()
    return {"page_count": len(pages), "pages": pages}


def _extract_single_page(fitz_doc, fitz_page, plumber_page, page_idx: int, img_dir: str) -> dict:
    """Extract layout from a single page using PyMuPDF for text/images and pdfplumber for tables."""
    rect = fitz_page.rect
    page_data = {
        "page_num": page_idx + 1,
        "width": rect.width,
        "height": rect.height,
        "text_blocks": [],
        "images": [],
        "tables": [],
    }

    tables_data = []
    table_regions = []
    if plumber_page:
        tables_data, table_regions = _extract_tables_pdfplumber(plumber_page)
    page_data["tables"] = tables_data

    text_dict = fitz_page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

    for block in text_dict.get("blocks", []):
        if block["type"] == 0:
            block_text = _extract_block_text(block)
            if block_text.strip():
                bbox = list(block["bbox"])
                if _block_overlaps_table(bbox, table_regions):
                    continue
                font_info = _get_block_font(block)
                page_data["text_blocks"].append({
                    "type": "text",
                    "bbox": bbox,
                    "text": block_text,
                    "font_name": font_info["name"],
                    "font_size": font_info["size"],
                    "is_bold": font_info["bold"],
                })
        elif block["type"] == 1:
            img_data = _extract_image_block(block, page_idx, img_dir, len(page_data["images"]))
            if img_data:
                page_data["images"].append(img_data)

    xref_images = _extract_xref_images(fitz_doc, fitz_page, page_idx, img_dir, len(page_data["images"]))
    page_data["images"].extend(xref_images)

    return page_data


def _extract_tables_pdfplumber(plumber_page) -> tuple[list, list]:
    """Use pdfplumber to find and extract tables with their bounding boxes.

    Returns (tables_data, table_regions) where table_regions are bboxes for overlap filtering.
    """
    tables_data = []
    table_regions = []

    try:
        found_tables = plumber_page.find_tables(table_settings={
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 4,
            "join_tolerance": 4,
        })
    except Exception:
        found_tables = []

    if not found_tables:
        try:
            found_tables = plumber_page.find_tables(table_settings={
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "min_words_vertical": 3,
                "min_words_horizontal": 2,
            })
        except Exception:
            found_tables = []

    for table in found_tables:
        try:
            raw_data = table.extract()
            if not raw_data:
                continue

            num_rows = len(raw_data)
            num_cols = max(len(row) for row in raw_data) if raw_data else 0

            if num_cols < 2:
                continue

            if num_rows < 2 and num_cols < 2:
                continue

            bbox = list(table.bbox)
            table_regions.append(bbox)

            rows = []
            for row in raw_data:
                cells = []
                for cell in row:
                    cell_text = cell if cell else ""
                    cell_text = cell_text.replace("\n", " ").strip()
                    cells.append({"text": cell_text, "bbox": bbox})
                rows.append({"cells": cells})

            tables_data.append({
                "bbox": bbox,
                "rows": rows,
                "row_count": num_rows,
                "col_count": num_cols,
            })
        except Exception:
            continue

    return tables_data, table_regions


def _block_overlaps_table(block_bbox: list, table_regions: list) -> bool:
    """Check if a text block substantially overlaps any detected table region."""
    bx0, by0, bx1, by1 = block_bbox
    block_area = max((bx1 - bx0) * (by1 - by0), 1)

    for tbbox in table_regions:
        tx0, ty0, tx1, ty1 = tbbox

        ox0 = max(bx0, tx0)
        oy0 = max(by0, ty0)
        ox1 = min(bx1, tx1)
        oy1 = min(by1, ty1)

        if ox0 < ox1 and oy0 < oy1:
            overlap_area = (ox1 - ox0) * (oy1 - oy0)
            if overlap_area / block_area > 0.5:
                return True

    return False


def _extract_block_text(block: dict) -> str:
    """Extract text from a text block dict."""
    lines = []
    for line in block.get("lines", []):
        spans_text = ""
        for span in line.get("spans", []):
            spans_text += span.get("text", "")
        lines.append(spans_text)
    return "\n".join(lines)


def _get_block_font(block: dict) -> dict:
    """Get the dominant font info from a block."""
    fonts = {}
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            key = (span.get("font", ""), round(span.get("size", 11)), "Bold" in span.get("font", ""))
            char_count = len(span.get("text", ""))
            fonts[key] = fonts.get(key, 0) + char_count

    if not fonts:
        return {"name": "unknown", "size": 11, "bold": False}

    dominant = max(fonts, key=fonts.get)
    return {"name": dominant[0], "size": dominant[1], "bold": dominant[2]}


def _extract_image_block(block: dict, page_idx: int, img_dir: str, img_count: int) -> dict | None:
    """Extract an inline image block."""
    try:
        img_data = block.get("image", b"")
        if not img_data:
            return None

        ext = block.get("ext", "png")
        bbox = block.get("bbox", [0, 0, 0, 0])
        filename = f"page{page_idx + 1}_img{img_count}.{ext}"
        filepath = os.path.join(img_dir, filename)

        with open(filepath, "wb") as f:
            f.write(img_data)

        return {
            "bbox": list(bbox),
            "path": filepath,
            "width": bbox[2] - bbox[0],
            "height": bbox[3] - bbox[1],
        }
    except Exception:
        return None


def _extract_xref_images(doc, page, page_idx: int, img_dir: str, start_count: int) -> list:
    """Extract referenced images from the page via xref."""
    images = []
    try:
        img_list = page.get_images(full=True)
        for img_idx, img_info in enumerate(img_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                if not base_image or not base_image.get("image"):
                    continue

                ext = base_image.get("ext", "png")
                filename = f"page{page_idx + 1}_xref{start_count + img_idx}.{ext}"
                filepath = os.path.join(img_dir, filename)

                with open(filepath, "wb") as f:
                    f.write(base_image["image"])

                img_rects = page.get_image_rects(xref)
                if img_rects:
                    r = img_rects[0]
                    bbox = [r.x0, r.y0, r.x1, r.y1]
                else:
                    bbox = [0, 0, base_image.get("width", 100), base_image.get("height", 100)]

                images.append({
                    "bbox": bbox,
                    "path": filepath,
                    "width": bbox[2] - bbox[0],
                    "height": bbox[3] - bbox[1],
                })
            except Exception:
                continue
    except Exception:
        pass
    return images


def layout_to_html(page_data: dict) -> str:
    """Convert extracted page layout to an HTML representation for Claude translation."""
    html_parts = []
    html_parts.append(f'<page num="{page_data["page_num"]}" width="{page_data["width"]:.1f}" height="{page_data["height"]:.1f}">')

    for i, block in enumerate(page_data["text_blocks"]):
        tag = "h" if block["is_bold"] and block["font_size"] >= 14 else "p"
        bbox_str = ",".join(f"{v:.1f}" for v in block["bbox"])
        escaped_text = block["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_parts.append(f'  <{tag} id="b{i}" bbox="{bbox_str}" font-size="{block["font_size"]}">{escaped_text}</{tag}>')

    for i, img in enumerate(page_data["images"]):
        bbox_str = ",".join(f"{v:.1f}" for v in img["bbox"])
        html_parts.append(f'  <img id="i{i}" bbox="{bbox_str}" src="{os.path.basename(img["path"])}" />')

    for i, table in enumerate(page_data["tables"]):
        bbox_str = ",".join(f"{v:.1f}" for v in table["bbox"])
        html_parts.append(f'  <table id="t{i}" bbox="{bbox_str}">')
        for row in table["rows"]:
            html_parts.append("    <tr>")
            for cell in row["cells"]:
                escaped = cell["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html_parts.append(f"      <td>{escaped}</td>")
            html_parts.append("    </tr>")
        html_parts.append("  </table>")

    html_parts.append("</page>")
    return "\n".join(html_parts)
