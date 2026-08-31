# Intent Discovery — which questions deserve a page

Intent landings are won or lost at **question selection**, not at writing. A question nobody
types gets zero impressions no matter how well you answer it, and a question with an
entrenched primary source loses the citation anyway.
The order is **discover → filter → map → prioritize**, and the rule in discovery is:
do not invent questions.

## 1. Discovery sources — dig, do not imagine

- [ ] **GSC query report** (first). A top query that already gets impressions but has
      **no dedicated landing page = the next page to build.** High impressions with low
      clicks means demand is already proven
- [ ] **Naver Search Advisor queries.** For the Korean market the list differs substantially
      from GSC — colloquial phrasing, place names, and "how much" questions surface here
- [ ] **Autocomplete and related searches** (Google, Naver). Type your core term and copy the
      list verbatim. These strings come from real query logs, so they beat anything you write
- [ ] **Ask the AI engines directly and reverse-engineer the cited pages.** Put your target
      question to ChatGPT, Gemini, Claude and Perplexity, then **open the pages in the source
      list** and see which question they answer and in what shape. Whoever takes the citation
      today is your baseline
- [ ] **Support and CS records.** Questions people actually asked are the source of long-tail
      intent no keyword tool sees, and they already come phrased in user language. Sweep
      support logs, inbound forms and call notes for the top 20 repeats

⚠️ Do not build the list from a keyword tool's estimated volume alone. Estimates are badly
wrong on brand and vertical terms. **Impressions actually recorded in your own GSC** are
always the stronger evidence.

## 2. Filter — keep only questions you can answer

- [ ] **Can data settle it?** "What does it cost", "how many days does it take" have one
      answer. "Which one is better", "should I buy now" are predictive or advisory — drop
      them. They are a liability in regulated verticals, and answer engines extract
      definitive sentences first
- [ ] **Can we be the primary source?** Prioritize questions answered with numbers we compute,
      aggregate or observe ourselves. Questions answered by summarizing someone else's
      statistics hand the citation back to the original source (→ `geo.md` §3)
- [ ] **Can you attach an as-of date?** An answer without a basis silently becomes a wrong
      page as it ages. Do not create a question nobody owns updating
- [ ] If the answer will not fit in one sentence, the question is too big. Split it or drop it

## 3. Question → page mapping rules

- [ ] **One question = one page.** A page covering ten things gets extracted as the answer to
      none of them
- [ ] URL, h1 and title reflect **the question itself** (the URL being its core noun phrase)
- [ ] **Direct answer in the first paragraph, ~40 characters.** No preamble, no company intro
      above it
- [ ] Below the answer, an **evidence table** — item, figure, unit, as-of date. Tables are the
      shape engines parse most reliably
- [ ] Attach 3–5 related questions as an FAQ block; split one out into its own page only when
      it grows big enough to stand alone

### Format — one well-structured guide beats a page count

- [ ] **Concentrate effort on a single comparison or roundup guide.** A well-built single
      page carrying a substantial share of a domain's total citations — and covering hundreds
      of keywords on its own — is a repeatedly observed pattern. One page carrying all the
      conditions and criteria beats 30 thin ones
- [ ] **Write for evaluation, not for feeling.** What cited pages have in common is
      **structured decision criteria** — price, spec, terms, pros and cons laid out side by
      side. Aspirational brand copy is not citation material
- [ ] **Community-style Q&A absorbs a large share of evaluation-stage intent.** If the answer
      to "has anyone used ○○", "A or B?" lives in a forum, the citation goes there too.
      Designing your own Q&A (FAQ, support archive) in that shape is a GEO task in itself
- [ ] ⚠️ **A report published only as a PDF does not reach the web.** However good it is, AI
      cannot take it — publish the same content as a web page and keep the PDF as an attachment
- [ ] **A report or statistics page with no methodology does not get adopted as evidence.**
      Put the sample, the period and the calculation in the body

## 4. ⚠️ The cannibalization trap

Splitting near-identical questions into separate pages makes them **eat each other.**
"Jeju car rental rates" and "Jeju car rental prices" are different query strings with the same
answer — build both and the engine cannot decide which to rank, so it demotes both.

The test is not the query string, it is **the content of the answer**.

- Same answer → **one page.** Absorb the phrasing variants in the body and FAQ, and pin the
  canonical
- Different answer (different table, basis, or subject) → separate pages
- Already split? Merge and 301 — one strong page always beats two weak ones

## 5. Prioritization

Multiply three axes and sort. If any one is near zero, push it back.

| Axis | Evidence | Low (1) ↔ High (3) |
|---|---|---|
| Volume evidence | Measured impressions in GSC / Search Advisor | estimates only ↔ many real impressions |
| Primary-source potential | Do we answer with our own data? | summarizing others ↔ numbers only we have |
| Production cost (inverted) | Can we build the data and table? | new collection needed ↔ reuse existing data |

- Cap the first batch at **6–10 pages.** Ship 30 at once and you cannot tell which one worked
- Record the ship date and re-measure 14 days later (→ `measure.md`)
- At re-measure, sweep the GSC query report again and **the next batch writes itself.**
  Once this loop runs, question discovery stops being guesswork
