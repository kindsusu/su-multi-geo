# NEO — Naver Engine Optimization

For a service targeting the Korean market, a large share of search traffic comes from Naver.
Global SEO and GEO guides do not cover it at all. Two goals: ① Naver search visibility
② **AI Briefing citation** (Naver's AI summary at the top of results naming your page as a source).

## 1. Search Advisor (the required foundation)

- [ ] Register the site at searchadvisor.naver.com and verify ownership
      (requires the operator's account — guide the steps, do not attempt it yourself)
- [ ] Submit the sitemap; confirm robots.txt **allows Yeti** (Naver's crawler)
- [ ] **Read Webmaster Tools on a weekly rhythm**: content impression/click trends plus
      per-query clicks, CTR, and position. This is where you see which questions drive traffic
- [ ] Request collection: for important new pages, a manual collection request right after
      registration accelerates pickup

## 2. AI Briefing citation requirements

Naver AI Briefing attaches source chips **at the paragraph level.** Conditions for a cited page:

- [ ] **Structured facts**: item-value grids (price / term / conditions …) that machines read
      easily. **Label-value structure gets cited over prose blocks**
- [ ] **Primary-source signals**: the page states it is based on an official source, with the
      original link alongside
- [ ] **Freshness**: whichever page stands up fastest after an event takes the citation
- [ ] **Mobile optimization**: Naver is mobile-first. The essentials must be visible in the
      first mobile screen
- [ ] Verification: search the target keyword **in the Naver app** and record the actual source chips

## 3. Two-track blogging (inside / outside)

Naver favors content **inside** its own ecosystem, while accurate data must live on **your own
domain**. The answer is both tracks:

- **inside** — brand blog: builds trust and dwell time inside Naver. What ranks in search and
  SmartBlock is often the blog post
- **outside** — your own domain: the ledger of facts. What AI Briefing cites is ultimately the
  structured data page
- Link naturally from blog posts to your data pages, but **no link spamming**

## 4. Additional items for local and offline businesses

- [ ] Register on Naver Place and keep details accurate. Hours, phone, and address **must match
      the website** — a mismatch is entity fragmentation, the same problem as `llmo.md` §1
- [ ] With multiple branches, build per-branch pages plus LocalBusiness JSON-LD
- [ ] Dedicated landings for "region + service" search questions

## 5. What not to do (Naver is especially sensitive)

- ❌ **Automated neighbor-adding and reciprocal commenting** — a primary target of the spam
  filter. Getting caught leads to low-quality classification for the blog. If Naver is your
  largest traffic channel, this is gambling that channel
- ❌ Mass repetition of identical phrasing (comments, posts) — a spam signal in itself
- ❌ Repeated edit-and-delete cycles after publishing — it erodes document trust score

## 6. Measurement

- Snapshot Webmaster Tools impressions and clicks weekly (there is no public API, so do it
  manually or collect it yourself)
- AI Briefing citation is confirmable **only by searching in the app** — it does not appear in logs
- Watch for the weekend-dip pattern: weekday-shaped topics going quiet on weekends is normal,
  and is evidence of real demand
