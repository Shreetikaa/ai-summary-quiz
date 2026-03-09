from faster_whisper import WhisperModel

# int8 is faster on CPU and avoids float16 warnings
model = WhisperModel("tiny", device="cpu", compute_type="int8")

def transcribe_video(path: str) -> str:
    segments, _ = model.transcribe(path)
    return " ".join(seg.text.strip() for seg in segments if seg.text).strip()
