# Runbook: Retraining the No-Show Model on Real Data

The no-show risk model (docs plan §10.3) bootstraps on synthetic data. Once the business has accumulated enough real booking history, retrain on that instead. This is the designed swap point, not a rewrite.

## When to switch

There's no hard rule, but a reasonable threshold: a few thousand completed/no-show/cancelled appointments, spanning at least a few months (so the time-based train/test split in `app/ml/train.py` has enough history to be meaningful), and covering both quiet and busy periods.

## What changes vs. what doesn't

- **`app/ml/features.py`**: unchanged. This is the schema contract both training and live scoring share; it's exactly why this swap doesn't touch `app/ml/predict.py` or the appointment-creation code path at all.
- **`app/ml/train.py`**: unchanged in structure. `train_and_persist_models(data_path, ...)` currently reads a CSV; swap `data_path` for a query.
- **New**: a data-loading function that builds the same columns `app/ml/features.py` expects (`ALL_FEATURES`) from the real `appointments`/`services` tables, e.g.:

  ```python
  # app/ml/load_training_data.py (new file)
  async def load_training_dataframe(db: AsyncSession) -> pd.DataFrame:
      """Builds one row per completed/cancelled/no_show appointment, computing
      the same causal (as-of-that-appointment) features
      scripts/generate_synthetic_data.py produces for the bootstrap dataset:
      client_past_no_show_rate, client_total_visits, etc. must only reflect
      appointments strictly before the one being scored, or the model will
      overfit on leaked future information (see the leakage-guard test in
      tests/test_ml_train.py for why this matters).
      """
  ```

  The client/staff historical-rate logic already exists and is exactly right for this: it's the same causal computation `app/ml/predict.py`'s `_client_history_stats`/`_staff_no_show_rate` do for live scoring. Reuse those functions rather than re-deriving the logic.

- **`app/tasks/ml_tasks.py`**: change `DEFAULT_TRAINING_DATA_PATH` handling: call the new `load_training_dataframe` and write it to a temp CSV (so `train_and_persist_models`'s CSV-reading interface doesn't need to change), or add a `train_and_persist_models_from_dataframe` variant.

## Steps

1. Implement `load_training_dataframe` (above).
2. Run it once manually and sanity-check the output: row count, no-show rate, no obviously-wrong values (e.g., negative lead times).
3. Run `train_and_persist_models` against the real dataframe with `min_auc=None` first, to see the actual measured AUC without the guard aborting the run, compare it against the 0.75 target and the synthetic-data baseline (0.765, per the Phase 3 verification).
4. If the AUC is acceptable, re-enable the `min_auc=0.75` guard and update `app/tasks/ml_tasks.py` to use the real-data path going forward.
5. Deploy: the weekly Celery Beat schedule (`retrain-no-show-model-weekly` in `app/tasks/celery_app.py`) picks up the new logic automatically; no schedule change needed.

## If the real-data AUC is lower than expected

This is common and doesn't necessarily mean something is broken: synthetic data has engineered, noise-controlled patterns; real client behavior is messier. Before concluding the model is unusable:

- Check for class imbalance (a very low real no-show rate makes AUC alone less informative, look at precision/recall at the top-20%-riskiest threshold too, which `train_and_persist_models` already reports).
- Confirm the causal computation isn't accidentally leaking (re-run the leakage-guard-style check from `tests/test_ml_train.py::test_generator_produces_no_trivial_leakage`, inverted: a suspiciously *high* AUC on real data is more likely to indicate leakage than a real signal).
- Consider keeping the synthetic-data model as a fallback (`app/ml/predict.py`'s `_load_model()` just reads whatever's at `GBM_MODEL_PATH`, you can keep both artifacts and choose which to promote).
