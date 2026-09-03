# tools/ — 진단 도구

전부 의존성 0이다. `audit.sh`는 bash + curl, 나머지는 파이썬 3.10+ 표준 라이브러리만 쓴다.

| 도구 | 무엇 | 입력 | 출력 |
|---|---|---|---|
| `audit.sh` | 홈 1페이지 빠른 진단 | 도메인 | 콘솔 |
| `crawl.py` | 사이트 전수 진단 | 도메인 | `out/<host>/audit.json` + 콘솔 |
| `report.py` | 진단 결과 → 보고서 | `audit.json` | `report.html` |
| `generate.py` | 진단 결과 → 배포 산출물 초안 | `audit.json` (+ `site.json`) | `out/<host>/deploy/` + `DEPLOY.md` |
| `verify.py` | 배포가 실제로 서빙되는지 / 전후 비교 | `audit.json` (+ `deploy/`) | `verify.json` + `VERIFY.md` |
| `measure.py` | AI 인용 측정 루프 | `audit.json` + `queries.json` | `log.jsonl` → `summary.json` + `MEASURE.md` |
| `test_audit.sh` | audit.sh 회귀 테스트 | — | PASS/FAIL |

흐름:

```
crawl.py → report.py(사람에게 보고) → generate.py(고칠 파일 초안)
        → [사람이 배포] → verify.py deploy(크롤러의 눈으로 증명)
        → (14일) crawl.py 재크롤 → verify.py diff(무엇이 해소됐나)

measure.py는 이 흐름과 나란히, 배포 전 기준선부터 돈다:
measure.py init → [사람이 질의 확정] → form → [사람이 측정] → import → report
                                                          ↑ (14일) 반복
```

## audit.sh — 빠른 1페이지 진단

```bash
bash tools/audit.sh example.com
```

홈 하나만 훑는다. 30초 안에 noindex 사고·robots 정책·사이트맵 유무를 본다.
"일단 상태부터 보자" 할 때 쓴다.

## crawl.py — 전수 진단

```bash
python tools/crawl.py example.com
python tools/crawl.py https://example.com --max-pages 500 --delay 1.0 --out reports/
```

| 옵션 | 기본값 | 뜻 |
|---|---|---|
| `--max-pages` | 300 | 크롤할 최대 페이지 수 |
| `--delay` | 0.5 | 요청 사이 대기(초). 남의 서버다, 줄이지 마라 |
| `--out` | `out` | 출력 루트. 실제 경로는 `<out>/<host>/audit.json` |

홈에서 시작해 같은 호스트의 내부 링크를 BFS로 따라간다. 쿼리스트링·프래그먼트는 떼고,
이미지·CSS·JS 같은 자산은 건너뛴다. **robots.txt의 Disallow는 크롤할 때 존중한다.**
User-Agent는 `su-multi-geo-audit/2.0`으로 밝히고 다닌다.

페이지마다 재는 것: 상태 코드·최종 URL·title·meta description·meta robots·
`X-Robots-Tag`·canonical·h1·JSON-LD 개수와 `@type`·본문 글자 수(바이트 아님)·
OG 태그·네이버 소유확인·`lang`·응답 시간.

사이트 수준으로 재는 것: robots.txt 원문과 UA 11종의 실효 정책, 사이트맵(선언·존재·URL 수·
크롤 결과와의 차집합), `llms.txt`, 404 프로브, 리다이렉트 홉, www↔apex 변형 접속.

중간에 실패하거나 Ctrl+C로 끊어도 **거기까지의 결과를 저장한다.**

### audit.json — 계약

`report.py`와 이후 도구가 이 스키마를 쓴다. 필드를 바꾸면 버전(`schema`)을 올린다.

