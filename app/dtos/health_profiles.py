"""3-1 설문 저장 요청 (api.md 3-1 "문항별 입력 규칙").

여기서는 형식(타입·범위·보기 값)만 본다 → 틀리면 FastAPI 기본 422.
필수 여부·건너뛰기·성별 조건은 kind와 앞 답에 따라 달라서 서비스의 검사 로직이 400으로 본다 (그래서 전부 None 허용).
범위·보기 값은 questions.py 상수와 같아야 함 → test_health_profile_dtos.py가 둘을 대조함.
"""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.models.health_profiles import SurveyKind

FamilyHistory = Literal[0, 1, 9]  # 아니요 / 예 / 모름
SiblingHistory = Literal[0, 1, 8, 9]  # + 형제자매 없음 8


# cm·kg는 소수 첫째 자리까지 (step 0.1), DB DECIMAL(4,1)
HeightCm = Annotated[Decimal, Field(ge=Decimal("100.0"), le=Decimal("230.0"), max_digits=4, decimal_places=1)]
WeightKg = Annotated[Decimal, Field(ge=Decimal("25.0"), le=Decimal("300.0"), max_digits=4, decimal_places=1)]
WaistCm = Annotated[Decimal, Field(ge=Decimal("40.0"), le=Decimal("200.0"), max_digits=4, decimal_places=1)]
CigarettesPerDay = Annotated[int, Field(ge=1, le=60)]


class HealthProfileCreateRequest(BaseModel):
    kind: SurveyKind
    survey_version: Annotated[str, Field(min_length=1, max_length=20)]

    height_cm: HeightCm | None = None
    weight_kg: WeightKg | None = None
    waist_cm: WaistCm | None = None

    father_diabetes_history: FamilyHistory | None = None
    mother_diabetes_history: FamilyHistory | None = None
    sibling_diabetes_history: SiblingHistory | None = None
    father_hypertension_history: FamilyHistory | None = None
    mother_hypertension_history: FamilyHistory | None = None
    sibling_hypertension_history: SiblingHistory | None = None

    # 건너뛰기로 생기는 8·888은 서버가 채움 → 프론트가 보내면 범위 밖이라 422
    alcohol_ever: Literal[1, 2] | None = None
    alcohol_frequency: Literal[1, 2, 3, 4, 5, 6] | None = None
    alcohol_amount: Literal[1, 2, 3, 4, 5] | None = None
    binge_frequency: Literal[1, 2, 3, 4, 5] | None = None

    smoking_lifetime: Literal[1, 2, 3] | None = None
    smoking_current: Literal[1, 2, 3] | None = None
    cigarettes_per_day: CigarettesPerDay | None = None
    heated_tobacco: Literal[1, 2, 3, 8] | None = None  # 사용한 적 없음 8은 사용자가 고른 보기
    liquid_ecig: Literal[1, 2, 8] | None = None

    is_hypertension_diagnosed: bool | None = None
    is_diabetes_diagnosed: bool | None = None
    is_pregnant: bool | None = None

    def answers(self) -> dict[str, object]:
        """검사 로직에 넘길 문항 값 (kind·survey_version 제외)."""
        return self.model_dump(exclude={"kind", "survey_version"})
