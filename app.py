from __future__ import annotations

import json
import os
import hashlib
import secrets
import sqlite3
import textwrap
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib import request

from flask import Flask, g, jsonify, render_template, request as flask_request

from ml_engine import run_ml_pipeline


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "career_ecosystem.db"
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "24"))

app = Flask(__name__)


@app.errorhandler(PermissionError)
def auth_error(_: PermissionError):
    return jsonify({"error": "Please log in first."}), 401


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def expires_iso() -> str:
    return (datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)).isoformat(timespec="seconds") + "Z"


def db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_: Exception | None = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            name TEXT,
            target_role TEXT,
            experience_level TEXT,
            skills TEXT,
            interests TEXT,
            goals TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_runs (
            id TEXT PRIMARY KEY,
            profile_id TEXT,
            agent TEXT,
            input_json TEXT,
            output_json TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS resumes (
            id TEXT PRIMARY KEY,
            profile_id TEXT,
            resume_text TEXT,
            review_json TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS interviews (
            id TEXT PRIMARY KEY,
            profile_id TEXT,
            question TEXT,
            answer TEXT,
            feedback_json TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            profile_id TEXT,
            role TEXT,
            message TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at TEXT,
            revoked_at TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS ml_predictions (
            id TEXT PRIMARY KEY,
            profile_id TEXT,
            user_id TEXT,
            input_json TEXT,
            output_json TEXT,
            created_at TEXT
        );
        """
    )
    columns = [row[1] for row in conn.execute("PRAGMA table_info(profiles)").fetchall()]
    if "user_id" not in columns:
        conn.execute("ALTER TABLE profiles ADD COLUMN user_id TEXT")
    session_columns = [row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()]
    if "expires_at" not in session_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN expires_at TEXT")
    if "revoked_at" not in session_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN revoked_at TEXT")
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_profiles_user_created ON profiles(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_agent_runs_profile_created ON agent_runs(profile_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_resumes_profile_created ON resumes(profile_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_interviews_profile_created ON interviews(profile_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_chats_profile_created ON chats(profile_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_token_expiry ON sessions(token, expires_at, revoked_at);
        """
    )
    conn.commit()
    conn.close()


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]


def keyword_score(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for word in keywords if word.lower() in lowered)


ROLE_BLUEPRINTS = {
    "ai engineer": {
        "must": ["python", "machine learning", "llm", "api", "vector database", "deployment"],
        "projects": ["Multi-agent career platform", "RAG knowledge assistant", "LLM evaluation dashboard"],
        "courses": ["DeepLearning.AI Generative AI", "FastAPI or Flask production APIs", "LangChain/LlamaIndex agents"],
    },
    "data scientist": {
        "must": ["python", "sql", "statistics", "machine learning", "visualization", "experimentation"],
        "projects": ["Churn prediction system", "Experiment analytics suite", "Forecasting dashboard"],
        "courses": ["Statistical Learning", "Kaggle feature engineering", "dbt analytics engineering"],
    },
    "full stack developer": {
        "must": ["react", "api", "database", "auth", "testing", "deployment"],
        "projects": ["SaaS dashboard", "Realtime collaboration app", "AI-enabled workflow manager"],
        "courses": ["React patterns", "Flask/Django APIs", "System design fundamentals"],
    },
    "cloud engineer": {
        "must": ["linux", "docker", "kubernetes", "aws", "ci/cd", "observability"],
        "projects": ["Auto-scaling deployment lab", "Infra cost monitor", "Secure CI/CD platform"],
        "courses": ["AWS Solutions Architect", "Kubernetes the Hard Way", "Terraform associate prep"],
    },
}


def role_blueprint(role: str) -> dict[str, list[str]]:
    normalized = role.lower()
    for key, value in ROLE_BLUEPRINTS.items():
        if key in normalized:
            return value
    return {
        "must": ["python", "communication", "problem solving", "projects", "testing", "deployment"],
        "projects": ["AI portfolio platform", "Analytics dashboard", "Automation assistant"],
        "courses": ["CS50x", "System design primer", "Career-ready project building"],
    }


def profile_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": data.get("name", "").strip() or "Future Builder",
        "target_role": data.get("target_role", "").strip() or "AI Engineer",
        "experience_level": data.get("experience_level", "Beginner").strip(),
        "skills": data.get("skills", "").strip(),
        "interests": data.get("interests", "").strip(),
        "goals": data.get("goals", "").strip(),
    }


