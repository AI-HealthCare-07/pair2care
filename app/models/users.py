from enum import StrEnum

from tortoise import fields, models


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class Region(StrEnum):
    # 날씨·미세먼지용 시·도 (api.md 11-7). 에어코리아 sidoName과 같은 이름
    SEOUL = "서울"
    BUSAN = "부산"
    DAEGU = "대구"
    INCHEON = "인천"
    GWANGJU = "광주"
    DAEJEON = "대전"
    ULSAN = "울산"
    SEJONG = "세종"
    GYEONGGI = "경기"
    GANGWON = "강원"
    CHUNGBUK = "충북"
    CHUNGNAM = "충남"
    JEONBUK = "전북"
    JEONNAM = "전남"
    GYEONGBUK = "경북"
    GYEONGNAM = "경남"
    JEJU = "제주"


class User(models.Model):
    id = fields.BigIntField(primary_key=True)
    email = fields.CharField(max_length=255, unique=True)
    hashed_password = fields.CharField(max_length=128)
    nickname = fields.CharField(max_length=50)
    gender = fields.CharEnumField(enum_type=Gender)
    birthday = fields.DateField()
    quiet_start = fields.TimeField(null=True)  # 방해 금지 시작, 안 쓰면 비어 있음
    quiet_end = fields.TimeField(null=True)  # 방해 금지 끝
    region = fields.CharEnumField(enum_type=Region, max_length=10, null=True)  # 날씨용 시·도, 안 고르면 비어 있음
    is_active = fields.BooleanField(default=True)
    is_admin = fields.BooleanField(default=False)
    last_login = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"
