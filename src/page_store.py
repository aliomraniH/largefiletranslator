"""Store and load per-page translation results as intermediate JSON files."""

import json
import os


def get_page_dir(temp_dir: str, doc_name: str) -> str:
    safe_name = doc_name.replace(" ", "_").replace(".", "_")
    page_dir = os.path.join(temp_dir, "pages", safe_name)
    os.makedirs(page_dir, exist_ok=True)
    return page_dir


def save_page_data(page_dir: str, page_num: int, page_data: dict):
    serializable = _make_serializable(page_data)
    path = os.path.join(page_dir, f"page_{page_num:04d}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
    return path


def load_all_pages(page_dir: str) -> list[dict]:
    pages = []
    files = sorted(f for f in os.listdir(page_dir) if f.endswith(".json"))
    for fname in files:
        path = os.path.join(page_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            pages.append(json.load(f))
    return pages


def _make_serializable(data: dict) -> dict:
    result = dict(data)
    result["text_blocks"] = [
        {
            "text": b.get("text", ""),
            "bbox": b.get("bbox", [0, 0, 0, 0]),
            "font_size": b.get("font_size", 11),
            "is_bold": b.get("is_bold", False),
            "font_name": b.get("font_name", ""),
        }
        for b in data.get("text_blocks", [])
    ]
    result["images"] = [
        {
            "path": img.get("path", ""),
            "bbox": img.get("bbox", [0, 0, 0, 0]),
            "width": img.get("width", 0),
            "height": img.get("height", 0),
        }
        for img in data.get("images", [])
    ]
    result["tables"] = [
        {
            "bbox": t.get("bbox", [0, 0, 0, 0]),
            "row_count": t.get("row_count", 0),
            "col_count": t.get("col_count", 0),
            "rows": [
                {
                    "cells": [
                        {"text": c.get("text", ""), "bbox": c.get("bbox", [0, 0, 0, 0])}
                        for c in row.get("cells", [])
                    ]
                }
                for row in t.get("rows", [])
            ],
        }
        for t in data.get("tables", [])
    ]
    return result
