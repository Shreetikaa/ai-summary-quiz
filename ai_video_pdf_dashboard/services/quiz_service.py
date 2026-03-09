import random

def generate_quiz(summary: str, num_questions: int = 5):
    """
    Local fallback quiz generator (used if Gemini is rate-limited).
    Always returns exactly num_questions questions (pads if needed).
    """
    summary = (summary or "").strip()
    if not summary:
        return []

    num_questions = int(num_questions)
    if num_questions not in (5, 10, 15):
        num_questions = 5

    sentences = [s.strip() for s in summary.split(".") if len(s.strip()) > 30]
    quiz = []

    for s in sentences:
        if len(quiz) >= num_questions:
            break

        words = [w.strip(" ,;:()[]\"'") for w in s.split() if len(w.strip()) > 4]
        if len(words) < 6:
            continue

        answer = random.choice(words)
        question = s.replace(answer, "_____")

        options = {answer}
        while len(options) < 4:
            options.add(random.choice(words))

        options = list(options)
        random.shuffle(options)

        quiz.append({
            "question": question,
            "options": options,
            "answer_index": options.index(answer)
        })

    while len(quiz) < num_questions:
        quiz.append({
            "question": "Based on the summary, what is the main idea?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "answer_index": 0
        })

    return quiz
