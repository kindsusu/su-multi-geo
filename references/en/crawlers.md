# Crawler Policy — the vendors are not built alike

AI crawlers come in **three purposes**, and robots.txt policy must be written per purpose.
No policy = leaving it to chance.

| Purpose | What blocking it costs |
|---|---|
| **Training** (model training data) | Future models' brand awareness → the whole LLMO lane |
| **Search indexing** (the engine's own index) | Citations in AI search results |
| **Live fetch** (retrieval at question time) | Direct citation and traffic at answer time |

## Per-vendor table

| Vendor | Training | Search index | Live fetch |
|---|---|---|---|
| **OpenAI** | `GPTBot` | `OAI-SearchBot` | `ChatGPT-User` |
| **Anthropic** | `ClaudeBot` | `Claude-SearchBot` | `Claude-User` |
| **Perplexity** | (none) | `PerplexityBot` | `Perplexity-User` |
| **Google** | `Google-Extended` ⚠️ | (Googlebot) | (Googlebot) |
| Others | `CCBot`, `Applebot-Extended`, `Bytespider`, `Meta-ExternalAgent` | | |

## ⚠️ Google-Extended is not a crawler — the structure differs

**This is the single most important difference in multi-engine GEO.**

`Google-Extended` has **no user-agent**. It never fetches a page. It is a robots.txt **token**
that decides whether content Googlebot has *already* crawled may be used for Gemini training
and grounding.

Three practical consequences:

1. **It never appears in server logs.** Grepping for `GPTBot`/`ClaudeBot` visits as a leading
   indicator does not work for Gemini. Measurement differs → see `measure.md`
2. **You cannot rate-limit or firewall it.** robots.txt is the only interface
3. **Blocking it does not affect Google Search ranking or inclusion** — Google states this
   explicitly. Which also means **allowing it will not raise your ranking.** It is a
   Gemini-grounding switch, nothing more

Scope: Gemini model training / grounding in Gemini Apps / Google Search grounding on Vertex AI.

> **Therefore: Gemini GEO = Google index optimization + `Google-Extended: Allow`.**
> A page Googlebot cannot crawl will never reach Gemini. If your GSC index is empty,
> Gemini-specific work is wasted effort. Start with `seo.md`.

## Full robots.txt (when citation traffic is the goal)

```
# OpenAI
User-agent: GPTBot
Allow: /
User-agent: OAI-SearchBot
Allow: /
User-agent: ChatGPT-User
Allow: /

# Anthropic
User-agent: ClaudeBot
Allow: /
User-agent: Claude-SearchBot
Allow: /
User-agent: Claude-User
Allow: /

# Perplexity
User-agent: PerplexityBot
Allow: /
User-agent: Perplexity-User
Allow: /

# Google (allow Gemini grounding + training)
User-agent: Google-Extended
Allow: /

Sitemap: https://example.com/sitemap.xml
```

**If your content is an asset and you want to block training only**, disallow just the
training column (`GPTBot`, `ClaudeBot`, `Google-Extended`, `CCBot`). Blocking search and
fetch alongside it kills citation traffic entirely.

Note that blocking `Google-Extended` **also turns off Gemini grounding** — training and
grounding share one token. If you want Gemini citations, this must be Allow.

## Verification

```bash
curl -sL https://example.com/robots.txt
```

- Whether each UA actually arrives is visible in **access logs** — except Google-Extended,
  which never does
- robots.txt is **advisory**. Compliance depends on vendor policy; the major vendors
  (OpenAI, Anthropic, Google, Apple, Perplexity) have publicly stated they honor it
- For real blocking, enforce at the **server/WAF layer** by user-agent, not in robots.txt

## Maintenance

**The list changes.** Anthropic revised its crawler documentation in February 2026.
**Re-verify each vendor's crawler docs quarterly** and update this file, recording the date.

- Last verified: 2026-08-30
- Sources: official crawler documentation from OpenAI / Anthropic / Google
