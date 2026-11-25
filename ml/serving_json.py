"""학습 결과 → 서버 모델 JSON + 같은 성별 평균 + 건강 나이 곡선 (api.md 5-0·5-2).

- 형식은 app/services/prediction/model.py(LogisticModel.from_dict)·health_age.py와 같음
- CI(app 그룹만 설치)에서 테스트할 수 있게 표준 라이브러리와 features.py만 씀 (pandas·sklearn 없음)
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from itertools import pairwise
from typing import Any, Final

from app.services.prediction.features import FEATURE_NAMES, MAX_AGE, MIN_AGE, SEX_CODE_BY_LABEL

CURVE_AGES: Final = tuple(range(MIN_AGE, MAX_AGE + 1))  # 30~69세, 40개 (서버 health_age.py와 같음)


def to_server_json(
    *,
    model_version: str,
    disease: str,
    intercept: float,
    coefficients: Mapping[str, float],
    means: Mapping[str, float],
    mlflow_run_id: str | None,
) -> dict[str, Any]:
    """원래 단위 계수·학습 평균 → 서버 JSON. features 순서는 FEATURE_NAMES 그대로 (서버가 순서를 검사함)."""
    missing = [name for name in FEATURE_NAMES if name not in coefficients or name not in means]
    if missing:
        raise ValueError(f"계수·평균이 없는 입력: {missing}")
    return {
        "model_version": model_version,
        "mlflow_run_id": mlflow_run_id,
        "disease": disease,
        "features": list(FEATURE_NAMES),
        "intercept": float(intercept),
        "coefficients": {name: float(coefficients[name]) for name in FEATURE_NAMES},
        "means": {name: float(means[name]) for name in FEATURE_NAMES},
    }


# 건강 나이·요인 7문항 중 생활습관 4개 (나머지 3개는 그 질환 가족력, api.md 5-2 health_age·5-3 factors)
HABIT_FIELDS: Final = ("bmi", "alcohol_frequency", "alcohol_amount", "smoking_current")
HEALTH_AGE_FIELD_COUNT: Final = 7


def health_age_fields(own_family_fields: Sequence[str]) -> tuple[str, ...]:
    """건강 나이·요인 7문항 = 생활습관 4개 + 그 질환 가족력 3개 (FEATURE_NAMES 순서). 다른 질환 가족력은 평균 고정."""
    wanted = {*HABIT_FIELDS, *own_family_fields}
    fields = tuple(name for name in FEATURE_NAMES if name in wanted)
    if len(fields) != HEALTH_AGE_FIELD_COUNT:
        raise ValueError(f"건강 나이 문항이 7개가 아님: {fields}")
    return fields


def build_means_by_sex(rows: Iterable[Mapping[str, float]], fields: Sequence[str]) -> dict[str, dict[str, float]]:
    """같은 성별 평균 (api.md 5-2 health_age·5-3 factors.years 기준). 남녀 합친 means를 쓰면 한쪽 성별이 일괄 치우침.

    rows: 모델 입력 12개 dict (100% 학습 데이터, means와 같은 집단). 키는 users.gender 값(MALE·FEMALE).
    """
    sums = {code: dict.fromkeys(fields, 0.0) for code in SEX_CODE_BY_LABEL.values()}
    counts = dict.fromkeys(SEX_CODE_BY_LABEL.values(), 0)
    for row in rows:
        code = int(row["sex"])
        counts[code] += 1
        for name in fields:
            sums[code][name] += float(row[name])

    means_by_sex: dict[str, dict[str, float]] = {}
    for label, code in SEX_CODE_BY_LABEL.items():
        if counts[code] == 0:
            raise ValueError(f"{label} 기준 집단이 없음")
        means_by_sex[label] = {name: sums[code][name] / counts[code] for name in fields}
    return means_by_sex


def linear_sum(spec: Mapping[str, Any], row: Mapping[str, float]) -> float:
    """서버 model.py probability와 같은 선형합 (이름으로 계수를 짝지음)."""
    return float(spec["intercept"]) + sum(
        float(spec["coefficients"][name]) * float(row[name]) for name in FEATURE_NAMES
    )


def sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z))


def build_health_age_curve(
    spec: Mapping[str, Any], rows: Iterable[Mapping[str, float]]
) -> dict[str, list[dict[str, float]]]:
    """건강 나이 곡선 (11/24 검증: 나이만 바꾼 값 + 성별 분리).

    같은 성별 기준 집단 전원의 나이만 a로 바꿔 예측한 확률의 평균을 30~69세 정수마다 계산.
    rows: 모델 입력 12개 dict (100% 학습 데이터 = 아직 진단받지 않은 사람). 확률은 반올림하지 않음.
    """
    age_coef = float(spec["coefficients"]["age"])
    if age_coef <= 0:
        raise ValueError("age 계수가 양수가 아니라 곡선이 커지지 않음")

    # 나이 항을 뺀 선형합을 성별로 모아 둠 → 나이 a의 확률 = sigmoid(나머지 + age 계수 × a)
    rest_by_sex: dict[int, list[float]] = {code: [] for code in SEX_CODE_BY_LABEL.values()}
    for row in rows:
        rest_by_sex[int(row["sex"])].append(linear_sum(spec, row) - age_coef * float(row["age"]))

    curve: dict[str, list[dict[str, float]]] = {}
    for label, code in SEX_CODE_BY_LABEL.items():
        rests = rest_by_sex[code]
        if not rests:
            raise ValueError(f"{label} 기준 집단이 없음")
        curve[label] = [
            {"age": age, "probability": sum(sigmoid(rest + age_coef * age) for rest in rests) / len(rests)}
            for age in CURVE_AGES
        ]
    check_health_age_curve(curve)
    return curve


def check_health_age_curve(curve: Mapping[str, Any]) -> None:
    """서버 곡선 검사와 같은 조건: 성별마다 30~69 정수 40개, 확률 0~1, 같은 값 없이 커짐. 어긋나면 ValueError."""
    for label in SEX_CODE_BY_LABEL:
        points = curve.get(label)
        if not isinstance(points, list):
            raise ValueError(f"health_age_curve에 {label}가 없음")
        if tuple(int(point["age"]) for point in points) != CURVE_AGES:
            raise ValueError(f"{label} 곡선 나이가 30~69 정수 40개가 아님")
        probabilities = [float(point["probability"]) for point in points]
        if not all(0 <= value <= 1 for value in probabilities):
            raise ValueError(f"{label} 곡선에 0~1 밖의 확률이 있음")
        if not all(before < after for before, after in pairwise(probabilities)):
            raise ValueError(f"{label} 곡선이 같은 값 없이 커지지 않음")
