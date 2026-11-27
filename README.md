# A-LifeLM · World Simulator

**LLM 에이전트의 환경 기반 정보 전달, 행동 선택, 재현 가능한 실험을 연구하는 개인 연구 프로젝트입니다.**

An independent research project on environmental information persistence, action selection, and reproducible experiments with language-model agents.

## 왜 시작했나

LLM 에이전트에게 협력 방식이나 사회적 역할을 미리 부여하지 않고, 환경의 규칙과 정보 접근 조건을 바꿨을 때 어떤 상호작용이 나타나는지 알아보기 위해 시작했습니다. 특히 **에이전트가 환경에 정보를 남기고, 그 정보가 다른 에이전트의 과제 해결에 쓰일 수 있는가**를 실험으로 확인하고자 했습니다.

이를 관찰하려면 모델이 출력한 제안과 실제로 성립한 행동을 구분하고, 실행을 중단해도 같은 상태와 증거를 복원할 수 있어야 했습니다. 그래서 결정적 시뮬레이션 커널, 실험 인터페이스, 증거 보관·감사 도구를 함께 구현했습니다.

## 무엇을 했고, 어떻게 됐나

- **실험 기반을 만들었습니다.** 통신·출생·죽음이 포함된 실제 모델 기반 다중 에이전트 실행을 기록했고, 별도의 결정적 정책 런타임으로 재시작·오류 복구·replay의 일관성을 검증했습니다. [EXP-000 기록](docs/research/world/WORLD_EXP000_CLOSURE_V1.md) · [Soak 검증](docs/research/world/WORLD_EXP000_SOAK_RESULT_V1.md)
- **정보 보존과 에이전트 간 의존성을 단계적으로 실험했습니다.** EXP-STIG-001–006에서는 제한된 조건에서 OLMo가 다른 에이전트에게 필요한 정보를 환경 상태에 기록하고, SmolLM3가 이를 답에 연결해 과제를 완료한 사례를 관측했습니다. 이 역할 구분은 관측 결과이며, 사전에 부여한 역할이 아닙니다. [통합 결과](docs/research/world/EXP-STIG-INTEGRATION.md)
- **성공하지 않은 경로도 확인했습니다.** 별도 흔적을 남기는 TRACE는 거의 선택되지 않았고, 흔적을 내부화하는 REUSE는 관측되지 않았습니다. 환경 상태 기록을 통한 성공을 TRACE/REUSE 경로의 성공으로 해석하지 않습니다. [EXP-STIG-006 결과](docs/research/world/EXP-STIG-006-results.md)
- **모델 적응과 행동 선택의 관계를 조사했습니다.** Foundation adapter와 WORLD-prefill의 영향을 비교하고 KV cache 개입으로 selector에 대한 인과적 영향을 일부 위치까지 좁혔습니다. 후속 F0 A/B 학습 비교는 자원 조건 충족을 기다리는 계획입니다. [P2 정리](docs/research/world/WORLD_P2_MECHANISTIC_TRACK_CLOSURE_V1.md) · [F0 실행 상태](specs/experiments/F0-foundation-ab-execution-v1.yaml)

현재 성과는 **실험 플랫폼 구현과 한정된 조건에서의 초기 관측 결과**입니다. 작은 모델 집단과 짧은 실험에서 나온 결과이며, 일반적인 협력 능력이나 진화·문화의 출현을 입증하지는 않습니다. 다음 과제는 핵심 결과의 반복 검증과 외부에서 확인 가능한 증거 패키지 정리입니다.

A-LifeLM은 에이전트의 제안, 검증된 행동, 실제 상태 변화를 구분해 기록하는 실험 플랫폼입니다. 이 저장소에는 플랫폼 구현, 실험 프로토콜, 테스트, 결과 기록이 함께 있습니다. 연구별 원시 증거는 별도로 보관되므로, 저장소를 복제하는 것만으로 모든 과거 결과를 재감사할 수 있는 것은 아닙니다.

## 연구 살펴보기

