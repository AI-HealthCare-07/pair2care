"""ml/plot_comparison.py: 위험 단계·보정 집계와 그림 저장 (가상 데이터만, DB 없이 도는 순수 테스트).

CI test 작업은 app 그룹만 설치해서 sklearn·matplotlib·xgboost가 없음 → 없으면 건너뜀. 로컬은 --group ml로 실행.
"""

from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("pandas")
pytest.importorskip("sklearn")
pytest.importorskip("matplotlib")
pytest.importorskip("mlflow")
try:
    import xgboost  # noqa: F401
except Exception:  # 설치 안 됨(ImportError) 또는 맥에 libomp 없음(XGBoostError)
    pytest.skip("xgboost를 쓸 수 없음 (맥은 brew install libomp)", allow_module_level=True)

import math  # noqa: E402

import numpy as np  # noqa: E402

from app.tests.ml_training.test_compare import make_fake_data  # noqa: E402
from ml.plot_comparison import calibration_bins, holdout_probabilities, level_outcomes, save_figures  # noqa: E402


def test_level_outcomes_split_by_server_thresholds() -> None:
    # 29.4점 → 29 낮음, 29.5점 → 30 주의, 59.5점 → 60 높음 (서버 to_score·to_level과 같음)
    probability = np.array([0.10, 0.294, 0.295, 0.50, 0.595, 0.90])
    y = np.array([0, 0, 1, 0, 1, 1])
    low, caution, high = level_outcomes(y, probability)
    assert (low.count, caution.count, high.count) == (2, 2, 2)
    assert (low.positive_rate, caution.positive_rate, high.positive_rate) == (0.0, 0.5, 1.0)


def test_level_outcomes_empty_level_is_nan() -> None:
    low, caution, high = level_outcomes(np.array([0, 1]), np.array([0.1, 0.2]))
    assert low.count == 2 and caution.count == 0 and math.isnan(caution.positive_rate)


def test_calibration_bins_equal_size_and_sorted() -> None:
    probability = np.linspace(0.0, 0.99, 100)
    y = (probability > 0.5).astype(int)
    bins = calibration_bins(y, probability, n_bins=10)
    assert len(bins.mean_predicted) == 10
    assert np.all(np.diff(bins.mean_predicted) > 0)
    assert bins.observed_rate[0] == 0.0 and bins.observed_rate[-1] == 1.0


def test_save_figures_writes_three_pngs(tmp_path: Path) -> None:
    x, y = make_fake_data(n_rows=600)
    result = holdout_probabilities(x, y)
    saved = save_figures({"diabetes": result, "hypertension": result}, tmp_path)
    assert [path.name for path in saved] == ["roc.png", "levels.png", "calibration.png"]
    assert all(path.stat().st_size > 10_000 for path in saved)
