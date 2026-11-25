"""REQ-NFR-017 결과 일관성: 같은 입력이면 같은 점수·단계·요인 (실제 모델 JSON, DB 없이 도는 순수 테스트)."""

import pytest

from app.models.risk_predictions import Disease
from app.services.prediction.features import build_input_snapshot
from app.services.prediction.model import LogisticModel, read_model_file, to_level, to_score
from app.tests.survey.test_validation import make_answers

REPEAT = 100


def sample_inputs() -> dict[str, float]:
    answers = make_answers(smoking_current=8)  # 비흡연은 저장 때 8로 채워짐 (3-1 건너뛰기 규칙)
    return build_input_snapshot("MALE", 45, answers)["model_inputs"]


@pytest.mark.parametrize("disease", list(Disease))
def test_same_input_gives_same_result_every_time(disease: Disease) -> None:
    model = LogisticModel.from_dict(read_model_file(disease))
    inputs = sample_inputs()
    first = (to_score(model.probability(inputs)), model.factors(inputs))

    for _ in range(REPEAT):
        score = to_score(model.probability(sample_inputs()))
        assert (score, model.factors(sample_inputs())) == first
        assert to_level(score) == to_level(first[0])


@pytest.mark.parametrize("disease", list(Disease))
def test_reloading_model_file_gives_same_score(disease: Disease) -> None:
    """서버를 다시 띄워 모델을 새로 읽어도 같은 점수 (버전 고정: model_version이 같으면 같은 계산)."""
    data = read_model_file(disease)
    inputs = sample_inputs()
    scores = {to_score(LogisticModel.from_dict(read_model_file(disease)).probability(inputs)) for _ in range(10)}

    assert len(scores) == 1
    assert data["model_version"].endswith(":v1")
