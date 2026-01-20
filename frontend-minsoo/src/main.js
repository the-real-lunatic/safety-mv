import "./style.css";
import { renderSuno, shouldContinueSunoPolling } from "./suno.js";

const apiBase = "http://localhost:8000";

document.querySelector("#app").innerHTML = `
  <main class="layout">
    <header class="hero">
      <div class="brand">
        <span class="chip">SafetyMV</span>
        <p class="tag">Safety rules → agentic blueprint</p>
      </div>
      <h1>안전 문서 입력 → Agentic Flow (HITL 전까지)</h1>
      <p class="lead">
        실제 LLM 호출로 컨셉 생성부터 QA, Blueprint, Style 고정까지 진행합니다.
        HITL 이전까지의 중간 산출물과 P·E·V 루프를 확인하세요.
      </p>
    </header>

    <section class="grid">
      <div class="column">
        <section class="panel input-panel">
          <div class="panel-header">
            <h2>안전 텍스트</h2>
            <span class="pill">LLM Flow</span>
          </div>
          <label class="file-field">
            <input id="pdf-input" type="file" accept="application/pdf" />
            <span>PDF 업로드 (선택)</span>
            <small id="pdf-status">PDF 미첨부</small>
          </label>
          <textarea id="doc-input" rows="10" placeholder="안전 텍스트를 입력하세요."></textarea>
          <div class="controls">
            <label class="field">
              <span>Length</span>
              <select id="length">
                <option value="30s">30s</option>
                <option value="60s" selected>60s</option>
                <option value="90s">90s</option>
              </select>
            </label>
            <div class="field">
              <span>영상 바이브 (택2)</span>
              <div class="checkboxes">
                <label><input type="checkbox" name="style" value="minimal" />minimal</label>
                <label><input type="checkbox" name="style" value="corporated" />corporated</label>
                <label><input type="checkbox" name="style" value="modern" />modern</label>
                <label><input type="checkbox" name="style" value="cute" />cute</label>
              </div>
            </div>
            <label class="field">
              <span>음악 장르</span>
              <select id="genre">
                <option value="hiphop" selected>hiphop</option>
                <option value="jazz">jazz</option>
                <option value="trot">trot</option>
                <option value="rnb">rnb</option>
                <option value="ballad">ballad</option>
                <option value="rock">rock</option>
                <option value="dance">dance</option>
                <option value="kpop">kpop</option>
              </select>
            </label>
            <label class="field">
              <span>추가 요구사항</span>
              <input id="additional" type="text" placeholder="예: 한국어 훅 강조" />
            </label>
          </div>
          <button id="run-flow" type="button">Run Agentic Flow</button>
          <p class="hint">/jobs 또는 /jobs/upload 엔드포인트로 job 등록 후 polling 합니다.</p>
        </section>

        <section class="panel flow-panel">
          <div class="panel-header">
            <h2>Flow Status</h2>
            <span id="flow-status" class="status">대기 중</span>
          </div>
          <div class="timeline">
            <h3>State History</h3>
            <ul id="state-history"></ul>
          </div>
          <div class="timeline">
            <h3>Trace</h3>
            <ul id="trace-log"></ul>
          </div>
          <div class="pev">
            <h3>P · E · V Loop</h3>
            <div id="pev-rounds" class="pev-rounds"></div>
          </div>
        </section>
      </div>

      <div class="column">
        <section class="panel preview-panel">
          <div class="panel-header">
            <h2>Concepts & QA</h2>
            <span id="flow-id" class="muted">job_id: -</span>
          </div>
          <div class="preview-grid">
            <div class="mini-card">
              <h4>Concepts</h4>
              <div id="concepts" class="stack"></div>
            </div>
            <div class="mini-card">
              <h4>Keywords</h4>
              <ul id="keywords"></ul>
            </div>
            <div class="mini-card">
              <h4>Key Points</h4>
              <ul id="key-points"></ul>
            </div>
            <div class="mini-card">
              <h4>Keyword Evidence</h4>
              <ul id="keyword-evidence"></ul>
            </div>
            <div class="mini-card">
              <h4>QA Results</h4>
              <div id="qa-results" class="stack"></div>
            </div>
            <div class="mini-card">
              <h4>Selected Concept</h4>
              <div id="selected-concept" class="stack"></div>
            </div>
            <div class="mini-card">
              <h4>Suno Audio</h4>
              <div id="suno-status" class="stack"></div>
              <div id="suno-tracks" class="stack"></div>
            </div>
          </div>
        </section>

        <section class="panel hitl-panel">
          <div class="panel-header">
            <h2>HITL 승인/수정</h2>
            <span id="hitl-status" class="muted">대기 중</span>
          </div>
          <div class="hitl-body">
            <div class="hitl-select">
              <h4>Concept 선택</h4>
              <div id="hitl-options" class="stack"></div>
            </div>
            <div class="hitl-edit">
              <button id="submit-hitl" type="button">Submit HITL</button>
              <p id="hitl-hint" class="hint">HITL 모드가 Required일 때만 제출이 가능합니다.</p>
            </div>
          </div>
        </section>

        <section class="panel options-panel">
          <div class="panel-header">
            <h2>Blueprint & Style</h2>
            <span class="pill ghost">pre-media</span>
          </div>
          <div class="options">
            <div class="option-card">
              <h3>Blueprint Scenes</h3>
              <ul id="blueprint-scenes"></ul>
            </div>
            <div class="option-card">
              <h3>Style Bind</h3>
              <ul id="style-bind"></ul>
            </div>
            <div class="option-card">
              <h3>Media Plan</h3>
              <ul id="media-plan"></ul>
              <div class="media-preview">
                <button id="fetch-character" type="button" class="secondary">Fetch Character Image</button>
                <p id="character-preview-status" class="muted">-</p>
                <img id="character-preview" class="character-preview hidden" alt="character preview" />
              </div>
            </div>
          </div>
        </section>
      </div>
    </section>
  </main>
`;

