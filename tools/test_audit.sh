#!/usr/bin/env bash
# audit.sh 핵심 로직 회귀 테스트. 사용: bash test_audit.sh   (전부 PASS여야 정상)
set -uo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
cd "$(dirname "$0")"
FAIL=0
SCRIPT_DIR="$(pwd)"

# POLICY 함수만 추출해 로드
eval "$(sed -n '/^POLICY()/,/^}/p' audit.sh)"

t() { # $1=설명 $2=UA $3=기대값 $4=robots
  got=$(printf '%s' "$4" | POLICY "$2")
  if [ "$got" = "$3" ]; then echo "PASS $1"; return 0; fi
  echo "FAIL $1: got=$got want=$3"
  return 1
}
t "명시 차단" GPTBot explicit-block $'User-agent: GPTBot\nDisallow: /\n' || FAIL=1
t "명시 허용" GPTBot explicit-allow $'User-agent: GPTBot\nAllow: /\n' || FAIL=1
t "와일드카드 차단" ClaudeBot star-block $'User-agent: *\nDisallow: /\n' || FAIL=1
t "빈 Disallow=허용" GPTBot star-allow $'User-agent: *\nDisallow:\n' || FAIL=1
t "CRLF" GPTBot explicit-block $'User-agent: GPTBot\r\nDisallow: /\r\n' || FAIL=1
t "다중 UA 그룹" B explicit-block $'User-agent: A\nUser-agent: B\nDisallow: /\n' || FAIL=1
t "부분 제한" GPTBot star-partial $'User-agent: *\nDisallow: /admin/\n' || FAIL=1
t "동률 Allow" GPTBot explicit-allow $'User-agent: GPTBot\nDisallow: /\nAllow: /\n' || FAIL=1
t "주석 제거" GPTBot explicit-block $'User-agent: GPTBot\nDisallow: / # all\n' || FAIL=1
t "빈 robots" GPTBot none '' || FAIL=1

# Sitemap 선언 필터: 외부 도메인·비URL은 접속 대상에서 제외되는지 (audit.sh의 case 로직과 동일)
HOST="example.com"
chk() { # $1=값 $2=기대(fetch|skip)
  case "$1" in
    http://"$HOST"/*|https://"$HOST"/*) got=fetch ;;
    http://*|https://*) got=skip ;;
    *) got=skip ;;
  esac
  if [ "$got" = "$2" ]; then echo "PASS sitemap:$1"; else echo "FAIL sitemap:$1 got=$got"; FAIL=1; fi
}
chk "https://example.com/sitemap.xml"  fetch
chk "http://127.0.0.1/steal"           skip
chk "https://evil.com/sitemap.xml"     skip
chk "--url=http://169.254.169.254/"    skip

# 실패 집계 자체의 회귀 검사: 자식 실행에 고의 실패를 넣었을 때 반드시 exit 1이어야 한다.
if [ "${AUDIT_FAILURE_PROBE:-0}" = "1" ]; then
  t "failure probe" GPTBot explicit-allow $'User-agent: GPTBot\nDisallow: /\n' || FAIL=1
  exit "$FAIL"
fi
PROBE_OUT=$(AUDIT_FAILURE_PROBE=1 "$BASH" "$SELF" 2>&1)
PROBE_RC=$?
if [ "$PROBE_RC" = "1" ] && printf '%s' "$PROBE_OUT" | grep -q 'FAIL failure probe'; then
  echo "PASS 실패가 비정상 종료로 전파됨"
else
  echo "FAIL 고의 실패가 정상 종료로 숨겨짐 (exit=$PROBE_RC)"
  FAIL=1
fi

exit $FAIL
