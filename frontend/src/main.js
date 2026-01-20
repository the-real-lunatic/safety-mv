import "./style.css";

const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const app = document.querySelector("#app");
app.innerHTML = `
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <span class="badge">SafetyMV</span>
        <div>
          <p class="eyebrow">Safety MV Studio</p>
          <h1>PDF 규칙을 뮤직비디오로</h1>
        </div>
      </div>
      <nav class="nav">
        <a href="#create">Job 생성</a>
        <a href="#results">결과 확인</a>
      </nav>
    </header>

    <main class="grid">
      <section id="create" class="panel">
        <div class="panel-header">
          <h2>Job 생성</h2>
          <p>PDF 업로드 + 프롬프트로 생성합니다.</p>
        </div>
        <form id="job-form" class="form">
          <label>
            <span>텍스트 프롬프트</span>
            <textarea name="prompt" rows="4" placeholder="지게차 안전 수칙을 힙합 MV로 요약해줘" required></textarea>
          </label>

          <label class="upload">
            <span>PDF 업로드</span>
            <input id="pdf-input" name="pdfs" type="file" accept="application/pdf" multiple required />
            <small>여러 파일 선택 가능</small>
          </label>
          <div class="upload-actions">
            <button type="button" id="upload-btn">PDF 업로드</button>
            <span id="upload-status" class="upload-status"></span>
          </div>
          <label>
            <span>업로드된 PDF 경로</span>
            <textarea name="pdf_paths" rows="3" placeholder="업로드 후 자동 입력" required></textarea>
          </label>

          <div class="field-row">
            <label>
              <span>전략</span>
              <select name="strategy" id="strategy-select"></select>
            </label>
            <label>
              <span>길이(초)</span>
              <input name="duration_seconds" type="number" min="30" max="90" value="60" />
            </label>
          </div>
          <div class="field-row">
            <label>
              <span>무드</span>
              <input name="mood" type="text" placeholder="tense / clear" />
            </label>
            <label>
              <span>현장 타입</span>
              <input name="site_type" type="text" placeholder="warehouse / plant" />
            </label>
          </div>
          <button type="submit">Job 생성 & 실행</button>
        </form>
        <div id="job-result" class="notice"></div>
      </section>

      <section id="results" class="panel">
        <div class="panel-header">
          <h2>결과 확인 / 다운로드</h2>
          <p>Job ID를 입력해 상태와 결과물을 확인하세요.</p>
        </div>
        <div class="form">
          <label>
            <span>Job ID</span>
            <input id="job-id-input" type="text" placeholder="uuid" />
          </label>
          <button id="job-load">상태 조회</button>
        </div>
        <div class="status-card" id="job-status"></div>
        <div class="artifact-list" id="artifact-list"></div>
      </section>
    </main>
  </div>
`;

const strategySelect = document.querySelector("#strategy-select");
const jobResult = document.querySelector("#job-result");
const jobStatus = document.querySelector("#job-status");
const artifactList = document.querySelector("#artifact-list");
const jobIdInput = document.querySelector("#job-id-input");
const uploadBtn = document.querySelector("#upload-btn");
const uploadStatus = document.querySelector("#upload-status");
const pdfInput = document.querySelector("#pdf-input");
const pdfPathsField = document.querySelector("textarea[name='pdf_paths']");

let pollTimer = null;

async function loadStrategies() {
  try {
    const res = await fetch(`${apiBase}/strategies`);
    const data = await res.json();
    const strategies = data.strategies || [];
    strategySelect.innerHTML = strategies
      .map((strategy) => `<option value="${strategy}">${strategy}</option>`)
      .join("");
  } catch (err) {
    strategySelect.innerHTML = `<option value="parallel_stylelock">parallel_stylelock</option>`;
  }
}

function setNotice(message, tone = "info") {
  jobResult.textContent = message;
  jobResult.dataset.tone = tone;
}

