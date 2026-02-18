"""Flask web server for LargeFileTranslator - serves translated PDFs for download."""

import os
import secrets
import threading
import resource
from functools import wraps
from flask import Flask, render_template, send_from_directory, redirect, url_for, jsonify, session, request, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

DOMAIN = os.environ.get("REPLIT_DEV_DOMAIN", "localhost:5000")
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "")

translation_status = {
    "running": False,
    "current_file": "",
    "current_page": 0,
    "total_pages": 0,
    "log": [],
}

claude_log = []

cost_report = []

REPLIT_COMPUTE_PER_SEC = 0.000007
REPLIT_MEMORY_PER_GB_SEC = 0.000002


def get_memory_mb():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return round(usage.ru_maxrss / 1024, 1)

MODEL_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-7-sonnet-20250219": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-5-20241101": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-haiku-4-5-20241101": {"input": 1.00, "output": 5.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    "claude-opus-4-5-20251101": {"input": 5.00, "output": 25.00},
}

DEFAULT_PRICING = {"input": 3.00, "output": 15.00}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> dict:
    known = model in MODEL_PRICING
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return {
        "total": round(input_cost + output_cost, 6),
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "estimated": not known,
    }


def get_translated_files():
    files = []
    if os.path.exists(OUTPUT_DIR):
        for f in sorted(os.listdir(OUTPUT_DIR)):
            if f.endswith(".pdf"):
                path = os.path.join(OUTPUT_DIR, f)
                size_mb = os.path.getsize(path) / (1024 * 1024)
                files.append({"name": f, "size": f"{size_mb:.2f} MB"})
    return files


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if ACCESS_PASSWORD and not session.get("authenticated"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if not ACCESS_PASSWORD:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        if request.form.get("password") == ACCESS_PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("index"))
        error = "Incorrect password"
    return render_template("login.html", error=error)


@app.route("/")
@login_required
def index():
    files = get_translated_files()
    return render_template("index.html", files=files, status=translation_status, domain=DOMAIN)


@app.route("/api/status")
@login_required
def api_status():
    return jsonify(translation_status)


@app.route("/api/drive-files")
@login_required
def api_drive_files():
    try:
        from src.config import SOURCE_FOLDER_ID
        from src.drive_service import get_drive_service, list_pdf_files
        service = get_drive_service()
        pdf_files = list_pdf_files(service, SOURCE_FOLDER_ID)
        return jsonify({"files": pdf_files, "error": None})
    except Exception as e:
        return jsonify({"files": [], "error": str(e)})


@app.route("/api/translated-files")
@login_required
def api_translated_files():
    return jsonify({"files": get_translated_files()})


@app.route("/api/claude-log")
@login_required
def api_claude_log():
    return jsonify({"entries": claude_log})


@app.route("/api/cost-report")
@login_required
def api_cost_report():
    return jsonify({"documents": cost_report})


@app.route("/download/<filename>")
@login_required
def download(filename):
    safe_name = os.path.basename(filename)
    if not safe_name.endswith(".pdf"):
        abort(404)
    return send_from_directory(OUTPUT_DIR, safe_name, as_attachment=True)


@app.route("/upload", methods=["POST"])
@login_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "" or not file.filename.endswith(".pdf"):
        return jsonify({"error": "Please upload a PDF file"}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_DIR, filename)
    file.save(save_path)
    return jsonify({"filename": filename, "path": save_path})


@app.route("/translate/upload", methods=["POST"])
@login_required
def translate_uploaded():
    if translation_status["running"]:
        return jsonify({"error": "Translation already in progress"}), 400

    data = request.get_json()
    filenames = data.get("filenames", [])
    if not filenames:
        return jsonify({"error": "No files selected"}), 400

    paths = []
    for fn in filenames:
        safe = secure_filename(fn)
        path = os.path.join(UPLOAD_DIR, safe)
        if os.path.exists(path):
            paths.append((safe, path))

    if not paths:
        return jsonify({"error": "No valid files found"}), 400

    thread = threading.Thread(target=run_local_translation, args=(paths,), daemon=True)
    thread.start()
    return jsonify({"started": True})


@app.route("/translate/drive", methods=["POST"])
@login_required
def translate_drive():
    if translation_status["running"]:
        return jsonify({"error": "Translation already in progress"}), 400

    data = request.get_json()
    file_ids = data.get("files", [])
    if not file_ids:
        return jsonify({"error": "No files selected"}), 400

    thread = threading.Thread(target=run_drive_translation, args=(file_ids,), daemon=True)
    thread.start()
    return jsonify({"started": True})