const docInput = document.querySelector("#doc-input");
const pdfInput = document.querySelector("#pdf-input");
const pdfStatus = document.querySelector("#pdf-status");
const lengthInput = document.querySelector("#length");
const genreInput = document.querySelector("#genre");
const DEFAULT_LLM_MODEL = "gpt-4o-mini";
const DEFAULT_LLM_TEMPERATURE = 0.4;
const DEFAULT_HITL_MODE = "required";
const additionalInput = document.querySelector("#additional");
const runFlowButton = document.querySelector("#run-flow");
const styleInputs = Array.from(document.querySelectorAll("input[name='style']"));

const statusEl = document.querySelector("#flow-status");
const flowIdEl = document.querySelector("#flow-id");
const stateHistoryEl = document.querySelector("#state-history");
const traceLogEl = document.querySelector("#trace-log");
const pevRoundsEl = document.querySelector("#pev-rounds");
const conceptsEl = document.querySelector("#concepts");
const keywordsEl = document.querySelector("#keywords");
const keyPointsEl = document.querySelector("#key-points");
const keywordEvidenceEl = document.querySelector("#keyword-evidence");
const qaResultsEl = document.querySelector("#qa-results");
const selectedConceptEl = document.querySelector("#selected-concept");
const sunoStatusEl = document.querySelector("#suno-status");
const sunoTracksEl = document.querySelector("#suno-tracks");
const blueprintScenesEl = document.querySelector("#blueprint-scenes");
const styleBindEl = document.querySelector("#style-bind");
const mediaPlanEl = document.querySelector("#media-plan");
const fetchCharacterBtn = document.querySelector("#fetch-character");
const characterPreviewEl = document.querySelector("#character-preview");
const characterPreviewStatusEl = document.querySelector("#character-preview-status");
const hitlStatusEl = document.querySelector("#hitl-status");
const hitlOptionsEl = document.querySelector("#hitl-options");
const hitlSubmitBtn = document.querySelector("#submit-hitl");
const hitlHintEl = document.querySelector("#hitl-hint");