function renderStatus(record) {
  if (!record) return;
  const { status, strategy, error, prompt } = record;
  jobStatus.innerHTML = `
    <div>
      <span class="pill ${status}">${status}</span>
      <p class="meta">${strategy} · ${prompt || ""}</p>
      ${error ? `<p class="error">${error}</p>` : ""}
    </div>
  `;
}

function renderArtifacts(jobId, artifacts = []) {
  if (!artifacts.length) {
    artifactList.innerHTML = `<p class="empty">아직 결과물이 없습니다.</p>`;
    return;
  }
  const items = artifacts
    .map((artifact) => {
      const filename = artifact.meta?.filename;
      const label = filename || artifact.kind || "artifact";
      let href = artifact.uri;
      if (artifact.kind === "file" && filename) {
        href = `${apiBase}/jobs/${jobId}/artifacts/${filename}`;
      }
      return `
        <div class="artifact">
          <div>
            <strong>${label}</strong>
            <p>${artifact.uri}</p>
          </div>
          <a href="${href}" target="_blank" rel="noreferrer">다운로드</a>
        </div>
      `;
    })
    .join("");
  artifactList.innerHTML = items;
}

async function fetchJob(jobId) {
  const res = await fetch(`${apiBase}/jobs/${jobId}`);
  if (!res.ok) {
    throw new Error("job not found");
  }
  return res.json();
}

async function pollJob(jobId) {
  clearInterval(pollTimer);
  async function tick() {
    try {
      const record = await fetchJob(jobId);
      renderStatus(record);
      renderArtifacts(jobId, record.artifacts || []);
      if (["completed", "failed", "canceled"].includes(record.status)) {
        clearInterval(pollTimer);
      }
    } catch (err) {
      jobStatus.innerHTML = `<p class="error">상태 조회 실패</p>`;
      clearInterval(pollTimer);
    }
  }
  await tick();
  pollTimer = setInterval(tick, 3000);
}

uploadBtn.addEventListener("click", async () => {
  if (!pdfInput.files.length) {
    uploadStatus.textContent = "PDF를 선택하세요.";
    return;
  }
  uploadStatus.textContent = "업로드 중...";
  try {
    const formData = new FormData();
    Array.from(pdfInput.files).forEach((file) => formData.append("files", file));
    const res = await fetch(`${apiBase}/uploads`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      throw new Error("upload failed");
    }
    const data = await res.json();
    pdfPathsField.value = (data.pdf_paths || []).join("\n");
    uploadStatus.textContent = "업로드 완료";
  } catch (err) {
    uploadStatus.textContent = `업로드 실패: ${err.message}`;
  }
});

const form = document.querySelector("#job-form");
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const prompt = data.get("prompt")?.toString().trim();
  const pdfPathsRaw = data.get("pdf_paths")?.toString() || "";
  const pdf_paths = pdfPathsRaw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const strategy = data.get("strategy")?.toString();
  const duration_seconds = Number(data.get("duration_seconds") || 60);
  const mood = data.get("mood")?.toString().trim() || null;
  const site_type = data.get("site_type")?.toString().trim() || null;

  const payload = {
    prompt,
    pdf_paths,
    strategy,
    options: { duration_seconds, mood, site_type },
  };

  try {
    setNotice("Job 생성 중...", "info");
    const res = await fetch(`${apiBase}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || "job create failed");
    }
    const record = await res.json();
    setNotice(`생성 완료: ${record.job_id}`, "success");
    jobIdInput.value = record.job_id;
    await pollJob(record.job_id);
  } catch (err) {
    setNotice(`실패: ${err.message}`, "error");
  }
});

const loadBtn = document.querySelector("#job-load");
loadBtn.addEventListener("click", async () => {
  const jobId = jobIdInput.value.trim();
  if (!jobId) {
    jobStatus.innerHTML = `<p class="error">Job ID를 입력하세요.</p>`;
    return;
  }
  await pollJob(jobId);
});

loadStrategies();