def _translate_pdf_file(local_pdf: str, filename: str, output_pdf: str, log: list):
    """Three-phase translation pipeline with comprehensive cost tracking.
    Phase 1: Extract layout, translate each page, store intermediate results.
    Phase 1.5: AI-powered document structure planning.
    Phase 2: Load all pages, measure content, assemble PDF with dynamic layout.
    """
    import time
    from datetime import datetime
    from src.config import TEMP_DIR
    from src.layout_extractor import extract_page_layout, layout_to_html
    from src.layout_translator import get_client, translate_page_layout, apply_translations
    from src.page_store import get_page_dir, save_page_data, load_all_pages
    from src.pdf_assembler import assemble_pdf

    translation_status["current_file"] = filename
    doc_start_time = time.time()
    mem_before = get_memory_mb()

    log.append(f"Phase 1: Analyzing layout of {filename}...")
    extract_start = time.time()
    layout_data = extract_page_layout(local_pdf, TEMP_DIR)
    extract_elapsed = round(time.time() - extract_start, 2)
    page_count = layout_data["page_count"]
    translation_status["total_pages"] = page_count

    total_text_blocks = sum(len(p.get("text_blocks", [])) for p in layout_data["pages"])
    total_images = sum(len(p.get("images", [])) for p in layout_data["pages"])
    total_tables = sum(len(p.get("tables", [])) for p in layout_data["pages"])
    log.append(f"Found {page_count} pages, {total_text_blocks} text blocks, {total_images} images, {total_tables} tables (extraction: {extract_elapsed}s)")

    page_dir = get_page_dir(TEMP_DIR, filename)
    client = get_client()

    page_details = []

    doc_cost_entry = {
        "filename": filename,
        "pages": page_count,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": 0.0,
        "model": "",
        "api_calls": 0,
        "status": "in_progress",
        "element_counts": {
            "text_blocks": total_text_blocks,
            "images": total_images,
            "tables": total_tables,
        },
        "phase_timing": {
            "extraction_sec": extract_elapsed,
            "translation_sec": 0.0,
            "planning_sec": 0.0,
            "assembly_sec": 0.0,
            "total_sec": 0.0,
        },
        "backend_costs": {
            "compute_sec": 0.0,
            "compute_cost_usd": 0.0,
            "peak_memory_mb": 0.0,
            "memory_cost_usd": 0.0,
        },
        "api_cost_usd": 0.0,
        "compute_cost_usd": 0.0,
        "grand_total_usd": 0.0,
        "page_details": page_details,
    }
    cost_report.append(doc_cost_entry)

    translation_start = time.time()

    for page_data in layout_data["pages"]:
        page_num = page_data["page_num"]
        translation_status["current_page"] = page_num
        page_start = time.time()

        text_blocks = page_data.get("text_blocks", [])
        tables = page_data.get("tables", [])
        images = page_data.get("images", [])

        pg_text_blocks = len(text_blocks)
        pg_tables = len(tables)
        pg_images = len(images)

        has_text = any(b["text"].strip() for b in text_blocks)
        has_tables = bool(tables)

        if not has_text and not has_tables:
            save_page_data(page_dir, page_num, page_data)
            page_details.append({
                "page_num": page_num,
                "text_blocks": pg_text_blocks,
                "tables": pg_tables,
                "images": pg_images,
                "api_cost": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "translate_sec": 0.0,
                "skipped": True,
            })
            log.append(f"Page {page_num}: no text ({pg_images} images), preserving layout only")
            continue

        page_html = layout_to_html(page_data)

        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "type": "request",
            "label": f"page {page_num} ({pg_text_blocks} blocks, {pg_tables} tables, {pg_images} images)",
            "input_chars": len(page_html),
            "status": "sending",
        }
        claude_log.append(entry)

        start = time.time()
        try:
            result = translate_page_layout(client, page_html, page_num)
            elapsed = round(time.time() - start, 1)

            model = result.get("model", "")
            in_tok = result.get("input_tokens", 0)
            out_tok = result.get("output_tokens", 0)
            cost_info = calculate_cost(model, in_tok, out_tok)
            page_cost = cost_info["total"]

            entry["status"] = "success"
            entry["elapsed_sec"] = elapsed
            entry["model"] = model
            entry["input_tokens"] = in_tok
            entry["output_tokens"] = out_tok
            entry["cost_usd"] = page_cost
            entry["cost_estimated"] = cost_info["estimated"]
            entry["output_chars"] = sum(
                len(b.get("translated_text", "")) if isinstance(b, dict) else 0
                for b in result.get("translated_blocks", [])
            )

            doc_cost_entry["total_input_tokens"] += in_tok
            doc_cost_entry["total_output_tokens"] += out_tok
            doc_cost_entry["total_cost_usd"] = round(doc_cost_entry["total_cost_usd"] + page_cost, 6)
            doc_cost_entry["model"] = model
            doc_cost_entry["api_calls"] += 1
            if cost_info["estimated"]:
                doc_cost_entry["cost_estimated"] = True

            translated_page = apply_translations(page_data, result)
            save_page_data(page_dir, page_num, translated_page)

            block_count = len(result.get("translated_blocks", []))
            table_count_t = len(result.get("translated_tables", []))
            page_total_sec = round(time.time() - page_start, 2)

            page_details.append({
                "page_num": page_num,
                "text_blocks": pg_text_blocks,
                "tables": pg_tables,
                "images": pg_images,
                "translated_blocks": block_count,
                "translated_tables": table_count_t,
                "api_cost": page_cost,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "translate_sec": elapsed,
                "total_sec": page_total_sec,
                "skipped": False,
            })

            est_label = " (est.)" if cost_info["estimated"] else ""
            log.append(f"Page {page_num}: {pg_text_blocks} blocks, {pg_tables} tables, {pg_images} images -> translated {block_count} blocks, {table_count_t} tables ({elapsed}s) [${page_cost:.4f}{est_label}]")

        except Exception as e:
            elapsed = round(time.time() - start, 1)
            entry["status"] = "error"
            entry["elapsed_sec"] = elapsed
            entry["error"] = str(e)
            doc_cost_entry["status"] = "error"
            raise

    translation_elapsed = round(time.time() - translation_start, 2)
    doc_cost_entry["phase_timing"]["translation_sec"] = translation_elapsed

    est_note = " (estimated)" if doc_cost_entry.get("cost_estimated") else ""
    log.append(f"Translation API cost: ${doc_cost_entry['total_cost_usd']:.4f}{est_note} ({doc_cost_entry['total_input_tokens']:,} in + {doc_cost_entry['total_output_tokens']:,} out tokens)")

    log.append("Planning document structure with AI...")
    all_pages = load_all_pages(page_dir)

    from src.document_planner import create_document_plan
    plan_entry = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "type": "request",
        "label": "document structure planning",
        "input_chars": sum(len(b.get("text", "")) for p in all_pages for b in p.get("text_blocks", [])),
        "status": "sending",
    }
    claude_log.append(plan_entry)

    plan_start = time.time()
    try:
        document_plan = create_document_plan(client, all_pages)
        plan_elapsed = round(time.time() - plan_start, 1)

        plan_model = document_plan.get("model", "")
        plan_in = document_plan.get("input_tokens", 0)
        plan_out = document_plan.get("output_tokens", 0)
        plan_cost_info = calculate_cost(plan_model, plan_in, plan_out)

        plan_entry["status"] = "success"
        plan_entry["elapsed_sec"] = plan_elapsed
        plan_entry["model"] = plan_model
        plan_entry["input_tokens"] = plan_in
        plan_entry["output_tokens"] = plan_out
        plan_entry["cost_usd"] = plan_cost_info["total"]
        plan_entry["cost_estimated"] = plan_cost_info["estimated"]
        plan_entry["output_chars"] = len(str(document_plan.get("sections", [])))

        doc_cost_entry["total_input_tokens"] += plan_in
        doc_cost_entry["total_output_tokens"] += plan_out
        doc_cost_entry["total_cost_usd"] = round(doc_cost_entry["total_cost_usd"] + plan_cost_info["total"], 6)
        doc_cost_entry["api_calls"] += 1

        section_count = len(document_plan.get("sections", []))
        doc_title = document_plan.get("document_title", "Unknown")
        log.append(f"Document plan: '{doc_title}' with {section_count} sections ({plan_elapsed}s) [${plan_cost_info['total']:.4f}]")

    except Exception as e:
        plan_elapsed = round(time.time() - plan_start, 1)
        plan_entry["status"] = "error"
        plan_entry["elapsed_sec"] = plan_elapsed
        plan_entry["error"] = str(e)
        document_plan = None
        log.append(f"Document planning failed ({e}), assembling without structure plan...")

    doc_cost_entry["phase_timing"]["planning_sec"] = round(plan_elapsed, 2)

    log.append("Phase 2: Assembling PDF with dynamic layout...")
    assembly_start = time.time()
    assemble_pdf(all_pages, output_pdf, document_plan)
    assembly_elapsed = round(time.time() - assembly_start, 2)
    doc_cost_entry["phase_timing"]["assembly_sec"] = assembly_elapsed

    doc_total_sec = round(time.time() - doc_start_time, 2)
    doc_cost_entry["phase_timing"]["total_sec"] = doc_total_sec

    mem_after = get_memory_mb()
    doc_mem = max(mem_after - mem_before, 10)
    compute_cost = round(doc_total_sec * REPLIT_COMPUTE_PER_SEC, 6)
    memory_cost = round(doc_total_sec * (doc_mem / 1024) * REPLIT_MEMORY_PER_GB_SEC, 6)
    total_backend_cost = round(compute_cost + memory_cost, 6)

    doc_cost_entry["backend_costs"]["compute_sec"] = doc_total_sec
    doc_cost_entry["backend_costs"]["compute_cost_usd"] = compute_cost
    doc_cost_entry["backend_costs"]["peak_memory_mb"] = doc_mem
    doc_cost_entry["backend_costs"]["memory_cost_usd"] = memory_cost

    doc_cost_entry["api_cost_usd"] = doc_cost_entry["total_cost_usd"]
    doc_cost_entry["compute_cost_usd"] = total_backend_cost
    doc_cost_entry["grand_total_usd"] = round(doc_cost_entry["total_cost_usd"] + total_backend_cost, 6)

    num_pages = max(len(page_details), 1)
    backend_per_page = round(total_backend_cost / num_pages, 8)

    for p in page_details:
        pg_api = p.get("api_cost", 0)
        if p.get("skipped"):
            p["compute_cost"] = 0.0
            p["overhead_cost"] = backend_per_page
            p["total_cost"] = round(backend_per_page, 6)
        else:
            p["compute_cost"] = backend_per_page
            p["overhead_cost"] = 0.0
            p["total_cost"] = round(pg_api + backend_per_page, 6)

    doc_cost_entry["status"] = "completed"

    output_size_mb = round(os.path.getsize(output_pdf) / (1024 * 1024), 2) if os.path.exists(output_pdf) else 0
    doc_cost_entry["output_size_mb"] = output_size_mb

    log.append(f"Assembly complete ({assembly_elapsed}s), output: {output_size_mb} MB")
    log.append(f"Total processing: {doc_total_sec}s | API: ${doc_cost_entry['api_cost_usd']:.4f} | Compute: ${doc_cost_entry['compute_cost_usd']:.6f} | Grand total: ${doc_cost_entry['grand_total_usd']:.4f}")


