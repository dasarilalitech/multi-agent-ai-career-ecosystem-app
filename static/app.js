localStorage.removeItem("careerToken");
localStorage.removeItem("careerUser");
localStorage.removeItem("careerProfile");

const state = {
  token: sessionStorage.getItem("careerToken") || "",
  user: JSON.parse(sessionStorage.getItem("careerUser") || "null"),
  profile: JSON.parse(sessionStorage.getItem("careerProfile") || "null"),
  outputs: null,
  ml: null,
  admin: null,
  history: null,
  chat: [],
  authMode: "login",
  interview: [
    {
      role: "assistant",
      agent: "Interview Coach",
      message: "When you are ready, start the mock interview. I will behave like a human interviewer: follow-ups, pressure, feedback, and practical coaching.",
    },
  ],
  currentQuestion: "Walk me through a project you are proud of. What tradeoffs did you make?",
};

const $ = (selector) => document.querySelector(selector);

function icon(name) {
  const icons = {
    lock: "M7 11V8a5 5 0 0 1 10 0v3M6 11h12v10H6V11Z",
    mic: "M12 3a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3Zm6 8a6 6 0 0 1-12 0M12 17v4M8 21h8",
    send: "M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z",
    spark: "M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2Z",
    save: "M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2ZM7 21v-8h10v8M7 3v5h8",
    play: "M8 5v14l11-7-11-7Z",
    logout: "M10 17l5-5-5-5M15 12H3M21 3v18",
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${icons[name]}"></path></svg>`;
}

function render() {
  const app = $("#app");
  if (!state.token || !state.user) {
    app.innerHTML = renderAuth();
    return;
  }

  app.innerHTML = `
    <aside class="rail">
      <div class="mark">ACE</div>
      <nav>
        <a href="#dashboard">Dashboard</a>
        <a href="#profile">Profile</a>
        <a href="#agents">Agents</a>
        <a href="#ml">ML Layer</a>
        <a href="#resume">Resume</a>
        <a href="#interview">Interview</a>
        <a href="#chat">Chat</a>
        <a href="#history">History</a>
        <a href="#admin">Admin</a>
      </nav>
      <button class="rail-logout" title="Logout" onclick="logout()">${icon("logout")} Logout</button>
      <div class="status"><span></span> ${state.user.email}</div>
    </aside>
    <main>
      <section class="dashboard-shell reveal" id="dashboard">
        <div class="section-head">
          <div><p class="eyebrow">Career Intelligence Dashboard</p><h2>Command Center</h2></div>
          <button onclick="loadHistory()" class="primary">${icon("spark")} Sync History</button>
        </div>
        <div class="dashboard-grid">${renderDashboard()}</div>
      </section>

      <section class="hero" id="profile">
        <div class="hero-copy">
          <p class="eyebrow">Advanced Multi-Agent Project</p>
          <h1>AI Career Ecosystem Agents</h1>
          <p>Six specialist agents analyze your profile, build a roadmap, recommend projects and courses, coach interviews, improve resumes, and preserve every result.</p>
        </div>
        <form class="profile-panel" onsubmit="saveProfile(event)">
          <div class="panel-head">
            <strong>Career Command Profile</strong>
            <span>${state.profile ? "Saved" : "New"}</span>
          </div>
          <label>Name<input name="name" value="${state.profile?.name || ""}" placeholder="Lalit Dasari"></label>
          <label>Target role<input name="target_role" value="${state.profile?.target_role || "AI Engineer"}" placeholder="AI Engineer"></label>
          <label>Level<select name="experience_level">
            ${["Beginner", "Intermediate", "Advanced"].map(level => `<option ${state.profile?.experience_level === level ? "selected" : ""}>${level}</option>`).join("")}
          </select></label>
          <label>Skills<textarea name="skills" placeholder="Python, React, Flask, SQL, Machine Learning">${state.profile?.skills || ""}</textarea></label>
          <label>Interests<textarea name="interests" placeholder="AI agents, cloud, product engineering">${state.profile?.interests || ""}</textarea></label>
          <label>Goals<textarea name="goals" placeholder="Get selected for a top-tier software/AI role">${state.profile?.goals || ""}</textarea></label>
          <button class="primary" type="submit">${icon("save")} Save and Analyze</button>
        </form>
      </section>

      <section class="metrics">
        ${metric("Readiness", state.outputs?.analysis?.fit_score || "--", "%")}
        ${metric("Agents", "6", "")}
        ${metric("Roadmap", state.outputs ? "Ready" : "Pending", "")}
        ${metric("Storage", "SQLite", "")}
      </section>

      <section class="workspace reveal" id="agents">
        <div class="section-head">
          <div><p class="eyebrow">AI Orchestrator</p><h2>Specialist Agent Console</h2></div>
          <button onclick="runAgents()" class="primary">${icon("play")} Run Agents</button>
        </div>
        <div class="agent-grid">${renderAgents()}</div>
      </section>

      <section class="workspace ml-workspace reveal" id="ml">
        <div class="section-head">
          <div><p class="eyebrow">TensorFlow/Keras Advanced Layer</p><h2>ML Prediction Console</h2></div>
          <button onclick="runML()" class="primary">${icon("spark")} Run ML Pipeline</button>
        </div>
        <div class="ml-grid">${renderML()}</div>
      </section>

      <section class="split reveal">
        <div class="tool" id="resume">
          <div class="section-head compact"><div><p class="eyebrow">Resume Reviewer Agent</p><h2>Resume Review</h2></div></div>
          <label>Upload resume file<input id="resumeFile" type="file" accept=".txt,.md,.csv"></label>
          <button onclick="uploadResume()" class="secondary">Upload and Review</button>
          <textarea id="resumeText" class="large-input" placeholder="Paste your resume text here..."></textarea>
          <button onclick="reviewResume()" class="secondary">Review Resume</button>
          <div id="resumeResult" class="result"></div>
        </div>
        <div class="tool interview-tool" id="interview">
          <div class="section-head compact">
            <div><p class="eyebrow">Interview Coach Agent</p><h2>Human-style Mock Interview</h2></div>
            <button onclick="startInterview()" class="secondary">${icon("play")} Start</button>
          </div>
          <div class="messages interview-messages" id="interviewMessages">${state.interview.map(renderMessage).join("")}</div>
          <div class="composer interview-composer">
            <button class="icon-btn" title="Voice input" onclick="startVoice('interviewInput')">${icon("mic")}</button>
            <input id="interviewInput" placeholder="Answer like you are in the interview...">
            <button class="icon-btn send" title="Send answer" onclick="sendInterviewAnswer()">${icon("send")}</button>
          </div>
          <div id="interviewResult" class="result"></div>
        </div>
      </section>

      <section class="chat-shell reveal" id="chat">
        <div class="section-head compact"><div><p class="eyebrow">Voice-enabled AI Chat</p><h2>Career Orchestrator Chat</h2></div></div>
        <div class="messages" id="messages">${state.chat.map(renderMessage).join("")}</div>
        <div class="composer">
          <button class="icon-btn" title="Voice input" onclick="startVoice('chatInput')">${icon("mic")}</button>
          <input id="chatInput" placeholder="Ask for roadmap, resume, project, interview help...">
          <button class="icon-btn send" title="Send" onclick="sendChat()">${icon("send")}</button>
        </div>
      </section>

      <section class="workspace history-workspace reveal" id="history">
        <div class="section-head">
          <div><p class="eyebrow">Career Profile History</p><h2>Saved Work</h2></div>
          <button onclick="loadHistory()" class="primary">${icon("spark")} Refresh History</button>
        </div>
        <div class="history-grid">${renderHistory()}</div>
      </section>

      <section class="workspace admin-workspace reveal" id="admin">
        <div class="section-head">
          <div><p class="eyebrow">Admin Analytics</p><h2>System Health Dashboard</h2></div>
          <button onclick="loadAdmin()" class="primary">${icon("spark")} Refresh Stats</button>
        </div>
        <div class="admin-grid">${renderAdmin()}</div>
      </section>
    </main>
  `;
  afterRender();
}

function renderAuth() {
  const isRegister = state.authMode === "register";
  return `
    <main class="auth-page">
      <section class="auth-hero">
        <div>
          <p class="eyebrow">Locked Career Operating System</p>
          <h1>AI Career Ecosystem Agents</h1>
          <p>Your private agent workspace for profile analysis, resume review, interview practice, project planning, and stored progress.</p>
        </div>
        <form class="auth-card" onsubmit="submitAuth(event)">
          <div class="auth-lock">${icon("lock")}</div>
          <h2>${isRegister ? "Create account" : "Welcome back"}</h2>
          <p>${isRegister ? "Register with email and password to unlock the dashboard." : "Login to open your saved career command center."}</p>
          <label>Email<input name="email" type="email" autocomplete="email" placeholder="you@example.com" required></label>
          <label>Password<input name="password" type="password" autocomplete="${isRegister ? "new-password" : "current-password"}" placeholder="Minimum 6 characters" required></label>
          <button class="primary" type="submit">${icon("lock")} ${isRegister ? "Register and Unlock" : "Login and Unlock"}</button>
          <button class="link-btn" type="button" onclick="toggleAuthMode()">${isRegister ? "Already registered? Login" : "New here? Create account"}</button>
          <div id="authError" class="auth-error"></div>
        </form>
      </section>
    </main>
  `;
}

function metric(label, value, suffix) {
  return `<div class="metric"><span>${label}</span><strong>${value}${suffix}</strong></div>`;
}

function renderDashboard() {
  const history = state.history || {};
  const counts = {
    profiles: history.profiles?.length || 0,
    agentRuns: history.runs?.length || 0,
    resumes: history.resumes?.length || 0,
    chats: history.chats?.length || state.chat.length,
  };
  const latestProfile = history.profiles?.[0] || state.profile;
  return `
    <article class="dash-card primary-card">
      <span>Active Target</span>
      <h3>${latestProfile?.target_role || "Set your target role"}</h3>
      <p>${latestProfile?.goals || "Save a career profile to unlock personalized recommendations."}</p>
    </article>
    <article class="dash-card"><span>Profiles Saved</span><strong>${counts.profiles}</strong><p>Career command profile snapshots.</p></article>
    <article class="dash-card"><span>Agent Runs</span><strong>${counts.agentRuns}</strong><p>Roadmaps, projects, courses, and analysis saved.</p></article>
    <article class="dash-card"><span>Resume Reviews</span><strong>${counts.resumes}</strong><p>Saved resume feedback and ML classifications.</p></article>
    <article class="dash-card"><span>Chat Messages</span><strong>${counts.chats}</strong><p>Career Orchestrator conversations preserved.</p></article>
  `;
}

function renderAgents() {
  const cards = [
    ["Profile Analyzer", state.outputs?.analysis?.headline || "Save your profile to calculate readiness, strengths, and gaps."],
    ["Roadmap Agent", state.outputs?.roadmap?.phases?.map(p => `${p.month}: ${p.focus}`).join("<br>") || "Creates a month-by-month learning and hiring plan."],
    ["Project Recommender", state.outputs?.projects?.projects?.map(p => p.title).join("<br>") || "Suggests resume-grade projects for your target role."],
    ["Course Finder", state.outputs?.courses?.resources?.map(r => r.name).join("<br>") || "Recommends targeted learning resources."],
    ["Resume Analyzer", "Paste your resume below for scoring and bullet rewrites."],
    ["Interview Coach", "Runs an adaptive human-style interview with contextual follow-ups."],
  ];
  return cards.map(([title, body]) => `<article class="agent-card"><div>${icon("spark")}</div><h3>${title}</h3><p>${body}</p></article>`).join("");
}

function shortText(value, limit = 180) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit)}...` : text;
}

function renderHistory() {
  const history = state.history;
  if (!history) {
    return `<article class="history-card wide"><span>No history loaded</span><h3>Sync your saved career work</h3><p>Profiles, agent outputs, resume reviews, interview answers, and chat messages are stored in SQLite and can be reviewed here.</p></article>`;
  }
  const profileCards = (history.profiles || []).slice(0, 4).map(item => `
    <article class="history-card">
      <span>Career Profile</span>
      <h3>${item.target_role}</h3>
      <p>${shortText(item.skills || item.goals)}</p>
      <em>${item.created_at}</em>
    </article>
  `).join("");
  const runCards = (history.runs || []).slice(0, 6).map(item => {
    const output = JSON.parse(item.output_json || "{}");
    return `
      <article class="history-card">
        <span>${item.agent}</span>
        <h3>${output.role || output.headline || item.agent}</h3>
        <p>${shortText(JSON.stringify(output), 220)}</p>
        <em>${item.created_at}</em>
      </article>
    `;
  }).join("");
  const resumeCards = (history.resumes || []).slice(0, 4).map(item => {
    const review = JSON.parse(item.review_json || "{}");
    return `
      <article class="history-card">
        <span>Resume Review</span>
        <h3>Score ${review.score || "--"}%</h3>
        <p>${shortText(review.summary || item.resume_text)}</p>
        <em>${item.created_at}</em>
      </article>
    `;
  }).join("");
  const chatCards = (history.chats || []).slice(-8).map(item => `
    <article class="history-card">
      <span>${item.role}</span>
      <h3>Career Chat</h3>
      <p>${shortText(item.message, 220)}</p>
      <em>${item.created_at}</em>
    </article>
  `).join("");
  return profileCards + runCards + resumeCards + chatCards || `<article class="history-card wide"><span>Empty</span><h3>No saved activity yet</h3><p>Use the profile, agents, resume, and chat sections first.</p></article>`;
}

function renderML() {
  const ml = state.ml || state.outputs?.ml;
  if (!ml) {
    return `
      <article class="ml-card wide">
        <span>Model Status</span>
        <h3>Ready for advanced ML inference</h3>
        <p>Run the pipeline to predict career paths, rank missing skills, and classify resume category using a TensorFlow/Keras-compatible ML layer.</p>
      </article>
      <article class="ml-card"><span>Career Model</span><strong>Career path confidence</strong><p>Skills, interests, education signal, and experience level.</p></article>
      <article class="ml-card"><span>Skill Gap Model</span><strong>Missing skill ranking</strong><p>Target-role gaps ranked by importance.</p></article>
      <article class="ml-card"><span>Resume Classifier</span><strong>Resume category prediction</strong><p>Data Science, Web, Cloud, Cybersecurity, or AI.</p></article>
    `;
  }
  return `
    <article class="ml-card wide">
      <span>${ml.model_status.framework}</span>
      <h3>${ml.model_status.mode}</h3>
      <p>${ml.model_status.note}</p>
      <div class="ml-metrics">
        ${Object.entries(ml.metrics).map(([key, value]) => `<b>${key.replaceAll("_", " ")}: ${value}</b>`).join("")}
      </div>
    </article>
    <article class="ml-card">
      <span>Career Recommendation Model</span>
      ${ml.career_recommendations.map(item => `<div class="prediction-row"><strong>${item.career}</strong><em>${item.confidence}%</em></div>`).join("")}
    </article>
    <article class="ml-card">
      <span>Skill Gap Prediction</span>
      ${ml.skill_gaps.slice(0, 6).map(item => `<div class="prediction-row"><strong>${item.skill}</strong><em>${item.importance}%</em></div>`).join("") || "<p>No major gaps detected.</p>"}
    </article>
    <article class="ml-card">
      <span>Resume Classification</span>
      <h3>${ml.resume_classification.top_category}</h3>
      <p>Confidence: ${ml.resume_classification.confidence}%</p>
      ${ml.resume_classification.ranked.slice(0, 3).map(item => `<div class="prediction-row"><strong>${item.category}</strong><em>${item.confidence}%</em></div>`).join("")}
    </article>
  `;
}

function renderAdmin() {
  if (!state.admin) {
    return `<article class="ml-card wide"><span>Admin Dashboard</span><h3>Ready to load system analytics</h3><p>Track users, profiles, agent runs, resumes, interviews, chat messages, ML predictions, session TTL, and database mode.</p></article>`;
  }
  return `
    <article class="ml-card wide">
      <span>${state.admin.database}</span>
      <h3>Session TTL: ${state.admin.session_ttl_hours} hours</h3>
      <div class="ml-metrics">
        ${Object.entries(state.admin.counts).map(([key, value]) => `<b>${key.replaceAll("_", " ")}: ${value}</b>`).join("")}
      </div>
    </article>
    <article class="ml-card wide">
      <span>Latest Agent Runs</span>
      ${state.admin.latest_runs.map(run => `<div class="prediction-row"><strong>${run.agent}</strong><em>${run.created_at}</em></div>`).join("") || "<p>No agent runs yet.</p>"}
    </article>
  `;
}

function renderMessage(item) {
  return `<div class="msg ${item.role}"><strong>${item.agent || item.role}</strong><p>${item.message}</p></div>`;
}

function afterRender() {
  requestAnimationFrame(() => {
    document.querySelectorAll(".reveal").forEach((element, index) => {
      element.style.animationDelay = `${Math.min(index * 45, 260)}ms`;
      element.classList.add("is-visible");
    });
    bindNavigation();
    if (location.hash) {
      document.querySelector(location.hash)?.scrollIntoView({behavior: "smooth", block: "start"});
    }
  });
}

function bindNavigation() {
  const links = [...document.querySelectorAll("nav a")];
  const sections = links.map(link => document.querySelector(link.getAttribute("href"))).filter(Boolean);
  links.forEach(link => {
    link.onclick = (event) => {
      event.preventDefault();
      const target = document.querySelector(link.getAttribute("href"));
      if (!target) return;
      history.pushState(null, "", link.getAttribute("href"));
      target.scrollIntoView({behavior: "smooth", block: "start"});
      links.forEach(item => item.classList.remove("active"));
      link.classList.add("active");
    };
  });
  const observer = new IntersectionObserver((entries) => {
    const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (!visible) return;
    links.forEach(link => link.classList.toggle("active", link.getAttribute("href") === `#${visible.target.id}`));
  }, {rootMargin: "-25% 0px -55% 0px", threshold: [0.2, 0.45, 0.7]});
  sections.forEach(section => observer.observe(section));
}

