#!/usr/bin/env bash
# audit.sh 핵심 로직 회귀 테스트. 사용: bash test_audit.sh   (전부 PASS여야 정상)
set -uo pipefail
cd "$(dirname "$0")"
FAIL=0

# POLICY 함수만 추출해 로드
eval "$(sed -n '/^POLICY()/,/^}/p' audit.sh)"

t() { # $1=설명 $2=UA $3=기대값 (robots는 stdin)
  got=$(POLICY "$2")
  if [ "$got" = "$3" ]; then echo "PASS $1"; else echo "FAIL $1: got=$got want=$3"; FAIL=1; fi
}
printf 'User-agent: GPTBot\nDisallow: /\n'                | t "명시 차단"          GPTBot    explicit-block
printf 'User-agent: GPTBot\nAllow: /\n'                   | t "명시 허용"          GPTBot    explicit-allow
printf 'User-agent: *\nDisallow: /\n'                     | t "와일드카드 차단"     ClaudeBot star-block
printf 'User-agent: *\nDisallow:\n'                       | t "빈 Disallow=허용"   GPTBot    star-allow
printf 'User-agent: GPTBot\r\nDisallow: /\r\n'            | t "CRLF"              GPTBot    explicit-block
printf 'User-agent: A\nUser-agent: B\nDisallow: /\n'      | t "다중 UA 그룹"       B         explicit-block
printf 'User-agent: *\nDisallow: /admin/\n'               | t "부분 제한"          GPTBot    star-partial
printf ''                                                 | t "빈 robots"          GPTBot    none

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

exit $FAIL