let cachedConcepts = [];
let selectedPdfFile = null;
let currentJobId = null;
let pollTimer = null;
let isProcessing = false;
let characterAssetId = null;

const sampleText = `안전 텍스트 예시:
작업 전 보호구를 착용한다. 위험 구역에는 출입하지 않는다.
기계 이상 징후가 있으면 즉시 작업을 중지하고 관리자에게 보고한다.`;

docInput.value = sampleText;

const clearElement = (el) => {
  while (el.firstChild) {
    el.removeChild(el.firstChild);
  }
};

const createListItem = (text) => {
  const item = document.createElement("li");
  item.textContent = text;
  return item;
};

const renderList = (el, items = []) => {
  clearElement(el);
  items.forEach((item) => el.appendChild(createListItem(item)));
};

const renderTrace = (trace = []) => {
  clearElement(traceLogEl);
  trace.forEach((entry) => {
    const item = document.createElement("li");
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const meta = [
      entry.step,
      entry.model ? `model: ${entry.model}` : null,
      entry.concept_id ? `concept: ${entry.concept_id}` : null,
    ]
      .filter(Boolean)
      .join(" · ");
    summary.textContent = meta;

    const messagesTitle = document.createElement("p");
    messagesTitle.textContent = "Messages";
    messagesTitle.className = "trace-label";

    const messagesBlock = document.createElement("pre");
    messagesBlock.textContent = JSON.stringify(entry.messages || [], null, 2);

    const outputTitle = document.createElement("p");
    outputTitle.textContent = "Output";
    outputTitle.className = "trace-label";

    const outputBlock = document.createElement("pre");
    outputBlock.textContent = JSON.stringify(entry.output || {}, null, 2);

    details.append(summary, messagesTitle, messagesBlock, outputTitle, outputBlock);
    item.appendChild(details);
    traceLogEl.appendChild(item);
  });
};

const renderPev = ({ concepts = [], qaResults = [], blueprint = null, retryCount = 0 }) => {
  clearElement(pevRoundsEl);
  const planCard = document.createElement("div");
  planCard.className = "pev-card";
  planCard.innerHTML = `<h4>Plan</h4><p>컨셉 후보: ${concepts.map((c) => c.concept_id).join(", ") || "-"}</p>`;

  const executeCard = document.createElement("div");
  executeCard.className = "pev-card";
  const blueprintInfo = blueprint ? `Blueprint scenes: ${blueprint.scenes?.length || 0}` : "Blueprint pending";
  executeCard.innerHTML = `<h4>Execute</h4><p>${blueprintInfo}</p><p>retry_count: ${retryCount}</p>`;

  const verifyCard = document.createElement("div");
  verifyCard.className = "pev-card";
  const summary = qaResults.length
    ? qaResults.map((qa) => `${qa.result.toUpperCase()} (${qa.score})`).join(" · ")
    : "-";
  verifyCard.innerHTML = `<h4>Verify</h4><p>${summary}</p>`;

  pevRoundsEl.append(planCard, executeCard, verifyCard);
};

const renderConcepts = (concepts = []) => {
  clearElement(conceptsEl);
  concepts.forEach((concept) => {
    const card = document.createElement("div");
    card.className = "stack-card";
    const title = document.createElement("strong");
    title.textContent = concept.concept_id;
    const lyrics = document.createElement("p");
    lyrics.textContent = concept.lyrics?.slice(0, 140) || "-";
    card.append(title, lyrics);
    conceptsEl.appendChild(card);
  });
};

