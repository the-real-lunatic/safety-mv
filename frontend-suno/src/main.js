import "./style.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

const app = document.querySelector("#app");

app.innerHTML = `
  <header>
    <div class="badge">Suno API Test Console</div>
    <h1>Safety MV · Suno Generator</h1>
    <p>Send lyrics + style + title to /suno/generate, then poll /suno/tasks/{task_id}.</p>
  </header>
  <section class="main-grid">
    <form class="panel" id="generate-form">
      <div>
        <label for="apiBase">API Base</label>
        <input id="apiBase" type="text" value="${API_BASE}" />
      </div>
      <div>
        <label for="jobId">Job ID (optional)</label>
        <input id="jobId" type="text" placeholder="job_ab12cd" />
      </div>
      <div>
        <label for="title">Title</label>
        <input id="title" type="text" value="Safety MV - Forklift" />
      </div>
      <div>
        <label for="style">Style</label>
        <input id="style" type="text" value="hiphop, tense, safety training" />
      </div>
      <div>
        <label for="lyrics">Lyrics</label>
        <textarea id="lyrics" placeholder="Put full lyrics here..."></textarea>
      </div>
      <div class="inline">
        <div>
          <label for="model">Model (optional)</label>
          <input id="model" type="text" placeholder="V4_5ALL" />
        </div>
        <div>
          <label for="vocalGender">Vocal Gender</label>
          <select id="vocalGender">
            <option value="">default</option>
            <option value="male">male</option>
            <option value="female">female</option>
          </select>
        </div>
      </div>
      <div class="inline">
        <div>
          <label for="negativeTags">Negative Tags</label>
          <input id="negativeTags" type="text" placeholder="off key, noisy" />
        </div>
        <div>
          <label for="personaId">Persona ID</label>
          <input id="personaId" type="text" placeholder="optional" />
        </div>
      </div>
      <div class="inline">
        <div>
          <label for="styleWeight">Style Weight</label>
          <input id="styleWeight" type="number" min="0" max="1" step="0.05" placeholder="0.6" />
        </div>
        <div>
          <label for="weirdness">Weirdness</label>
          <input id="weirdness" type="number" min="0" max="1" step="0.05" placeholder="0.2" />
        </div>
      </div>
      <div class="inline">
        <div>
          <label for="audioWeight">Audio Weight</label>
          <input id="audioWeight" type="number" min="0" max="1" step="0.05" placeholder="0.8" />
        </div>
        <div>
          <label for="instrumental">Instrumental</label>
          <select id="instrumental">
            <option value="false">false</option>
            <option value="true">true</option>
          </select>
        </div>
      </div>
      <div class="inline">
        <button type="submit">Generate</button>
        <button type="button" class="secondary" id="clearBtn">Clear</button>
      </div>
    </form>

    <div class="panel status">
      <div class="status-row">
        <strong>Status</strong>
        <span class="badge" id="statusBadge">idle</span>
      </div>
      <div>
        <label for="taskId">Task ID</label>
        <div class="task-input">
          <input id="taskId" type="text" placeholder="task_id" />
          <button type="button" class="secondary" id="pollBtn">Poll</button>
        </div>
      </div>
      <div>
        <label>Last Response</label>
        <pre id="responseBox">Waiting for action...</pre>
      </div>
    </div>
  </section>
`;

const form = document.querySelector("#generate-form");
const statusBadge = document.querySelector("#statusBadge");
const responseBox = document.querySelector("#responseBox");
const taskIdInput = document.querySelector("#taskId");
const pollBtn = document.querySelector("#pollBtn");
const clearBtn = document.querySelector("#clearBtn");

function setStatus(text) {
  statusBadge.textContent = text;
}

function setResponse(payload) {
  responseBox.textContent = JSON.stringify(payload, null, 2);
}

function readNumber(id) {
  const value = document.querySelector(id).value.trim();
  if (!value) return undefined;
  return Number(value);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("sending");

  const apiBase = document.querySelector("#apiBase").value.trim();
  const body = {
    job_id: document.querySelector("#jobId").value.trim() || undefined,
    lyrics: document.querySelector("#lyrics").value.trim(),
    style: document.querySelector("#style").value.trim(),
    title: document.querySelector("#title").value.trim(),
    model: document.querySelector("#model").value.trim() || undefined,
    vocal_gender: document.querySelector("#vocalGender").value || undefined,
    negative_tags: document.querySelector("#negativeTags").value.trim() || undefined,
    persona_id: document.querySelector("#personaId").value.trim() || undefined,
    style_weight: readNumber("#styleWeight"),
    weirdness_constraint: readNumber("#weirdness"),
    audio_weight: readNumber("#audioWeight"),
    instrumental: document.querySelector("#instrumental").value === "true",
  };

  try {
    const response = await fetch(`${apiBase}/suno/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Request failed");
    }
    setStatus("queued");
    setResponse(data);
    if (data.task_id) {
      taskIdInput.value = data.task_id;
    }
  } catch (error) {
    setStatus("error");
    setResponse({ error: error.message });
  }
});

pollBtn.addEventListener("click", async () => {
  const apiBase = document.querySelector("#apiBase").value.trim();
  const taskId = taskIdInput.value.trim();
  if (!taskId) {
    setResponse({ error: "task_id is required" });
    return;
  }
  setStatus("polling");

  try {
    const response = await fetch(`${apiBase}/suno/tasks/${taskId}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Poll failed");
    }
    setStatus(data.status || "ok");
    setResponse(data);
  } catch (error) {
    setStatus("error");
    setResponse({ error: error.message });
  }
});

clearBtn.addEventListener("click", () => {
  document.querySelector("#lyrics").value = "";
  setStatus("idle");
  responseBox.textContent = "Waiting for action...";
});
