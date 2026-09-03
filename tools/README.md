# tools/ — 진단 도구

전부 의존성 0이다. `audit.sh`는 bash + curl, 나머지는 파이썬 3.10+ 표준 라이브러리만 쓴다.

| 도구 | 무엇 | 입력 | 출력 |
|---|---|---|---|
| `audit.sh` | 홈 1페이지 빠른 진단 | 도메인 | 콘솔 |
| `crawl.py` | 사이트 전수 진단 | 도메인 | `out/<host>/audit.json` + 콘솔 |
| `report.py` | 진단 결과 → 보고서 | `audit.json` | `report.html` |
| `test_audit.sh` | audit.sh 회귀 테스트 | — | PASS/FAIL |

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

## 테스트

```bash
bash tools/test_audit.sh          # audit.sh
python -m unittest discover tests # crawl.py + report.py (네트워크 없음)
```