const renderQaResults = (qaResults = []) => {
  clearElement(qaResultsEl);
  qaResults.forEach((qa) => {
    const card = document.createElement("div");
    card.className = "stack-card";
    const title = document.createElement("strong");
    title.textContent = `${qa.result.toUpperCase()} · ${qa.score}`;
    const missing = document.createElement("p");
    missing.textContent = `missing: ${qa.missing_keywords?.join(", ") || "-"}`;
    const issues = document.createElement("p");
    issues.textContent = `issues: ${qa.structural_issues?.join(", ") || "-"}`;
    card.append(title, missing, issues);
    qaResultsEl.appendChild(card);
  });
};

const renderSelectedConcept = (concept) => {
  clearElement(selectedConceptEl);
  if (!concept) {
    selectedConceptEl.textContent = "HITL 대기 중";
    return;
  }
  const card = document.createElement("div");
  card.className = "stack-card";
  const title = document.createElement("strong");
  title.textContent = concept.concept_id;
  const lyrics = document.createElement("p");
  lyrics.textContent = concept.lyrics?.slice(0, 160) || "-";
  card.append(title, lyrics);
  selectedConceptEl.appendChild(card);
};

const renderBlueprintScenes = (blueprint) => {
  clearElement(blueprintScenesEl);
  if (!blueprint?.scenes) {
    blueprintScenesEl.appendChild(createListItem("Blueprint pending (HITL or error)"));
    return;
  }
  blueprint.scenes.forEach((scene) => {
    const time = `${scene.time_range?.start ?? 0}-${scene.time_range?.end ?? 0}s`;
    const text = scene.visual?.action || scene.lyrics?.text || "scene";
    blueprintScenesEl.appendChild(createListItem(`${scene.scene_id} · ${time} · ${text}`));
  });
};

const renderStyle = (style) => {
  clearElement(styleBindEl);
  if (!style) {
    styleBindEl.appendChild(createListItem("Style pending (HITL or error)"));
    return;
  }
  const lines = [
    `character: ${style.character?.appearance || "-"} / ${style.character?.outfit || "-"}`,
    `background: ${style.background?.environment || "-"} / ${style.background?.lighting || "-"}`,
    `color: ${style.color?.primary || "-"} / ${style.color?.secondary || "-"}`,
  ];
  lines.forEach((line) => styleBindEl.appendChild(createListItem(line)));
};

const renderMediaPlan = (plan) => {
  clearElement(mediaPlanEl);
  if (!plan) {
    mediaPlanEl.appendChild(createListItem("media plan pending"));
    return;
  }
  if (plan.character_job) {
    const assetInfo = plan.character_job.asset_id
      ? `asset: ${plan.character_job.asset_id}`
      : "asset: -";
    const statusInfo = plan.character_job.status ? `status: ${plan.character_job.status}` : null;
    mediaPlanEl.appendChild(
      createListItem(
        `character · ${plan.character_job.provider} · ${plan.character_job.type} · ${assetInfo}${statusInfo ? ` · ${statusInfo}` : ""}`
      )
    );
  }
  (plan.video_jobs || []).slice(0, 5).forEach((job) => {
    mediaPlanEl.appendChild(
      createListItem(
        `${job.scene_id} · ${job.provider} · ${job.duration_seconds}s`
      )
    );
  });
  if (plan.music_job) {
    mediaPlanEl.appendChild(
      createListItem(`music · ${plan.music_job.provider}`)
    );
  }
};

const resetCharacterPreview = () => {
  characterPreviewEl.src = "";
  characterPreviewEl.classList.add("hidden");
  characterPreviewStatusEl.textContent = "-";
  characterAssetId = null;
  fetchCharacterBtn.disabled = true;
};