function toggleAuthMode() {
  state.authMode = state.authMode === "login" ? "register" : "login";
  render();
}

async function submitAuth(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target).entries());
  try {
    const result = await api(`/api/auth/${state.authMode}`, data, false);
    state.token = result.token;
    state.user = result.user;
    sessionStorage.setItem("careerToken", state.token);
    sessionStorage.setItem("careerUser", JSON.stringify(state.user));
    await loadHistory(false);
    render();
  } catch (error) {
    $("#authError").textContent = error.message;
  }
}

function logout() {
  if (state.token) {
    fetch("/api/auth/logout", {method: "POST", headers: {Authorization: `Bearer ${state.token}`}}).catch(() => {});
  }
  state.token = "";
  state.user = null;
  state.profile = null;
  state.outputs = null;
  localStorage.removeItem("careerToken");
  localStorage.removeItem("careerUser");
  localStorage.removeItem("careerProfile");
  sessionStorage.removeItem("careerToken");
  sessionStorage.removeItem("careerUser");
  sessionStorage.removeItem("careerProfile");
  render();
}

async function apiGet(path) {
  const response = await fetch(path, {headers: {Authorization: `Bearer ${state.token}`}});
  const result = await response.json().catch(() => ({}));
  if (response.status === 401) logout();
  if (!response.ok) throw new Error(result.error || "Request failed.");
  return result;
}

