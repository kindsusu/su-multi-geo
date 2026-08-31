# AEO — Getting Cited by Answer Engines (Google AI Overviews · Bing Copilot)

The lane that makes the AI answer box at the top of search results cite you. Answer engines do
not "read and summarize" a page — they **find the sentence that is the answer and extract it.**
Being shaped for extraction is the whole game.

## 0. Bing registration — the half everybody skips

Most sites watch GSC and skip Bing entirely. But **Copilot pulls answers from the Bing index,
and ChatGPT search leans heavily on it too.** Not registered with Bing = throwing away half of
AEO and GEO.

- [ ] Register with [Bing Webmaster Tools](https://www.bing.com/webmasters) — supports
      **one-click import from GSC** (brings over verification and sitemaps). A 10-minute job
- [ ] Submit the sitemap and wire up IndexNow (Bing consumes it directly)
- [ ] **Actually** run `site:yourdomain` on Bing to confirm indexing

## The core rule: one question, one page

Give every question people type into search its own page. A page covering ten questions gets
extracted as the answer to none of them. URL, h1, and title reflect the question directly.

## Which sentences actually get lifted

- [ ] **Answer directly in the first paragraph**: one sentence, ~40 characters, at the very top
- [ ] **Every sentence must state a fact independently**: context-dependent phrasing like
      "the figure mentioned above" becomes meaningless once extracted. Each paragraph must
      carry its own **subject, figure, and as-of date**
- [ ] **State the basis and the date**: a number without a basis is penalized in the engine's
      trust assessment
- [ ] **Use tables**: engines parse tables as structured facts reliably

### Writing so the extracted sentence cannot mislead — four checks

If one sentence getting lifted is the premise, then **that sentence must not be wrong on its
own.** Check all four, sentence by sentence.

- [ ] **Conditions and exceptions inside the same sentence.** A condition living in the next
      sentence is a condition that gets cut off
- [ ] **Attach subject, period and basis to every figure.** A number alone becomes a number
      that applies everywhere
- [ ] **Separate fact from evaluation.** "two years" is a fact; "best in the industry" is an
      evaluation. Mixed into one sentence, the evaluation gets cited as fact too
- [ ] **Every sentence complete in subject and meaning.** "in this case", "as mentioned above"
      are meaningless once extracted

**Bad** — the condition is in the next sentence, and fact is fused with evaluation:
> The warranty period is two years, the best in the industry. Consumables and user damage are excluded.

**Good** — condition, exception and basis in one sentence, evaluation dropped:
> The standard warranty runs two years from the purchase date and excludes consumables and
> damage caused by user error (as of 2026-08, units sold through official domestic channels).

## FAQ blocks

- [ ] An FAQ section at the foot of the page, built from 3–5 questions people really search
- [ ] Attach FAQPage JSON-LD, **character-identical to the visible text** — a mismatch reads as spam
- [ ] Only answers that data settles. No predictive or advisory Q&A (especially in regulated industries)
- [ ] ℹ️ **Expectation management**: since August 2023 Google has restricted FAQ rich results
      (the collapsible Q&A UI) to authoritative sites such as government and health, and
      retired HowTo rich results. The reason to still attach FAQPage LD is not the rich result
      but **the engine's content comprehension and answer extraction** — do not confuse the
      purpose and strip it because "the stars stopped showing"

## Who is speaking (E-E-A-T)

Answer engines care about **who is speaking**. The same data gets cited from a page with a
verifiable identity over an anonymous one.

- [ ] **Disclose the operator**: an About page saying who built this and why, wired to
      the site's Organization JSON-LD
- [ ] **Attribute author and source**: state where the data came from and how it was processed
- [ ] **Be contactable**: a site with an email or form scores higher on trust than a ghost site
- [ ] **Honest `dateModified`**: bumping the date without changing content is manipulation and
      backfires when detected

## Confirming it worked

After deploy, **actually search** the question on Google and Bing and record whether the AI
answer cites you. If not, check in order: ① is the direct-answer sentence above the fold
② data freshness versus competing pages ③ page trust (domain age, structured data).
