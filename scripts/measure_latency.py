"""담당 API 응답 시간 점검 (REQ-NFR-016: 전체 API P95 3초 이내).

데모 시드(scripts/seed_demo.py)를 넣은 로컬 서버에 실제 HTTP로 요청해서 API마다 P50·P95·최대를 잼.
출력은 집계 숫자만 (응답 본문·건강정보는 찍지 않음).

실행 (레포 루트, 서버가 떠 있는 상태):
    DEMO_PASSWORD='시드 때 정한 비밀번호' uv run python -m scripts.measure_latency                # 읽기 API만 (기본 30번씩)
    DEMO_PASSWORD='시드 때 정한 비밀번호' uv run python -m scripts.measure_latency --with-writes  # 3-1·6-1 저장도 (행이 쌓임 → 끝나면 시드 다시)

- 주소는 BASE_URL 환경 변수, 없으면 http://localhost (nginx 경유, 실제 화면과 같은 길)
- 첫 요청 1번은 준비 운동으로 빼고 잼 (모델 파일 읽기·연결 만들기)
"""

import argparse
import asyncio
import os
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Final
from zoneinfo import ZoneInfo

import httpx

from scripts.seed_demo import DEMO_EMAIL, read_demo_password

P95_LIMIT_MS: Final = 3000
DEFAULT_REPEAT: Final = 30
KST: Final = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class Target:
    name: str  # api.md 번호 + 이름
    method: str
    path: str
    body: Callable[[int], dict[str, Any]] | None = None  # 몇 번째 요청인지 받아서 본문 (쓰기 API용)


@dataclass(frozen=True)
class Result:
    name: str
    count: int
    p50_ms: float
    p95_ms: float
    max_ms: float
    errors: int


def percentile(values: list[float], ratio: float) -> float:
    """최근접 순위 백분위 (표본이 30개 안팎이라 보간 없이)."""
    ordered = sorted(values)
    rank = max(1, round(ratio * len(ordered)))
    return ordered[rank - 1]


def summarize(name: str, elapsed_ms: list[float], errors: int) -> Result:
    if not elapsed_ms:
        return Result(name, 0, 0.0, 0.0, 0.0, errors)
    return Result(
        name=name,
        count=len(elapsed_ms),
        p50_ms=statistics.median(elapsed_ms),
        p95_ms=percentile(elapsed_ms, 0.95),
        max_ms=max(elapsed_ms),
        errors=errors,
    )


def read_targets(today: date, prediction_id: int, checkup_id: int | None) -> list[Target]:
    monday = today - timedelta(days=today.weekday())
    month_ago = today - timedelta(days=28)
    targets = [
        Target("3-2 최근 설문", "GET", "/api/v1/health-profiles/latest"),
        Target("3-6 설문 문항", "GET", "/api/v1/health-profiles/questions?kind=WEEKLY"),
        Target("4-2 검진 목록", "GET", "/api/v1/checkup-records?limit=20"),
        Target("5-2 최근 예측", "GET", "/api/v1/risk-predictions/latest"),
        Target("5-3 예측 상세", "GET", f"/api/v1/risk-predictions/{prediction_id}"),
        Target(
            "5-4 습관 시뮬레이션",
            "POST",
            "/api/v1/risk-predictions/simulate",
            body=lambda _: {"changes": {"weight_kg": 76.0, "alcohol_frequency": 2}},
        ),
        Target(
            "6-2 기록 조회(혈압 4주)", "GET", f"/api/v1/health-logs?log_type=BLOOD_PRESSURE&from={month_ago}&to={today}"
        ),
        Target("6-5 주간 기록 조회", "GET", f"/api/v1/health-logs/weekly/{monday}"),
        Target("7-1 위험도 추이(12주)", "GET", "/api/v1/dashboard/risk-trend?weeks=12"),
        Target(
            "7-2 항목별 그래프(걸음 일별)",
            "GET",
            f"/api/v1/dashboard/logs?log_type=STEPS&from={month_ago}&to={today}&bucket=day",
        ),
        Target("7-3 요약 카드", "GET", "/api/v1/dashboard/summary"),
    ]
    if checkup_id is not None:
        targets.insert(3, Target("4-3 검진 한 건", "GET", f"/api/v1/checkup-records/{checkup_id}"))
    return targets


