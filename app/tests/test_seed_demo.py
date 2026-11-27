"""scripts/seed_demo.py: 데모 시드가 서비스 규칙이 바뀌어도 계속 돌아가는지 (가상 데이터, 테스트 DB)."""

import os
from datetime import datetime
from unittest.mock import patch

import pytest
from tortoise.contrib.test import TestCase

from app.models.health_logs import HealthLog, HealthLogType
from app.models.risk_predictions import Disease, PredictionMethod, RiskPrediction
from app.models.users import User
from app.services.health_log_rules import KST
from scripts.seed_demo import DEMO_EMAIL, read_demo_password, seed

NOW = datetime(2026, 11, 26, 10, 0, tzinfo=KST)


class TestSeedDemo(TestCase):
    async def test_seed_builds_improving_four_weeks_and_is_repeatable(self) -> None:
        first = await seed(NOW, "Demo1234!")
        second = await seed(NOW, "Demo1234!")  # 다시 돌리면 지우고 새로 만듦

        assert await User.filter(email=DEMO_EMAIL).count() == 1
        assert (second.health_profiles, second.risk_predictions, second.health_logs) == (
            first.health_profiles,
            first.risk_predictions,
            first.health_logs,
        )
        assert second.health_profiles == 5  # 가입 설문 + 재설문 4번

        for disease in Disease:
            rows = await RiskPrediction.filter(
                user_id=second.user_id, disease=disease, method=PredictionMethod.MODEL
            ).order_by("created_at", "id")
            scores = [row.score for row in rows]
            assert scores[0] > scores[-1], f"{disease} 위험도가 4주 동안 내려가야 데모 시나리오가 됨"
            assert rows[0].created_at.astimezone(KST).date() < rows[-1].created_at.astimezone(KST).date()

        steps = await HealthLog.filter(user_id=second.user_id, log_type=HealthLogType.STEPS).count()
        assert steps == 29  # 28일 전 ~ 오늘, 하루 1행
        assert all(log.measured_at <= NOW for log in await HealthLog.filter(user_id=second.user_id))


def test_read_demo_password_stops_without_env() -> None:
    # 공개 레포라 비밀번호 기본값을 두지 않음 → 없으면 DB에 닿기 전에 멈춤
    # main()을 asyncio.run으로 부르면 이벤트 루프가 닫혀 다른 테스트가 깨지므로 동기 함수만 확인
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("DEMO_PASSWORD", None)
        with pytest.raises(SystemExit, match="DEMO_PASSWORD"):
            read_demo_password()


def test_read_demo_password_returns_env_value() -> None:
    with patch.dict(os.environ, {"DEMO_PASSWORD": "virtual-pass-1"}):
        assert read_demo_password() == "virtual-pass-1"
