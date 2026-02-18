# LargeFileTranslator

## Overview
A web-based PDF translation pipeline with layout-aware processing. Extracts text blocks, images, and tables from PDFs, translates content using Claude AI with tool-use API for structured output, and reconstructs translated PDFs using a three-phase approach: per-page translation with intermediate storage, AI-powered document structure planning, then dynamic layout assembly with consistent headers/footers and section organization.

## Project Architecture
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
├── temp/                         # Temp files, extracted images, intermediate page JSON
│   ├── images/                   # Extracted images from PDFs
│   └── pages/<doc_name>/         # Per-page intermediate JSON files
└── src/
    ├── __init__.py
    ├── config.py                 # Configuration from environment
    ├── drive_service.py          # Google Drive API operations
    ├── layout_extractor.py       # PyMuPDF (text/images) + pdfplumber (tables) extraction
    ├── layout_translator.py      # Claude tool-use API translation with structured output
    ├── document_planner.py       # AI-powered document structure planning (sections, headers/footers)
    ├── page_store.py             # Intermediate per-page JSON storage (Phase 1 output)
    ├── pdf_assembler.py          # Dynamic layout PDF assembly with plan-based formatting (Phase 2)
    ├── layout_pdf_writer.py      # Legacy: absolute-position PDF writer
    ├── pdf_processor.py          # Legacy: simple PDF text extraction
    ├── translator.py             # Legacy: simple text translation
    ├── pdf_writer.py             # Legacy: simple text-only PDF generation
    └── create_demo_pdf.py        # Demo French PDF generator
```

## Translation Pipeline (Three-Phase)
### Phase 1: Extract + Translate + Store
1. **Layout Extraction** (`layout_extractor.py`): Uses PyMuPDF for text blocks with bounding boxes and font info + images with positions. Uses pdfplumber for accurate table detection with line-based strategy.
2. **Structured HTML**: Each page is converted to an HTML/XML representation preserving spatial layout, block IDs, and image references.
3. **Claude Tool-Use Translation** (`layout_translator.py`): Sends structured page HTML to Claude with a tool-use schema (`submit_translated_page`). Claude returns translated text per block and table cells in structured JSON.
4. **Intermediate Storage** (`page_store.py`): Each translated page is saved as a JSON file with all text, images, and table data.

### Phase 1.5: Document Structure Planning
5. **Document Planner** (`document_planner.py`): Sends compact page summaries to Claude to analyze document structure. Returns a plan with: document title/subtitle, header text (left/right), logical sections with types (cover, toc, body, appendix), and per-page annotations (show_header, show_footer, section assignment).

### Phase 2: Measure + Assemble
6. **PDF Assembly** (`pdf_assembler.py`): Uses the document plan to create a professionally formatted PDF:
   - Consistent page headers with organization name and document title
   - Section dividers with styled headings and separator lines
   - Page footers with document title and sequential page numbers
   - Cover pages without headers/footers
   - Dynamic content flow measuring actual text/table/image sizes
   - Automatic page breaks with header/footer continuity
   - Tables with header row styling and repetition on page breaks
   - Images centered and scaled to fit content width

## Cost Tracking
- **Per-page breakdown**: Text blocks, tables, images processed; API cost, compute cost, overhead allocation, total cost per page
- **Per-document summary**: Element counts (text blocks/tables/images), phase timing (extraction/translation/planning/assembly), API tokens and cost
- **Backend costs**: Estimated Replit compute cost (CPU time) and memory cost (peak RSS) tracked per document
- **Grand total**: API costs + compute + memory = true total cost per document
- **Three-column UI cards**: Elements Processed, Processing Time, Cost Breakdown with expandable per-page details
- **Claude API Log**: Per-call cost with total summary; pricing includes structure planning call
- Model-specific pricing (Sonnet, Haiku, Opus variants) with fallback defaults

## Setup Requirements
- **Python 3.11**
- **Dependencies**: flask, google-api-python-client, google-auth-httplib2, google-auth-oauthlib, anthropic, fpdf2, pymupdf, pdfplumber, python-dotenv

## Required Secrets/Environment Variables
- `claude-translator` - Anthropic API key for Claude translations (falls back to `ANTHROPIC_API_KEY`)
- `GOOGLE_SERVICE_ACCOUNT_FILE` - Path to Google service account JSON (default: `service_account.json`)
- `SOURCE_FOLDER_ID` - Google Drive source folder ID
- `DESTINATION_FOLDER_ID` - Google Drive destination folder ID
- `TARGET_LANGUAGE` - Target translation language (default: English)
- `SOURCE_LANGUAGE` - Source language (default: French)
- `ACCESS_PASSWORD` - Password for web UI login
- `CLAUDE_MODEL` - Claude model (default: claude-sonnet-4-20250514)

## How It Works
1. User uploads PDFs directly or selects files from Google Drive source folder
2. User clicks "Translate Selected" on the web UI
3. Phase 1: Pipeline extracts layout (text, images, tables), translates each page via Claude tool-use API, stores results as intermediate JSON
4. Phase 1.5: Claude analyzes all page content and creates a document structure plan (title, sections, headers/footers)
5. Phase 2: Assembler reads all page JSON files, applies the structure plan, measures content, builds PDF with professional formatting
6. Per-document cost report shows API usage and cost breakdown
7. Translated PDFs appear in the web UI for download
8. Claude API Log panel shows real-time details of each API call (model, tokens, timing, cost, errors)

## Google Drive Note
Service accounts cannot upload files to regular Drive folders (no storage quota). Downloads work fine. Translated files are served via the web interface instead.

## Running
- **Web interface**: `python app.py` (port 5000)
- **CLI**: `python main.py` (saves to output/ directory)
