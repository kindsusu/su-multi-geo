#!/usr/bin/env bash
# Phase 0 진단 — 크롤러의 눈으로 사이트를 훑는다.
# 사용: bash audit.sh example.com
set -uo pipefail

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
  echo "사용법: bash audit.sh <도메인>   (예: bash audit.sh example.com)"
  exit 1
fi
case "$DOMAIN" in http*) URL="$DOMAIN" ;; *) URL="https://$DOMAIN" ;; esac
BASE="${URL%/}"
UA='Mozilla/5.0 (compatible; multi-geo-audit/1.0)'

C()     { curl -sL  --max-time 20 -A "$UA" "$@"; }
CODE()  { curl -s -o /dev/null -w '%{http_code}' --max-time 15 -A "$UA" "$1"; }
COUNT() { grep -oi "$1" | wc -l | tr -d ' '; }

echo "════════════════════════════════════════════"
echo " Phase 0 진단 — $BASE"
echo " $(date '+%Y-%m-%d %H:%M')"
echo "════════════════════════════════════════════"

HTML="$(C "$BASE")"
if [ -z "$HTML" ]; then
  echo "❌ 응답 없음 — 도메인·네트워크를 확인하라"
  exit 1
fi

echo ""
echo "── 0. noindex 사고 점검 (최우선) ──"
META_ROBOTS="$(printf '%s' "$HTML" | grep -oiE '<meta[^>]*robots[^>]*>' | head -3)"
XROBOTS="$(curl -sIL --max-time 20 -A "$UA" "$BASE" | grep -i 'x-robots-tag' || true)"
if printf '%s%s' "$META_ROBOTS" "$XROBOTS" | grep -qi 'noindex'; then
  echo "🚨 noindex 발견 — 다른 모든 최적화가 무효다. 이것부터 고쳐라"
  [ -n "$META_ROBOTS" ] && echo "   meta   : $META_ROBOTS"
  [ -n "$XROBOTS" ]     && echo "   header : $XROBOTS"
else
  echo "✅ noindex 없음"
  [ -n "$META_ROBOTS" ] && echo "   (meta robots: $META_ROBOTS)"
fi

echo ""
echo "── 1. SEO: 크롤러가 보는 HTML ──"
H1=$(printf '%s' "$HTML" | COUNT '<h1')
OG=$(printf '%s' "$HTML" | COUNT 'og:')
LD=$(printf '%s' "$HTML" | grep -oiF 'application/ld+json' | wc -l | tr -d ' ')
TITLE=$(printf '%s' "$HTML" | grep -oiE '<title[^>]*>[^<]*' | head -1 | sed 's/<[^>]*>//' | cut -c1-70)
DESC=$(printf '%s' "$HTML" | grep -oiE 'name="description"[^>]*content="[^"]*' | head -1 | sed 's/.*content="//')
CANON=$(printf '%s' "$HTML" | grep -oiE 'rel="canonical"[^>]*' | head -1 | cut -c1-70)
TEXT=$(printf '%s' "$HTML" | sed 's/<[^>]*>//g' | tr -s ' \n' ' ' | wc -c | tr -d ' ')

echo "   h1 태그        : ${H1}개"
echo "   title          : ${TITLE:-(없음)}"
echo "   meta desc      : ${#DESC}자  (권장 150~160)"
echo "   og: 태그       : ${OG}개"
echo "   JSON-LD        : ${LD}개"
echo "   canonical      : ${CANON:-(없음)}"
echo "   본문 텍스트량  : 약 ${TEXT}자   ← 적으면 CSR 의심 (SSR 확인 필요)"

echo ""
echo "── 2. sitemap / robots ──"
SM_CODE=$(CODE "$BASE/sitemap.xml")
echo "   sitemap.xml    : HTTP $SM_CODE"
if [ "$SM_CODE" = "200" ]; then
  LOCS=$(C "$BASE/sitemap.xml" | grep -o '<loc>' | wc -l | tr -d ' ')
  echo "   └ URL 수       : ${LOCS}개"
fi
RB="$(C "$BASE/robots.txt")"
if [ -n "$RB" ]; then
  echo "   robots.txt     : 있음"
  if printf '%s' "$RB" | grep -qi 'sitemap:'; then
    echo "   └ Sitemap 참조 : ✅"
  else
    echo "   └ Sitemap 참조 : ❌ 없음"
  fi
else
  echo "   robots.txt     : ❌ 없음"
fi

echo ""
echo "── 3. GEO: AI 크롤러 정책 (robots.txt) ──"
for ua in GPTBot OAI-SearchBot ChatGPT-User \
          ClaudeBot Claude-SearchBot Claude-User \
          PerplexityBot Perplexity-User Google-Extended; do
  if printf '%s' "$RB" | grep -qiE "^[[:space:]]*User-agent:[[:space:]]*${ua}[[:space:]]*$"; then
    STATE="명시됨"
  else
    STATE="⚠️  미설정"
  fi
  printf '   %-18s %s\n' "$ua" "$STATE"
done
echo "   ※ Google-Extended는 UA가 아니라 robots 토큰이다 — 서버 로그에 안 잡힌다"

echo ""
echo "── 4. GEO: llms.txt ──"
for f in llms.txt llms-full.txt; do
  printf '   /%-14s HTTP %s\n' "$f" "$(CODE "$BASE/$f")"
done

echo ""
echo "── 5. 응답 위생 ──"
echo "   404 동작       : HTTP $(CODE "$BASE/__multi_geo_404_probe__")  (404여야 정상)"
echo "   리다이렉트 홉  : $(curl -sIL -o /dev/null -w '%{num_redirects}' --max-time 20 -A "$UA" "$BASE")"
echo "   응답 시간      : $(curl -s -o /dev/null -w '%{time_total}' --max-time 20 -A "$UA" "$BASE")s"

echo ""
echo "════════════════════════════════════════════"
echo " 이 결과로 레인별 ✅/⚠️/❌ 점수표를 만들고"
echo " 우선순위를 승인받은 뒤 Phase 1부터 진행한다."
echo ""
echo " 스크립트로 안 되는 것 (사람이 확인):"
echo "  · GSC / Bing WMT / 네이버 서치어드바이저 색인 수"
echo "  · 각 엔진에 직접 질의한 AI 인용 O/X (특히 Gemini)"
echo "════════════════════════════════════════════"
