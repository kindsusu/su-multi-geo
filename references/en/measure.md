# Measurement Loop — fixing it is not finishing it

This is where a playbook differs from an agency report. **Optimization without measurement
is just a claim.**

## 1. Baseline — capture it before you change anything

If you do not record the "before," you can never prove the effect.

| Item | Where | Cadence |
|---|---|---|
| Impressions · clicks · avg position | Google Search Console (28d) | weekly |
| Bing impressions · clicks | Bing Webmaster Tools | weekly |
| Naver impressions · clicks · queries | Naver Search Advisor | weekly |
| Indexed pages | GSC + `site:domain` (Google and Bing separately) | weekly |
| **AI citation O/X** | protocol in §2 | biweekly |
| **AI crawler visits** | server access log | weekly |
| **AI referral traffic** | GA4 Traffic acquisition → session source filter | weekly |

Filter sessions whose source is `chatgpt.com`, `perplexity.ai`, `gemini.google.com`,
`claude.ai`, `copilot.microsoft.com`. Unlike the manual citation O/X check, this is the
**only lagging citation indicator that collects itself** — and the only automatic evidence
that a citation turned into an actual visit.
⚠️ It **undercounts structurally.** Clients that do not pass a referrer (in-app browsers,
some redirect hops) land in Direct, so read the **trend**, never the absolute number.

```bash
# AI crawler visits — the leading indicator that moves before citations do
grep -icE 'GPTBot|OAI-SearchBot|ChatGPT-User|ClaudeBot|Claude-SearchBot|Claude-User|PerplexityBot|Perplexity-User' access.log

# Break it down per vendor to see the trend
for ua in GPTBot OAI-SearchBot ChatGPT-User ClaudeBot Claude-SearchBot Claude-User PerplexityBot; do
  printf '%-20s %s\n' "$ua" "$(grep -icF "$ua" access.log)"
done
```

No log access? Substitute your host's bot-traffic classification (Cloudflare, Vercel, etc.).

## 2. AI citation protocol — the method differs per engine

Fix **5–10 target questions** and measure with the same ones every time.
If the questions change, the trend is meaningless.

| Engine | Log-observable | Method |
|---|---|---|
| ChatGPT | ✅ 3 UAs | Query in search mode → domain in sources, O/X |
| **Gemini** | ❌ **impossible** | **Direct querying is the only method** |
| Claude | ✅ 3 UAs | Query with web search on → cited, O/X |
| Perplexity | ✅ 2 UAs | Query → source card, O/X |
| Naver AI Briefing | ❌ | Search in the Naver app → source chip, O/X |
| Google AI Overviews | ❌ | Google search → answer box sources, O/X |

> **⚠️ Gemini has no leading indicator.**
> `Google-Extended` is a robots.txt token, not a user-agent, so it **never appears in server
> logs.** You cannot watch "the crawler came, so a citation is coming."
> Use the **GSC indexed-page count** as Gemini's leading indicator instead — Googlebot's index
> is the only gateway to Gemini. More indexed pages means more reachable surface.

Record like this:

```
2026-09-15 | Q1 "long-term car rental Jeju" | ChatGPT ✗ / Gemini ✗ / Claude ✓ / Naver ✗
```

## 3. The re-measure date is part of the work

- Search reflection lags. **Re-measure 14 days after the change** as a default
- Exclude the **most recent 2–3 days** from comparisons — aggregation lags
- LLMO moves on training cycles, so measure it **quarterly**, separately (`llmo.md`)
- Do not leave re-measurement to memory. **Naming the re-measure date in the report is the
  completion condition.**

## 4. The stale-data trap

> **Stale data passes every lower bound.**

A monitor that only checks "not zero" will happily pass a value that has been frozen for days.
When building a measurement pipeline, watch the **date of the value**, not the value.
"If the last update is older than N days, do not display this metric" is the safe default.

## 5. How to read the numbers

- **Impressions first, clicks later.** The first signal of structural work is impressions.
  CTR moves only after titles and descriptions follow. Impressions up but CTR flat → next job is meta
- **Weekend dips are normal.** Weekday-shaped topics (B2B, finance, corporate) go quiet on
  weekends. That pattern is evidence of real demand
- **The query list is the roadmap.** Top queries in GSC and Search Advisor are the questions
  people actually type. A top query with no dedicated landing page = the next page to build
- **AI referrals are a lagging indicator.** The order is crawler visits (leading) → citation
  O/X (present) → referral traffic (lagging). Zero referrals alongside a confirmed citation is
  normal — you were cited but not clicked, or the referrer was stripped. Referrals rising is
  evidence citations are rising
- **Beware growth rates.** When the baseline is near zero, any change produces a percentage in
  the tens of thousands. **Always report absolute values alongside.**

## 6. Report format

```
[Baseline] 8/1–8/28  impressions 12,400 · clicks 180 · indexed 340 · AI cited 0/8
[Change]   8/29      6 intent landings + llms.txt + robots for all vendors + FAQ LD
[Scheduled] 9/12
[Result]   9/12      impressions 31,000 (+18,600) · clicks 610 · indexed 890 · AI cited 3/8
                     └ ChatGPT 2/8, Claude 1/8, Gemini 0/8 (indexed 890 → Gemini pending)
```