def save_agent_run(profile_id: str, agent: str, input_data: dict[str, Any], output: dict[str, Any]) -> None:
    db().execute(
        "INSERT INTO agent_runs VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), profile_id, agent, json.dumps(input_data), json.dumps(output), now_iso()),
    )
    db().commit()


def password_hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()


def current_user() -> dict[str, Any] | None:
    header = flask_request.headers.get("Authorization", "")
    token = header.removeprefix("Bearer ").strip()
    if not token:
        return None
    row = db().execute(
        """
        SELECT users.id, users.email
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ?
          AND sessions.revoked_at IS NULL
          AND (sessions.expires_at IS NULL OR sessions.expires_at > ?)
        """,
        (token, now_iso()),
    ).fetchone()
    return dict(row) if row else None


def current_token() -> str:
    return flask_request.headers.get("Authorization", "").removeprefix("Bearer ").strip()


def require_user() -> dict[str, Any]:
    user = current_user()
    if not user:
        raise PermissionError("Authentication required")
    return user


def analyze_profile(profile: dict[str, Any]) -> dict[str, Any]:
    skills = split_csv(profile["skills"])
    interests = split_csv(profile["interests"])
    blueprint = role_blueprint(profile["target_role"])
    missing = [skill for skill in blueprint["must"] if skill.lower() not in {s.lower() for s in skills}]
    strength = min(98, 38 + len(skills) * 7 + len(interests) * 4 + (12 if profile["goals"] else 0))
    return {
        "fit_score": strength,
        "headline": f"{profile['name']} is tracking toward {profile['target_role']} with a {strength}% readiness signal.",
        "strengths": skills[:6] or ["Curiosity", "Learning momentum", "Career focus"],
        "growth_gaps": missing[:6],
        "positioning": [
            "Lead with one complete deployed project.",
            "Show measurable impact in every resume bullet.",
            "Practice explaining architecture decisions clearly.",
        ],
    }


def run_advanced_ml(profile: dict[str, Any], resume_text: str = "") -> dict[str, Any]:
    prediction = run_ml_pipeline(profile, resume_text)
    profile_id = profile.get("id", "anonymous")
    user = current_user()
    db().execute(
        "INSERT INTO ml_predictions VALUES (?, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            profile_id,
            user["id"] if user else None,
            json.dumps({"profile": profile, "resume_text": resume_text[:2000]}),
            json.dumps(prediction),
            now_iso(),
        ),
    )
    db().commit()
    return prediction


def generate_roadmap(profile: dict[str, Any]) -> dict[str, Any]:
    blueprint = role_blueprint(profile["target_role"])
    gaps = analyze_profile(profile)["growth_gaps"]
    phases = [
        {"month": "Month 1", "focus": "Core foundations", "tasks": [f"Sharpen {item}" for item in (gaps[:2] or blueprint["must"][:2])]},
        {"month": "Month 2", "focus": "Build proof", "tasks": ["Ship a polished project", "Write architecture notes", "Add tests and persistence"]},
        {"month": "Month 3", "focus": "Interview readiness", "tasks": ["Mock interviews twice weekly", "Refine resume bullets", "Publish a case study"]},
        {"month": "Month 4", "focus": "Hiring sprint", "tasks": ["Apply to targeted roles", "Message hiring managers", "Track outcomes and iterate"]},
    ]
    return {"role": profile["target_role"], "phases": phases, "weekly_rhythm": ["3 coding sessions", "2 learning blocks", "1 portfolio polish", "1 mock interview"]}


