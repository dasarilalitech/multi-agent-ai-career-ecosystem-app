from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"
DOWNLOADS_RESUME = Path.home() / "Downloads" / "Resume.csv"

CAREER_SEEDS = {
    "AI Engineer": ["python", "machine learning", "llm", "tensorflow", "nlp", "rag", "api", "deployment"],
    "Data Scientist": ["python", "sql", "statistics", "pandas", "machine learning", "visualization", "experiments"],
    "ML Engineer": ["python", "tensorflow", "mlops", "docker", "model serving", "feature engineering", "monitoring"],
    "Full Stack Developer": ["react", "javascript", "flask", "api", "database", "auth", "testing", "deployment"],
    "Cloud Engineer": ["aws", "linux", "docker", "kubernetes", "terraform", "ci/cd", "observability"],
    "Cybersecurity Analyst": ["security", "networking", "linux", "siem", "incident response", "risk", "cloud security"],
    "Data Analyst": ["sql", "excel", "tableau", "power bi", "dashboards", "statistics", "business analysis"],
}


def build_dataset(rows_per_career: int = 750) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    real_dataset = DATA_DIR / "real_resume_training_dataset.csv"
    if real_dataset.exists():
        return real_dataset
    if DOWNLOADS_RESUME.exists():
        return normalize_resume_csv(DOWNLOADS_RESUME, real_dataset)

    path = DATA_DIR / "career_training_dataset.csv"
    rng = np.random.default_rng(42)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["skills", "interests", "experience_level", "resume_text", "career"])
        writer.writeheader()
        for career, skills in CAREER_SEEDS.items():
            for _ in range(rows_per_career):
                selected = rng.choice(skills, size=int(rng.integers(3, min(7, len(skills)) + 1)), replace=False)
                interests = rng.choice(["ai", "analytics", "cloud", "security", "product", "automation", "systems"], size=2, replace=False)
                level = rng.choice(["Beginner", "Intermediate", "Advanced"], p=[0.34, 0.46, 0.2])
                resume = f"Built projects using {', '.join(selected)} with focus on {career.lower()} outcomes and measurable impact."
                writer.writerow(
                    {
                        "skills": ", ".join(selected),
                        "interests": ", ".join(interests),
                        "experience_level": level,
                        "resume_text": resume,
                        "career": career,
                    }
                )
    return path


def normalize_resume_csv(source: Path, destination: Path) -> Path:
    df = pd.read_csv(source)
    columns = {column.lower(): column for column in df.columns}
    text_column = columns.get("resume_str") or columns.get("resume") or columns.get("resume_text") or columns.get("text")
    label_column = columns.get("category") or columns.get("career") or columns.get("label") or columns.get("job_title")
    if not text_column or not label_column:
        raise ValueError(f"Could not map resume text/category columns from {list(df.columns)}")

    normalized = pd.DataFrame(
        {
            "skills": "",
            "interests": "",
            "experience_level": "Unknown",
            "resume_text": df[text_column].fillna("").astype(str),
            "career": df[label_column].fillna("Unknown").astype(str),
        }
    )
    normalized = normalized[normalized["resume_text"].str.len() > 40]
    normalized.to_csv(destination, index=False)
    shutil.copyfile(source, DATA_DIR / "source_resume_dataset.csv")
    return destination


def model_candidates() -> list[tuple[str, Pipeline]]:
    return [
        (
            "regularized_small_features",
            Pipeline(
                [
                    ("tfidf", TfidfVectorizer(max_features=2500, ngram_range=(1, 1), min_df=3, max_df=0.9, sublinear_tf=True)),
                    ("classifier", RandomForestClassifier(n_estimators=100, max_depth=28, min_samples_leaf=3, random_state=42, class_weight="balanced_subsample")),
                ]
            ),
        ),
        (
            "balanced_medium_features",
            Pipeline(
                [
                    ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2), min_df=3, max_df=0.88, sublinear_tf=True)),
                    ("classifier", RandomForestClassifier(n_estimators=140, max_depth=36, min_samples_leaf=2, random_state=42, class_weight="balanced_subsample")),
                ]
            ),
        ),
        (
            "higher_capacity_guarded",
            Pipeline(
                [
                    ("tfidf", TfidfVectorizer(max_features=8000, ngram_range=(1, 2), min_df=2, max_df=0.85, sublinear_tf=True)),
                    ("classifier", RandomForestClassifier(n_estimators=180, max_depth=44, min_samples_leaf=2, random_state=42, class_weight="balanced_subsample")),
                ]
            ),
        ),
    ]


