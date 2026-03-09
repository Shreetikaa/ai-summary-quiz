let currentRunId = null;
let currentQuiz = [];

const pdfForm = document.getElementById("pdfForm");
const pdfFile = document.getElementById("pdfFile");
const pdfBtn = document.getElementById("pdfBtn");

const pdfStatus = document.getElementById("pdfStatus");
const summaryBlock = document.getElementById("summaryBlock");
const summaryText = document.getElementById("summaryText");

const usedPill = document.getElementById("usedPill");
const sourcePill = document.getElementById("sourcePill");

const difficultyEl = document.getElementById("difficulty");
const numQuestionsEl = document.getElementById("numQuestions");
const genQuizBtn = document.getElementById("genQuizBtn");
const quizMeta = document.getElementById("quizMeta");

const quizArea = document.getElementById("quizArea");
const submitQuizBtn = document.getElementById("submitQuizBtn");
const resetQuizBtn = document.getElementById("resetQuizBtn");
const scoreArea = document.getElementById("scoreArea");

function esc(s){ return (s||"").replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])); }

function status(msg, type="info"){
  if (!msg) { pdfStatus.innerHTML = ""; return; }
  pdfStatus.innerHTML = `<div class="alert alert-${type} mb-0">${msg}</div>`;
}

function setLoading(btn, isLoading, textWhenLoading="Working…", textWhenDone=null){
  if (!btn) return;
  btn.disabled = isLoading;
  if (isLoading){
    btn.dataset.oldText = btn.innerText;
    btn.innerText = textWhenLoading;
  } else {
    btn.innerText = textWhenDone || btn.dataset.oldText || btn.innerText;
  }
}

function resetQuizUI(){
  currentQuiz = [];
  quizMeta.style.display = "none";
  quizArea.innerHTML = "";
  scoreArea.innerHTML = "";
  submitQuizBtn.style.display = "none";
  resetQuizBtn.style.display = "none";
}

function showSummary(run){
  currentRunId = run.id;

  summaryText.innerText = run.summary || "";
  summaryBlock.style.display = "block";

  usedPill.style.display = "inline-flex";
  usedPill.innerText = `Used: ${run.used || "unknown"}`;

  sourcePill.style.display = "inline-flex";
  sourcePill.innerText = `Source: ${run.source_type || "pdf"}`;

  genQuizBtn.disabled = false;
  resetQuizUI();
  summaryBlock.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderQuiz(quiz){
  quizArea.innerHTML = "";
  if (!quiz || quiz.length === 0){
    quizArea.innerHTML = `<div class="text-muted">No quiz generated.</div>`;
    return;
  }

  quizArea.innerHTML = quiz.map((q, idx) => {
    const opts = Array.isArray(q.options) ? q.options : [];
    return `
      <div class="mb-3 p-3 border rounded-4 bg-white">
        <div class="fw-semibold mb-2">${idx + 1}. ${esc(q.question || "")}</div>
        ${opts.map((opt, i) => `
          <div class="form-check">
            <input class="form-check-input" type="radio" name="q${idx}" id="q${idx}_o${i}" value="${i}">
            <label class="form-check-label" for="q${idx}_o${i}">${esc(opt)}</label>
          </div>
        `).join("")}
        <div id="feedback_${idx}" class="mt-2"></div>
      </div>
    `;
  }).join("");
}

function gradeQuiz(){
  if (!currentQuiz || currentQuiz.length === 0){
    status("No quiz to submit.", "warning");
    return;
  }

  let score = 0;
  let answered = 0;

  currentQuiz.forEach((q, idx) => {
    const answerIndex = q.answer_index;
    const selected = document.querySelector(`input[name="q${idx}"]:checked`);
    const feedback = document.getElementById(`feedback_${idx}`);

    if (!selected){
      feedback.innerHTML = `<div class="text-warning fw-semibold">Not answered.</div>`;
      return;
    }

    answered += 1;
    const chosen = parseInt(selected.value, 10);

    if (chosen === answerIndex){
      score += 1;
      feedback.innerHTML = `<div class="text-success fw-semibold">Correct ✅</div>`;
    } else {
      const correctText = (q.options && q.options[answerIndex]) ? q.options[answerIndex] : "N/A";
      const chosenText = (q.options && q.options[chosen]) ? q.options[chosen] : "N/A";
      feedback.innerHTML = `
        <div class="text-danger fw-semibold">Incorrect ❌</div>
        <div class="small text-muted">Your answer: <b>${esc(chosenText)}</b></div>
        <div class="small text-muted">Correct answer: <b>${esc(correctText)}</b></div>
      `;
    }
  });

  scoreArea.innerHTML = `
    <div class="alert alert-primary">
      <div class="fw-bold">Score: ${score} / ${currentQuiz.length}</div>
      <div class="small">Answered: ${answered} / ${currentQuiz.length}</div>
    </div>
  `;

  status("Submitted ✅ Scroll down to see the results for each question.", "success");
  scoreArea.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function generateQuiz(){
  if (!currentRunId){
    status("Generate a summary first.", "warning");
    return;
  }

  const difficulty = difficultyEl.value;
  const num_questions = parseInt(numQuestionsEl.value, 10);

  setLoading(genQuizBtn, true, "Generating Quiz…");
  submitQuizBtn.style.display = "none";
  resetQuizBtn.style.display = "none";
  scoreArea.innerHTML = "";
  quizArea.innerHTML = "";
  quizMeta.style.display = "none";

  status("Generating quiz… please wait.", "info");

  try {
    const res = await fetch("/api/generate-quiz", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ run_id: currentRunId, difficulty, num_questions })
    });

    const data = await res.json().catch(()=> ({}));

    if (!res.ok){
      status(esc(data.error || `Error ${res.status}`), "danger");
      return;
    }

    currentQuiz = Array.isArray(data.quiz) ? data.quiz : [];
    quizMeta.style.display = "block";
    quizMeta.innerHTML = `Selected: <b>${esc(difficulty)}</b> • <b>${num_questions}</b> questions${data.used ? ` • Used: <b>${esc(data.used)}</b>` : ""}`;

    renderQuiz(currentQuiz);

    submitQuizBtn.style.display = "inline-block";
    resetQuizBtn.style.display = "inline-block";

    status("Quiz ready ✅ Answer the questions and submit.", "success");
    quizArea.scrollIntoView({ behavior: "smooth", block: "start" });
  } finally {
    setLoading(genQuizBtn, false);
  }
}

function resetAll(){
  resetQuizUI();
  scoreArea.innerHTML = "";
  status("");
}

genQuizBtn.addEventListener("click", generateQuiz);
submitQuizBtn.addEventListener("click", gradeQuiz);
resetQuizBtn.addEventListener("click", resetAll);

pdfForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  if (!pdfFile.files || pdfFile.files.length === 0){
    status("Please choose a PDF first.", "warning");
    return;
  }

  resetAll();
  setLoading(pdfBtn, true, "Generating Summary…");
  genQuizBtn.disabled = true;

  status("Generating summary from PDF… please wait.", "info");

  const formData = new FormData();
  formData.append("file", pdfFile.files[0]);

  try {
    const res = await fetch("/api/process-pdf", { method:"POST", body: formData });
    const data = await res.json().catch(()=> ({}));

    if (!res.ok){
      status(esc(data.error || `Error ${res.status}`), "danger");
      return;
    }

    showSummary(data);
    status("Summary ready ✅ Now choose quiz options below.", "success");
  } catch (err){
    status(`Client error: ${esc(String(err))}`, "danger");
  } finally {
    setLoading(pdfBtn, false);
  }
});
