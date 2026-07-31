import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pipeline.parser import parse_pdf
from pipeline.extractor import extract_facts
from pipeline.verifier import verify_extraction
from pipeline.highlighter import render_highlighted_pages
from google.genai import errors as genai_errors

app = Flask(__name__)

import warnings
warnings.filterwarnings("ignore", module="flask_limiter")

limiter = Limiter(get_remote_address, app=app, default_limits=["100 per hour"])
# NOTE: in-memory storage means each gunicorn worker counts separately - with
# 2 workers that's effectively 20/hour, not 10. 
# keeping this small on purpose - no config file needed yet
MAX_FILE_SIZE_MB = 10


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
@limiter.limit("10 per hour")  # each call makes 2 real Gemini requests - this isn't free
def analyze():
    if "file" not in request.files:
        return jsonify({"error": "no file uploaded"}), 400

    uploaded = request.files["file"]

    if uploaded.filename == "":
        return jsonify({"error": "no file selected"}), 400

    if not uploaded.filename.lower().endswith(".pdf"):
        return jsonify({"error": "only PDF files are supported right now"}), 400

    # read straight into memory, never write to disk
    file_bytes = uploaded.read()

    if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        return jsonify({"error": f"file too large (max {MAX_FILE_SIZE_MB}MB)"}), 400

    try:
        parsed = parse_pdf(file_bytes)
    except Exception as e:
        # not narrowing this down yet, just surfacing it so we can see what breaks
        return jsonify({"error": f"couldn't read this PDF: {str(e)}"}), 500

    document_text = parsed["full_text"]

    try:
        extraction = extract_facts(document_text)
        verified = verify_extraction(document_text, extraction, parsed["page_breaks"])
    except genai_errors.ClientError as e:
        if e.code == 429:
            return jsonify({"error": "Gemini's rate limit was hit and retries didn't clear it - wait a minute and try again."}), 503
        return jsonify({"error": f"couldn't analyze this lease: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"couldn't analyze this lease: {str(e)}"}), 500

    citations = [
        {"page": f["page"], "quote": f["source_quote"]}
        for f in verified["facts"] + verified["red_flags"]
        if f.get("page")
    ]
    page_images = render_highlighted_pages(file_bytes, citations)

    return jsonify({
        "clause_count": len(parsed["clauses"]),
        "facts": verified["facts"],
        "red_flags": verified["red_flags"],
        "page_images": page_images,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
