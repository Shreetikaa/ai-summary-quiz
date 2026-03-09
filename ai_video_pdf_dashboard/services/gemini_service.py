import os
import json
import re
import base64
import time
import random
import requests
from typing import Any, Dict

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def _extract_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}

    return {}


def _post_generate_content(payload: Dict[str, Any], timeout_sec: int = 240, max_retries: int = 5) -> Dict[str, Any]:
    """
    Gemini generateContent caller with exponential backoff for 429/503.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set (put it in .env)")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}

    for attempt in range(max_retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)

            # Rate limit / transient
            if r.status_code in (429, 503):
                sleep_s = (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(sleep_s)
                continue

            r.raise_for_status()
            return r.json()

        except requests.exceptions.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            if status in (429, 503) and attempt < max_retries - 1:
                sleep_s = (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(sleep_s)
                continue
            raise

    raise RuntimeError("Gemini API rate-limited (429). Please try again in a minute.")


def generate_summary_from_text(text: str) -> str:
    prompt = """
Summarize the following content in 150–220 words.
Return ONLY the summary text.
""".strip()

    payload = {"contents": [{"parts": [{"text": prompt + "\n\nText:\n" + text}]}]}
    data = _post_generate_content(payload, timeout_sec=240)

    out = ""
    try:
        out = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        out = ""
    return (out or "").strip()


def generate_summary_from_pdf_path(pdf_path: str) -> str:
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    prompt = """
Summarize the document in 150–220 words.
Return ONLY the summary text.
""".strip()

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "application/pdf", "data": encoded_pdf}},
                {"text": prompt}
            ]
        }]
    }

    data = _post_generate_content(payload, timeout_sec=300)

    out = ""
    try:
        out = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        out = ""
    return (out or "").strip()


def generate_summary_from_youtube(youtube_url: str) -> str:
    prompt = """
Summarize the YouTube video in 150–220 words.
Return ONLY the summary text.
""".strip()

    payload = {
        "contents": [{
            "parts": [
                {"file_data": {"file_uri": youtube_url}},
                {"text": prompt}
            ]
        }]
    }

    data = _post_generate_content(payload, timeout_sec=300)

    out = ""
    try:
        out = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        out = ""
    return (out or "").strip()


def generate_quiz_from_summary(summary: str, difficulty: str, num_questions: int) -> Dict[str, Any]:
    """
    Generate MCQ quiz from summary using Gemini.
    Returns dict: { "quiz": [ {question, options, answer_index} ] }
    """
    difficulty = (difficulty or "mid").lower()
    if difficulty not in ("easy", "mid", "hard"):
        difficulty = "mid"

    if num_questions not in (5, 10, 15):
        num_questions = 5

    diff_rules = {
        "easy": "Questions should be straightforward and fact-based from the summary.",
        "mid": "Questions should test understanding and main ideas (moderate).",
        "hard": "Questions should test deeper reasoning/inference and tricky distinctions."
    }[difficulty]

    prompt = f"""
Create a multiple-choice quiz FROM THIS SUMMARY.

Return ONLY valid JSON in this format:
{{
  "quiz": [
    {{
      "question": "string",
      "options": ["A", "B", "C", "D"],
      "answer_index": 0
    }}
  ]
}}

Rules:
- Create exactly {num_questions} questions.
- 4 options each.
- answer_index must be 0..3.
- No explanations.
- {diff_rules}

SUMMARY:
{summary}
""".strip()

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    data = _post_generate_content(payload, timeout_sec=240)

    out_text = ""
    try:
        out_text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        out_text = ""

    parsed = _extract_json(out_text)
    if not isinstance(parsed.get("quiz"), list):
        parsed["quiz"] = []
    return parsed