def recommend_projects(profile: dict[str, Any]) -> dict[str, Any]:
    blueprint = role_blueprint(profile["target_role"])
    projects = []
    for index, title in enumerate(blueprint["projects"], start=1):
        projects.append(
            {
                "title": title,
                "level": ["Flagship", "Advanced", "Recruiter-friendly"][index - 1],
                "impact": "Demonstrates product thinking, engineering depth, and clear business value.",
                "stack": ["React", "Flask", "SQLite", "AI API", "Charts", "Voice UX"],
                "resume_bullet": f"Built {title.lower()} with persistent data, polished UX, and measurable workflows for {profile['target_role']} readiness.",
            }
        )
    return {"projects": projects}


def recommend_courses(profile: dict[str, Any]) -> dict[str, Any]:
    blueprint = role_blueprint(profile["target_role"])
    links = {
        "DeepLearning.AI Generative AI": "https://www.deeplearning.ai/courses/generative-ai-for-everyone/",
        "FastAPI or Flask production APIs": "https://flask.palletsprojects.com/",
        "LangChain/LlamaIndex agents": "https://python.langchain.com/docs/",
        "Statistical Learning": "https://www.statlearning.com/",
        "Kaggle feature engineering": "https://www.kaggle.com/learn/feature-engineering",
        "dbt analytics engineering": "https://www.getdbt.com/resources",
        "React patterns": "https://react.dev/learn",
        "System design fundamentals": "https://github.com/donnemartin/system-design-primer",
        "AWS Solutions Architect": "https://aws.amazon.com/certification/certified-solutions-architect-associate/",
        "Kubernetes the Hard Way": "https://github.com/kelseyhightower/kubernetes-the-hard-way",
        "Terraform associate prep": "https://developer.hashicorp.com/terraform/tutorials/certification-003",
    }
    return {
        "resources": [
            {"name": course, "type": "Course", "url": links.get(course, "https://www.coursera.org/"), "why": "Closes a direct skill gap for the target role."}
            for course in blueprint["courses"]
        ]
        + [
            {"name": "Buildspace-style public build log", "type": "Practice", "url": "https://buildspace.so/", "why": "Turns learning into proof recruiters can inspect."},
            {"name": "Pramp / interviewing.io mock sessions", "type": "Interview", "url": "https://www.pramp.com/", "why": "Builds calm explanation under pressure."},
        ]
    }


def review_resume(profile: dict[str, Any], resume_text: str) -> dict[str, Any]:
    score = 45
    score += min(20, resume_text.count("%") * 5 + keyword_score(resume_text, ["increased", "reduced", "built", "deployed"]) * 3)
    score += min(20, keyword_score(resume_text, split_csv(profile["skills"])) * 2)
    score += 10 if len(resume_text) > 700 else 0
    score = min(score, 97)
    return {
        "score": score,
        "summary": "Strongest when bullets show ownership, metrics, architecture, and user impact.",
        "fixes": [
            "Start bullets with action verbs and end with measurable results.",
            "Add project links, deployed URLs, GitHub links, and architecture keywords.",
            "Mirror the target role keywords without stuffing.",
        ],
        "rewritten_bullets": [
            "Built a multi-agent career platform with Flask, SQLite, and voice-enabled chat, improving job-prep workflow completion by 40% in testing.",
            "Designed persistent AI agent outputs for resume review, roadmap planning, project recommendations, and interview feedback.",
        ],
    }


INTERVIEW_QUESTIONS = [
    "Walk me through a project you are proud of. What tradeoffs did you make?",
    "How would you design a scalable AI career assistant for thousands of users?",
    "Tell me about a time you debugged a difficult problem.",
    "How do you evaluate whether an AI feature is actually useful?",
    "Explain one technical decision in this project that a senior engineer might challenge.",
    "How would you reduce hallucinations in an AI career coach?",
    "What metrics would you track to prove this product helps job seekers?",
    "Tell me about a time you learned a difficult skill quickly.",
    "How would you secure user resume and career data in this system?",
    "What would you improve if you had one more week on this project?",
]


