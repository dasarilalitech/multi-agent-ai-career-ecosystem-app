# AI Career Ecosystem Agents

A polished full-stack portfolio project: a Flask backend orchestrates six AI-style career agents, persists user data in SQLite, and serves a high-end interactive frontend with voice input for chat.

## Features

- Profile Analyzer Agent
- Roadmap Agent
- Project Recommender Agent
- Course Finder Agent
- Interview Coach Agent
- Resume Reviewer Agent
- AI Orchestrator chat with voice input
- TensorFlow/Keras-compatible ML Prediction Layer
- Career Recommendation Model
- Skill Gap Prediction
- Resume Classification
- Resume file upload for text-based resumes
- Admin analytics dashboard
- Safer sessions with expiry and backend logout
- Deployment-ready Render/Railway files
- Persistent SQLite storage for profiles, agent outputs, resumes, interviews, and chat history
- API-key ready: uses `OPENAI_API_KEY` or `GEMINI_API_KEY` when present, with strong local fallbacks when not configured

## Run

```powershell
python app.py
```

Open `http://127.0.0.1:5000`.

## Optional AI Keys

```powershell
$env:OPENAI_API_KEY="your_key"
$env:GEMINI_API_KEY="your_key"
```

The app works without keys using deterministic local agent logic.

## Advanced ML Layer

The project includes an ML pipeline for:

- Career path recommendations from skills, interests, and experience level
- Skill gap prediction for the target career
- Resume category classification

TensorFlow/Keras is listed as the primary advanced ML framework. If TensorFlow is not installed on a demo machine, the app automatically uses a deterministic baseline inference layer so the product remains runnable.

## Training and Evaluation

The repository includes a reproducible training script:

```powershell
python training\train_models.py
```

Generated artifacts:

- `data/real_resume_training_dataset.csv` - normalized real resume dataset from `Resume.csv`
- `data/source_resume_dataset.csv` - copied source resume dataset
- `models/career_recommender.joblib` - trained TF-IDF + RandomForest baseline
- `reports/evaluation_report.json` - accuracy/F1 evaluation report

Current real-dataset metrics:

- Dataset rows: 2,483
- Accuracy: 71.83%
- Weighted F1: 0.6912

TensorFlow export:

- When TensorFlow is installed, the training script also exports `models/career_recommender.keras`.
- In this local environment TensorFlow was not installed, so the app uses the trained sklearn baseline and keeps TensorFlow export ready.

## Tests

```powershell
python -m pytest tests -q
```

If `pytest` is not installed, install dependencies first:

```powershell
pip install -r requirements.txt
```