async function api(path, body, needsAuth = true) {
  const headers = {"Content-Type": "application/json"};
  if (needsAuth && state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  const result = await response.json().catch(() => ({}));
  if (response.status === 401) logout();
  if (!response.ok) throw new Error(result.error || "Request failed.");
  return result;
}

async function saveProfile(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target).entries());
  const result = await api("/api/profile", data);
  state.profile = result.profile;
  state.outputs = {analysis: result.analysis};
  sessionStorage.setItem("careerProfile", JSON.stringify(state.profile));
  await loadHistory(false);
  render();
}

async function runAgents() {
  state.outputs = await api("/api/agents/run", {profile: state.profile || {}});
  state.ml = state.outputs.ml;
  await loadHistory(false);
  render();
}

async function runML() {
  state.ml = await api("/api/ml/predict", {profile: state.profile || {}, resume: $("#resumeText")?.value || ""});
  render();
}

async function reviewResume() {
  const review = await api("/api/resume/review", {profile: state.profile || {}, resume: $("#resumeText").value});
  $("#resumeResult").innerHTML = `<strong>Score: ${review.score}%</strong><p>${review.summary}</p><ul>${review.fixes.map(f => `<li>${f}</li>`).join("")}</ul><p>${review.rewritten_bullets.join("<br>")}</p><p><b>ML Category:</b> ${review.ml_classification.top_category} (${review.ml_classification.confidence}%)</p>`;
  await loadHistory(false);
}