```json
{"schema":"su-multi-geo/audit/1","generated_at":"ISO8601",
 "target":{"input":"...","base":"https://host","host":"host"},
 "site":{"robots":{"status":200,"present":true,"raw":"...","policies":{"GPTBot":"star-allow"},"sitemap_declared":[]},
         "sitemaps":[{"url":"...","status":200,"is_index":false,"url_count":0}],
         "sitemap_vs_crawl":{"only_in_sitemap":[],"only_in_crawl":[]},
         "llms":{"llms.txt":404,"llms-full.txt":404},
         "hygiene":{"probe_404":404,"redirect_hops":0,"home_response_ms":0,
                    "alt_host":{"host":"www.x","result":"ok|redirect|tls_fail|dns_fail|error",
                                "status":null,"location":null}}},
 "pages":[{"url":"...","status":200,"final_url":"...","title":null,"meta_description":null,
           "meta_robots":null,"x_robots_tag":null,"canonical":null,"h1":[],
           "jsonld_count":0,"jsonld_types":[],"text_chars":0,
           "og":{},"naver_site_verification":false,"lang":null,"response_ms":0,"error":null}],
 "stats":{"pages_crawled":0,"unique_titles":0,"unique_descriptions":0,
          "pages_with_jsonld":0,"pages_noindex":0},
 "findings":[{"lane":"SEO","severity":"critical|warn|info","code":"TITLE_DUPLICATE",
              "message":"...","urls":["..."],"data":{}}],
 "scorecard":{"SEO":{"status":"ok|warn|bad|na","evidence":["TITLE_DUPLICATE"]}}}
```

레인은 여섯이다: `SEO` `AEO` `GEO` `LLMO` `NEO` `reputation`.
`reputation`은 사이트 밖 표면이라 크롤로 잴 수 없다 — 항상 `na`로 두고 사람이 점검한다.

## report.py — 보고서 생성

```bash
python tools/report.py out/example.com/audit.json
python tools/report.py out/example.com/audit.json --lang en --out reports/en.html
```

`audit.json` 하나만 읽어 독립 HTML 한 장을 만든다. 외부 자원은 웹폰트뿐이고,
나머지는 파일 안에 다 들어 있다. 여덟 페이지 구성: 진단 요약 → 사이트 구성 → 레인별 상세 →
강점 → 인용 자산 → 권고 로드맵 → 측정 계획 → 용어 설명.

**이 도구는 아무것도 창작하지 않는다.** 수치·회사명·도메인은 전부 `audit.json`에서 오고,
데이터로 판정할 수 없는 칸은 추정하지 않고 "미확인"으로 남긴다.

- 템플릿: `templates/report.html` (구조·CSS·JS)
- 용어 사전: `templates/glossary.json` (`ko`/`en`) — 본문의 용어에 자동으로 툴팁이 붙는다
- 외부 입력(페이지 title·URL·findings 메시지)은 전부 HTML 이스케이프한다

## generate.py — 배포 산출물 초안

```bash
python tools/generate.py all out/example.com/audit.json --site out/example.com/site.json
python tools/generate.py robots out/example.com/audit.json
python tools/generate.py meta out/example.com/audit.json --out /tmp/draft
```

| 서브커맨드 | 입력 | 출력 |
|---|---|---|
| `sitemap` | 크롤한 페이지 | `sitemap.xml` (한도 초과 시 `sitemap_index.xml` + 분할) |
| `robots` | 기존 robots.txt 원문 + UA 실효 정책 | `robots.txt` (기존 보존 + AI 크롤러 명시 + `Sitemap:`) |
| `llms` | 섹션 대표 URL + `site.json` | `llms.txt` |
| `jsonld` | `site.json` + 크롤한 경로 구조 | `jsonld/*.json` + `jsonld/*.snippet.html` |
| `meta` | 페이지별 h1·title·설명 | `meta-draft.csv` / `meta-draft.json` (검토용) |
| `deploy` | 위 전부 | `DEPLOY.md` 배포 지시서 |
| `all` | — | 위 전부를 `out/<host>/deploy/`에 |

