"""Trains the no-show risk model per docs plan §10.3: a HistGradientBoostingClassifier
as the persisted production model, plus a LogisticRegression companion kept for its
interpretable coefficients (the admin dashboard's future "why is this client at
risk" tooltip, per §12).

Run directly:
    python -m app.ml.train --data-path data/synthetic_appointments.csv

Also invoked by the weekly Celery Beat retraining task (app/tasks/ml_tasks.py).
"""

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline

from app.ml.features import ALL_FEATURES, TARGET_COLUMN, build_preprocessor

MODELS_DIR = Path(__file__).parent / "models"
GBM_MODEL_PATH = MODELS_DIR / "no_show_gbm.joblib"
LOGREG_MODEL_PATH = MODELS_DIR / "no_show_logreg.joblib"

TOP_RISK_FRACTION = 0.20  # the "top 20% riskiest flagged" operating point from §10.3


def _time_based_split(df: pd.DataFrame, train_fraction: float = 0.8) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train on earlier appointments, test on later ones — simulates real
    deployment (§10.3) far better than a random shuffle would."""
    ordered = df.sort_values("scheduled_start").reset_index(drop=True)
    split_index = int(len(ordered) * train_fraction)
    return ordered.iloc[:split_index], ordered.iloc[split_index:]


def _evaluate(model: Pipeline, test_df: pd.DataFrame) -> dict:
    x_test = test_df[ALL_FEATURES]
    y_test = test_df[TARGET_COLUMN].to_numpy()
    probabilities = model.predict_proba(x_test)[:, 1]

    auc = roc_auc_score(y_test, probabilities)

    n_flagged = max(1, int(len(probabilities) * TOP_RISK_FRACTION))
    threshold = sorted(probabilities, reverse=True)[n_flagged - 1]
    predicted_high_risk = (probabilities >= threshold).astype(int)

    return {
        "auc": float(auc),
        "precision_at_top_20pct": float(precision_score(y_test, predicted_high_risk, zero_division=0)),
        "recall_at_top_20pct": float(recall_score(y_test, predicted_high_risk, zero_division=0)),
        "threshold_at_top_20pct": float(threshold),
    }


def train_and_persist_models(
    data_path: str | Path,
    *,
    min_auc: float | None = 0.75,
    gbm_path: Path = GBM_MODEL_PATH,
    logreg_path: Path = LOGREG_MODEL_PATH,
) -> dict:
    """Trains both models on `data_path`, persists them, and returns a metrics
    report. Raises ValueError if the gradient-boosting model's AUC falls below
    `min_auc` (pass None to skip the check — used by fast/small-sample tests).

    `data_path` is a CSV today, bootstrapped from scripts/generate_synthetic_data.py.
    Swapping to real accumulated booking history later means changing what this
    loads (e.g. a query over the `appointments` table) — the feature schema in
    app/ml/features.py is the shared contract, not this loader.
    """
    df = pd.read_csv(data_path, parse_dates=["scheduled_start"])
    train_df, test_df = _time_based_split(df)

    x_train = train_df[ALL_FEATURES]
    y_train = train_df[TARGET_COLUMN]

    gbm_pipeline = Pipeline(
        steps=[("preprocess", build_preprocessor()), ("classifier", HistGradientBoostingClassifier(random_state=42))]
    )
    gbm_pipeline.fit(x_train, y_train)
    gbm_metrics = _evaluate(gbm_pipeline, test_df)

    logreg_pipeline = Pipeline(
        steps=[("preprocess", build_preprocessor()), ("classifier", LogisticRegression(max_iter=1000))]
    )
    logreg_pipeline.fit(x_train, y_train)
    logreg_metrics = _evaluate(logreg_pipeline, test_df)

    if min_auc is not None and gbm_metrics["auc"] < min_auc:
        raise ValueError(f"Gradient boosting AUC {gbm_metrics['auc']:.3f} is below the required minimum {min_auc}")

    gbm_path.parent.mkdir(parents=True, exist_ok=True)
    logreg_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(gbm_pipeline, gbm_path)
    joblib.dump(logreg_pipeline, logreg_path)

    return {
        "rows_trained": len(train_df),
        "rows_tested": len(test_df),
        "gradient_boosting": gbm_metrics,
        "logistic_regression": logreg_metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", type=Path, default=Path("data/synthetic_appointments.csv"))
    parser.add_argument("--min-auc", type=float, default=0.75)
    args = parser.parse_args()

    report = train_and_persist_models(args.data_path, min_auc=args.min_auc)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
