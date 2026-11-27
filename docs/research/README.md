# 연구 안내

이 문서는 연구를 찾아보기 위한 안내입니다. 개별 실험의 설계, 수치, 주장, 제외 기준은 연결된 원본 문서가 기준이며, 기존 기록을 다시 정의하지 않습니다.

## 1. 환경 기반 정보 전달 · EXP-STIG

질문은 에이전트가 상호작용 이후에도 남는 환경 정보를 쓰고, 그 정보가 자신이나 다른 에이전트의 과제 해결로 이어지는지입니다. 실험은 행동 인터페이스, 정보 보존의 필요성, 에이전트 간 의존성, TRACE/REUSE 읽기 경로를 순차적으로 바꿉니다.

**먼저 읽기:** [EXP-STIG-001–006 통합 기록](world/EXP-STIG-INTEGRATION.md)

| 실험 | 설계 또는 변경점 | 결과 |
|---|---|---|
| 001 | [메시지·지속 흔적·상태 변경 조건과 인터페이스](world/EXP-STIG-001.md) | [결과 및 측정 제약](world/EXP-STIG-001-results.md) |
| 002 | 정보 보존을 과제 수행에 연결하는 조건 | [설계 설명과 pilot 결과](world/EXP-STIG-002-results.md) |
| 003 | [정보 보존이 필요한 제출 과제](world/EXP-STIG-003.md) | [결과](world/EXP-STIG-003-results.md) |
| 004 | [다른 에이전트만 필요한 정보를 볼 수 있는 조건](world/EXP-STIG-004.md) | [결과](world/EXP-STIG-004-results.md) |
| 005 | [세 모델 계열을 포함한 집단](world/EXP-STIG-005.md) | [결과](world/EXP-STIG-005-results.md) |
| 006 | [REUSE가 필요한 흔적 읽기 경로](world/EXP-STIG-006.md) | [결과](world/EXP-STIG-006-results.md) |

해석할 때는 모델 계열·규모, decoding 조건, 짧은 tick 범위, 기회 수를 함께 봐야 합니다. TRACE 쓰기와 REUSE 선택, world-state COMMIT은 서로 다른 경로입니다. 한 경로의 과제 완료를 다른 경로의 성공으로 집계하지 않습니다.

실험 코드는 `src/alifelm/experiments/`, 명세는 `specs/experiments/`, 실행 도구는 `tools/exp_stig_*`에 있습니다. 이 경로 목록은 읽기 안내이며 전체 실험을 실행하는 명령이 아닙니다.

## 2. 모델 적응과 행동 선택 · Foundation / P1 / P2

인터페이스와 관측 정보의 grounding을 개선하는 학습이 이후의 행동 선택에 어떤 영향을 주는지 조사합니다.

| 읽기 순서 | 자료 | 구분 |
|---|---|---|
| 1 | [Foundation tuning study](foundation/ALIFELM_FOUNDATION_TUNING_STUDY_V1.md), [후속 경계 수정](foundation/ALIFELM_FOUNDATION_TUNING_STUDY_V1_AMENDMENT_01.md) | 연구 질문·학습 경계·가설 |
| 2 | [P1 행동 선택 결과](world/WORLD_P1_CONTEXT_SENSITIVE_POLICY_RESULTS_V1.md) | 결과 기록 |
| 3 | [P2 분석 정리](world/WORLD_P2_MECHANISTIC_TRACK_CLOSURE_V1.md) | 개입 실험의 연결과 해석 한계 |
| 4 | [P2-D4 결과](world/WORLD_P2_D4_KV_COMPONENT_DECOMPOSITION_RESULT_V1.md) | KV component 개입 결과 |
| 5 | [F0 Stage-0 복구된 평가 기록](../../specs/experiments/F0-foundation-stage0-result-v1.yaml) | 실행 provenance와 평가 기록 |
| 6 | [F0 A/B 실행 명세](../../specs/experiments/F0-foundation-ab-execution-v1.yaml) | `PENDING_RESOURCE_GATE`; 완료된 비교 결과가 아님 |

평가 정확도, 행동 admission, 개입에 따른 selector 변화는 서로 다른 측정입니다. 초기 adapter 비교의 단일 실행 결과로 안정적인 우열을 주장하지 않습니다. P2는 제한된 경로의 인과적 영향을 조사하며 모델 전체의 메커니즘 설명을 완성한 것으로 취급하지 않습니다.

## 3. 실험 플랫폼과 재현성 · EXP-000

- [EXP-000 완료 범위](world/WORLD_EXP000_CLOSURE_V1.md): 실제 모델 기반 다중 에이전트 실행과 허용된 주장 범위.
- [Live grounding pilot 결과](world/WORLD_EXP000_LIVE_GROUNDING_PILOT_RESULT_V1.md): 실험 실행의 세부 기록.
- [Soak 결과](world/WORLD_EXP000_SOAK_RESULT_V1.md): 결정적 정책 런타임을 사용한 restart·fault·replay 검증. 모델 행동에 대한 증거와 구분합니다.
- [Observatory 안내](../observatory/README.md): 원본 증거 아카이브를 읽는 로컬 관측 도구.
- [Architecture Index](../../architecture/INDEX.md): 상태 변경, 시간, 가시성, 증거 보관 규칙의 문서 위치.

## 자료를 검토하는 방법

1. 실험 명세와 변경 이력을 확인합니다.
2. 결과 문서에서 사용 모델, 실행 조건, 제외·검열, 지원되는 주장을 확인합니다.
3. 연결된 코드·테스트·manifest를 확인합니다.
4. 원시 증거가 실제로 제공되는지 [재현 안내](../REPRODUCIBILITY.md)에서 구분합니다.

문서에 기록된 `AUDIT PASS`는 해당 기록이 보고하는 상태입니다. 이 안내 문서를 작성하면서 모든 과거 실행의 원시 증거를 다시 감사한 것은 아닙니다. 새 확증 주장은 [연구 lineage 원칙](../../architecture/views/DF-260-research-lineage.md)에 따라 별도의 신선한 실행 증거가 필요합니다.
