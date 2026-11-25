"""ml/compare.py: 모델 비교 (가상 데이터만, DB 없이 도는 순수 테스트).

CI test 작업은 app 그룹만 설치해서 sklearn·xgboost가 없음 → 없으면 건너뜀. 로컬은 --group ml로 실행.
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")
pytest.importorskip("xgboost")
pytest.importorskip("mlflow")

from app.services.prediction.features import FEATURE_NAMES  # noqa: E402
from ml.compare import (  # noqa: E402
    BASE_MODEL,
    auroc_difference,
    bootstrap_indices,
    compare_models,
    flatten_metrics,
    percentile_interval,
    summary_table,
)


def make_fake_data(n_rows: int = 1200, seed: int = 0) -> tuple[pd.DataFrame, pd.Series]:
    """나이·BMI·가족력이 위험을 올리는 가상 사람들 (실제 국건영 아님)."""
    rng = np.random.default_rng(seed)
    x = pd.DataFrame(0, index=range(n_rows), columns=list(FEATURE_NAMES), dtype=float)
    x["sex"] = rng.integers(1, 3, n_rows)
    x["age"] = rng.integers(30, 70, n_rows)
    x["bmi"] = rng.normal(24, 3, n_rows).round(1)
    x["father_diabetes_history"] = rng.integers(0, 2, n_rows)
    x["smoking_current"] = rng.integers(0, 2, n_rows)
    z = -9 + 0.06 * x["age"] + 0.2 * x["bmi"] + 0.8 * x["father_diabetes_history"]
    y = pd.Series((rng.random(n_rows) < 1 / (1 + np.exp(-z))).astype(int))
    return x, y


def test_bootstrap_indices_are_reproducible() -> None:
    first = bootstrap_indices(50, 10, seed=42)
    second = bootstrap_indices(50, 10, seed=42)
    assert first.shape == (10, 50)
    assert np.array_equal(first, second)
    assert first.min() >= 0 and first.max() < 50


def test_percentile_interval_ignores_nan() -> None:
    samples = np.array([np.nan, *np.linspace(0, 1, 101)])
    low, high = percentile_interval(samples)
    assert low == pytest.approx(0.025)
    assert high == pytest.approx(0.975)


def test_same_model_difference_is_zero() -> None:
    rng = np.random.default_rng(1)
    y = rng.integers(0, 2, 200)
    probability = rng.random(200)
    result = auroc_difference(y, probability, probability, bootstrap_indices(200, 50, seed=42))
    assert result == {"auroc_diff_vs_logistic": 0.0, "auroc_diff_ci_low": 0.0, "auroc_diff_ci_high": 0.0}


def test_compare_models_ranks_full_model_above_age_only() -> None:
    x, y = make_fake_data()

    results = compare_models(x, y, n_bootstrap=50)

    assert list(results) == [BASE_MODEL, "age_only", "age_bmi", "xgboost"]
    logistic = results[BASE_MODEL]
    assert logistic["auroc_ci_low"] <= logistic["auroc"] <= logistic["auroc_ci_high"]
    assert {"auroc_male", "auroc_female_ci_low", "recall_caution_or_high", "cv_auroc_std"} <= set(logistic)
    assert "auroc_diff_vs_logistic" not in logistic
    assert results["age_only"]["auroc"] < logistic["auroc"]
    assert results["age_only"]["auroc_diff_vs_logistic"] < 0


def test_outputs_are_aggregates_only() -> None:
    x, y = make_fake_data(n_rows=600)
    results = compare_models(x, y, n_bootstrap=20, model_names=(BASE_MODEL, "age_only"))

    table = summary_table(results)
    flat = flatten_metrics(results)

    assert table.count("\n") == 3  # 머리줄 + 구분줄 + 모델 2줄
    assert "| age_only |" in table and "기준" in table
    assert all(isinstance(value, float) for value in flat.values())
    assert "logistic_auroc" in flat and "age_only_auroc_diff_ci_low" in flat
