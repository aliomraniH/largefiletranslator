# LargeFileTranslator

A web-based PDF translation pipeline that preserves document layout, images, and tables. Built with Claude AI's tool-use API for structured translation output, the system uses a three-phase architecture: layout-aware extraction and per-page translation, AI-powered document structure planning, and dynamic PDF assembly with professional formatting.

## Features

- **Layout-Aware Extraction**: Extracts text blocks with bounding boxes and font metadata, images with positions, and tables with cell structure
- **Structured AI Translation**: Uses Claude's tool-use API to return translated content in structured JSON, preserving block-level granularity
- **Document Structure Planning**: AI analyzes full document content to create a coherent output plan with titles, sections, headers, and footers
- **Professional PDF Output**: Dynamically assembled PDFs with consistent headers/footers, section dividers, styled tables, and properly placed images
- **Comprehensive Cost Tracking**: Per-page and per-document cost breakdown including API tokens, compute time, memory usage, and backend costs
- **Google Drive Integration**: Optional source/destination folder support via service account
- **Web Interface**: Upload PDFs, monitor translation progress, view cost reports, and download results
- **CLI Mode**: Standalone command-line pipeline for batch processing

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │           Phase 1: Extract + Translate   │
                    │                                         │
  Upload PDF ──►    │  Layout Extractor (PyMuPDF + pdfplumber)│
                    │         │                               │
                    │         ▼                               │
                    │  Structured HTML per page                │
                    │         │                               │
                    │         ▼                               │
                    │  Claude Tool-Use Translation             │
                    │         │                               │
                    │         ▼                               │
                    │  Intermediate JSON (per-page storage)    │
                    └─────────────┬───────────────────────────┘
                                  │
                    ┌─────────────▼───────────────────────────┐
                    │       Phase 1.5: Document Planning       │
                    │                                         │
                    │  Claude analyzes all page summaries      │
                    │  Returns: title, sections, headers,      │
                    │           footers, per-page annotations   │
                    └─────────────┬───────────────────────────┘
                                  │
                    ┌─────────────▼───────────────────────────┐
                    │       Phase 2: Measure + Assemble        │
                    │                                         │
                    │  Read page JSON + document plan          │
                    │         │                               │
                    │         ▼                               │
                    │  Dynamic layout calculation              │
                    │  Content flow with page breaks           │
                    │  Headers, footers, section dividers      │
                    │         │                               │
                    │         ▼                               │
                    │  Professional formatted PDF              │
                    └─────────────────────────────────────────┘
```

## Translation Pipeline

### Phase 1: Extract + Translate + Store

1. **Layout Extraction** (`src/layout_extractor.py`): Uses PyMuPDF to extract text blocks with bounding boxes and font information, plus images with positions. Uses pdfplumber for accurate table detection with a line-based strategy.

2. **Structured HTML Generation**: Each page is converted to an HTML/XML representation that preserves spatial layout, block IDs, and image references.

3. **Claude Tool-Use Translation** (`src/layout_translator.py`): Sends structured page HTML to Claude with a tool-use schema (`submit_translated_page`). Claude returns translated text per block and table cells in structured JSON format.

4. **Intermediate Storage** (`src/page_store.py`): Each translated page is saved as a JSON file containing all text blocks, images, and table data. This enables resumable processing and decouples translation from assembly.

### Phase 1.5: Document Structure Planning

5. **Document Planner** (`src/document_planner.py`): Sends compact page summaries to Claude to analyze the overall document structure. Returns a plan including:
   - Document title and subtitle
   - Header text (left/right)
   - Logical sections with types (cover, table of contents, body, appendix)
   - Per-page annotations (show_header, show_footer, section assignment)

### Phase 2: Measure + Assemble

6. **PDF Assembly** (`src/pdf_assembler.py`): Uses the document plan to create a professionally formatted PDF:
   - Consistent page headers with organization name and document title
   - Section dividers with styled headings and separator lines
   - Page footers with document title and sequential page numbers
   - Cover pages without headers/footers
   - Dynamic content flow measuring actual text/table/image sizes
   - Automatic page breaks with header/footer continuity
   - Tables with header row styling and repetition on page breaks
   - Images centered and scaled to fit content width

## Cost Tracking

The system provides comprehensive cost tracking at multiple levels:

- **Per-page breakdown**: Text blocks, tables, and images processed; API cost, backend cost, shared costs, and total cost per page
- **Per-document summary**: Aggregate element counts, phase timing (extraction, translation, planning, assembly), total API tokens, and cost
- **Backend costs**: Estimated compute cost (CPU time) and memory cost (peak RSS) tracked per document using Replit pricing rates
- **Grand total**: API costs + compute + memory = true total cost per document
- **Claude API Log**: Real-time per-call details showing model, tokens, timing, cost, and errors
- **Model-specific pricing**: Supports Sonnet, Haiku, and Opus variants with fallback defaults

## Project Structure

```
largefiletranslator/
├── app.py                        # Flask web server (main entry point)
├── main.py                       # CLI pipeline (standalone usage)
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variable template
├── templates/
│   ├── index.html                # Web UI template
│   └── login.html                # Login page template
├── output/                       # Translated PDFs saved here
├── uploads/                      # User-uploaded PDFs
├── temp/                         # Temp files during processing
│   ├── images/                   # Extracted images from PDFs
│   └── pages/<doc_name>/         # Per-page intermediate JSON files
└── src/
    ├── __init__.py
    ├── config.py                 # Configuration from environment
    ├── drive_service.py          # Google Drive API operations
    ├── layout_extractor.py       # PyMuPDF (text/images) + pdfplumber (tables)
    ├── layout_translator.py      # Claude tool-use API translation
    ├── document_planner.py       # AI-powered document structure planning
    ├── page_store.py             # Intermediate per-page JSON storage
    ├── pdf_assembler.py          # Dynamic layout PDF assembly
    ├── layout_pdf_writer.py      # Legacy: absolute-position PDF writer
    ├── pdf_processor.py          # Legacy: simple PDF text extraction
    ├── translator.py             # Legacy: simple text translation
    ├── pdf_writer.py             # Legacy: simple text-only PDF generation
    └── create_demo_pdf.py        # Demo French PDF generator
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Required packages**: flask, anthropic, fpdf2, pymupdf, pdfplumber, python-dotenv, werkzeug, google-api-python-client, google-auth-httplib2, google-auth-oauthlib

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your settings:

