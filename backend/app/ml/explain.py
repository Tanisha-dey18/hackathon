"""SHAP explanations for the supervised models."""
from __future__ import annotations

import numpy as np
import pandas as pd
import shap

_explainers: dict[int, object] = {}


def _explainer(pipe, algorithm: str, background: pd.DataFrame):
    key = id(pipe)
    if key not in _explainers:
        model = pipe.named_steps["model"]
        if algorithm == "logistic_regression":
            bg = pipe[:-1].transform(background)
            _explainers[key] = shap.LinearExplainer(model, bg)
        else:
            _explainers[key] = shap.TreeExplainer(model)
    return _explainers[key]


def shap_matrix(pipe, algorithm: str, X: pd.DataFrame, background: pd.DataFrame) -> np.ndarray:
    """SHAP values (n_rows x n_features) for the positive (fraud) class.

    XGBoost/LR values are in log-odds space; Random Forest values are in probability space."""
    Xt = pipe[:-1].transform(X)
    vals = _explainer(pipe, algorithm, background).shap_values(Xt)
    if isinstance(vals, list):  # older shap: one array per class
        vals = vals[1]
    vals = np.asarray(vals)
    if vals.ndim == 3:  # (n, features, classes)
        vals = vals[:, :, 1]
    return vals


def shap_space(algorithm: str) -> str:
    return "probability" if algorithm == "random_forest" else "log-odds"