async function uploadResume() {
  const input = $("#resumeFile");
  if (!input.files.length) return;
  const data = new FormData();
  data.append("resume", input.files[0]);
  const response = await fetch("/api/resume/upload", {
    method: "POST",
    headers: {Authorization: `Bearer ${state.token}`},
    body: data,
  });
  const review = await response.json();
  if (!response.ok) {
    $("#resumeResult").innerHTML = `<strong>${review.error || "Upload failed."}</strong>`;
    return;
  }
  $("#resumeText").value = "";
  $("#resumeResult").innerHTML = `<strong>${review.filename}: ${review.score}%</strong><p>${review.summary}</p><p><b>ML Category:</b> ${review.ml_classification.top_category} (${review.ml_classification.confidence}%)</p>`;
  await loadHistory(false);
}

async function loadAdmin() {
  state.admin = await apiGet("/api/admin/stats");
  render();
}

async function loadHistory(shouldRender = true) {
  if (!state.token) return;
  state.history = await apiGet("/api/history");
  state.chat = (state.history.chats || []).map(item => ({role: item.role, agent: item.role === "assistant" ? "Career Orchestrator" : "user", message: item.message}));
  if (shouldRender) render();
}

async function startInterview() {
  const reply = await api("/api/interview", {profile: state.profile || {}, answer: "", turn: 0});
  state.currentQuestion = reply.next_question;
  state.interview = [{role: "assistant", agent: "Interview Coach", message: reply.coach_message}];
  render();
}

