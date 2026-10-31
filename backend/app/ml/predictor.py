"""Loads the active model bundle and produces scored, explained predictions."""
from __future__ import annotations

import math
import threading

import joblib
import numpy as np
import pandas as pd

from .explain import shap_matrix, shap_space
from .features import FEATURE_NAMES, describe_factor

_lock = threading.Lock()
_cache: dict[str, dict] = {}


def load_bundle(path: str) -> dict:
    with _lock:
        if path not in _cache:
            _cache.clear()
            _cache[path] = joblib.load(path)
        return _cache[path]


def _anomaly_percentile(bundle: dict, raw: np.ndarray) -> np.ndarray:
    ref = bundle["train_anomaly_sorted"]
    return np.searchsorted(ref, raw, side="right") / len(ref)


def predict_frame(bundle: dict, X: pd.DataFrame, explain: bool = True, top_k: int = 5) -> list[dict]:
    primary = bundle["primary"]
    pipe = bundle["models"][primary]
    X = X[FEATURE_NAMES]
    probs = pipe.predict_proba(X)[:, 1]
    anomaly = _anomaly_percentile(bundle, -bundle["isolation_forest"].score_samples(X))
    shap_vals = shap_matrix(pipe, primary, X, bundle["background"]) if explain else None
    out = []
    for i in range(len(X)):
        row = X.iloc[i]
        feats = {k: (None if isinstance(v, float) and math.isnan(v) else float(v)) for k, v in row.items()}
        result = {
            "fraud_probability": float(round(probs[i], 4)),
            "anomaly_score": float(round(anomaly[i], 4)),
            "model_algorithm": primary,
            "model_version": bundle["version"],
            "features": feats,
            "shap_values": {},
            "top_risk_factors": [],
            "shap_space": shap_space(primary),
        }
        if shap_vals is not None:
            contrib = {f: float(round(v, 5)) for f, v in zip(FEATURE_NAMES, shap_vals[i])}
            result["shap_values"] = contrib
            positive = sorted(((f, v) for f, v in contrib.items() if v > 0), key=lambda kv: -kv[1])
            # log_amount duplicates amount; report one of them only
            seen_amount = False
            for f, v in positive:
                if f in ("amount", "log_amount"):
                    if seen_amount:
                        continue
                    seen_amount = True
                result["top_risk_factors"].append({
                    "feature": f,
                    "value": feats[f],
                    "shap": v,
                    "description": describe_factor(f, feats[f]),
                })
                if len(result["top_risk_factors"]) >= top_k:
                    break
        out.append(result)
    return out
