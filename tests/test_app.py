from __future__ import annotations

import time

from app import app, init_db


def auth_headers(client):
    email = f"test{int(time.time() * 1000)}@example.com"
    response = client.post("/api/auth/register", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json['token']}"}


def test_core_workflows():
    init_db()
    client = app.test_client()
    headers = auth_headers(client)
    profile = {
        "name": "Lalit",
        "target_role": "AI Engineer",
        "experience_level": "Intermediate",
        "skills": "Python, React, Flask, Machine Learning, TensorFlow",
        "interests": "AI agents, NLP",
        "goals": "top AI role",
    }
    profile_response = client.post("/api/profile", json=profile, headers=headers)
    assert profile_response.status_code == 200
    saved_profile = profile_response.json["profile"]

    ml_response = client.post("/api/ml/predict", json={"profile": saved_profile}, headers=headers)
    assert ml_response.status_code == 200
    assert ml_response.json["career_recommendations"]

    resume_response = client.post(
        "/api/resume/review",
        json={"profile": saved_profile, "resume": "Built Flask React TensorFlow AI platform."},
        headers=headers,
    )
    assert resume_response.status_code == 200
    assert "ml_classification" in resume_response.json

    stats_response = client.get("/api/admin/stats", headers=headers)
    assert stats_response.status_code == 200
