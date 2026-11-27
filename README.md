# A-LifeLM · World Simulator

**LLM 에이전트가 환경에 정보를 남기고 활용하는 행동을 연구하는 개인 실험 프로젝트입니다.**

An independent research project on environmental information persistence and action selection in language-model agents.

## 어떤 목적으로 시작했나

에이전트에게 협력 방식이나 사회적 역할을 미리 부여하지 않고, 환경의 규칙과 정보 접근 조건에 따라 어떤 상호작용이 나타나는지 알아보기 위해 시작했습니다. 핵심 질문은 **“한 에이전트가 환경에 남긴 정보가 다른 에이전트의 과제 해결에 쓰일 수 있는가?”**입니다.

이를 확인하기 위해 결정적 시뮬레이션 커널, 모델 행동 인터페이스, 실험 프로토콜, 실행 증거 보관·감사 도구를 구현했습니다. 모델의 출력과 실제로 성립한 행동을 구분하고, 중단 후에도 실행 상태를 복원할 수 있도록 설계했습니다.

## 무엇을 했고, 어떻게 됐나

| 연구 | 진행한 내용 | 현재까지 기록된 결과 |
|---|---|---|
| 실험 플랫폼 · EXP-000 | 통신·출생·죽음이 있는 실제 모델 기반 다중 에이전트 실행과 증거 보관 | 최소 실행 경로를 구현·기록했고, 별도의 결정적 정책 런타임으로 restart·fault recovery·replay의 일관성을 검증 |
| 환경 기반 정보 전달 · EXP-STIG-001–006 | 정보 보존의 필요성, 에이전트 간 의존성, 모델 집단, TRACE/REUSE 조건을 단계적으로 변경 | 제한된 조건에서 OLMo가 필요한 정보를 환경 상태에 기록하고 SmolLM3가 이를 답에 연결해 과제를 완료한 사례 관측 |
| 실패 경로 분석 | 지속 흔적 쓰기와 내부화 경로를 분리해 관찰 | TRACE는 거의 선택되지 않았고 REUSE는 관측되지 않음. 환경 상태 기록의 성공과 별도로 해석 |
| 모델 적응 · Foundation / P1 / P2 | Adapter와 WORLD-prefill의 영향, KV cache 개입 분석 | Selector에 대한 인과적 영향을 일부 위치까지 좁힘. 후속 F0 A/B 학습 비교는 자원 조건 충족을 기다리는 계획 |

모델 간 역할 구분은 실험에서 관측한 결과이며 사전에 지정한 역할이 아닙니다. 현재 성과는 **실험 플랫폼과 한정된 조건에서의 초기 관측 결과**입니다. 작은 모델 집단과 짧은 실험에서 나온 결과이므로 일반적 협력 능력이나 진화·문화의 출현까지 입증한 것은 아닙니다.

## 상세 자료와 코드

최신 실험 코드와 정리한 문서는 **[`docs/research-portfolio` 연구 브랜치](https://github.com/gyeongbin-38/world-simulator/tree/docs/research-portfolio)**에 있습니다. 현재 기본 `master`의 구현은 연구 브랜치보다 이전 상태이며, 이 첫 화면은 연구 전체를 안내합니다.

- [연구 개요와 실행 안내](https://github.com/gyeongbin-38/world-simulator/blob/docs/research-portfolio/README.md)
- [실험별 설계·결과 찾아보기](https://github.com/gyeongbin-38/world-simulator/blob/docs/research-portfolio/docs/research/README.md)
- [EXP-STIG 통합 결과와 해석 한계](https://github.com/gyeongbin-38/world-simulator/blob/docs/research-portfolio/docs/research/world/EXP-STIG-INTEGRATION.md)
- [EXP-000 구현·실행 범위](https://github.com/gyeongbin-38/world-simulator/blob/docs/research-portfolio/docs/research/world/WORLD_EXP000_CLOSURE_V1.md)
- [P2 행동 메커니즘 분석 정리](https://github.com/gyeongbin-38/world-simulator/blob/docs/research-portfolio/docs/research/world/WORLD_P2_MECHANISTIC_TRACK_CLOSURE_V1.md)
- [재현 방법과 원시 증거 가용성](https://github.com/gyeongbin-38/world-simulator/blob/docs/research-portfolio/docs/REPRODUCIBILITY.md)

연구 브랜치의 GPU 없는 시작 경로는 문서 검사와 계약·커널·복원 테스트 53개를 통과했습니다. 원시 실험 증거는 별도 보관 중이므로 저장소 복제만으로 모든 과거 모델 결과를 재감사할 수는 없습니다. 다음 과제는 핵심 결과의 반복 검증과 공개 증거 패키지 정리입니다.
