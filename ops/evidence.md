# 판단 기준과 근거의 범위

확인일: 2026-09-05. 다음 공식 문서를 기준으로 규칙을 갱신한다.

| 관측 | 알 수 있는 것 | 별도 확인할 것 |
|---|---|---|
| HTTP 원시 HTML | 이 요청의 상태·본문·메타·LD | Google 렌더링, 봇별 WAF, 실제 색인 |
| robots 정책 | 특정 UA/경로의 허용 규칙 | 봇 방문·검색 인용 |
| sitemap | 발견/검사한 URL | 사이트의 모든 URL, 색인 수 |
| 구조화 데이터 | 파싱·유형·값 대응 | 사실성·인용 가치·랭킹 효과 |
| 직접 질의 | 해당 조건의 답과 인용 URL | 다른 계정/지역/모델/시점의 결과 |
| 검색 콘솔/분석 | 해당 제품의 노출·클릭·전환 | 다른 제품의 성과·변경의 인과효과 |

## 기술 조건과 개선 기회

Google AI Overviews/AI Mode는 일반 검색의 색인·snippet 적격성을 사용한다. 특별한 AI 파일이나
schema.org 타입은 필수 조건이 아니다. llms.txt와 FAQ는 필요에 맞는 선택 항목이다.
[Google AI 기능](https://developers.google.com/search/docs/appearance/ai-features).

`none`은 noindex/nofollow, `nosnippet`과 `max-snippet:0`은 snippet 제한이다. 페이지 목적에 맞게
의도된 제외와 실수를 구분한다. [robots 메타](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag).

Google은 JavaScript를 렌더링한다. 원시 HTML 본문이 적다는 사실만으로 검색 불가를 확정하지 않는다.
SSR/사전 렌더링은 여러 봇 접근성과 성능을 위해 유용할 수 있다.
[JavaScript SEO](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics).

robots는 주석·경로 대소문자·그룹·최장 규칙·동률 Allow·`*`/`$`를 구분한다.
[공식 규칙](https://developers.google.com/crawling/docs/robots-txt/robots-txt-spec).

학습용 ClaudeBot, 검색용 Claude-SearchBot, 사용자 요청 Claude-User는 별도 역할이다.
[Anthropic 봇](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler).
Google-Extended는 HTTP UA가 아닌 학습/일부 Gemini grounding 제어 토큰이다. Search 포함/순위 제어가 아니다.
[Google-Extended](https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers#google-extended).

## 측정과 인과관계

API 오류는 미인용이 아니라 관측 실패다. 실패·누락과 인용 성공/관측 수를 함께 기록한다.
UI와 API, 브랜드와 비브랜드, 측정일과 누적 기간을 혼합하지 않는다. 비교 전 질의·조건·가중치를 대조한다.
모델/질문/환경이 바뀌면 새 기준선이 필요할 수 있다.

5~10회는 초기 변동성 관찰용이다. 1회도 관측이지만 대표성은 낮다. 작은 차이를 성공/실패로 확정하지
않고 표본 수·불확실성·오류율을 표시한다. 반복 관측과 유사 미변경 페이지 비교가 해석에 도움이 되지만
전후 상관관계만으로 수정의 인과효과를 증명하지는 못한다.

next_due는 계획, snapshot은 기록, verify는 특정 시점의 기술 검사다. 실제 인용이나 사업 성과의 대체 지표가 아니다.
