"""
LargeFileTranslator - Main pipeline

Workflow:
1. Create a demo French PDF (optional, for first run)
2. Upload the demo PDF to the Google Drive source folder
3. List all PDFs in the source folder
4. Download each PDF, extract text, translate via Claude API
5. Generate a translated PDF and upload to the destination folder
"""

import os
import sys
import argparse

from src.config import SOURCE_FOLDER_ID, DESTINATION_FOLDER_ID, TEMP_DIR
from src.drive_service import (
    get_drive_service,
    list_pdf_files,
    download_file,
    upload_file,
    file_exists_in_folder,
)
from src.pdf_processor import extract_text_from_pdf, get_pdf_page_count
from src.translator import translate_pages
from src.pdf_writer import create_translated_pdf
from src.create_demo_pdf import create_demo_french_pdf, DEMO_FILENAME


def upload_demo(service):
    """Create and upload the demo French PDF to the source folder."""
    print("\n=== Step 1: Creating demo French PDF ===")
    demo_path = create_demo_french_pdf()

    print("\n=== Step 2: Uploading demo PDF to source folder ===")
    if file_exists_in_folder(service, SOURCE_FOLDER_ID, DEMO_FILENAME):
        print(f"  '{DEMO_FILENAME}' already exists in source folder, skipping upload.")
    else:
        result = upload_file(service, demo_path, SOURCE_FOLDER_ID)
        print(f"  Upload complete. View: {result.get('webViewLink', 'N/A')}")

    return demo_path


def translate_and_upload(service, file_id: str, file_name: str):
    """Download, translate, and upload a single PDF file."""
    print(f"\n--- Processing: {file_name} ---")

    # Check if translated version already exists
    translated_name = f"translated_{file_name}"
    if file_exists_in_folder(service, DESTINATION_FOLDER_ID, translated_name):
        print(f"  '{translated_name}' already exists in destination folder, skipping.")
        return

    # Download
    local_pdf = os.path.join(TEMP_DIR, file_name)
    print(f"  Downloading {file_name}...")
    download_file(service, file_id, local_pdf)

    # Extract text
    page_count = get_pdf_page_count(local_pdf)
    print(f"  Extracted {page_count} page(s) from PDF.")
    pages = extract_text_from_pdf(local_pdf)

    # Translate
    print(f"  Translating {page_count} page(s) with Claude API...")
    translated_pages = translate_pages(pages)

    # Generate translated PDF
    output_pdf = os.path.join(TEMP_DIR, translated_name)
    create_translated_pdf(translated_pages, output_pdf)
    print(f"  Translated PDF written to: {output_pdf}")

    # Upload to destination folder
    print(f"  Uploading '{translated_name}' to destination folder...")
    result = upload_file(service, output_pdf, DESTINATION_FOLDER_ID, translated_name)
    print(f"  Upload complete. View: {result.get('webViewLink', 'N/A')}")


def run_pipeline(skip_demo: bool = False):
    """Run the full translation pipeline."""
    print("=" * 60)
    print("  LargeFileTranslator - PDF Translation Pipeline")
    print("=" * 60)

    # Authenticate
    print("\nAuthenticating with Google Drive...")
    service = get_drive_service()
    print("  Authenticated successfully.")

    # Optionally create and upload demo
    if not skip_demo:
        upload_demo(service)

    # List all PDFs in source folder
    print("\n=== Step 3: Listing PDFs in source folder ===")
    pdf_files = list_pdf_files(service, SOURCE_FOLDER_ID)

    if not pdf_files:
        print("  No PDF files found in the source folder.")
        return

    print(f"  Found {len(pdf_files)} PDF(s):")
    for f in pdf_files:
        print(f"    - {f['name']} (ID: {f['id']})")

    # Translate each file
    print("\n=== Step 4: Translating and uploading PDFs ===")
    for f in pdf_files:
        translate_and_upload(service, f["id"], f["name"])

    print("\n" + "=" * 60)
    print("  Pipeline complete!")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="LargeFileTranslator - Translate PDFs via Claude API and Google Drive")
    parser.add_argument(
        "--skip-demo",
        action="store_true",
        help="Skip creating and uploading the demo French PDF",
    )
    parser.add_argument(
        "--demo-only",
        action="store_true",
        help="Only create and upload the demo PDF, don't translate",
    )
    args = parser.parse_args()

    if args.demo_only:
        service = get_drive_service()
        upload_demo(service)
    else:
        run_pipeline(skip_demo=args.skip_demo)


if __name__ == "__main__":
    main()
