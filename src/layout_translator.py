"""Translate structured page content using Claude with tool-use for structured output."""

import json
import re
import anthropic

from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, SOURCE_LANGUAGE, TARGET_LANGUAGE


TRANSLATE_TOOLS = [
    {
        "name": "submit_translated_page",
        "description": "Submit the translated page content. Each text block and table cell must be translated while preserving the XML/HTML structure, attributes, and image references exactly as-is.",
        "input_schema": {
            "type": "object",
            "properties": {
                "translated_blocks": {
                    "type": "array",
                    "description": "Array of translated text blocks, in the same order as the source",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Block ID (e.g., b0, b1)"},
                            "translated_text": {"type": "string", "description": "Translated text content"},
                        },
                        "required": ["id", "translated_text"],
                    },
                },
                "translated_tables": {
                    "type": "array",
                    "description": "Array of translated tables, in the same order as the source",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Table ID (e.g., t0, t1)"},
                            "rows": {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "description": "2D array of translated cell texts",
                            },
                        },
                        "required": ["id", "rows"],
                    },
                },
            },
            "required": ["translated_blocks", "translated_tables"],
        },
    }
]


def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def translate_page_layout(client: anthropic.Anthropic, page_html: str, page_num: int) -> dict:
    """Translate a structured page using Claude tool-use for reliable structured output.

    Args:
        client: Anthropic client
        page_html: HTML/XML representation of the page layout
        page_num: Page number for logging

    Returns:
        dict with 'translated_blocks' and 'translated_tables' and API metadata
    """
    prompt = (
        f"You are a professional document translator. Translate ALL text content from {SOURCE_LANGUAGE} to {TARGET_LANGUAGE}.\n\n"
        f"Below is a structured representation of page {page_num} of a PDF document. "
        f"It contains text blocks (<p> and <h> tags), images (<img> tags), and possibly tables (<table> tags).\n\n"
        f"RULES:\n"
        f"1. Translate EVERY text block and table cell from {SOURCE_LANGUAGE} to {TARGET_LANGUAGE}\n"
        f"2. Preserve technical terms, proper nouns, and abbreviations as-is\n"
        f"3. Keep the same block IDs (b0, b1, etc.) and table IDs (t0, t1, etc.)\n"
        f"4. Do NOT translate image references or attributes\n"
        f"5. Preserve formatting: if text has line breaks, keep the structure\n"
        f"6. For tables, return a 2D array of translated cell texts matching the original row/column structure\n\n"
        f"Use the submit_translated_page tool to return your translation.\n\n"
        f"SOURCE PAGE:\n{page_html}"
    )

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8192,
        tools=TRANSLATE_TOOLS,
        tool_choice={"type": "tool", "name": "submit_translated_page"},
        messages=[{"role": "user", "content": prompt}],
    )

    result = {
        "translated_blocks": [],
        "translated_tables": [],
        "model": message.model,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }

    for content_block in message.content:
        if content_block.type == "tool_use" and content_block.name == "submit_translated_page":
            tool_input = content_block.input
            result["translated_blocks"] = tool_input.get("translated_blocks", [])
            result["translated_tables"] = tool_input.get("translated_tables", [])
            break

    if not result["translated_blocks"] and not result["translated_tables"]:
        raise RuntimeError(
            f"Claude returned no translations for page {page_num}. "
            f"The tool-use response was empty or malformed."
        )

    return result


def apply_translations(page_data: dict, translation_result: dict) -> dict:
    """Apply translation results back to the page data structure.

    Returns a new page_data dict with translated text.
    """
    translated_page = {
        "page_num": page_data["page_num"],
        "width": page_data["width"],
        "height": page_data["height"],
        "text_blocks": [],
        "images": page_data["images"],
        "tables": [],
    }

    block_translations = {}
    for b in translation_result.get("translated_blocks", []):
        if isinstance(b, dict) and "id" in b and "translated_text" in b:
            block_translations[b["id"]] = b["translated_text"]

    for i, block in enumerate(page_data["text_blocks"]):
        block_id = f"b{i}"
        new_block = dict(block)
        if block_id in block_translations:
            new_block["text"] = block_translations[block_id]
        translated_page["text_blocks"].append(new_block)

    table_translations = {}
    for t in translation_result.get("translated_tables", []):
        if isinstance(t, dict) and "id" in t and "rows" in t:
            table_translations[t["id"]] = t["rows"]

    for i, table in enumerate(page_data["tables"]):
        table_id = f"t{i}"
        new_table = dict(table)
        new_table["rows"] = []

        if table_id in table_translations:
            translated_rows = table_translations[table_id]
            if not isinstance(translated_rows, list):
                new_table["rows"] = table["rows"]
            else:
                for row_idx, orig_row in enumerate(table["rows"]):
                    new_row = {"cells": []}
                    for cell_idx, orig_cell in enumerate(orig_row["cells"]):
                        new_cell = dict(orig_cell)
                        if (row_idx < len(translated_rows)
                                and isinstance(translated_rows[row_idx], list)
                                and cell_idx < len(translated_rows[row_idx])):
                            cell_val = translated_rows[row_idx][cell_idx]
                            new_cell["text"] = str(cell_val) if cell_val is not None else ""
                        new_row["cells"].append(new_cell)
                    new_table["rows"].append(new_row)
        else:
            new_table["rows"] = table["rows"]

        translated_page["tables"].append(new_table)

    return translated_page
