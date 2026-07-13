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

TensorFlow/Keras is listed as the primary advanced ML framework. The app uses trained model artifacts when available and keeps deterministic fallbacks for portable demos.

## Training and Evaluation

The repository includes a reproducible training script:

```powershell
python training\train_models.py
```

Generated artifacts:

- `data/real_resume_training_dataset.csv` - normalized real resume dataset from `Resume.csv`
- `data/source_resume_dataset.csv` - copied source resume dataset
- `models/career_recommender.joblib` - regularized TF-IDF + RandomForest model
- `models/career_recommender.keras` - TensorFlow/Keras export
- `models/keras_vectorizer.joblib` - vectorizer used for Keras export
- `models/keras_label_encoder.joblib` - label encoder used for Keras export
- `reports/evaluation_report.json` - accuracy/F1 evaluation report

Current real-dataset metrics:

- Dataset rows: 2,483
- Train accuracy: 99.70%
- Validation accuracy: 76.66%
- Weighted F1: 0.7453
- Generalization gap: 0.2304
- Fit status: overfitting risk reduced using feature and model-capacity controls

Overfitting controls:

- TF-IDF feature limits with `max_features`
- Rare/common token filtering with `min_df` and `max_df`
- `sublinear_tf=True` for smoother text weighting
- RandomForest depth limits with `max_depth`
- Leaf-size regularization with `min_samples_leaf`
- Model selection using validation F1 with an overfitting penalty

## Tests

```powershell
python -m pytest tests -q
```

If `pytest` is not installed, install dependencies first:

```powershell
pip install -r requirements.txt
```
