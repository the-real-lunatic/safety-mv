import "./style.css";

document.querySelector("#app").innerHTML = `
  <main class="hero">
    <div class="brand">
      <span class="chip">SafetyMV</span>
      <p class="tag">안전 규칙을 60초 뮤직비디오로</p>
    </div>
    <h1>기억되는 안전 교육의 시작</h1>
    <p class="lead">
      긴 안전 문서를 짧고 몰입되는 영상으로 변환하는 플랫폼 인프라를 준비 중입니다.
    </p>
    <div class="cards">
      <div class="card">
        <h2>Input</h2>
        <p>PDF/텍스트 안전 문서</p>
      </div>
      <div class="card">
        <h2>Process</h2>
        <p>행동 규칙 추출 · 씬 구성</p>
      </div>
      <div class="card">
        <h2>Output</h2>
        <p>30–90초 뮤직비디오</p>
      </div>
    </div>
    <div class="cta">
      <button type="button">Get Ready</button>
      <span class="sub">Backend health: /health</span>
    </div>
  </main>
`;
