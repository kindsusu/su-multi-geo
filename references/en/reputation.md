# Reputation Surfaces — the third-party material AI reads when describing you

Every other file in this skill deals with **first-party data you produce**. But ask an AI
"what kind of company is ○○" and half the answer comes from text you did not write.
Leave those surfaces alone and your company description is not your sentence — it is
**somebody else's sentence from years ago**.

## 1. Four axes — if one is empty, the AI cannot assemble a recommendation

To make brand meaning reusable by a model, all four have to be present.

| Axis | What | Missing means |
|---|---|---|
| **Attributes** | specs, terms, figures — what it is | you are not in the comparison set |
| **Reasons** | how it solves the problem, usage context — why this is the answer | you do not match the search intent |
| **Evidence** | tests, certifications, data, press — how we know it is true | you lose on trust assessment |
| **Reputation** | reviews, ratings, testimonials, communities — what others say | **no recommendation can be assembled** |

⚠️ **This skill's existing emphasis (primary source = numbers only we can produce) covers
attributes and evidence — two axes out of four.** You can execute `geo.md` §3 perfectly and
still be a brand the AI can *describe* but has no grounds to *recommend*.

## 2. Diagnose — what is describing us right now

The measurement protocol is the same as `measure.md` §2 (logged out, repeated queries, record
the cited URLs). Only the question set changes.

- [ ] "what kind of company is ○○", "○○ reputation", "○○ reviews", "what is it like to work
      at ○○", "alternatives to ○○"
- [ ] **Write down every source URL** that appears. That list *is* your reputation surface inventory
- [ ] Open each URL and record its **last-updated date** and any **factual errors**
- [ ] Run the same questions for competitors — this reveals which surfaces actually get cited

## 3. Split into controllable and uncontrollable

The response differs completely, so keep the inventory in two columns from the start.

| | Surfaces | Response |
|---|---|---|
| **Controllable** | own careers page, employer profiles on job boards, business and map profiles, trade-association member profiles, app store listings | Update directly. Reuse the wording fixed in Phase 2 **verbatim** |
| **Uncontrollable** | wiki-type articles, community posts, reviews, news coverage | Continuous monitoring + request corrections **for factual errors only** (`measure.md` §7) |

⚠️ Do not try to control the uncontrollable column. Pressuring for deletions or running
astroturf campaigns becomes its own reputation event. You have exactly two moves:
① correct factual errors ② strengthen your own evidence.

## 4. Job boards and review platforms — the core of the reputation axis

These are the surfaces most often cited for company-reputation queries. And in most companies
**nobody owns them.**

- [ ] Employer profile on job boards: industry, headcount, founding year, address, flagship
      services — **are they current?**
- [ ] **Check the last-updated date.** A profile untouched for two-plus years may be the thing
      describing your company today
- [ ] Pull the **recurring themes** out of company and interview reviews, then split them:
      factual errors (correct them) versus real problems (fix the organization). Mixing the two
      means neither gets fixed
- [ ] Does the company blurb in your job postings **say the same thing as the umbrella message**
      (→ SKILL.md Phase 2)? Different descriptions per posting get learned as-is
- [ ] Business and map profiles: hours, phone, address **must match the website**
      (a mismatch is entity fragmentation — the same problem as `llmo.md` §1)
- [ ] Trade-association member profiles: the classic home of a stale boilerplate description
- [ ] Confirm these surfaces are listed in the `sameAs` array from `llmo.md` §1

## 5. Assign the owning department — this is the actual failure point

⚠️ **Reputation surfaces are frequently not marketing's job.** Job-board profiles and
company/interview reviews are effectively **HR and recruiting** assets; association profiles
belong to external affairs; map profiles often to facilities or admin.

- [ ] Write a **department and a named owner on every row** of the surface inventory.
      A blank cell means that surface is abandoned
- [ ] Set a cadence — **quarterly** for profiles, **monthly** for review monitoring
- [ ] Decide who judges a factual error and who sends the correction request (`measure.md` §7)

## 6. What not to do

- ❌ **Faking reviews** — paid testimonials, staff-mobilized ratings, reviews from friends.
  Getting caught does not end with a platform penalty; you acquire a new reputation as
  "the company that faked its reviews"
- ❌ Pressuring for deletion of negative reviews — the deletion attempt itself becomes the story
- ❌ Undisclosed community promotion — exposed once, the brand burns on that whole channel
- ✅ Instead: correct factual errors with evidence attached, fix the real problems, and put the
  fix on the record

## 7. Measurement

Reputation surfaces move slowly. Keep them out of the two-week loop and measure **quarterly**
(the same cadence as `llmo.md`).

```
[Quarter] 2026-Q3  5 reputation queries · 7 cited surfaces · 3 factual errors · 2 stale profiles
[Actions]          2 profiles updated · 2 correction requests sent · 1 handled by strengthening evidence
[Next]    2026-Q4 scheduled
```