def next_interview_question(profile: dict[str, Any], answer: str, turn: int) -> str:
    lower = answer.lower()
    role = profile.get("target_role", "your target role")
    if not any(word in lower for word in ["because", "so", "therefore", "decided", "chose"]):
        return "What was the reasoning behind your decision, and why was that better than the obvious alternative?"
    if not any(word in lower for word in ["metric", "%", "users", "latency", "accuracy", "time", "cost", "reduced", "improved"]):
        return "How would you measure whether that work succeeded? Give me one concrete metric."
    if not any(word in lower for word in ["tradeoff", "alternative", "instead", "risk", "constraint"]):
        return "What tradeoff or risk did you accept, and how did you manage it?"
    if not any(word in lower for word in ["team", "user", "customer", "stakeholder", "recruiter"]):
        return "Who benefited from this work, and how did their workflow improve?"
    if "scale" not in lower and "deploy" not in lower and "production" not in lower:
        return f"If this were used by 10,000 users, what would you change to make it production-ready for {role} expectations?"
    return INTERVIEW_QUESTIONS[turn % len(INTERVIEW_QUESTIONS)]


def interview_feedback(profile: dict[str, Any], answer: str, question: str, turn: int) -> dict[str, Any]:
    words = len(answer.split())
    lower = answer.lower()
    signals = {
        "context": any(word in lower for word in ["when", "during", "project", "problem", "needed", "goal"]),
        "action": any(word in lower for word in ["built", "created", "implemented", "designed", "trained", "deployed", "tested"]),
        "reasoning": any(word in lower for word in ["because", "chose", "decided", "tradeoff", "alternative", "constraint"]),
        "impact": any(word in lower for word in ["improved", "reduced", "increased", "users", "%", "accuracy", "time", "cost", "score"]),
        "technical_depth": any(word in lower for word in ["api", "database", "model", "tensorflow", "flask", "react", "sqlite", "vector", "auth", "security"]),
    }
    score = min(96, 42 + min(words, 55) + sum(signals.values()) * 7)
    missing = [name.replace("_", " ") for name, present in signals.items() if not present]
    if words < 10:
        feedback = "Your answer is understandable, but it sounds like a note instead of an interview answer."
    elif missing:
        feedback = f"Good direction. To make it stronger, add {', '.join(missing[:2])}."
    elif score > 84:
        feedback = "Strong answer. You gave context, technical substance, and impact. Now make it sharper and more executive."
    else:
        feedback = "Solid answer. The next improvement is to connect your technical choices directly to business or user value."
    coaching_tip = {
        0: "Use STAR: situation, task, action, result.",
        1: "Name the constraint first, then explain your decision.",
        2: "Add one number, even if it is an estimate from testing.",
        3: "Mention what you would improve in version two.",
        4: "Close with what you learned.",
    }[turn % 5]
    next_question = next_interview_question(profile, answer, turn)
    return {
        "score": score,
        "feedback": feedback,
        "coach_message": f"{feedback}\n\nTip: {coaching_tip}\n\nFollow-up: {next_question}",
        "next_question": next_question,
        "previous_question": question,
    }


