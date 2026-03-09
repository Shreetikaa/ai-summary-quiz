import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
RUNS_FOLDER = os.path.join(BASE_DIR, "runs")

# Optional safety: limit upload size (adjust if needed)
# 50MB example:
MAX_CONTENT_LENGTH = 50 * 1024 * 1024
