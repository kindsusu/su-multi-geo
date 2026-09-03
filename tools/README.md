# tools/ — 진단 도구

전부 의존성 0이다. `audit.sh`는 bash + curl, 나머지는 파이썬 3.10+ 표준 라이브러리만 쓴다.

| 도구 | 무엇 | 입력 | 출력 |
|---|---|---|---|
| `audit.sh` | 홈 1페이지 빠른 진단 | 도메인 | 콘솔 |
| `crawl.py` | 사이트 전수 진단 | 도메인 | `out/<host>/audit.json` + 콘솔 |
| `report.py` | 진단 결과 → 보고서 | `audit.json` | `report.html` |
| `generate.py` | 진단 결과 → 배포 산출물 초안 | `audit.json` (+ `site.json`) | `out/<host>/deploy/` + `DEPLOY.md` |
| `test_audit.sh` | audit.sh 회귀 테스트 | — | PASS/FAIL |

흐름은 `crawl.py` → `report.py`(사람에게 보고) → `generate.py`(고칠 파일 초안) 순이다.

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

## 테스트

```bash
bash tools/test_audit.sh          # audit.sh
python -m unittest discover tests # crawl.py + report.py + generate.py (네트워크 없음)
```