| Variable | Description | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude translations | *required* |
| `ACCESS_PASSWORD` | Password for web UI login | *none (no auth)* |
| `CLAUDE_MODEL` | Claude model to use | `claude-sonnet-4-20250514` |
| `TARGET_LANGUAGE` | Target translation language | `English` |
| `SOURCE_LANGUAGE` | Source document language | `French` |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to Google service account JSON | `service_account.json` |
| `SOURCE_FOLDER_ID` | Google Drive source folder ID | *optional* |
| `DESTINATION_FOLDER_ID` | Google Drive destination folder ID | *optional* |

### 3. Google Drive Setup (Optional)

Google Drive integration is optional. You can upload PDFs directly through the web UI without it.

If you want Google Drive source folder support:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the **Google Drive API**
3. Create a **Service Account** and download the JSON key file
4. Save it as `service_account.json` in the project root
5. Share the Google Drive source folder with the service account email (give Viewer access)

**Note**: Service accounts cannot upload files to regular Drive folders (no storage quota). Downloads work fine. Translated files are served via the web interface instead.

## Running

### Web Interface

```bash
python app.py
```

The web UI runs on port 5000 and provides:
- PDF upload (drag and drop or file picker)
- Google Drive file browser (if configured)
- Real-time translation progress
- Cost report with per-page breakdown
- Claude API call log
- Download links for translated PDFs

### CLI Mode

```bash
python main.py

python main.py --skip-demo    # Skip demo PDF creation
python main.py --demo-only    # Only create the demo PDF
```

Translated PDFs are saved to the `output/` directory.

## How It Works

1. User uploads PDFs directly through the web UI or selects files from a Google Drive source folder
2. User clicks "Translate Selected" to start the pipeline
3. **Phase 1**: Pipeline extracts layout (text blocks, images, tables), translates each page via Claude tool-use API, and stores results as intermediate JSON files
4. **Phase 1.5**: Claude analyzes all page content and creates a document structure plan (title, sections, headers/footers)
5. **Phase 2**: Assembler reads all page JSON files, applies the structure plan, measures content dimensions, and builds the final PDF with professional formatting
6. Per-document cost report shows API usage, compute costs, and full cost breakdown
7. Translated PDFs appear in the web UI for download
8. Claude API Log panel shows real-time details of each API call (model, tokens, timing, cost, errors)

## Technology Stack

- **Python 3.11**
- **Flask** - Web server and API
- **Anthropic Claude API** - AI translation with tool-use for structured output
- **PyMuPDF (fitz)** - PDF text and image extraction with bounding boxes
- **pdfplumber** - Table detection and extraction
- **FPDF2** - PDF generation with dynamic layout
- **Google Drive API** - Optional file source integration
