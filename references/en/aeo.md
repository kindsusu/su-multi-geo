# AEO — Answer Engine Optimization (Google AI Overviews · Bing Copilot)

The lane that makes the AI answer box at the top of search results cite you. Answer engines do
not "read and summarize" a page — they **find the sentence that is the answer and extract it.**
Being shaped for extraction is the whole game.

## 0. Bing registration — the forgotten half

Most sites watch GSC and skip Bing entirely. But **Copilot pulls answers from the Bing index,
and ChatGPT search leans heavily on it too.** Not registered with Bing = throwing away half of
AEO and GEO.

- [ ] Register with [Bing Webmaster Tools](https://www.bing.com/webmasters) — supports
      **one-click import from GSC** (brings over verification and sitemaps). A 10-minute job
- [ ] Submit the sitemap and wire up IndexNow (Bing consumes it directly)
- [ ] **Actually** run `site:yourdomain` on Bing to confirm indexing

## Principle: one question = one page

Give every question people type into search its own page. A page covering ten questions gets
extracted as the answer to none of them. URL, h1, and title reflect the question directly.

## The shape of an extractable sentence

- [ ] **Answer directly in the first paragraph**: one sentence, ~40 characters, at the very top
- [ ] **Every sentence must state a fact independently**: context-dependent phrasing like
      "the figure mentioned above" becomes meaningless once extracted. Each paragraph must
      carry its own **subject, figure, and as-of date**
- [ ] **State the basis and the date**: a number without a basis is penalized in the engine's
      trust assessment
- [ ] **Use tables**: engines parse tables as structured facts reliably

## FAQ blocks

- [ ] 3–5 real search questions as an FAQ section at the bottom of the page
- [ ] Attach FAQPage JSON-LD, **character-identical to the visible text** — a mismatch reads as spam
- [ ] Only answers that data settles. No predictive or advisory Q&A (especially in regulated industries)
- [ ] ℹ️ **Expectation management**: since August 2023 Google has restricted FAQ rich results
      (the collapsible Q&A UI) to authoritative sites such as government and health, and
      retired HowTo rich results. The reason to still attach FAQPage LD is not the rich result
      but **the engine's content comprehension and answer extraction** — do not confuse the
      purpose and strip it because "the stars stopped showing"

## Trust signals (E-E-A-T)

Answer engines care about **who is speaking**. The same data gets cited from a page with a
verifiable identity over an anonymous one.

- [ ] **Disclose the operator**: an About page saying who built this and why, linked to
      Organization JSON-LD
- [ ] **Attribute author and source**: state where the data came from and how it was processed
- [ ] **Be contactable**: a site with an email or form scores higher on trust than a ghost site
- [ ] **Honest `dateModified`**: bumping the date without changing content is manipulation and
      backfires when detected

## Verification

After deploy, **actually search** the question on Google and Bing and record whether the AI
answer cites you. If not, check in order: ① is the direct-answer sentence above the fold
② data freshness versus competing pages ③ page trust (domain age, structured data).