옵션: `--site <site.json>` (없으면 회사 사실 없이 만들 수 있는 것만), `--out <폴더>`
(기본 `audit.json` 옆의 `deploy/`).

### 무엇을 지어내지 않는가

이 도구는 **초안 생성기**다. 값의 출처는 둘뿐이다 — `audit.json`의 실측값과 `site.json`에
사람이 적어 준 사실. 그 밖의 칸은 `<<TODO: ...>>` 표식으로 남긴다.

- 사이트맵 `lastmod` — 실제 수정일을 모르므로 태그 자체를 넣지 않는다
- llms.txt의 한 줄 소개·페이지 설명·데이터 정책 — 전부 TODO
- Organization의 빈 필드 — TODO가 아니라 **아예 생략**한다 (LD에 빈 값을 넣지 않는다).
  `sameAs`는 `site.json`의 `same_as`에서만 온다
- FAQPage — `site.json`의 `faqs` 중 **크롤된 page_url**에 붙은, q·a가 모두 있는 것만
- Product `offers` — `price`와 `currency`가 둘 다 있을 때만. 가격은 절대 만들지 않는다
- description 초안 — 페이지에 이미 있는 문장(기존 meta description·og:description)만 후보로
  쓴다. 없으면 TODO. `audit.json`에는 본문 텍스트가 없으므로 첫 문장 추출은 사람 몫이다

BreadcrumbList만은 크롤한 URL 경로와 페이지 title에서 **실측 기반으로** 자동 생성한다.

### robots.txt를 다루는 규칙

- 기존 원문을 **그대로 보존**하고 그 뒤에 블록을 덧붙인다. 기존 `Disallow`는 지우지도
  완화하지도 않는다
- 이미 차단된 UA(`explicit-block`·`star-block`)는 허용으로 뒤집지 않는다 —
  `DEPLOY.md`에 "차단 유지 — 의도 확인 필요"로 적는다
- 이미 명시된 UA는 건드리지 않는다
- `User-agent: *`에 부분 제한이 걸린 사이트에서는 그 제한 규칙을 **글자 그대로 복사**해
  UA 그룹을 만든다 (현재 실효 정책과 동일 — 넓히지 않는다)
- 전/후 unified diff를 `DEPLOY.md`에 싣는다

### site.json — 사용자가 채우는 회사 사실

`templates/site.example.json`을 `out/<host>/site.json`으로 복사해 값을 바꾼다.
키: `name` `legal_name` `url` `logo` `description`(우산 메시지 한 문장) `same_as[]`
`contact{phone,email}` `address{street,locality,region,postal_code,country}`
`founding_year` `faqs[{q,a,page_url}]` `products[{page_url,name,offers{price,currency,unit}}]`.

**모르는 값은 빈 문자열로 두거나 키를 지운다.** 빈 값은 생략되거나 TODO로 남고,
지어낸 값은 인용 신뢰를 죽인다.

## verify.py — 배포 후 검증

```bash
python tools/verify.py deploy out/example.com/audit.json
python tools/verify.py deploy out/example.com/audit.json --deploy out/example.com/deploy \
                              --max-urls 1000 --delay 1.0 --out out/example.com/verify.json
python tools/verify.py diff out/example.com/audit.json out/after/example.com/audit.json
```

**"고쳤다"를 증명하는 도구다.** 패키지에 파일이 있다는 것은 근거가 아니다 —
라이브 사이트를 다시 받아 항목별로 ✅/❌를 낸다. `fail`이 하나라도 있으면 **exit code 1**
(CI·스크립트 연계용).

### `deploy` — 배포 패키지가 실제로 서빙되는가