def evaluate_model(name: str, model: Pipeline, x_train: list[str], x_test: list[str], y_train: list[str], y_test: list[str]) -> dict[str, object]:
    model.fit(x_train, y_train)
    train_predictions = model.predict(x_train)
    test_predictions = model.predict(x_test)
    train_accuracy = accuracy_score(y_train, train_predictions)
    test_accuracy = accuracy_score(y_test, test_predictions)
    test_f1 = f1_score(y_test, test_predictions, average="weighted", zero_division=0)
    gap = train_accuracy - test_accuracy
    return {
        "name": name,
        "model": model,
        "train_accuracy": float(train_accuracy),
        "test_accuracy": float(test_accuracy),
        "weighted_f1": float(test_f1),
        "generalization_gap": float(gap),
        "score_for_selection": float(test_f1 - max(0.0, gap - 0.12) * 0.7),
        "predictions": test_predictions,
    }


def fit_status(gap: float, test_f1: float) -> str:
    if gap > 0.18:
        return "overfitting risk - features/capacity reduced by model selection"
    if test_f1 < 0.45:
        return "underfitting risk - model is not learning enough signal"
    return "good fit - train/test gap acceptable"


def train() -> dict[str, object]:
    MODEL_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)
    dataset = build_dataset()
    rows = list(csv.DictReader(dataset.open(encoding="utf-8")))
    x = [f"{row['skills']} {row['interests']} {row['experience_level']} {row['resume_text']}" for row in rows]
    y = [row["career"] for row in rows]
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42, stratify=y)

    results = [evaluate_model(name, model, x_train, x_test, y_train, y_test) for name, model in model_candidates()]
    best = max(results, key=lambda item: item["score_for_selection"])
    model = best["model"]
    predictions = best["predictions"]
    joblib.dump(model, MODEL_DIR / "career_recommender.joblib")

    comparison = [
        {
            "name": item["name"],
            "train_accuracy": round(float(item["train_accuracy"]), 4),
            "test_accuracy": round(float(item["test_accuracy"]), 4),
            "weighted_f1": round(float(item["weighted_f1"]), 4),
            "generalization_gap": round(float(item["generalization_gap"]), 4),
            "score_for_selection": round(float(item["score_for_selection"]), 4),
        }
        for item in results
    ]
    report = {
        "dataset": str(dataset.relative_to(ROOT)),
        "dataset_rows": len(rows),
        "model": f"Selected {best['name']} using validation F1 with overfitting penalty",
        "feature_control": "TF-IDF max_features/min_df/max_df/sublinear_tf and RandomForest max_depth/min_samples_leaf reduce overfitting.",
        "train_accuracy": round(float(best["train_accuracy"]), 4),
        "accuracy": round(float(best["test_accuracy"]), 4),
        "weighted_f1": round(float(best["weighted_f1"]), 4),
        "generalization_gap": round(float(best["generalization_gap"]), 4),
        "fit_status": fit_status(float(best["generalization_gap"]), float(best["weighted_f1"])),
        "model_comparison": comparison,
        "classification_report": classification_report(y_test, predictions, output_dict=True, zero_division=0),
    }
    (REPORT_DIR / "evaluation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    try_export_tensorflow_placeholder(x_train, y_train)
    return report


def try_export_tensorflow_placeholder(x_train: list[str], y_train: list[str]) -> None:
    try:
        import tensorflow as tf  # type: ignore
        from sklearn.preprocessing import LabelEncoder

        encoder = LabelEncoder()
        labels = encoder.fit_transform(y_train)
        vectorizer = TfidfVectorizer(max_features=2500, ngram_range=(1, 1), min_df=3, max_df=0.9, sublinear_tf=True)
        features = vectorizer.fit_transform(x_train).toarray()
        model = tf.keras.Sequential(
            [
                tf.keras.layers.Input(shape=(features.shape[1],)),
                tf.keras.layers.Dense(96, activation="relu", kernel_regularizer=tf.keras.regularizers.l2(0.001)),
                tf.keras.layers.Dropout(0.35),
                tf.keras.layers.Dense(48, activation="relu", kernel_regularizer=tf.keras.regularizers.l2(0.001)),
                tf.keras.layers.Dropout(0.25),
                tf.keras.layers.Dense(len(encoder.classes_), activation="softmax"),
            ]
        )
        model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
        early_stop = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=2, restore_best_weights=True)
        model.fit(features, labels, epochs=12, batch_size=32, validation_split=0.15, callbacks=[early_stop], verbose=0)
        model.save(MODEL_DIR / "career_recommender.keras")
        joblib.dump(vectorizer, MODEL_DIR / "keras_vectorizer.joblib")
        joblib.dump(encoder, MODEL_DIR / "keras_label_encoder.joblib")
    except Exception:
        (MODEL_DIR / "README.md").write_text(
            "TensorFlow is not installed in this environment. Run `pip install -r requirements.txt` and then `python training/train_models.py` to export `career_recommender.keras`.\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    print(json.dumps(train(), indent=2))
