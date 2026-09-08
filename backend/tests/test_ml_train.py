from pathlib import Path

import joblib
import pandas as pd
import pytest

from app.ml.features import ALL_FEATURES
from app.ml.train import train_and_persist_models
from scripts.generate_synthetic_data import generate


@pytest.fixture
def small_dataset_path(tmp_path: Path) -> Path:
    df = generate(rows=1500, seed=7)
    path = tmp_path / "synthetic.csv"
    df.to_csv(path, index=False)
    return path


def test_train_and_persist_models_creates_loadable_pipelines(tmp_path: Path, small_dataset_path: Path) -> None:
    gbm_path = tmp_path / "gbm.joblib"
    logreg_path = tmp_path / "logreg.joblib"

    report = train_and_persist_models(small_dataset_path, min_auc=None, gbm_path=gbm_path, logreg_path=logreg_path)

    assert gbm_path.exists()
    assert logreg_path.exists()
    assert 0.0 <= report["gradient_boosting"]["auc"] <= 1.0
    assert 0.0 <= report["logistic_regression"]["auc"] <= 1.0
    assert report["rows_trained"] + report["rows_tested"] == 1500

    loaded = joblib.load(gbm_path)
    sample = pd.read_csv(small_dataset_path, parse_dates=["scheduled_start"]).iloc[:5][ALL_FEATURES]
    probabilities = loaded.predict_proba(sample)[:, 1]
    assert all(0.0 <= p <= 1.0 for p in probabilities)


def test_train_raises_when_auc_below_required_minimum(tmp_path: Path, small_dataset_path: Path) -> None:
    with pytest.raises(ValueError, match="AUC"):
        train_and_persist_models(
            small_dataset_path,
            min_auc=0.999,  # unreachable on this small sample — forces the guard to fire
            gbm_path=tmp_path / "gbm.joblib",
            logreg_path=tmp_path / "logreg.joblib",
        )


def test_generator_produces_no_trivial_leakage(small_dataset_path: Path) -> None:
    # A perfect (or near-perfect) AUC on synthetic data almost always means the
    # label leaked into a feature — guard against ever reintroducing that bug.
    gbm_path = small_dataset_path.parent / "leak_check_gbm.joblib"
    logreg_path = small_dataset_path.parent / "leak_check_logreg.joblib"
    report = train_and_persist_models(small_dataset_path, min_auc=None, gbm_path=gbm_path, logreg_path=logreg_path)
    assert report["gradient_boosting"]["auc"] < 0.98