| 체크 id | 무엇을 본다 |
|---|---|
| `noindex` | **최우선.** 배포로 noindex가 새로 생기지 않았는가 (meta + `X-Robots-Tag`) |
| `robots.status` | robots.txt 200 응답 |
| `robots.preserved` | 배포 전 원문 줄이 **한 줄도 빠짐없이** 남아 있는가 |
| `robots.policy` | 추가한 UA 블록이 실제로 서빙되는가 (UA 11종 실효 정책 재판정) |
| `robots.sitemap` | `Sitemap:` 선언 존재 |
| `sitemap.reachable` | 선언된 사이트맵 200 · XML 파싱 (인덱스면 하위까지) |
| `sitemap.locs` | `<loc>` **전수** 200 (동일 호스트만, `--max-urls` 상한) |
| `sitemap.noindex` | noindex 페이지가 사이트맵에 실렸는가 |
| `sitemap.canonical` | 사이트맵 URL과 canonical이 일치하는가 |
| `llms.status` / `llms.todo` | llms.txt 200 / `<<TODO` 잔존 → ❌ "미완성 배포" |
| `jsonld.present` / `jsonld.type` | 대상 페이지에 LD가 들어갔는가 · @type이 맞는가 |
| `jsonld.visible` | **LD 값이 가시 텍스트에 글자 그대로 있는가** — FAQ 문답, Organization name, Product name·가격. 없으면 ❌ "LD가 화면에 없는 말을 한다"(스팸 리스크) |
| `jsonld.org_id` | Organization `@id`가 전 페이지에서 하나인가 |
| `meta.applied` / `meta.duplicate` | meta 초안 반영 여부(바뀜/그대로) · 중복 title 잔존 |

가시 텍스트 비교는 태그를 걷어내고 **공백만 정규화**한 뒤 부분 문자열로 본다
(가격은 `89000` ↔ `89,000` 표기를 같게 본다).

### `diff` — 전/후 진단 비교

`after`는 사용자가 `crawl.py`를 다시 돌려 만든다. 네트워크를 쓰지 않는다.

| 체크 id | 무엇을 본다 |
|---|---|
| `diff.resolved` | 사라진 findings (code 기준) |
| `diff.new` | 새로 생긴 findings — critical이 섞이면 ❌ |
| `diff.persisting` | 그대로 남은 findings + 영향 URL 수 증감 |
| `diff.scorecard` | 레인별 전후 (`bad→warn` 등). 악화가 있으면 ❌ |
| `diff.stats` | 중복 title·JSON-LD 페이지·noindex 수 전후 |
| `diff.pages` | 사라진 URL(→404 확인 필요) · 새 URL |

### 안전선

- **대상 호스트 외에는 요청하지 않는다.** 리다이렉트 목적지가 밖으로 나가면 본문을 쓰지 않고
  실패로 본다 (SSRF 방지 — `crawl.py`의 사이트맵 후보 필터와 같은 규칙)
- 요청 간격 `--delay`(기본 0.5초)를 지킨다. 같은 URL은 한 번만 받는다
- 파서·robots 정책 판정·URL 정규화·noindex 판정은 전부 `crawl.py` 함수를 **임포트해 쓴다**
- 네트워크 함수는 주입 가능하다 (`verify_deploy(..., fetch=...)`) — 테스트는 가짜 응답으로 돈다

### verify.json — 계약

```json
{"schema":"su-multi-geo/verify/1","mode":"deploy|diff","generated_at":"ISO8601",
 "target":{"base":"https://host","host":"host","deploy":"out/host/deploy"},
 "checks":[{"id":"sitemap.locs","status":"pass|fail|warn|skip","message":"...","evidence":{}}],
 "summary":{"pass":0,"fail":0,"warn":0,"skip":0},"exit_code":0}
```

`VERIFY.md`는 같은 내용의 사람용 요약이다 — ❌를 먼저 싣고 항목마다 다음 조치를 한 줄 붙인다.

## measure.py — AI 인용 측정

