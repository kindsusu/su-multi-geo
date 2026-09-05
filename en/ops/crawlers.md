# Crawler Policy — the vendors are not built alike

AI crawlers come in **three purposes**, and robots.txt policy must be written per purpose.
No policy = leaving it to chance.

| Purpose | What blocking it costs |
|---|---|
| **Training** (model training data) | Potential future training through that bot |
| **Search indexing** (the engine's own index) | That bot's direct discovery and refresh route |
| **Live fetch** (retrieval at question time) | Direct retrieval for that user request |

## Per-vendor table

| Vendor | Training | Search index | Live fetch |
|---|---|---|---|
| **OpenAI** | `GPTBot` | `OAI-SearchBot` | `ChatGPT-User` |
| **Anthropic** | `ClaudeBot` | `Claude-SearchBot` | `Claude-User` |
| **Perplexity** | (none) | `PerplexityBot` | `Perplexity-User` |
| **Naver** | (none) | `Yeti` | (none) |
| **Google** | `Google-Extended` ⚠️ | (Googlebot) | (Googlebot) |
| Others | `CCBot`, `Applebot-Extended`, `Bytespider`, `Meta-ExternalAgent` | | |

## ⚠️ Google-Extended is not a crawler — the structure differs

`Google-Extended` has **no user-agent**. It never fetches a page. It is a robots.txt **token**
that controls whether content Googlebot has *already* fetched may be used for Gemini training
and some grounding uses.

Three practical consequences:

1. **It never appears in server logs.** Grepping for `GPTBot`/`ClaudeBot` visits as a leading
   indicator does not work for Gemini. Measurement differs → see `measure.md`
2. The token is not an HTTP request, so UA-based rate limits and firewall rules do not target it
3. **Blocking it does not affect Google Search ranking or inclusion** — Google states this
   explicitly. Which also means **allowing it will not raise your ranking.** It is a
   Allowing it does not guarantee ranking gains or a Gemini citation

Scope: Gemini model training / grounding in Gemini Apps / Google Search grounding on Vertex AI.

> For Google Search-based AI surfaces, check Googlebot access, indexing, and snippet eligibility.
> Manage Google-Extended separately as a training/some-grounding policy; it does not control
> Search inclusion or ranking.

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

# Naver (essential for the Korean market — NEO lane)
User-agent: Yeti
Allow: /

Sitemap: https://example.com/sitemap.xml
```

**If your content is an asset and you want to block training only**, disallow just the
training column (`GPTBot`, `ClaudeBot`, `Google-Extended`, `CCBot`). Treat search and fetch
controls separately; blocking them limits those bots' direct routes.

Follow Google's current product-specific documentation for the exact Google-Extended scope.
Blocking it does not affect Search inclusion or ranking, and allowing it does not guarantee citation.

## Verification

```bash
curl -sL https://example.com/robots.txt
```

- Whether each UA actually arrives is visible in **access logs** — except Google-Extended,
  which never does
- robots.txt is **advisory**. Major vendors have stated they honor it, but there have
  been documented compliance controversies (Perplexity, 2024) — don't trust the statement,
  **verify compliance in your access logs**
- For real blocking, enforce at the **server/WAF layer** by user-agent, not in robots.txt

## Maintenance

**The list changes.** Anthropic revised its crawler documentation in February 2026.
**Re-verify each vendor's crawler docs quarterly** and update this file, recording the date.

- Last verified: 2026-08-30
- Sources: official crawler documentation from OpenAI / Anthropic / Google
