"""5-4 습관 시뮬레이션: 최근 설문 값 위에 바꾼 습관만 덮어서 다시 계산 (저장 안 함). DB 없이 쓰는 순수 함수."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Annotated, Any, Final, Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.services.survey.validation import MISSING_DETAIL_BY_FIELD, SKIP_VIOLATION_DETAIL

# 위험도를 바꾸는 생활 요인 = 체중·음주·흡연 (운동은 체중 변화로 보여줌)
SIMULATABLE_FIELDS: Final = ("weight_kg", "alcohol_frequency", "alcohol_amount", "smoking_current")

NOT_SIMULATABLE_DETAIL: Final = "체중·음주·흡연만 바꿔 볼 수 있어요."
NOT_APPLICABLE_DETAIL: Final = "지금 해당하지 않는 습관은 바꿔 볼 수 없어요."


class SimulationChanges(BaseModel):
    """바꿀 값 형식 (3-1 입력 규칙과 같은 범위). 틀리면 422."""

    model_config = ConfigDict(extra="forbid")

    weight_kg: (
        Annotated[Decimal, Field(ge=Decimal("25.0"), le=Decimal("300.0"), max_digits=4, decimal_places=1)] | None
    ) = None
    alcohol_frequency: Literal[1, 2, 3, 4, 5, 6] | None = None
    alcohol_amount: Literal[1, 2, 3, 4, 5] | None = None
    smoking_current: Literal[1, 2, 3] | None = None


class SimulationRequest(BaseModel):
    changes: dict[str, Any]


def check_simulatable_keys(changes: Mapping[str, Any]) -> None:
    """체중·음주·흡연 외의 필드가 오면 400 (형식 검사 422보다 먼저, api.md 5-4)."""
    if not changes or any(key not in SIMULATABLE_FIELDS for key in changes):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=NOT_SIMULATABLE_DETAIL)


def apply_changes(survey: Mapping[str, Any], changes: SimulationChanges) -> dict[str, Any]:
    """최근 설문 값(21개) 위에 바꾼 값을 덮은 새 값. 건너뛰기 규칙은 3-1과 같음.

    - 최근 설문에서 비해당인 습관(술을 마셔 본 적 없음·담배를 피운 적 없음)은 바꿀 수 없음 → 400
    - 음주 빈도를 1(최근 1년 안 마심)로 바꾸면 한 번 음주량은 서버가 8로 채움 (같이 보내면 400)
    - 음주 빈도를 1에서 2 이상으로 바꾸면 한 번 음주량도 같이 보내야 함 (없으면 400)
    """
    sent = changes.model_dump(exclude_none=True)
    merged = dict(survey)

    if survey["alcohol_ever"] == 1 and ("alcohol_frequency" in sent or "alcohol_amount" in sent):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=NOT_APPLICABLE_DETAIL)
    if survey["smoking_lifetime"] == 3 and "smoking_current" in sent:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=NOT_APPLICABLE_DETAIL)

    merged.update(sent)

    if "alcohol_frequency" in sent or "alcohol_amount" in sent:
        if merged["alcohol_frequency"] == 1:
            if "alcohol_amount" in sent:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=SKIP_VIOLATION_DETAIL[("alcohol_frequency", "alcohol_amount")],
                )
            merged["alcohol_amount"] = 8
        elif merged["alcohol_amount"] == 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=MISSING_DETAIL_BY_FIELD["alcohol_amount"]
            )
    return merged