async function sendInterviewAnswer() {
  const input = $("#interviewInput");
  const answer = input.value.trim();
  if (!answer) return;
  state.interview.push({role: "user", message: answer});
  input.value = "";
  const reply = await api("/api/interview", {
    profile: state.profile || {},
    question: state.currentQuestion,
    answer,
    turn: state.interview.filter(item => item.role === "user").length,
  });
  state.currentQuestion = reply.next_question;
  state.interview.push({role: "assistant", agent: "Interview Coach", message: reply.coach_message});
  await loadHistory(false);
  render();
  const box = $("#interviewMessages");
  if (box) box.scrollTop = box.scrollHeight;
}

async function sendChat() {
  const input = $("#chatInput");
  const message = input.value.trim();
  if (!message) return;
  state.chat.push({role: "user", message});
  input.value = "";
  render();
  const reply = await api("/api/chat", {profile: state.profile || {}, message});
  state.chat.push({role: "assistant", agent: reply.agent, message: reply.message});
  await loadHistory(false);
  render();
  $("#messages").scrollTop = $("#messages").scrollHeight;
}

function startVoice(targetId) {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    alert("Voice input is not supported in this browser. Try Chrome or Edge.");
    return;
  }
  const recognition = new Recognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.onresult = (event) => {
    $(`#${targetId}`).value = event.results[0][0].transcript;
  };
  recognition.start();
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && event.target.id === "chatInput") sendChat();
  if (event.key === "Enter" && event.target.id === "interviewInput") sendInterviewAnswer();
});

render();
