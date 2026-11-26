# 예측 파이프라인 흐름도 (서빙)

> 작성 최현영 · 11/25 멘토링 후속 (성은·현영). 학습 흐름은 [ml/README.md](../ml/README.md) "학습" 참고, 이 문서는 **사용자 입력이 화면까지 가는 길**만 다룸.
> 규칙의 기준은 [api.md](api.md) 5장. 둘이 다르면 api.md를 따르고 이 문서를 고침.

## 한눈에 보기
```mermaid
flowchart LR
    subgraph G1["입력"]
        A["S-06 설문 21문항<br/>3-1 POST health-profiles"]
        B["S-07 검진 수치<br/>4-1·4-4 checkup-records"]
        U["회원 정보<br/>성별·생년월일"]
    end

    subgraph G2["전처리"]
        V["답 검증<br/>resolve_answers<br/>건너뛰기 규칙·범위"]
        PL{"예측 대상 고르기<br/>plan_predictions"}
        F["입력 12개로 변환<br/>features.py<br/>BMI·흡연·음주·가족력"]
    end

    subgraph G3["모델"]
        M["로지스틱 JSON<br/>diabetes_risk:v1<br/>hypertension_risk:v1"]
        C["기준표 판정<br/>criteria.py<br/>검진 1년 이내만"]
    end

    subgraph G4["결과"]
        S["score 0~100<br/>확률×100 반올림"]
        L["위험 단계<br/>30 미만 LOW · 60 이상 HIGH"]
        FA["요인 상위 3개 (조회 때 계산)<br/>7문항 · 가감 나이(+5살) · 0살 제외"]
        HA["건강 나이 (조회 때 계산)<br/>실제 나이 + 7문항 가감(±15)<br/>10살 단위"]
        DB[("risk_predictions<br/>MODEL · CHECKUP_CRITERIA 행")]
    end

    subgraph G5["화면"]
        S09["S-09 위험도 결과<br/>5-2 latest · 5-3 상세"]
        S10["S-10 습관 시뮬레이션<br/>5-4 저장 안 함"]
        D["대시보드<br/>7-1 추이 · 7-3 요약"]
    end

    A --> V
    U --> V
    V --> PL
    PL -- "진단 예" --> MG["관리 중 카드"]
    PL -- "임신 · 30~69세 밖" --> SK["일반 안내<br/>skipped_reason"]
    PL -- "예측 대상" --> F
    F --> M
    B --> C
    M --> S --> L
    L --> DB
    C --> DB
    MG --> S09
    SK --> S09
    DB --> S09
    DB -- "input_snapshot" --> HA --> S09
    DB -- "input_snapshot" --> FA --> S09
    DB --> D
    F -. "바뀐 입력으로 다시 계산" .-> S10
```

## 단계별 규칙 (요약)
| 단계 | 하는 일 | 코드 | 규칙 근거 |
|---|---|---|---|
| 입력 | 설문 저장 시 바로 예측, 최근 검진이 바뀌면(수정·삭제) 다시 예측 | `services/health_profiles.py`, `services/checkup_records.py` | api.md 3-1, 4장 |
| 검증 | 건너뛴 문항·범위 오류는 400 + `field` | `services/survey/validation.py` | api.md 3-1 |
| 대상 고르기 | 진단 "예" → 관리 중, 임신·나이 범위 밖 → 예측 안 함 | `services/prediction/plan.py` | api.md 5-0 |
| 전처리 | 설문 코드 → 모델 입력 12개 (학습과 같은 함수) | `services/prediction/features.py` | survey-mapping.md |
| 모델 | 계수·평균이 든 JSON, `model_version`·`mlflow_run_id` 같이 저장 | `services/prediction/model.py` | ml/README.md |
| 위험 단계 | 반올림한 score 기준 30/60 | `model.py` `to_level` | api.md 5-0 |
| 요인 | 조회 때 7문항 가감 나이(같은 성별 평균 기준), 0살 빼고 큰 순 3개 | `model.py` `factors` | api.md 5-0·5-3 |
| 기준표 | 검진 수치가 있으면 같은 질환에 별도 행, 1년 지나면 숨김 | `services/prediction/criteria.py`, `views.py` | api.md 5-1·5-2 |
| 화면 | "위험도 참고값", "의료 진단이 아니며 전문가 상담 필요" 안내 | 프론트 S-09·S-10 | CLAUDE.md 5장 |

## 건강 나이 (11/25 재결정)
- 곡선 방식(#102·#110) → **자가검진 7문항 + 산식**: 실제 나이 + clamp(Σ 계수 × (내 값 − 같은 성별 평균) ÷ 나이 계수, ±15) → 10살 단위. 자세한 규칙은 api.md 5-2 `health_age`
- `risk_predictions`에 저장하지 않고 5-2·5-3 조회 때 행의 `input_snapshot`으로 계산 (모델 JSON이 바뀌면 `model_version`이 같을 때만)
- 새로 학습하지 않아서 과적합 걱정이 없고, 항목별로 "+5살"처럼 설명할 수 있음 (멘토 의견: 모델링 대신 산식 + 자가검진)
