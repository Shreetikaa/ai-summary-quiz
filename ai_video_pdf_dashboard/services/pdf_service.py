from PyPDF2 import PdfReader

def extract_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        if txt.strip():
            parts.append(txt.strip())
    return "\n\n".join(parts).strip()