| 연구 축 | 핵심 질문 | 대표 기록 |
|---|---|---|
| 환경 기반 정보 전달 | 에이전트는 환경에 정보를 남기고 다른 에이전트의 과제 해결에 기여하는가? | [EXP-STIG-001–006 통합 기록](docs/research/world/EXP-STIG-INTEGRATION.md) |
| 모델 적응과 행동 선택 | 인터페이스 학습과 adapter가 행동 선택에 어떤 영향을 주는가? | [P2 메커니즘 분석 정리](docs/research/world/WORLD_P2_MECHANISTIC_TRACK_CLOSURE_V1.md) |
| 실험 플랫폼과 재현성 | 통신·출생·죽음이 있는 실행을 중단 후에도 동일하게 복원할 수 있는가? | [EXP-000 완료 범위](docs/research/world/WORLD_EXP000_CLOSURE_V1.md), [Soak 결과](docs/research/world/WORLD_EXP000_SOAK_RESULT_V1.md) |

실험별 설계·결과·코드의 연결은 **[연구 안내](docs/research/README.md)**에서 확인할 수 있습니다.

## 현재까지 기록된 범위

- **실험 플랫폼:** 결정적 tick 처리, 검증을 거친 상태 변경, SQLite/CAS 기반 증거 보관, restart/replay 경로가 구현돼 있습니다. EXP-000 기록에는 실제 모델을 사용한 다중 에이전트 실행이 포함됩니다.
- **환경 기반 정보 전달:** EXP-STIG 기록은 제한된 모델 집단과 짧은 실험에서 환경에 남긴 정보와 과제 완료의 연결을 보고합니다. TRACE/REUSE 경로의 거의 부재와 모델별 차이도 결과에 포함됩니다.
- **모델 적응:** Foundation 평가와 P1/P2 개입 기록이 있습니다. 후속 F0 A/B 학습 실행은 [실행 명세](specs/experiments/F0-foundation-ab-execution-v1.yaml)에서 `PENDING_RESOURCE_GATE`로 남아 있습니다.
- **관측 도구:** [Observatory](docs/observatory/README.md)는 보존된 실행 증거를 읽는 로컬 뷰어입니다. 사용하려면 해당 증거 아카이브가 필요합니다.

위 내용은 연결된 연구 기록의 요약입니다. 일반적 사회 지능, 진화적 적응, 신경 유전, 장기적 집단 안정성을 입증한 것으로 해석하지 않습니다. 실험 조건과 주장 한계는 각 결과 문서가 기준입니다.

## 시작하기 · GPU 없이 확인

Python 3.12+와 `uv`를 사용합니다. 저장소 루트에서 실행하세요.

```sh
uv sync --locked
uv run --locked python tools/docs_lint.py
uv run --locked python -m pytest tests/contracts tests/kernel tests/live/test_exp000_soak.py -q
```

이 경로는 문서 연결과 결정적 실행·복원 동작을 확인합니다. 실제 LLM 추론이나 과거 행동 실험의 재현을 수행하지 않습니다.

실행 환경, 새 Soak 실행, 원시 증거의 가용성은 **[재현 안내](docs/REPRODUCIBILITY.md)**를 참고하세요.

## 저장소 구조

| 경로 | 내용 |
|---|---|
| `src/alifelm/` | 커널, 모델 인터페이스, 증거 보관, 실험 및 관측 구현 |
| `tests/` | 계약, 커널, 모델, 복원, 실험 테스트 |
| `tools/` | 실험 실행·평가·감사 도구 |
| `specs/experiments/` | 버전이 고정된 실험 명세와 실행 상태 |
| `docs/research/` | 연구 설계, 결과, 감사 및 통합 기록 |
| `architecture/` | 시스템 규칙과 경계별 설계 문서 |
| `observatory/` | 읽기 전용 연구 뷰어 프런트엔드 |

## 설계와 기여

구조를 살펴볼 때는 [DESIGN.md](DESIGN.md), 정확한 규칙은 [Architecture Index](architecture/INDEX.md)에서 시작하세요. 코드 변경 시에는 [AGENTS.md](AGENTS.md)와 [문서 정책](docs/DOCS_POLICY.md)을 따릅니다. 연구 주장과 증거의 연결 원칙은 [DF-260](architecture/views/DF-260-research-lineage.md)에 있습니다.

외부 모델·라이브러리의 출처, 코드와 연구 자료의 이용 조건, AI 보조 작업의 기여 표시는 [공개 준비 현황](docs/PUBLICATION_STATUS.md)에 정리했습니다. 현재 연구 기록의 버전별 상태와 제한을 유지하면서 공개용 자료를 정리하고 있습니다.
