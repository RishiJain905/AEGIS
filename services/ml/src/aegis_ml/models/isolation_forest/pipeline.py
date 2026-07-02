"""Isolation Forest sklearn pipeline factory."""

from __future__ import annotations

from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DEFAULT_RANDOM_STATE = 42
DEFAULT_N_ESTIMATORS = 100
DEFAULT_CONTAMINATION = 0.05


def build_isolation_forest_pipeline(
    *,
    random_state: int = DEFAULT_RANDOM_STATE,
    n_estimators: int = DEFAULT_N_ESTIMATORS,
    contamination: float = DEFAULT_CONTAMINATION,
) -> Pipeline:
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "model",
                IsolationForest(
                    n_estimators=n_estimators,
                    contamination=contamination,
                    random_state=random_state,
                    n_jobs=1,
                ),
            ),
        ]
    )


def default_hyperparameters() -> dict[str, int | float]:
    return {
        "n_estimators": DEFAULT_N_ESTIMATORS,
        "contamination": DEFAULT_CONTAMINATION,
        "random_state": DEFAULT_RANDOM_STATE,
    }