```bash
python tools/measure.py init   out/example.com/audit.json
python tools/measure.py form   out/example.com/audit.json --engines chatgpt,google_aio --runs 5
python tools/measure.py import out/example.com/audit.json out/example.com/measure/form-2026-09-15-filled.csv
python tools/measure.py report out/example.com/audit.json --since 2026-09-01
python tools/measure.py auto   out/example.com/audit.json --engines chatgpt,claude --runs 5
```

**크롤로는 AI 인용을 잴 수 없다.** 엔진에 실제로 물어야 하고, 그 답은 매번 다르다 —
그래서 "떴다/안 떴다"가 아니라 **N회 중 몇 회**로 적는다 (`ops/measure.md` 2번).

| 서브커맨드 | 무엇 | 출력 |
|---|---|---|
| `init` | `measure/` 폴더 + 질의 세트 **빈칸** 생성 (이미 있으면 안 건드림) | `measure/queries.json` |
| `form` | 질의 × 엔진 × 회차 행이 미리 채워진 수동 입력 양식 | `form-<날짜>.csv` · `form-<날짜>.html` |
| `import` | 채운 CSV를 검증해 로그에 append (문제 행은 건너뛰고 사유 출력) | `measure/log.jsonl` |
| `report` | 로그 집계 — 엔진별 인용률·인용 URL 빈도·추이·재측정일 | `summary.json` + `MEASURE.md` |
| `auto` | **선택.** 환경변수에 키가 있을 때만 ChatGPT·Claude 자동 질의 | `log.jsonl`에 append |

옵션: `--engines`(쉼표 구분, 기본 `chatgpt,google_aio`) · `--runs`(기본 5) ·
`--date YYYY-MM-DD`(기본 오늘) · `--since`(report) · `--delay`·`--yes`(auto).

### 수동이 기본 골격이다

API 키가 하나도 없어도 측정 루프는 완전히 돈다. 자동화는 붙였다 뗐다 하는 플러그인이고,
**자동이든 수동이든 같은 `log.jsonl`에 같은 형식으로 쌓인다** (`mode` 칸으로만 구분).

- `form-<날짜>.csv` — 엑셀용. **UTF-8 BOM**을 붙여 한글이 깨지지 않는다.
  입력 열(`cited`·`cited_urls`·`brand_mentioned`·`competitor_domains`·`note`)만 비어 있다
- `form-<날짜>.html` — **오프라인 단일 파일 폼**. 외부 자원이 하나도 없어 인터넷 없이 열린다.
  상단에 측정 규칙 6가지 체크리스트, 질의별 표(라디오 Y/N·URL·경쟁 도메인·메모), 진행률,
  하단 "CSV로 내보내기"(내려받기가 막히면 textarea로 떨어져 복사 가능).
  입력값은 `localStorage`에 자동 저장된다 — 브라우저를 닫아도 남지만
  **저장 실패해도 입력은 계속된다**(try/catch)

### 계약

```
out/<host>/measure/queries.json   su-multi-geo/queries/1
  {"queries":[{"id":"Q01","text":"...","type":"brand|nonbrand","note":""}]}

out/<host>/measure/log.jsonl      su-multi-geo/measure-row/1  · append-only · 한 줄 = 질의 1회
  {"date":"2026-09-15","query_id":"Q01","engine":"chatgpt","run_no":1,
   "mode":"manual|api","signed_out":true|false|null,"cited":true,
   "cited_urls":["https://example.com/pricing"],"brand_mentioned":true,
   "competitor_domains":["competitor.com"],"note":"","recorded_at":"ISO8601"}

out/<host>/measure/summary.json   su-multi-geo/measure/1   · report가 생성
```

`engine`은 고정 목록이다: `chatgpt` `google_aio` `gemini` `claude` `perplexity`
`naver_ai` `daum` `copilot` `other`. 값이 늘면 스키마 버전을 올린다.

로그는 **append-only**다 — 고치지 말고 다시 넣어라. 같은 `date+query_id+engine+run_no`가
여러 번 들어오면 **읽을 때 마지막 것만** 쓴다.

