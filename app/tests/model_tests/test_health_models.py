"""건강 프로필·검진 모델이 ERD(docs/erd.dbml)와 맞는지 확인."""

from tortoise.fields import DecimalField

from app.models.checkup_records import CheckupRecord, CheckupSource
from app.models.health_profiles import HealthProfile, SurveyKind


def _nullable(model: type, name: str) -> bool:
    return bool(model._meta.fields_map[name].null)  # type: ignore[attr-defined]


def test_health_profile_nullable_fields_match_erd() -> None:
    # ERD에서 null 허용은 허리둘레(선택)·임신 여부(남성은 null) 둘뿐
    nullable = {name for name in HealthProfile._meta.db_fields if _nullable(HealthProfile, name)}
    assert nullable == {"waist_cm", "is_pregnant"}


def test_health_profile_decimal_precision() -> None:
    for name in ("height_cm", "weight_kg", "waist_cm"):
        field = HealthProfile._meta.fields_map[name]
        assert isinstance(field, DecimalField)
        assert (field.max_digits, field.decimal_places) == (4, 1)


def test_checkup_values_are_all_optional() -> None:
    # 수치는 모두 선택 (최소 1개 검사는 API에서)
    values = ("systolic_bp", "diastolic_bp", "fasting_glucose", "waist_cm", "triglyceride", "hdl_cholesterol", "hba1c")
    assert all(_nullable(CheckupRecord, name) for name in values)
    assert not _nullable(CheckupRecord, "checked_on")


def test_checkup_defaults_and_hba1c_precision() -> None:
    assert CheckupRecord._meta.fields_map["source"].default == CheckupSource.MANUAL
    hba1c = CheckupRecord._meta.fields_map["hba1c"]
    assert isinstance(hba1c, DecimalField)
    assert (hba1c.max_digits, hba1c.decimal_places) == (3, 1)


def test_enum_values_match_erd() -> None:
    assert {k.value for k in SurveyKind} == {"ONBOARDING", "WEEKLY"}
    assert {s.value for s in CheckupSource} == {"MANUAL", "OCR"}