const resetOutputs = () => {
  renderList(stateHistoryEl, []);
  renderList(traceLogEl, []);
  renderConcepts([]);
  renderQaResults([]);
  renderSelectedConcept(null);
  renderList(keywordsEl, []);
  renderList(keyPointsEl, []);
  renderList(keywordEvidenceEl, []);
  renderBlueprintScenes(null);
  renderStyle(null);
  renderMediaPlan(null);
  resetCharacterPreview();
  renderPev({ concepts: [], qaResults: [], blueprint: null, retryCount: 0 });
  renderSuno(sunoStatusEl, sunoTracksEl, null);
};

const renderHitlOptions = (concepts = [], selectedId, enabled) => {
  clearElement(hitlOptionsEl);
  if (!concepts.length) {
    hitlOptionsEl.textContent = "컨셉 없음";
    return;
  }
  concepts.forEach((concept, index) => {
    const wrapper = document.createElement("label");
    wrapper.className = "hitl-option";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "hitl-concept";
    input.value = concept.concept_id;
    input.checked = concept.concept_id === selectedId || index === 0;
    input.disabled = !enabled;
    const text = document.createElement("span");
    text.textContent = concept.concept_id;
    wrapper.append(input, text);
    hitlOptionsEl.appendChild(wrapper);
  });
};

const renderFlow = (data) => {
  if (!data) return;
  statusEl.textContent = `state: ${data.job?.state || "-"} · retry: ${data.job?.retry_count ?? 0}`;
  flowIdEl.textContent = `job_id: ${data.job?.job_id || "-"}`;

  renderList(stateHistoryEl, data.state_history || []);
  renderTrace(data.trace || []);

  const artifacts = data.job?.artifacts || {};
  cachedConcepts = artifacts.concepts || [];
  renderConcepts(artifacts.concepts || []);
  renderList(keywordsEl, artifacts.extracted_keywords || []);
  renderList(keyPointsEl, artifacts.key_points || []);
  renderKeywordEvidence(artifacts.keyword_evidence || []);
  renderQaResults(artifacts.qa_results || []);
  renderSelectedConcept(artifacts.selected_concept);
  renderBlueprintScenes(artifacts.blueprint);
  renderStyle(artifacts.style);
  renderMediaPlan(artifacts.media_plan);
  const assetId =
    artifacts.character_asset?.asset_id || artifacts.media_plan?.character_asset_id || null;
  characterAssetId = assetId;
  if (assetId) {
    fetchCharacterBtn.disabled = false;
    characterPreviewStatusEl.textContent = `character asset: ${assetId}`;
  } else {
    fetchCharacterBtn.disabled = true;
    characterPreviewStatusEl.textContent = "character asset pending";
  }
  const previewUrl = artifacts.character_asset?.preview_url;
  if (previewUrl) {
    characterPreviewEl.src = previewUrl;
    characterPreviewEl.classList.remove("hidden");
    characterPreviewStatusEl.textContent = `character preview ready (${assetId})`;
  }
  renderPev({
    concepts: artifacts.concepts || [],
    qaResults: artifacts.qa_results || [],
    blueprint: artifacts.blueprint,
    retryCount: data.job?.retry_count || 0,
  });

  const hitl = data.hitl || {};
  const requiresHuman = hitl.requires_human === true;
  hitlStatusEl.textContent = requiresHuman ? "HITL Required" : "Auto-approved";
  hitlSubmitBtn.disabled = !requiresHuman;
  hitlHintEl.textContent = requiresHuman
    ? "선택한 컨셉을 수정한 뒤 Submit 할 수 있습니다."
    : "HITL 모드가 Skip이면 자동으로 진행됩니다.";
  renderHitlOptions(artifacts.concepts || [], hitl.selected_concept_id, requiresHuman);
};

characterPreviewEl.addEventListener("load", () => {
  characterPreviewEl.classList.remove("hidden");
  characterPreviewStatusEl.textContent = "이미지 로드 완료";
});

characterPreviewEl.addEventListener("error", () => {
  characterPreviewEl.classList.add("hidden");
  characterPreviewStatusEl.textContent = "이미지 로드 실패 또는 아직 준비 중";
});

