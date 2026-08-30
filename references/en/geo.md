# GEO — Generative Engine Optimization (per-engine lanes)

The lane that makes generative AI cite you as a **primary source**. Because engines draw on
**different index sources**, split the work into shared tasks plus per-engine tasks.

## Engine matrix — where to actually push

| Engine | Index source | Decisive control point | Log-observable |
|---|---|---|---|
| **ChatGPT** | Own crawlers + **leans on Bing index** | Bing WMT registration + allow OAI-SearchBot | ✅ |
| **Gemini** | **Google index (Googlebot)** | GSC indexing + allow Google-Extended | ❌ impossible |
| **Claude** | Own crawler (Claude-SearchBot) | Allow all three robots.txt agents | ✅ |
| **Perplexity** | Own crawler | Allow PerplexityBot | ✅ |

**How to read it:**
- ChatGPT not showing up → check the **Bing index first**. Most sites watch GSC and forget Bing
- Gemini not showing up → check the **GSC indexed-page count**. If Googlebot cannot crawl it, it is over
- Claude/Perplexity not showing up → check robots.txt and SSR

## 1. Shared — llms.txt

A markdown site guide for AI at `/llms.txt`:

```markdown
# Service Name

> One-line description (state what you are the primary source of)

## Key pages
- [Pricing](https://example.com/pricing): per-vehicle daily and monthly rates, updated daily
- [Locations](https://example.com/branches): nationwide branches and hours

## Data policy
- Source: own operational data, updated daily
- Attribution: example.com
```

- [ ] `/llms.txt`, plus `/llms-full.txt` (full core data) if you can
- [ ] Carry trust signals: source, update cadence, what you originate
- [ ] Serving it from an app route is fine — keeps it current

⚠️ llms.txt is a **convention, not a standard**. There is no guarantee every engine reads it.
The cost is low so do it, but do not expect citations from this alone. The body of the work is §3.

## 2. Shared — crawler access

Read `crawlers.md` and settle robots.txt. **This is priority zero.**
If access is blocked, nothing below arrives.

## 3. Shared — becoming the primary source (the real work)

Generative engines trace "where did this number start." A page that summarizes someone
else's data loses the citation to the origin.

- [ ] Define which numbers **you** compute or collect (own metrics, aggregates, observations)
- [ ] Name them and always serve them from the **same URL** (stable URL = citable address)
- [ ] **Paragraph-level citability**: when each paragraph carries [subject + figure + as-of date
      + method], it gets cited as a paragraph. Engines slice paragraphs, not pages

## 4. Per-engine — ChatGPT

- [ ] **Register with Bing Webmaster Tools** (one-click import from GSC, ~10 minutes).
      ChatGPT search leans heavily on the **Bing index** on top of its own crawlers.
      Not registered = half the lane abandoned
- [ ] Wire up IndexNow (Bing consumes it directly) to accelerate new pages
- [ ] Actually run `site:yourdomain` **on Bing** to confirm indexing
- [ ] robots: allow `GPTBot`, `OAI-SearchBot`, `ChatGPT-User`

## 5. Per-engine — Gemini ★ structurally different

Gemini has **no crawler of its own.** It sits on top of Googlebot's index.

- [ ] **Check the GSC indexed-page count first.** If pages are not indexed, Gemini work is moot —
      go do the SSR and sitemap items in `seo.md`
- [ ] `Google-Extended: Allow` — the Gemini grounding switch. Absent means unset policy
- [ ] AI Overviews and Gemini are separate surfaces. AI Overviews belongs to `aeo.md`
- [ ] ⚠️ **Measurement differs** — invisible in logs, so direct querying is the only way → `measure.md`

## 6. Per-engine — Claude

- [ ] robots: allow `ClaudeBot` (training) / `Claude-SearchBot` (indexing) / `Claude-User` (live).
      The three are independent, so **blocking training while keeping search and fetch open**
      is a valid choice
- [ ] Watch for `Claude-SearchBot` in logs — a leading indicator of index entry
- [ ] Claude does a meaningful share of live fetching, so **SSR response time** affects citation

## 7. Verification

Actually ask each engine and check whether your domain appears in the sources.
If not, check in order:

1. Is the crawler allowed (robots.txt)?
2. Does the page render server-side (curl)?
3. Is it in that engine's index source (ChatGPT → Bing, Gemini → GSC)?
4. Does a competing primary source already own it? If so, differentiate what you originate
