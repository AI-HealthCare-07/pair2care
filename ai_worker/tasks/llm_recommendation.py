"""Pair2Care LLM 추천 핵심: 검증된 근거 후보 중 한 가지를 Claude가 선택한다.

의료 문구를 LLM이 자유 작성하지 않도록 공식 출처에 묶인 action만 반환한다.
개인식별정보는 호출 전에 제거하고, 근거가 없거나 프로필이 없으면 추천을 만들지 않는다.
"""

import asyncio
import json
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")
PROMPT_VERSION = "llm_verified_actions_v2"
NO_EVIDENCE = "지금은 근거가 충분하지 않아 추천하기 어려워요."
GUIDES_PATH = Path(__file__).resolve().parent.parent / "resources" / "health_guides.json"
# 동시 Claude 요청 상한 (프로세스별); 워커의 3회 재시도는 별도 처리한다.
_SEMAPHORE = asyncio.Semaphore(3)
_BOOLEAN_FACTS = {"is_hypertension_diagnosed", "is_diabetes_diagnosed", "is_drink", "is_broth_dish"}
_NUMERIC_FACTS = {"sodium_mg", "sugar_g", "carbs_g", "portion"}
SYSTEM_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "recommendation.txt"


class ClaudeCallError(RuntimeError):
    """전송을 시도한 호출의 오류. 설정 오류와 구분해 사용량을 기록한다."""


@dataclass(frozen=True)
class Evidence:
    id: str
    title: str
    url: str
    topics: tuple[str, ...]
    signals: tuple[str, ...]
    summary: str
    action: str


@dataclass(frozen=True)
class RecommendationResult:
    content: str
    sources: list[dict[str, Any]]
    model: str | None
    prompt_version: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    # 실제 API 호출이 없었다면 False. llm_usage_logs에는 호출이 있을 때만 기록한다.
    called_model: bool = False


class Selector(Protocol):
    async def choose(self, prompt: str, allowed_ids: list[str]) -> tuple[str, dict[str, int]]: ...


def clean_facts(raw: dict[str, Any]) -> dict[str, int | float | bool]:
    """승인된 숫자와 불리언만 허용하며 자유 입력 텍스트는 전송하지 않는다."""
    safe: dict[str, int | float | bool] = {}
    for key, value in raw.items():
        if key in _BOOLEAN_FACTS and type(value) in (bool, int) and value in (0, 1):
            safe[key] = bool(value)
        elif key in _NUMERIC_FACTS and type(value) in (int, float, Decimal):
            if (type(value) is not Decimal or value.is_finite()) and 0 <= value <= 100_000:
                safe[key] = float(value)
    return safe


def load_guides(path: Path = GUIDES_PATH) -> list[Evidence]:
    items = json.loads(path.read_text(encoding="utf-8"))
    return [Evidence(**{**item, "topics": tuple(item["topics"]), "signals": tuple(item["signals"])}) for item in items]


def retrieve_guides(kind: str, facts: dict[str, Any], guides: list[Evidence], limit: int = 5) -> list[Evidence]:
    """추천 유형과 양성 신호가 일치하는 근거만 순위화한다."""
    if kind not in {"DAILY_ACTION", "MEAL_ALTERNATIVE"}:
        raise ValueError("지원하지 않는 추천 종류")
    found: list[tuple[int, Evidence]] = []
    for guide in guides:
        if kind not in guide.topics:
            continue
        if kind == "MEAL_ALTERNATIVE":
            if guide.id == "htn_less_salt" and not facts.get("is_broth_dish"):
                continue
            if guide.id == "dm_reduce_added_sugar" and not facts.get("is_drink"):
                continue
            if guide.id == "dm_more_fiber" and facts.get("is_drink"):
                continue
        score = sum(bool(facts.get(signal)) for signal in guide.signals)
        if score:
            found.append((score, guide))
    return [guide for _, guide in sorted(found, key=lambda item: (-item[0], item[1].id))[:limit]]


def build_prompt(kind: str, facts: dict[str, Any], candidates: list[Evidence]) -> str:
    # 진단 여부는 서버에서 근거 검색에만 사용한다.
    meal_facts = {key: value for key, value in facts.items() if key in _NUMERIC_FACTS}
    return json.dumps(
        {
            "kind": kind,
            "meal_facts": meal_facts,
            "candidates": [{"id": guide.id, "summary": guide.summary, "action": guide.action} for guide in candidates],
        },
        ensure_ascii=False,
    )


class AnthropicSelector:
    """SDK는 호출 시에만 가져온다. 테스트에는 Selector 스텁을 넣을 수 있다."""

    async def choose(self, prompt: str, allowed_ids: list[str]) -> tuple[str, dict[str, int]]:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY가 설정되지 않았어")
        from anthropic import AsyncAnthropic  # langchain-anthropic 설치 의존성

        try:
            async with asyncio.timeout(60), _SEMAPHORE, AsyncAnthropic(timeout=40.0, max_retries=0) as client:
                message = await client.messages.create(
                    model=MODEL,
                    max_tokens=128,
                    temperature=0,
                    system=[
                        {
                            "type": "text",
                            "text": SYSTEM_PROMPT.read_text(encoding="utf-8"),
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[{"role": "user", "content": prompt}],
                )
            content = "".join(x.text for x in message.content if x.type == "text").strip()
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
            selected = json.loads(content)["selected_id"]
            if not isinstance(selected, str) or selected not in allowed_ids:
                raise ValueError("모델이 허용되지 않은 근거 ID를 선택함")
        except Exception as exc:
            raise ClaudeCallError("Claude 추천 선택 실패") from exc
        usage = message.usage
        return selected, {
            "input_tokens": usage.input_tokens or 0,
            "output_tokens": usage.output_tokens or 0,
            "cache_creation_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
            "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
        }


async def generate_recommendation(
    kind: str,
    facts: dict[str, Any],
    *,
    selector: Selector | None = None,
    guides: list[Evidence] | None = None,
) -> RecommendationResult:
    sanitized = clean_facts(facts)
    candidates = retrieve_guides(kind, sanitized, guides if guides is not None else load_guides())
    if not sanitized or not candidates:
        return RecommendationResult(NO_EVIDENCE, [], None, PROMPT_VERSION)
    chooser = selector or AnthropicSelector()
    chosen_id, usage = await chooser.choose(build_prompt(kind, sanitized, candidates), [g.id for g in candidates])
    if chosen_id not in {g.id for g in candidates}:
        raise ValueError("허용되지 않은 근거 ID")
    guide = next(g for g in candidates if g.id == chosen_id)
    # 출처 번호와 추천 문구는 서버가 확정: 잘못된 URL이나 의료 문구 생성 차단.
    return RecommendationResult(
        content=f"{guide.action} [1]",
        sources=[{"number": 1, "title": guide.title, "url": guide.url}],
        model=MODEL,
        prompt_version=PROMPT_VERSION,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        cache_creation_tokens=usage.get("cache_creation_tokens", 0),
        cache_read_tokens=usage.get("cache_read_tokens", 0),
        called_model=True,
    )