const fetchCharacterImage = async () => {
  if (!currentJobId) {
    characterPreviewStatusEl.textContent = "job_id 없음";
    return;
  }
  if (!characterAssetId) {
    characterPreviewStatusEl.textContent = "character asset 없음";
    return;
  }
  characterPreviewStatusEl.textContent = "이미지 확인 중...";
  try {
    const response = await fetch(`${apiBase}/jobs/${currentJobId}/character`);
    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      const detail = errorPayload.detail || response.status;
      throw new Error(`Backend error: ${detail}`);
    }
    const data = await response.json();
    if (data.preview_url) {
      characterPreviewEl.src = data.preview_url;
      characterPreviewStatusEl.textContent = `status: ${data.status || "-"}`;
      return;
    }
    characterPreviewStatusEl.textContent = `status: ${data.status || "-"} (proxying)`;
    characterPreviewEl.src = `${apiBase}/jobs/${currentJobId}/character/image`;
  } catch (error) {
    characterPreviewStatusEl.textContent = `이미지 확인 오류: ${error.message}`;
  }
};

const renderKeywordEvidence = (evidence = []) => {
  clearElement(keywordEvidenceEl);
  if (!evidence.length) {
    keywordEvidenceEl.appendChild(createListItem("no evidence"));
    return;
  }
  evidence.forEach((item) => {
    const li = document.createElement("li");
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = item.keyword;
    details.appendChild(summary);
    (item.sources || []).forEach((source) => {
      const line = document.createElement("div");
      const page =
        source.page_number === 0 ? "input" : `p${source.page_number ?? "-"}`;
      const range =
        source.start_offset !== undefined && source.end_offset !== undefined
          ? `${source.start_offset}-${source.end_offset}`
          : "-";
      line.textContent = `${page} [${range}] ${source.text}`;
      line.className = "evidence-line";
      details.appendChild(line);
    });
    li.appendChild(details);
    keywordEvidenceEl.appendChild(li);
  });
};

const setLoading = (loading) => {
  if (loading) {
    runFlowButton.disabled = true;
    runFlowButton.textContent = "Submitting...";
    return;
  }
  if (!isProcessing) {
    runFlowButton.disabled = false;
    runFlowButton.textContent = "Run Agentic Flow";
  }
};

const getSelectedStyles = () =>
  styleInputs.filter((input) => input.checked).map((input) => input.value);

styleInputs.forEach((input) => {
  input.addEventListener("change", () => {
    if (getSelectedStyles().length > 2) {
      input.checked = false;
      statusEl.textContent = "영상 바이브는 최대 2개까지 선택 가능합니다.";
    }
  });
});

pdfInput.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    selectedPdfFile = null;
    pdfStatus.textContent = "PDF 미첨부";
    return;
  }
  selectedPdfFile = file;
  pdfStatus.textContent = `${file.name} · 업로드 준비`;
});

const pollJob = async (jobId) => {
  const response = await fetch(`${apiBase}/jobs/${jobId}/debug`);
  if (!response.ok) {
    throw new Error(`Job error: ${response.status}`);
  }
  const job = await response.json();
  statusEl.textContent = `status: ${job.status} · progress: ${job.progress ?? 0}`;
  renderSuno(sunoStatusEl, sunoTracksEl, job.suno || null);
  if (job.result) {
    renderFlow(job.result);
  }
  const isTerminal = ["completed", "hitl_required", "failed"].includes(job.status);
  const keepPollingForSuno = shouldContinueSunoPolling(job);
  if (isTerminal && !keepPollingForSuno) {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
    isProcessing = false;
    runFlowButton.disabled = false;
    runFlowButton.textContent = "Run Agentic Flow";
  }
  if (job.status === "failed") {
    statusEl.textContent = `오류: ${job.error || "failed"}`;
  }
};

