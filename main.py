"""
LargeFileTranslator - Main pipeline

Workflow:
1. List all PDFs in the Google Drive source folder
2. Download each PDF, extract text, translate via Claude API
3. Save translated PDFs locally in the output/ directory
"""

import os
import sys
import argparse

from src.config import SOURCE_FOLDER_ID, TEMP_DIR
from src.drive_service import (
    get_drive_service,
    list_pdf_files,
    download_file,
)
from src.pdf_processor import extract_text_from_pdf, get_pdf_page_count
from src.translator import translate_pages
from src.pdf_writer import create_translated_pdf

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def translate_file(service, file_id: str, file_name: str):
    """Download, translate, and save a single PDF file locally."""
    print(f"\n--- Processing: {file_name} ---")

    translated_name = f"translated_{file_name}"
    output_pdf = os.path.join(OUTPUT_DIR, translated_name)

    if os.path.exists(output_pdf):
        print(f"  '{translated_name}' already exists in output/, skipping.")
        return

    local_pdf = os.path.join(TEMP_DIR, file_name)
    print(f"  Downloading {file_name}...")
    download_file(service, file_id, local_pdf)

    page_count = get_pdf_page_count(local_pdf)
    print(f"  Extracted {page_count} page(s) from PDF.")
    pages = extract_text_from_pdf(local_pdf)

    print(f"  Translating {page_count} page(s) with Claude API...")
    translated_pages = translate_pages(pages)

    create_translated_pdf(translated_pages, output_pdf)
    print(f"  Translated PDF saved to: {output_pdf}")


def run_pipeline():
    """Run the full translation pipeline."""
    print("=" * 60)
    print("  LargeFileTranslator - PDF Translation Pipeline")
    print("=" * 60)

    print("\nAuthenticating with Google Drive...")
    service = get_drive_service()
    print("  Authenticated successfully.")

    print("\n=== Step 1: Listing PDFs in source folder ===")
    pdf_files = list_pdf_files(service, SOURCE_FOLDER_ID)

    if not pdf_files:
        print("  No PDF files found in the source folder.")
        print("  Upload PDFs to your 'Original File' Google Drive folder and run again.")
        return

    print(f"  Found {len(pdf_files)} PDF(s):")
    for f in pdf_files:
        print(f"    - {f['name']} (ID: {f['id']})")

    print("\n=== Step 2: Translating PDFs ===")
    for f in pdf_files:
        translate_file(service, f["id"], f["name"])

    print("\n" + "=" * 60)
    print(f"  Pipeline complete! Translated files are in: {OUTPUT_DIR}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="LargeFileTranslator - Translate PDFs via Claude API and Google Drive")
    args = parser.parse_args()
    run_pipeline()


if __name__ == "__main__":
    main()
