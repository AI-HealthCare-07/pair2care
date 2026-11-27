"""scripts/measure_latency.py 집계 (DB·서버 없이 도는 순수 테스트)."""

from scripts.measure_latency import Result, percentile, report, summarize


def test_percentile_nearest_rank() -> None:
    values = [float(v) for v in range(1, 21)]  # 1~20

    assert percentile(values, 0.95) == 19.0
    assert percentile(values, 0.5) == 10.0
    assert percentile([5.0], 0.95) == 5.0


def test_summarize_and_report_mark_slow_or_failed_api() -> None:
    fast = summarize("5-2 최근 예측", [10.0, 20.0, 30.0], errors=0)
    slow = Result("3-1 재설문 저장(+예측)", 3, 2900.0, 3100.0, 3200.0, 0)
    failed = summarize("7-3 요약 카드", [10.0], errors=1)

    table = report([fast, slow, failed])

    assert fast.p50_ms == 20.0 and fast.max_ms == 30.0
    assert "| 5-2 최근 예측 | 3 | 20 | 30 | 30 | 0 | ✅ |" in table
    assert "| 3-1 재설문 저장(+예측) | 3 | 2900 | 3100 | 3200 | 0 | ❌ |" in table
    assert "| 7-3 요약 카드 | 1 | 10 | 10 | 10 | 1 | ❌ |" in table
