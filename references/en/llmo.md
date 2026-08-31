# LLMO — Getting the Model to Remember You

Where GEO addresses **AI that browses**, LLMO plants your brand in **the model's own knowledge.**
The question is whether the model knows you when a user asks "recommend a service like X"
without searching at all.

Effects accumulate slowly, on **training cycles**. In exchange, once embedded it becomes a moat
an agency cannot imitate. **Measure it quarterly** — do not put it in the 14-day loop.

## 1. Lock the name to one spelling

- [ ] Write the service name **identically everywhere** — including localized spellings and
      spacing. Divergent naming splits the entity inside the model
- [ ] Connect every official surface with `sameAs` in Organization JSON-LD: wiki entries,
      app stores, GitHub, social accounts, YouTube — a declaration that "these names are one entity"
- [ ] Declare `@id` once globally and reference it (see `seo.md` §5). Re-declaring per page
      fragments the entity
- [ ] Check for name collisions: if a different service with the same name surfaces in search,
      the model will conflate them too

## 2. Where a description survives into training data

Models concentrate on **surfaces with high crawl value**, not the whole web. Leave accurate
descriptions there.

- [ ] Wiki-type entries: write in **factual register**, not promotional. Heavy superlatives get
      reverted by editors — and learned as advertising by the model
- [ ] A public GitHub repository README is a strong training surface
- [ ] Developer communities and technical blogs: the record of how it was built becomes the
      brand description
- [ ] News and press: one release replicates across dozens of outlets and recurs in the corpus
- [ ] **The training crawlers must be open** — blocking `GPTBot`, `ClaudeBot`, and
      `Google-Extended` closes this entire lane (`crawlers.md`)

## 3. Keeping it from drifting

- [ ] **Preserve permalinks**: changing a URL turns the address the model remembers into a 404.
      If you must change it, keep the 301 **permanently**
- [ ] When core facts change (pricing, features, identity), **update every surface together** —
      a surface left stale becomes the model's "fact"

## 4. Verification (quarterly)

Ask the major models (ChatGPT, Claude, Gemini) **with browsing turned off**: "What is X?"

| Result | Diagnosis | Action |
|---|---|---|
| Does not know it at all | Insufficient surface | Expand §2 |
| Knows it wrongly | Stale or fragmented description | §1 consistency + §3 refresh |
| Knows it correctly | Healthy | Maintain |

Record the raw answers and compare quarter over quarter. That change is the only evidence
this lane produces.