def orchestrator_reply(profile: dict[str, Any], message: str) -> dict[str, Any]:
    lower = message.lower()
    role = profile.get("target_role", "your target role")
    skills = profile.get("skills", "your current skills")
    if "roadmap" in lower:
        agent = "Roadmap Agent"
        content = (
            f"Here is a practical roadmap for {role}:\n\n"
            "1. This week: strengthen the weakest skill gap and write notes from what you learn.\n"
            "2. Next 2 weeks: build one feature that proves the skill in a real project.\n"
            "3. Next 30 days: polish the project with auth, database, tests, and deployment.\n"
            "4. Interview prep: prepare 5 STAR stories from the project.\n\n"
            "Tell me your deadline and I will convert this into a daily plan."
        )
    elif "resume" in lower:
        agent = "Resume Reviewer Agent"
        content = (
            "Paste your resume or upload it in the Resume Review section. I will check role match, missing keywords, weak bullets, "
            "project impact, and rewrite bullets using action + metric + technical depth."
        )
    elif "interview" in lower:
        agent = "Interview Coach Agent"
        content = (
            f"Let's practice for {role}. I will ask one question at a time, then push you like a real interviewer.\n\n"
            f"First question: {INTERVIEW_QUESTIONS[0]}"
        )
    elif "project" in lower:
        agent = "Project Recommender Agent"
        content = (
            f"Based on your skills ({skills}), your strongest project angle is a deployed AI workflow product. "
            "Make sure it has login, saved history, database persistence, model inference, admin analytics, and a clear README. "
            "That gives recruiters proof of product thinking plus engineering depth."
        )
    elif "skill" in lower or "gap" in lower:
        agent = "Skill Analyzer Agent"
        gaps = analyze_profile(profile).get("growth_gaps", [])
        content = f"Your likely gaps for {role}: {', '.join(gaps) if gaps else 'mostly project polish and interview storytelling'}. Pick one gap and I will give you a 7-day sprint."
    elif "course" in lower or "learn" in lower:
        agent = "Course Recommender Agent"
        resources = recommend_courses(profile)["resources"][:3]
        content = "Start with these:\n\n" + "\n".join([f"- {item['name']}: {item['url']}" for item in resources])
    else:
        agent = "AI Orchestrator"
        content = (
            f"I can help you like a career-focused ChatGPT for {role}. Ask me for a roadmap, resume rewrite, project idea, "
            "skill gap plan, interview practice, or course list.\n\n"
            "Best next move: describe your current goal in one sentence, and I will turn it into a concrete action plan."
        )
    return {"agent": agent, "message": content}


def call_external_ai(prompt: str) -> str | None:
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    if openai_key:
        payload = json.dumps(
            {
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.35,
            }
        ).encode()
        req = request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
        )
    elif gemini_key:
        payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
        req = request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
    else:
        return None

    try:
        with request.urlopen(req, timeout=12) as response:
            data = json.loads(response.read().decode())
        if openai_key:
            return data["choices"][0]["message"]["content"]
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None


def latest_profile() -> dict[str, Any]:
    user = current_user()
    if user:
        row = db().execute("SELECT * FROM profiles WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user["id"],)).fetchone()
    else:
        row = db().execute("SELECT * FROM profiles ORDER BY created_at DESC LIMIT 1").fetchone()
    if not row:
        return profile_payload({})
    return dict(row)


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/auth/register", methods=["POST"])
def register():
    data = flask_request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if "@" not in email or len(password) < 6:
        return jsonify({"error": "Use a valid email and a password with at least 6 characters."}), 400
    salt = secrets.token_hex(16)
    user_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    try:
        db().execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", (user_id, email, password_hash(password, salt), salt, now_iso()))
        db().execute(
            "INSERT INTO sessions (token, user_id, expires_at, revoked_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (token, user_id, expires_iso(), None, now_iso()),
        )
        db().commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "That email is already registered. Please log in."}), 409
    return jsonify({"token": token, "user": {"id": user_id, "email": email}})


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = flask_request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    row = db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row or row["password_hash"] != password_hash(password, row["salt"]):
        return jsonify({"error": "Invalid email or password."}), 401
    token = secrets.token_urlsafe(32)
    db().execute(
        "INSERT INTO sessions (token, user_id, expires_at, revoked_at, created_at) VALUES (?, ?, ?, ?, ?)",
        (token, row["id"], expires_iso(), None, now_iso()),
    )
    db().commit()
    return jsonify({"token": token, "user": {"id": row["id"], "email": row["email"]}})


@app.route("/api/auth/me")
def me():
    user = current_user()
    if not user:
        return jsonify({"user": None})
    return jsonify({"user": user})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    token = current_token()
    if token:
        db().execute("UPDATE sessions SET revoked_at = ? WHERE token = ?", (now_iso(), token))
        db().commit()
    return jsonify({"ok": True})