def write_targets() -> list[Target]:
    """저장 API. 3-1은 예측까지 하는 가장 무거운 요청이라 따로 잼."""
    return [
        Target(
            "3-1 재설문 저장(+예측)",
            "POST",
            "/api/v1/health-profiles",
            body=lambda i: {
                "kind": "WEEKLY",
                "survey_version": "v1.0",
                "weight_kg": 79.5 - 0.1 * (i % 10),
                "waist_cm": 92.0,
                "alcohol_ever": 2,
                "alcohol_frequency": 2,
                "alcohol_amount": 1,
                "binge_frequency": 1,
                "smoking_lifetime": 2,
                "smoking_current": 3,
                "is_hypertension_diagnosed": False,
                "is_diabetes_diagnosed": False,
            },
        ),
        Target(
            "6-1 일일 기록 저장(혈압)",
            "POST",
            "/api/v1/health-logs",
            body=lambda i: {"log_type": "BLOOD_PRESSURE", "value": 128 + i % 5, "value2": 82},
        ),
    ]


async def login(client: httpx.AsyncClient, password: str) -> None:
    response = await client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": password})
    if response.status_code != httpx.codes.OK:
        raise SystemExit(f"데모 사용자 로그인 실패 ({response.status_code}): 시드를 먼저 넣었는지 확인")
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


async def find_ids(client: httpx.AsyncClient) -> tuple[int, int | None]:
    latest = (await client.get("/api/v1/risk-predictions/latest")).json()
    model_rows = [row for row in latest["predictions"] if row["method"] == "MODEL"]
    if not model_rows:
        raise SystemExit("모델 예측이 없음: 시드를 먼저 넣었는지 확인")
    checkups = (await client.get("/api/v1/checkup-records?limit=1")).json()["items"]
    return model_rows[0]["id"], checkups[0]["id"] if checkups else None


async def measure(client: httpx.AsyncClient, target: Target, repeat: int) -> Result:
    elapsed_ms: list[float] = []
    errors = 0
    for i in range(repeat + 1):
        body = target.body(i) if target.body else None
        started = time.perf_counter()
        response = await client.request(target.method, target.path, json=body)
        took = (time.perf_counter() - started) * 1000
        if i == 0:
            continue  # 준비 운동
        if response.status_code >= 400:
            errors += 1
            continue
        elapsed_ms.append(took)
    return summarize(target.name, elapsed_ms, errors)


def report(results: list[Result]) -> str:
    lines = [
        f"| API | 횟수 | P50 (ms) | P95 (ms) | 최대 (ms) | 오류 | {P95_LIMIT_MS // 1000}초 이내 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        verdict = "✅" if r.count and r.p95_ms <= P95_LIMIT_MS and r.errors == 0 else "❌"
        lines.append(
            f"| {r.name} | {r.count} | {r.p50_ms:.0f} | {r.p95_ms:.0f} | {r.max_ms:.0f} | {r.errors} | {verdict} |"
        )
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description="담당 API 응답 시간 점검 (REQ-NFR-016)")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    parser.add_argument("--with-writes", action="store_true", help="3-1·6-1 저장도 잼 (데모 사용자에 행이 쌓임)")
    args = parser.parse_args()

    password = read_demo_password()  # 없으면 요청 보내기 전에 멈춤 (시드와 같은 규칙)
    base_url = os.environ.get("BASE_URL", "http://localhost")
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        await login(client, password)
        prediction_id, checkup_id = await find_ids(client)
        targets = read_targets(datetime.now(KST).date(), prediction_id, checkup_id)
        if args.with_writes:
            targets += write_targets()
        results = [await measure(client, target, args.repeat) for target in targets]

    print(f"\n{base_url} · API마다 {args.repeat}번 (첫 요청 제외)\n")
    print(report(results))


if __name__ == "__main__":
    asyncio.run(main())