### import가 걸러내는 것

날짜가 `YYYY-MM-DD`가 아닌 행 · `queries.json`에 없는 `query_id` · 고정 목록 밖의 `engine` ·
1 미만인 `run_no` · `cited`가 비었거나 Y/N이 아닌 행. **건너뛰고 사유를 출력한다.**
`brand_mentioned`가 비면 `cited` 값을 따르고, URL이 아닌 토큰은 버리되 `note`에 남긴다.
`cited=Y`인데 URL이 없으면 `[인용 URL 미기록]`으로 표시된다 — 다음 작업을 정할 수 없다는 신호다.

### report가 내는 것

- **엔진 × (브랜드/비브랜드) 인용률** `N/M` — 회차 합산
- **인용 URL 빈도** — 우리 호스트 vs 경쟁 도메인, 질의별로 어느 URL이 뽑히는지
- **날짜별 추이** — 첫 측정일이 기준선, 이후는 기준선 대비 증감
- `ops/measure.md` 6번과 같은 형식의 한 줄 요약과 **다음 재측정 예정일**(마지막 측정 +14일)

`브랜드 4/4`(질의 단위: 한 번이라도 인용된 질의 수)와 `ChatGPT 20/30`(회차 합산)은
**다른 숫자다.** 둘 다 낸다.

### auto — 선택이고, 대체가 아니다

`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`가 **환경변수에 있을 때만** 해당 엔진을 돌린다.
없으면 "수동 모드 — form을 쓰라"고 안내하고 **정상 종료한다(에러 아님)**.
Gemini·Perplexity·Google AI Overviews·네이버·다음·Copilot은 자동화 대상이 아니다 —
수동 폼으로 안내한다.

- OpenAI Responses API(`/v1/responses` + `tools:[{"type":"web_search"}]`)의 `url_citation`
  주석에서, Anthropic Messages API(`/v1/messages` + 서버 도구 `web_search_20250305`)의
  text 블록 `citations`에서 URL을 뽑는다. **검색 결과 전체가 아니라 실제 인용만 센다**
- `urllib`만 쓴다 (SDK 의존 없음). HTTP 전송 함수는 주입 가능하다 — 테스트는 가짜 응답으로 돈다
- ⚠️ **모델명은 각사 문서에서 현재 값을 확인하라.** 코드 상수는 출발점일 뿐이고,
  `OPENAI_MODEL` / `ANTHROPIC_MODEL` 환경변수로 덮어쓴다
- ⚠️ **API 응답은 비로그인 웹 UI와 다른 표면이다.** 자동 측정은 수동 측정을 대체하지 않는다 —
  추세를 싸게 자주 보는 보조 수단으로만 써라

### 안전선 — 키와 비용

- **키는 환경변수에서만 읽는다.** `queries.json`·`log.jsonl`·`summary.json`·폼 어디에도
  쓰지 않고, 콘솔에도 찍지 않는다. 없는 키를 사용자에게 요구하지도 않는다
- **응답 원문을 저장하지 않는다.** 남기는 것은 인용 URL·브랜드 언급 여부·모델명뿐이다
- HTTP 오류는 상태 코드만 `note`에 남기고 본문은 버린다 (본문에 키가 실릴 이유는 없지만 안 받는다)
- **비용은 전부 사용자 부담이다.** 실행 전에 예상 호출 수(엔진 × 질의 × 회차)를 세어
  출력하고, `--yes`가 없으면 확인을 받는다. 회차 사이에 `--delay`(기본 2초)를 지킨다
- 실패한 회차는 버리지 않고 `note`에 사유를 적어 기록한다 — 표본에서 빠지면 분포가 왜곡된다

## 테스트

```bash
bash tools/test_audit.sh          # audit.sh
python -m unittest discover tests # crawl·report·generate·verify·measure (네트워크 없음)
```
