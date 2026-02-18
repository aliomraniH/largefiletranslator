"""Use Claude to analyze translated pages and create a document structure plan.

Sends a compact summary of all pages to Claude, which returns a structured
plan with document title, sections, header/footer text, and element annotations.
The assembler uses this plan for consistent, professional formatting.
"""

import anthropic
from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL


PLANNER_TOOL = {
    "name": "submit_document_plan",
    "description": "Submit the document structure plan after analyzing all page content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "document_title": {
                "type": "string",
                "description": "Main document title extracted from the content",
            },
            "document_subtitle": {
                "type": "string",
                "description": "Subtitle or secondary title if present, empty string otherwise",
            },
            "header_left": {
                "type": "string",
                "description": "Text for the left side of page headers (e.g. company name or 'Confidential')",
            },
            "header_right": {
                "type": "string",
                "description": "Text for the right side of page headers (e.g. short document title or category)",
            },
            "sections": {
                "type": "array",
                "description": "Ordered list of document sections identified from the content",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_page": {
                            "type": "integer",
                            "description": "Original page number where this section starts",
                        },
                        "title": {
                            "type": "string",
                            "description": "Section title (e.g. '1. Introduction', '2. Findings')",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["cover", "toc", "body", "appendix", "references"],
                            "description": "Type of section for styling purposes",
                        },
                    },
                    "required": ["source_page", "title", "type"],
                },
            },
            "page_annotations": {
                "type": "array",
                "description": "Per-page annotations to guide assembly. One entry per source page.",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_page": {
                            "type": "integer",
                            "description": "Original page number",
                        },
                        "section_title": {
                            "type": "string",
                            "description": "Which section this page belongs to",
                        },
                        "show_header": {
                            "type": "boolean",
                            "description": "Whether to show the header on this page (false for cover pages)",
                        },
                        "show_footer": {
                            "type": "boolean",
                            "description": "Whether to show the footer on this page",
                        },
                    },
                    "required": ["source_page", "section_title", "show_header", "show_footer"],
                },
            },
        },
        "required": [
            "document_title",
            "document_subtitle",
            "header_left",
            "header_right",
            "sections",
            "page_annotations",
        ],
    },
}


def _build_page_summary(pages: list[dict]) -> str:
    """Build a compact summary of all pages for Claude to analyze."""
    lines = []
    for page in pages:
        pn = page.get("page_num", 0)
        blocks = page.get("text_blocks", [])
        tables = page.get("tables", [])
        images = page.get("images", [])

        text_preview = []
        for b in blocks:
            t = b.get("text", "").strip()
            if not t:
                continue
            fs = b.get("font_size", 11)
            bold = b.get("is_bold", False)
            prefix = f"[BOLD fs={fs}]" if bold else f"[fs={fs}]"
            preview = t[:200] + ("..." if len(t) > 200 else "")
            text_preview.append(f"  {prefix} {preview}")

        table_info = []
        for ti, tbl in enumerate(tables):
            rc = tbl.get("row_count", len(tbl.get("rows", [])))
            cc = tbl.get("col_count", 1)
            first_row = ""
            rows = tbl.get("rows", [])
            if rows:
                cells = rows[0].get("cells", [])
                first_row = " | ".join(c.get("text", "")[:40] for c in cells[:5])
            table_info.append(f"  TABLE ({rc} rows x {cc} cols): {first_row}")

        lines.append(f"--- PAGE {pn} ---")
        lines.append(f"  Images: {len(images)}, Tables: {len(tables)}, Text blocks: {len(blocks)}")
        for tp in text_preview[:8]:
            lines.append(tp)
        if len(text_preview) > 8:
            lines.append(f"  ... and {len(text_preview) - 8} more text blocks")
        for ti in table_info:
            lines.append(ti)
        lines.append("")

    return "\n".join(lines)


def create_document_plan(client: anthropic.Anthropic, pages: list[dict]) -> dict:
    """Send page summaries to Claude and get a document structure plan.

    Returns:
        dict with document_title, sections, page_annotations, header/footer text, and API metadata
    """
    summary = _build_page_summary(pages)

    prompt = (
        "You are a professional document layout analyst. Below is a summary of all pages "
        "from a translated PDF document. Analyze the content and create a structured document plan.\n\n"
        "YOUR TASK:\n"
        "1. Identify the document title and subtitle from the content (usually on page 1)\n"
        "2. Determine appropriate header text (left: organization/confidentiality, right: short document name)\n"
        "3. Identify logical sections and their starting pages (cover, table of contents, numbered sections, appendices)\n"
        "4. For each page, annotate which section it belongs to, and whether it should show headers/footers\n"
        "   - Cover pages typically don't show headers/footers\n"
        "   - Table of contents pages may or may not show headers\n"
        "   - Body and appendix pages should show headers and footers\n\n"
        "GUIDELINES:\n"
        "- Look at font sizes and bold text to identify headings and section titles\n"
        "- Number sections logically (1. Introduction, 2. Findings, etc.) based on the content\n"
        "- Keep header text short and professional\n"
        "- Use the actual content to derive titles - don't invent content\n\n"
        f"DOCUMENT PAGES ({len(pages)} total):\n{summary}\n\n"
        "Use the submit_document_plan tool to return your analysis."
    )

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        tools=[PLANNER_TOOL],
        tool_choice={"type": "tool", "name": "submit_document_plan"},
        messages=[{"role": "user", "content": prompt}],
    )

    result = {
        "document_title": "",
        "document_subtitle": "",
        "header_left": "",
        "header_right": "",
        "sections": [],
        "page_annotations": [],
        "model": message.model,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }

    for content_block in message.content:
        if content_block.type == "tool_use" and content_block.name == "submit_document_plan":
            plan = content_block.input
            result["document_title"] = plan.get("document_title", "")
            result["document_subtitle"] = plan.get("document_subtitle", "")
            result["header_left"] = plan.get("header_left", "")
            result["header_right"] = plan.get("header_right", "")
            result["sections"] = plan.get("sections", [])
            result["page_annotations"] = plan.get("page_annotations", [])
            break

    return result
