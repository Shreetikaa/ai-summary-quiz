from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify, redirect
import os, uuid, json

from config import UPLOAD_FOLDER, RUNS_FOLDER, MAX_CONTENT_LENGTH
from services.video_service import transcribe_video
from services.pdf_service import extract_pdf_text
from services.summarize_service import summarize_text

from services.quiz_service import generate_quiz  # fallback quiz

from services.gemini_service import (
    generate_summary_from_text,
    generate_summary_from_pdf_path,
    generate_summary_from_youtube,
    generate_quiz_from_summary
)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RUNS_FOLDER, exist_ok=True)


# ---------- UI ----------
@app.route("/")
def home():
    return redirect("/video")

@app.route("/video")
def video_page():
    return render_template("video.html", active_page="video", title="Video Summarizer")

@app.route("/pdf")
def pdf_page():
    return render_template("pdf.html", active_page="pdf", title="PDF Summarizer")



# ---------- Helpers ----------
def _run_path(run_id: str) -> str:
    return os.path.join(RUNS_FOLDER, f"{run_id}.json")

def _save_run(run: dict) -> None:
    with open(_run_path(run["id"]), "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=2)

def _load_run(run_id: str) -> dict:
    with open(_run_path(run_id), "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- APIs ----------
@app.route("/api/process-video", methods=["POST"])
def api_process_video():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    if not file.filename.lower().endswith(".mp4"):
        return jsonify({"error": "Please upload an .mp4 file"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    transcript = (transcribe_video(file_path) or "").strip()
    if len(transcript) < 50:
        return jsonify({"error": "Not enough transcript extracted to summarize"}), 400

    used = "gemini_text"
    try:
        summary = generate_summary_from_text(transcript)
        if not summary:
            raise ValueError("Empty summary")
    except Exception:
        used = "local_fallback"
        summary = summarize_text(transcript)

    run = {
        "id": str(uuid.uuid4()),
        "source_type": "video_upload",
        "used": used,
        "summary": summary,
        "quiz": [],
        "quiz_settings": {}
    }
    _save_run(run)
    return jsonify(run)


@app.route("/api/process-youtube", methods=["POST"])
def api_process_youtube():
    data = request.get_json(silent=True) or {}
    youtube_url = (data.get("youtube_url") or "").strip()

    if not youtube_url:
        return jsonify({"error": "youtube_url is required"}), 400
    if "youtube.com" not in youtube_url and "youtu.be" not in youtube_url:
        return jsonify({"error": "Please provide a valid YouTube URL"}), 400

    used = "gemini_youtube"
    try:
        summary = generate_summary_from_youtube(youtube_url)
        if not summary:
            raise ValueError("Empty summary")
    except Exception as e:
        return jsonify({"error": f"YouTube summarization failed: {str(e)}"}), 500

    run = {
        "id": str(uuid.uuid4()),
        "source_type": "youtube",
        "used": used,
        "youtube_url": youtube_url,
        "summary": summary,
        "quiz": [],
        "quiz_settings": {}
    }
    _save_run(run)
    return jsonify(run)


@app.route("/api/process-pdf", methods=["POST"])
def api_process_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Please upload a .pdf file"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    extracted_text = (extract_pdf_text(file_path) or "").strip()

    used = "gemini_pdf"
    try:
        summary = generate_summary_from_pdf_path(file_path)
        if not summary:
            raise ValueError("Empty summary")
    except Exception:
        used = "local_fallback"
        if len(extracted_text) < 50:
            return jsonify({"error": "Not enough PDF text extracted for fallback summary"}), 400
        summary = summarize_text(extracted_text)

    run = {
        "id": str(uuid.uuid4()),
        "source_type": "pdf",
        "used": used,
        "uploaded_pdf": os.path.basename(file_path),
        "summary": summary,
        "quiz": [],
        "quiz_settings": {}
    }
    _save_run(run)
    return jsonify(run)


@app.route("/api/generate-quiz", methods=["POST"])
def api_generate_quiz():
    data = request.get_json(silent=True) or {}

    run_id = (data.get("run_id") or "").strip()
    difficulty = (data.get("difficulty") or "mid").strip().lower()
    num_questions = int(data.get("num_questions") or 5)

    if not run_id:
        return jsonify({"error": "run_id is required"}), 400
    if difficulty not in ("easy", "mid", "hard"):
        return jsonify({"error": "difficulty must be easy/mid/hard"}), 400
    if num_questions not in (5, 10, 15):
        return jsonify({"error": "num_questions must be 5/10/15"}), 400

    run = _load_run(run_id)
    summary = (run.get("summary") or "").strip()
    if len(summary) < 30:
        return jsonify({"error": "Summary too short to generate quiz"}), 400

    # ✅ Cache: same settings -> return existing quiz without calling Gemini
    old = run.get("quiz_settings") or {}
    if (
        old.get("difficulty") == difficulty and
        old.get("num_questions") == num_questions and
        isinstance(run.get("quiz"), list) and
        len(run["quiz"]) == num_questions
    ):
        return jsonify({
            "run_id": run_id,
            "difficulty": difficulty,
            "num_questions": num_questions,
            "quiz": run["quiz"],
            "used": old.get("used", "cache")
        })

    # ✅ Try Gemini first; fallback if rate limited
    used = "gemini_quiz"
    try:
        gem = generate_quiz_from_summary(summary, difficulty, num_questions)
        quiz = gem.get("quiz") or []
        if not isinstance(quiz, list) or len(quiz) == 0:
            raise ValueError("Gemini returned empty quiz")
    except Exception:
        used = "local_fallback_quiz"
        quiz = generate_quiz(summary, num_questions=num_questions)

    run["quiz"] = quiz
    run["quiz_settings"] = {"difficulty": difficulty, "num_questions": num_questions, "used": used}
    _save_run(run)

    return jsonify({
        "run_id": run_id,
        "difficulty": difficulty,
        "num_questions": num_questions,
        "quiz": quiz,
        "used": used
    })


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "File too large. Increase MAX_CONTENT_LENGTH in config.py"}), 413


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
