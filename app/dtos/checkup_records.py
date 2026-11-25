"""4장 검진 수치 요청 (api.md 4-1·4-4). 범위·타입이 틀리면 FastAPI 기본 422.

날짜가 미래인지, 수축기 > 이완기인지, 수치가 하나라도 있는지는 서비스가 400으로 봄 (수정은 기존 값과 합쳐서 봐야 해서).
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, Field

SystolicBp = Annotated[int, Field(ge=60, le=260)]
DiastolicBp = Annotated[int, Field(ge=30, le=160)]
FastingGlucose = Annotated[int, Field(ge=40, le=600)]
WaistCm = Annotated[Decimal, Field(ge=Decimal("40.0"), le=Decimal("200.0"), max_digits=4, decimal_places=1)]
Triglyceride = Annotated[int, Field(ge=20, le=2000)]
HdlCholesterol = Annotated[int, Field(ge=10, le=150)]
Hba1c = Annotated[Decimal, Field(ge=Decimal("3.0"), le=Decimal("15.0"), max_digits=3, decimal_places=1)]


class CheckupValuesFields(BaseModel):
    systolic_bp: SystolicBp | None = None
    diastolic_bp: DiastolicBp | None = None
    fasting_glucose: FastingGlucose | None = None
    waist_cm: WaistCm | None = None
    triglyceride: Triglyceride | None = None
    hdl_cholesterol: HdlCholesterol | None = None
    hba1c: Hba1c | None = None


class CheckupRecordCreateRequest(CheckupValuesFields):
    """source는 받지 않음: 4-6 결과지 인식 전까지 서버가 MANUAL로 저장 (보내도 무시, #103 리뷰)."""

    checked_on: date


class CheckupRecordUpdateRequest(CheckupValuesFields):
    """보낸 필드만 바꿈. 수치에 null을 보내면 그 값을 지움 (수정 후에도 최소 1개). 출처(source)는 못 바꿈."""

    checked_on: date | None = None

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)
