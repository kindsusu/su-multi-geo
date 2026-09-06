# 변경 이력

형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/), 버전은 [유의적 버전](https://semver.org/lang/ko/)을 따른다.
날짜는 해당 작업이 커밋된 날이다.

## [Unreleased]

### 문서·저장소 탐색

- 한국어·영어 README를 설치·첫 실행·측정·한계 중심으로 정리.
- 문서 안내, 기여 방법, 버그 신고·PR 양식, 조사·실측 범위 추가.
- 신뢰성 검토 기록을 `docs/reviews/`로 옮기고 main 반영·원격 CI 결과 갱신.
- 파이프라인 도식과 명령 참조의 이전 설명을 현재 동작에 맞게 수정.
- GitHub Actions를 Node.js 24 기반 공식 버전으로 갱신해 Node.js 20 지원 종료 경고 제거.

### 신뢰성·실행 흐름 보강

- `seo_geo.py` 통합 CLI: 환경 확인, 진단+보고서, 기록 상태, 도구별 명령 전달.
- robots 경로·그룹·주석·와일드카드와 중복 X-Robots-Tag/UA 범위 처리 교정.
- sitemap seed 및 수집 한계 기록. 불완전한 수집·배포 검증은 종료 코드 2.
- 불완전 크롤로 교체용 사이트맵을 만들지 않으며, JSON-LD 파일명 충돌과 HTML 탈출 방지.
- 파일→URL manifest, 생성기 소유 파일 정리, 라이브 구조화 데이터·메타 초안 대조.
- 측정 v2: 오류·미측정 분리, 표면/모델/질의/표본 구성을 고정한 비교, 스냅샷 무결성 검증.
- FAQ·llms.txt·학습 봇 허용을 검색 인용의 필수 조건으로 판단하던 설명 교정.
- 보고서 검사 범위 표시, HTML escaping, 외부 글꼴 의존 제거, 관련 회귀/E2E 검사 추가.

### 호환성 주의

- 기존 측정 v1 파일은 읽는다. 새 로그·요약은 v2이며 기본 집계는 최신 측정일이다.
  과거 누적 집계는 `--cumulative`를 명시한다. 누적값은 배포 전후 회귀 판정에 사용하지 않는다.
- JSON-LD 적용 위치는 새 `jsonld/manifest.json`을 기준으로 확인한다.
- 종료 코드 0만 완료로 취급하는 자동화는 1(검증 실패), 2(미완료/입력 오류)를 구분해야 한다.

## [2.0.0] — 2026-09-03

절차서 한 벌이던 스킬에 **도구 여섯 개와 스키마 네 개**가 붙었다. 진단부터 재측정 일정까지가
파일로 남는다 — "고쳤다"를 말이 아니라 산출물로 증명한다. 전부 파이썬 3.10+ 표준 라이브러리만
쓰고 pip 의존은 0이다.

### 추가 — 도구 (M1~M5)

- **M1 `tools/crawl.py`** — 사이트 전수 진단. 자바스크립트 없이 받은 HTML만 보고,
  robots.txt의 Disallow를 지키며 BFS로 훑는다. → `out/<host>/audit.json`
- **M1 `tools/report.py`** — `audit.json` 한 개로 자립형 HTML 보고서 8페이지를 만든다.
  창작하지 않고, 판정할 수 없는 칸은 "미확인"으로 남긴다
- **M2 `tools/generate.py`** — `audit.json` + `site.json` → `sitemap.xml`·`robots.txt`·
  `llms.txt`·`jsonld/`·`meta-draft.csv` + `DEPLOY.md`. 기존 robots 원문을 보존하고,
  모르는 값은 지어내지 않고 `<<TODO: ...>>`로 남긴다
- **M3 `tools/verify.py`** — 배포 후 라이브를 다시 받아 항목별 ✅/❌. `deploy`(서빙 검증)와
  `diff`(전/후 진단 비교) 두 모드. fail이 하나라도 있으면 exit code 1
- **M4 `tools/measure.py`** — AI 인용 측정 루프. 수동 폼(CSV + 오프라인 HTML)이 기본 골격이고
  API 자동화는 선택이다. `init` → `form` → `import` → `report` (+ `auto`)
- **M5 `tools/drift.py`** — 불변 스냅샷 보관소와 드리프트 비교. 회귀 6종을 판정해
  하나라도 걸리면 exit code 1, 완료 조건인 `next_due`를 계산한다

### 추가 — 스키마 (계약)

| 스키마 | 만드는 도구 |
|---|---|
| `su-multi-geo/audit/1` | `crawl.py` |
| `su-multi-geo/verify/1` | `verify.py` |
| `su-multi-geo/queries/1` · `su-multi-geo/measure-row/1` · `su-multi-geo/measure/1` | `measure.py` |
| `su-multi-geo/history/1` · `su-multi-geo/drift/1` | `drift.py` |

### 추가 — 품질 체계 (M6)

- **E2E 통합 테스트** `tests/test_e2e.py` — `tests/fixtures/site/`의 결함 심은 8페이지 사이트를
  `http.server`로 127.0.0.1 임시 포트에 띄우고, crawl → report → generate → 배포 흉내 →
  verify → 재크롤 → measure → drift까지 **전부 실제 CLI로** 돈다. 외부 네트워크 없음
- **GitHub Actions CI** `.github/workflows/ci.yml` — ubuntu·windows·macos ×
  Python 3.10·3.12·3.13 매트릭스. 의존성 설치 단계가 없다는 것 자체가 "표준 라이브러리만"의 증명
- 단위 테스트 **217개** (crawl·report·generate·verify·measure·drift + E2E)
- `.editorconfig`, `CHANGELOG.md`(이 파일), `tools/README.md`의 흐름도와 스키마 버전 표

### 변경

- `lanes/aeo.md`(+ en 미러) — "추출되는 문장의 형태"에 **한글 기준 문단 길이 가이드** 추가
- `ops/intent.md` — 포맷 절에서 `aeo.md` 길이 가이드로 상호 참조
- `SKILL.md` — 맨 아래 "도구 요약" 절: 도구 여섯 개를 Phase에 매핑한 표
- `crawl.py` — 대상 호스트가 IP·localhost면 `www↔apex` 변형 접속을 시도하지 않는다
  (`hygiene.alt_host.result = "na"`). 출력 폴더 이름에서 `:` 등을 치환해 Windows에서도
  `127.0.0.1:8000` 같은 대상을 다룰 수 있다

## [1.x] — 2026-08-30 ~ 2026-08-31

절차서(`SKILL.md` + `lanes/` + `ops/` + `en/` 미러) 한 벌과 `tools/audit.sh`(홈 1페이지 빠른 진단).