@app.route("/api/profile", methods=["POST"])
def create_profile():
    user = require_user()
    payload = profile_payload(flask_request.get_json(force=True))
    profile_id = str(uuid.uuid4())
    db().execute(
        """
        INSERT INTO profiles
            (id, user_id, name, target_role, experience_level, skills, interests, goals, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (profile_id, user["id"], payload["name"], payload["target_role"], payload["experience_level"], payload["skills"], payload["interests"], payload["goals"], now_iso()),
    )
    db().commit()
    payload["id"] = profile_id
    analysis = analyze_profile(payload)
    save_agent_run(profile_id, "Profile Analyzer Agent", payload, analysis)
    return jsonify({"profile": payload, "analysis": analysis})


@app.route("/api/agents/run", methods=["POST"])
def run_agents():
    require_user()
    data = flask_request.get_json(force=True)
    profile = data.get("profile") or latest_profile()
    profile = profile_payload(profile) | {"id": profile.get("id", str(uuid.uuid4()))}
    outputs = {
        "analysis": analyze_profile(profile),
        "roadmap": generate_roadmap(profile),
        "projects": recommend_projects(profile),
        "courses": recommend_courses(profile),
        "ml": run_advanced_ml(profile, data.get("resume", "")),
    }
    for agent, output in outputs.items():
        save_agent_run(profile["id"], agent, profile, output)
    return jsonify(outputs)


@app.route("/api/resume/review", methods=["POST"])
def resume_review():
    require_user()
    data = flask_request.get_json(force=True)
    profile = data.get("profile") or latest_profile()
    profile_id = profile.get("id", "anonymous")
    resume_text = data.get("resume", "")
    review = review_resume(profile_payload(profile), resume_text)
    review["ml_classification"] = run_ml_pipeline(profile_payload(profile), resume_text)["resume_classification"]
    db().execute("INSERT INTO resumes VALUES (?, ?, ?, ?, ?)", (str(uuid.uuid4()), profile_id, resume_text, json.dumps(review), now_iso()))
    db().commit()
    return jsonify(review)


@app.route("/api/resume/upload", methods=["POST"])
def resume_upload():
    require_user()
    uploaded = flask_request.files.get("resume")
    if not uploaded:
        return jsonify({"error": "Upload a resume file first."}), 400
    raw = uploaded.read()
    text = raw.decode("utf-8", errors="ignore")
    if not text.strip():
        return jsonify({"error": "Could not extract text. Upload a .txt resume or paste text into the reviewer."}), 400
    profile = latest_profile()
    review = review_resume(profile_payload(profile), text)
    review["ml_classification"] = run_ml_pipeline(profile_payload(profile), text)["resume_classification"]
    review["filename"] = uploaded.filename
    db().execute("INSERT INTO resumes VALUES (?, ?, ?, ?, ?)", (str(uuid.uuid4()), profile.get("id", "anonymous"), text, json.dumps(review), now_iso()))
    db().commit()
    return jsonify(review)


@app.route("/api/ml/predict", methods=["POST"])
def ml_predict():
    require_user()
    data = flask_request.get_json(force=True)
    profile = data.get("profile") or latest_profile()
    profile = profile_payload(profile) | {"id": profile.get("id", str(uuid.uuid4()))}
    resume_text = data.get("resume", "")
    return jsonify(run_advanced_ml(profile, resume_text))


@app.route("/api/interview", methods=["POST"])
def interview():
    require_user()
    data = flask_request.get_json(force=True)
    profile = data.get("profile") or latest_profile()
    answer = data.get("answer", "")
    question = data.get("question", INTERVIEW_QUESTIONS[0])
    turn = int(data.get("turn", 1))
    if not answer.strip():
        return jsonify(
            {
                "score": None,
                "feedback": "Interview started.",
                "coach_message": f"I will interview you like a real hiring manager for {profile.get('target_role', 'your target role')}. {INTERVIEW_QUESTIONS[0]}",
                "next_question": INTERVIEW_QUESTIONS[0],
            }
        )
    prompt = textwrap.dedent(
        f"""
        You are a strict but supportive human interview coach for {profile.get('target_role', 'a software role')}.
        Current question: {question}
        Candidate answer: {answer}
        Give concise feedback and ask one natural follow-up question. Do not end the interview.
        """
    ).strip()
    external = call_external_ai(prompt)
    feedback = interview_feedback(profile_payload(profile), answer, question, turn)
    if external:
        feedback["coach_message"] = external
        feedback["next_question"] = external.splitlines()[-1][:260] or feedback["next_question"]
    db().execute(
        "INSERT INTO interviews VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), profile.get("id", "anonymous"), question, answer, json.dumps(feedback), now_iso()),
    )
    db().commit()
    return jsonify(feedback)


@app.route("/api/chat", methods=["POST"])
def chat():
    require_user()
    data = flask_request.get_json(force=True)
    profile = data.get("profile") or latest_profile()
    message = data.get("message", "")
    profile_id = profile.get("id", "anonymous")
    db().execute("INSERT INTO chats VALUES (?, ?, ?, ?, ?)", (str(uuid.uuid4()), profile_id, "user", message, now_iso()))
    prompt = textwrap.dedent(
        f"""
        You are an AI career ecosystem orchestrator.
        Profile: {json.dumps(profile)}
        User message: {message}
        Reply in a practical, concise coaching style.
        """
    ).strip()
    external = call_external_ai(prompt)
    reply = {"agent": "Gemini/OpenAI API", "message": external} if external else orchestrator_reply(profile_payload(profile), message)
    db().execute("INSERT INTO chats VALUES (?, ?, ?, ?, ?)", (str(uuid.uuid4()), profile_id, "assistant", reply["message"], now_iso()))
    db().commit()
    return jsonify(reply)


@app.route("/api/history")
def history():
    user = require_user()
    profiles = db().execute("SELECT * FROM profiles WHERE user_id = ? ORDER BY created_at DESC LIMIT 20", (user["id"],)).fetchall()
    profile_ids = [row["id"] for row in profiles]
    if profile_ids:
        placeholders = ",".join(["?"] * len(profile_ids))
        runs = db().execute(f"SELECT * FROM agent_runs WHERE profile_id IN ({placeholders}) ORDER BY created_at DESC LIMIT 40", profile_ids).fetchall()
        resumes = db().execute(f"SELECT * FROM resumes WHERE profile_id IN ({placeholders}) ORDER BY created_at DESC LIMIT 30", profile_ids).fetchall()
        interviews = db().execute(f"SELECT * FROM interviews WHERE profile_id IN ({placeholders}) ORDER BY created_at DESC LIMIT 30", profile_ids).fetchall()
        chats = db().execute(f"SELECT * FROM chats WHERE profile_id IN ({placeholders}) ORDER BY created_at ASC LIMIT 100", profile_ids).fetchall()
    else:
        runs, resumes, interviews, chats = [], [], [], []
    return jsonify(
        {
            "profiles": [dict(row) for row in profiles],
            "runs": [dict(row) for row in runs],
            "resumes": [dict(row) for row in resumes],
            "interviews": [dict(row) for row in interviews],
            "chats": [dict(row) for row in chats],
        }
    )


@app.route("/api/admin/stats")
def admin_stats():
    require_user()
    tables = ["users", "profiles", "agent_runs", "resumes", "interviews", "chats", "ml_predictions"]
    counts = {table: db().execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"] for table in tables}
    latest_runs = db().execute("SELECT agent, created_at FROM agent_runs ORDER BY created_at DESC LIMIT 8").fetchall()
    latest_ml = db().execute("SELECT created_at, output_json FROM ml_predictions ORDER BY created_at DESC LIMIT 1").fetchone()
    return jsonify(
        {
            "counts": counts,
            "latest_runs": [dict(row) for row in latest_runs],
            "latest_ml": json.loads(latest_ml["output_json"]) if latest_ml else None,
            "session_ttl_hours": SESSION_TTL_HOURS,
            "database": "PostgreSQL-ready config via DATABASE_URL; SQLite active locally",
        }
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)