def run_local_translation(file_paths):
    translation_status["running"] = True
    translation_status["log"] = []
    claude_log.clear()
    cost_report.clear()
    log = translation_status["log"]

    try:
        for filename, local_pdf in file_paths:
            translated_name = f"translated_{filename}"
            output_pdf = os.path.join(OUTPUT_DIR, translated_name)

            if os.path.exists(output_pdf):
                log.append(f"'{translated_name}' already exists, skipping.")
                continue

            _translate_pdf_file(local_pdf, filename, output_pdf, log)
            log.append(f"Saved: {translated_name}")

        log.append("Translation complete!")
    except Exception as e:
        log.append(f"Error: {str(e)}")
    finally:
        translation_status["running"] = False
        translation_status["current_file"] = ""
        translation_status["current_page"] = 0
        translation_status["total_pages"] = 0


def run_drive_translation(file_selections):
    from src.config import TEMP_DIR
    from src.drive_service import get_drive_service, download_file

    translation_status["running"] = True
    translation_status["log"] = []
    claude_log.clear()
    cost_report.clear()
    log = translation_status["log"]

    try:
        log.append("Connecting to Google Drive...")
        service = get_drive_service()
        log.append("Connected.")

        for file_info in file_selections:
            file_id = file_info["id"]
            file_name = file_info["name"]
            translated_name = f"translated_{file_name}"
            output_pdf = os.path.join(OUTPUT_DIR, translated_name)

            if os.path.exists(output_pdf):
                log.append(f"'{translated_name}' already exists, skipping.")
                continue

            log.append(f"Downloading {file_name}...")
            local_pdf = os.path.join(TEMP_DIR, file_name)
            download_file(service, file_id, local_pdf)

            _translate_pdf_file(local_pdf, file_name, output_pdf, log)
            log.append(f"Saved: {translated_name}")

        log.append("Translation complete!")
    except Exception as e:
        log.append(f"Error: {str(e)}")
    finally:
        translation_status["running"] = False
        translation_status["current_file"] = ""
        translation_status["current_page"] = 0
        translation_status["total_pages"] = 0


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
