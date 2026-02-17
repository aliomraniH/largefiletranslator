# LargeFileTranslator

Translate large PDF files using Claude API and Google Drive. The pipeline reads PDFs from a source Google Drive folder, translates them from French to English (configurable), and uploads the translated PDFs to a destination folder.

## Architecture

```
Google Drive (Source Folder)
        |
        v
  Download PDF
        |
        v
  Extract Text (PyMuPDF)
        |
        v
  Translate via Claude API (chunked for large files)
        |
        v
  Generate Translated PDF (fpdf2)
        |
        v
Google Drive (Destination Folder)
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Google Drive API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the **Google Drive API**
3. Create a **Service Account** and download the JSON key file
4. Save it as `service_account.json` in the project root
5. Share both Google Drive folders with the service account email (give Editor access)

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `ANTHROPIC_API_KEY` - your Anthropic API key
- `GOOGLE_SERVICE_ACCOUNT_FILE` - path to your service account JSON (default: `service_account.json`)
- Source/destination folder IDs are pre-configured

### 4. Run the pipeline

```bash
# Full pipeline: create demo PDF, upload, translate all PDFs, upload results
python main.py

# Skip the demo PDF creation
python main.py --skip-demo

# Only create and upload the demo PDF
python main.py --demo-only
```

## Project Structure

```
largefiletranslator/
├── main.py                  # Main pipeline entry point
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── .gitignore
├── README.md
└── src/
    ├── __init__.py
    ├── config.py            # Configuration from environment
    ├── drive_service.py     # Google Drive API operations
    ├── pdf_processor.py     # PDF text extraction (PyMuPDF)
    ├── translator.py        # Claude API translation with chunking
    ├── pdf_writer.py        # Translated PDF generation (fpdf2)
    └── create_demo_pdf.py   # Demo French PDF generator
```

## How It Works

1. **Demo PDF**: A 3-page French document about AI is generated locally
2. **Upload**: The demo PDF is uploaded to the source Google Drive folder
3. **List**: All PDFs in the source folder are listed
4. **For each PDF**:
   - Download locally
   - Extract text page-by-page using PyMuPDF
   - Translate each page via Claude API (large pages are chunked automatically)
   - Generate a new PDF with the translated content
   - Upload the translated PDF to the destination folder

## Google Drive Folders

- **Source**: [Input PDFs](https://drive.google.com/drive/folders/1XBs5PdhcUSgFr2oBsrpt5UQgwHkfefAo)
- **Destination**: [Translated PDFs](https://drive.google.com/drive/folders/1kUsgJwhunnz6V85blXnyBKAvKKTRnU0c)
