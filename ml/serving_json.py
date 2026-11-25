"""학습 결과 → 서버 모델 JSON + 같은 성별 평균 (api.md 5-0·5-2).

- 형식은 app/services/prediction/model.py(LogisticModel.from_dict)·health_age.py(parse_means_by_sex)와 같음
- CI(app 그룹만 설치)에서 테스트할 수 있게 표준 라이브러리와 app 코드만 씀 (pandas·sklearn 없음)
- 건강 나이는 곡선 대신 산식으로 바뀌어(#114·#121) 곡선은 만들지 않음
"""

from collections.abc import Iterable, Mapping
from typing import Any

from app.models.risk_predictions import Disease
from app.services.prediction.features import FEATURE_NAMES, SEX_CODE_BY_LABEL
from app.services.prediction.health_age import ITEM_FIELDS_BY_DISEASE


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


def health_age_fields(disease: Disease) -> tuple[str, ...]:
    """건강 나이·요인 7문항 = 서버 ITEM_FIELDS_BY_DISEASE 그대로 (학습·서빙 어긋남 방지). JSON에는 FEATURE_NAMES 순서로."""
    wanted = set(ITEM_FIELDS_BY_DISEASE[disease])
    return tuple(name for name in FEATURE_NAMES if name in wanted)


def build_means_by_sex(rows: Iterable[Mapping[str, float]], fields: Iterable[str]) -> dict[str, dict[str, float]]:
    """같은 성별 평균 (api.md 5-2 health_age·5-3 factors.years 기준). 남녀 합친 means를 쓰면 한쪽 성별이 일괄 치우침.

    rows: 모델 입력 12개 dict (100% 학습 데이터, means와 같은 집단). 키는 users.gender 값(MALE·FEMALE).
    """
    fields = tuple(fields)
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