const startPolling = async (jobId) => {
  if (pollTimer) clearInterval(pollTimer);
  await pollJob(jobId);
  pollTimer = setInterval(() => {
    pollJob(jobId).catch((error) => {
      statusEl.textContent = `오류: ${error.message}`;
    });
  }, 2000);
};

const runFlow = async () => {
  setLoading(true);
  statusEl.textContent = "요청 중...";
  resetOutputs();
  try {
    let response;
    const styles = getSelectedStyles();
    if (selectedPdfFile) {
      const formData = new FormData();
      formData.append("file", selectedPdfFile);
      formData.append("guidelines", docInput.value);
      formData.append("length", lengthInput.value);
      formData.append("selectedStyles", styles.join(","));
      formData.append("selectedGenres", genreInput.value);
      formData.append("additionalRequirements", additionalInput.value);
      formData.append("llm_model", DEFAULT_LLM_MODEL);
      formData.append("llm_temperature", String(DEFAULT_LLM_TEMPERATURE));
      formData.append("hitl_mode", DEFAULT_HITL_MODE);
      response = await fetch(`${apiBase}/jobs/upload`, {
        method: "POST",
        body: formData,
      });
    } else {
      response = await fetch(`${apiBase}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          guidelines: docInput.value,
          length: lengthInput.value,
          selectedStyles: styles,
          selectedGenres: genreInput.value,
          additionalRequirements: additionalInput.value,
          llm_model: DEFAULT_LLM_MODEL,
          llm_temperature: DEFAULT_LLM_TEMPERATURE,
          hitl_mode: DEFAULT_HITL_MODE,
        }),
      });
    }
    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      const detail = errorPayload.detail || response.status;
      throw new Error(`Backend error: ${detail}`);
    }
    const data = await response.json();
    currentJobId = data.job_id;
    flowIdEl.textContent = `job_id: ${currentJobId}`;
    isProcessing = true;
    runFlowButton.disabled = true;
    runFlowButton.textContent = "Processing...";
    await startPolling(currentJobId);
  } catch (error) {
    statusEl.textContent = `오류: ${error.message}`;
    isProcessing = false;
    runFlowButton.disabled = false;
    runFlowButton.textContent = "Run Agentic Flow";
  } finally {
    setLoading(false);
  }
};

runFlowButton.addEventListener("click", runFlow);
fetchCharacterBtn.addEventListener("click", fetchCharacterImage);

hitlOptionsEl.addEventListener("change", () => {
  const selected = hitlOptionsEl.querySelector("input[name='hitl-concept']:checked");
  if (!selected) return;
  const concept = cachedConcepts.find((item) => item.concept_id === selected.value);
  if (!concept) return;
  hitlLyricsEl.value = concept.lyrics || "";
  hitlScriptEl.value = JSON.stringify(concept.mv_script || [], null, 2);
});

const submitHitl = async () => {
  const jobId = currentJobId;
  if (!jobId) {
    hitlStatusEl.textContent = "job_id 없음";
    return;
  }
  const selectedInput = hitlOptionsEl.querySelector("input[name='hitl-concept']:checked");
  if (!selectedInput) {
    hitlStatusEl.textContent = "컨셉 선택 필요";
    return;
  }
  hitlSubmitBtn.disabled = true;
  hitlStatusEl.textContent = "HITL 제출 중...";
  try {
    const response = await fetch(`${apiBase}/jobs/${jobId}/hitl`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: jobId,
        selected_concept_id: selectedInput.value,
      }),
    });
    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      const detail = errorPayload.detail || response.status;
      throw new Error(`Backend error: ${detail}`);
    }
    const data = await response.json();
    renderFlow(data);
  } catch (error) {
    hitlStatusEl.textContent = `HITL 오류: ${error.message}`;
  } finally {
    hitlSubmitBtn.disabled = false;
  }
};

hitlSubmitBtn.addEventListener("click", submitHitl);
