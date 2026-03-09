from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from utils.chunking import chunk_text

_MODEL_NAME = "facebook/bart-large-cnn"

device = torch.device("cpu")
tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
model = AutoModelForSeq2SeqLM.from_pretrained(_MODEL_NAME).to(device)
model.eval()


def _summarize_chunk(chunk: str, max_length=150, min_length=50) -> str:
    inputs = tokenizer(
        chunk,
        return_tensors="pt",
        truncation=True,
        max_length=1024
    ).to(device)

    with torch.no_grad():
        summary_ids = model.generate(
            **inputs,
            num_beams=4,
            max_length=max_length,
            min_length=min_length,
            early_stopping=True,
            forced_bos_token_id=0
        )

    return tokenizer.decode(summary_ids[0], skip_special_tokens=True)


def summarize_text(text: str) -> str:
    text = (text or "").strip()
    if len(text) < 50:
        return "Text too short to summarize."

    chunks = chunk_text(text, 1000)
    summaries = []
    for c in chunks:
        c = c.strip()
        if c:
            summaries.append(_summarize_chunk(c))

    return " ".join(summaries).strip()
