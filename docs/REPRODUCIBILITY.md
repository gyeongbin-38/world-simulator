# 재현 안내

## 무엇을 확인할 수 있나

| 확인 대상 | 필요한 자료·환경 | 이 저장소의 역할 |
|---|---|---|
| 문서 연결·구조 | Python 3.12+ | 문서 lint 제공 |
| 결정적 커널과 복원 동작 | Python 개발 환경 | 코드·계약 테스트·Soak 도구 제공; 모델 다운로드 불필요 |
| 과거 LLM 실험의 증거 재감사 | 해당 run의 SQLite, CAS, manifest 등 | 결과 기록과 도구 제공; 원시 증거는 별도 보관 |
| 실제 모델 실험 재실행 | 실험별 모델 revision, backend, 하드웨어, 명세 | 실험 코드·명세 제공; 모든 실험을 한 명령으로 실행하는 배포판은 아님 |
| Observatory 관측 | 원본 증거 아카이브와 Node 환경 | 로컬 뷰어 제공; 기본 clone만으로 과거 실행을 표시할 수 없음 |

문서의 과거 수치를 읽는 것, 보존된 실행을 replay하는 것, 모델을 새로 호출해 실험하는 것은 각각 다른 검증입니다.

## 개발 환경

Python 3.12+와 `uv`가 설치된 환경에서 저장소 루트로 이동합니다.

```sh
uv sync --locked
uv run --locked python tools/docs_lint.py
uv run --locked python -m pytest tests/contracts tests/kernel tests/live/test_exp000_soak.py -q
```

`uv.lock`은 기본 개발 환경의 dependency 해석을 고정합니다. 위 명령은 GPU 모델 패키지나 모델 가중치를 설치하지 않습니다. `model`과 `model-diagnostics` extras, CUDA 환경, GGUF backend는 실험별로 별도 설정이 필요합니다. 예를 들어 [P0 환경 기록](research/world/WORLD_P0_RUNTIME_ENVIRONMENT_V1.md)은 해당 실험의 환경 기록이며, 모든 후속 실험에 공통인 실행 환경은 아닙니다.

## 새 Soak 실행과 감사

아래 명령은 실제 LLM 대신 결정적 `SoakPolicyRuntime`으로 실행합니다. 새 실행 디렉터리에 증거를 만들며, 과거 실험 결과를 덮어쓰지 않습니다.

```sh
uv run --locked python tools/world_exp000_soak.py --execute --output-root runtime-data/portfolio-soak
uv run --locked python tools/world_exp000_soak.py --audit --output-root runtime-data/portfolio-soak
```

실행 도구는 write-once 출력을 사용하므로 재실행할 때는 새로운 `--output-root`를 지정하세요. 기본 horizon은 48 ticks입니다. population capacity에 따른 `CENSORED`는 명시적인 실험 종료이며, 그 자체가 인프라 감사 실패를 의미하지 않습니다. 결과 해석은 [Soak 결과 문서](research/world/WORLD_EXP000_SOAK_RESULT_V1.md)와 도구가 출력한 검증 항목을 기준으로 합니다.

`runtime-data/`는 `.gitignore`로 제외됩니다. 생성한 데이터는 로컬 확인용이며 자동으로 연구 결과나 공개 release가 되지 않습니다.

## 과거 증거의 가용성

기존 기록에는 `E:/WORLD/AI_CACHE/evidence/` 및 `E:/WORLD/RECOVERY/` 같은 실행 당시의 로컬 경로가 있습니다. 이 경로는 공개 다운로드 주소가 아닙니다. 원래 경로와 hash는 provenance를 보존하기 위해 기존 결과 문서에 그대로 남깁니다.

현재 이 안내는 공개 증거 패키지의 배포 주소를 제공하지 않습니다. 원시 증거가 없는 독자는 구현과 결과 기록을 검토할 수 있지만, 과거 수치와 원시 모델 출력까지 독립적으로 재검산할 수는 없습니다. hidden/reserved 평가 자료는 명세의 격리 조건을 확인하기 전에는 공개 묶음에 넣지 않습니다.

증거 패키지를 제공할 때는 해당 run ID, source commit, 실행 환경, 명세·평가기 버전, 파일별 hash, 포함·제외 항목, 감사 명령을 함께 기록해야 합니다. 근거 연결의 기준은 [DF-260](../architecture/views/DF-260-research-lineage.md)입니다.

## Observatory

원본 아카이브가 준비된 경우에만 [Observatory 실행 안내](observatory/README.md)를 따릅니다. 뷰어는 보존된 증거를 검증하고 읽는 도구이며, 새 실험 실행이나 원본 증거 수정을 위한 인터페이스가 아닙니다.
