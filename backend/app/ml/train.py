"""Model training pipeline: cleaning -> point-in-time features -> imputation -> class-imbalance aware
training of four models -> honest hold-out evaluation -> persistence.

All reported metrics are computed on a stratified hold-out test set the models never saw.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from .features import FEATURE_NAMES, FeatureState, StaticContext, TxnRecord

log = logging.getLogger("sentinel.ml")
RANDOM_STATE = 42


def build_dataset(records: list[TxnRecord], labels: list[int | None], ctx: StaticContext):
    """Replay history chronologically so each row only sees the past. Returns (X, y, ids, state)."""
    order = sorted(range(len(records)), key=lambda i: records[i].ts)
    state = FeatureState(ctx)
    rows, ys, ids = [], [], []
    for i in order:
        r = records[i]
        feats = state.features(r)
        state.add(r)
        rows.append(feats)
        ys.append(labels[i])
        ids.append(r.id)
    X = pd.DataFrame(rows, columns=FEATURE_NAMES)
    return X, pd.Series(ys, dtype="float"), ids, state


def clean(X: pd.DataFrame, y: pd.Series, ids: list[str]):
    """Data cleaning: drop unlabeled rows, duplicates and invalid amounts; clip extreme values."""
    df = X.copy()
    df["_y"] = y.values
    df["_id"] = ids
    before = len(df)
    df = df[df["_y"].notna()]
    df = df.drop_duplicates(subset="_id")
    df = df[df["amount"] > 0]
    df["geo_velocity_kmh"] = df["geo_velocity_kmh"].clip(upper=5000)
    df["amount_to_avg_ratio"] = df["amount_to_avg_ratio"].clip(upper=200)
    df["amount_zscore"] = df["amount_zscore"].clip(-50, 200)
    report = {
        "rows_in": before,
        "rows_out": len(df),
        "dropped": before - len(df),
        "missing_values": {c: int(df[c].isna().sum()) for c in FEATURE_NAMES if df[c].isna().any()},
    }
    return df[FEATURE_NAMES], df["_y"].astype(int), report


def _curve_points(xs, ys, n=60):
    idx = np.linspace(0, len(xs) - 1, min(n, len(xs))).astype(int)
    return [{"x": round(float(xs[i]), 4), "y": round(float(ys[i]), 4)} for i in idx]


def _evaluate(y_true, scores, preds) -> dict:
    cm = confusion_matrix(y_true, preds, labels=[0, 1])
    fpr, tpr, _ = roc_curve(y_true, scores)
    prec, rec, thr = precision_recall_curve(y_true, scores)
    f1s = 2 * prec * rec / np.clip(prec + rec, 1e-9, None)
    best = int(np.nanargmax(f1s[:-1])) if len(thr) else 0
    return {
        "precision": round(float(precision_score(y_true, preds, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, preds, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, preds, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, scores)), 4),
        "pr_auc": round(float(average_precision_score(y_true, scores)), 4),
        "confusion_matrix": {"tn": int(cm[0, 0]), "fp": int(cm[0, 1]), "fn": int(cm[1, 0]), "tp": int(cm[1, 1])},
        "best_f1_threshold": round(float(thr[best]), 4) if len(thr) else None,
        "best_f1": round(float(f1s[best]), 4) if len(thr) else None,
        "roc_curve": _curve_points(fpr, tpr),
        "pr_curve": _curve_points(rec[::-1], prec[::-1]),
    }


def train_all(X: pd.DataFrame, y: pd.Series, version: str, model_dir: str, cleaning_report: dict) -> dict:
    t0 = time.time()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, stratify=y, random_state=RANDOM_STATE
    )
    pos, neg = int(y_train.sum()), int((1 - y_train).sum())
    imbalance = neg / max(pos, 1)

    models = {
        "logistic_regression": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(class_weight="balanced", max_iter=3000, C=0.5)),
        ]),
        "random_forest": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("model", RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced_subsample",
                                             random_state=RANDOM_STATE, n_jobs=-1)),
        ]),
        "xgboost": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("model", XGBClassifier(n_estimators=250, max_depth=4, learning_rate=0.07, subsample=0.9,
                                    colsample_bytree=0.85, min_child_weight=2, reg_lambda=1.5,
                                    scale_pos_weight=imbalance, eval_metric="aucpr",
                                    random_state=RANDOM_STATE, n_jobs=2)),
        ]),
    }
    results: dict[str, dict] = {}
    for name, pipe in models.items():
        pipe.fit(X_train, y_train)
        scores = pipe.predict_proba(X_test)[:, 1]
        results[name] = _evaluate(y_test, scores, (scores >= 0.5).astype(int))
        results[name]["threshold"] = 0.5

    # Isolation Forest is unsupervised: fit without labels, evaluated against labels for honesty.
    iso = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("model", IsolationForest(n_estimators=300, contamination=round(pos / (pos + neg), 3),
                                  random_state=RANDOM_STATE)),
    ])
    iso.fit(X_train)
    train_anomaly = np.sort(-iso.score_samples(X_train))
    test_anomaly = -iso.score_samples(X_test)
    results["isolation_forest"] = _evaluate(y_test, test_anomaly, (iso.predict(X_test) == -1).astype(int))
    results["isolation_forest"]["threshold"] = "contamination"

    supervised = ["xgboost", "random_forest", "logistic_regression"]
    primary = max(supervised, key=lambda n: (results[n]["pr_auc"], n == "xgboost"))

    # Global explanation: mean |SHAP| over the test set for the primary model.
    from .explain import shap_matrix

    shap_vals = shap_matrix(models[primary], primary, X_test, X_train)
    importance = sorted(
        ({"feature": f, "mean_abs_shap": round(float(v), 5)} for f, v in zip(FEATURE_NAMES, np.abs(shap_vals).mean(0))),
        key=lambda d: -d["mean_abs_shap"],
    )

    out_dir = Path(model_dir) / version
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "version": version,
        "feature_names": FEATURE_NAMES,
        "models": models,
        "isolation_forest": iso,
        "train_anomaly_sorted": train_anomaly,
        "primary": primary,
        "background": X_train.sample(min(200, len(X_train)), random_state=RANDOM_STATE),
    }
    path = out_dir / "bundle.joblib"
    joblib.dump(bundle, path)

    summary = {
        "version": version,
        "primary": primary,
        "artifact_path": str(path),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "train_positive": pos,
        "test_positive": int(y_test.sum()),
        "positive_rate": round(float(y.mean()), 4),
        "class_imbalance_ratio": round(imbalance, 2),
        "cleaning": cleaning_report,
        "results": results,
        "global_importance": importance,
        "training_seconds": round(time.time() - t0, 2),
        "split": "stratified random 75/25, random_state=42",
    }
    log.info("Trained models %s in %.1fs; primary=%s pr_auc=%.3f", version, summary["training_seconds"], primary,
             results[primary]["pr_auc"])
    return summary
