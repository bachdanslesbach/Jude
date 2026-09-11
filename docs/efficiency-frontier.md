---
title: Efficiency frontier
layout: default
---

# Where the efficient point is — speed, size, and what a firm actually needs

The question, as put by a collaborator: fine-tuning a huge model will
always beat a tiny one, with steeply diminishing returns; so place the
blockers on logarithmic scales first — *one page in 10 s, one page per
second, ten pages per second; 0.1 B, 1 B, 100 B parameters* — and refine
around the operating point afterwards. This page does that in two
halves: what the demand side needs (a law firm, a lawyer bound by
professional secrecy), and what the supply side buys at each rung,
measured on the benchmark corpus.

## Units

A *page* here is 3,000 characters — about 450 words or 700 tokens of
legal English or French; a 20-page memo is 60,000 characters. The
harness measures characters per second, one runner per process, model
load excluded; pages per second is that figure divided by 3,000.

## Demand: what has to be true for a lawyer to use it

### 1. Latency, not throughput, is what a user feels

Three usage patterns, three different numbers:

| Pattern | Volume | What "fast enough" means | Pages / s needed |
|---|---|---|---|
| Interactive — one lawyer, one document, before sending it to an LLM | 2–40 pages | A spinner the user tolerates: ~5 s for a 5-page letter, under a minute for a 40-page brief | **≈ 1** per user, on the machine that runs it |
| Batch — a data room, a disclosure set, an archive | 1,000–100,000 pages | Overnight | 10,000 pages in 8 h = **0.35** sustained |
| Firm-wide peak — a shared server | 300 fee-earners, a third active in the same hour, 20 pages each | Nobody queues | 1,800 pages/h ≈ 0.5 average, **≈ 2–5** at peak |

So the log ladder reads: **0.1 page/s** is tolerable on a laptop with a
progress bar (a 40-page brief in seven minutes — annoying, not
blocking); **1 page/s** is comfortable single-user; **10 pages/s** is a
firm-scale shared server. Nothing in a law firm needs 100 pages/s.
Throughput is almost never the blocker; the blocker is *where* the
computation is allowed to run.

### 2. Where it may run

Professional secrecy (Belgian Art. 458 Code pénal, the French *secret
professionnel*, GDPR Art. 28) does not forbid computation; it forbids
disclosure. Three tiers pass that test, with very different budgets:

| Tier | Typical hardware | Model budget | Who |
|---|---|---|---|
| Laptop | Apple M-series, 8–16 GB unified memory; Windows laptops without a GPU | Encoders ≤ ~1 B (bf16), quantised LLMs ≤ 4 B; CPU-only inference must remain acceptable | Solo practitioners, small firms — the majority of the bar |
| Firm server | CPU-only 64–256 GB (most mid-size firms); one or two GPUs at the larger ones (Latham & Watkins bought NVIDIA servers in 2026) | Encoders ≤ 1 B on CPU with batching; LLMs 7–14 B on one GPU; 70 B needs several | Mid-size and large firms |
| EU sovereign cloud (OVH, Scaleway; not under the US CLOUD Act) | Rented GPU instances | 70–100 B possible — but "local" has become a contract rather than a machine, and every page has a price | Large firms with an IT function willing to sign the DPA |

**100 B on premises is out for all but a handful of firms**, and — see
the supply side — it is not needed for the extraction task. Anything
that must run on the majority tier has to be ≤ 1 B and fast on CPU.

### 3. What a lawyer will and will not pay for

The asymmetry that shapes everything: a missed identifier is a
potential breach of professional secrecy — liability, reputational
harm, possibly a bar complaint. An over-redaction is a worse answer
from the LLM and some review time. The two errors are not symmetric,
so F1 is the wrong objective. The objective is:

* **recall → 1**, with the residual closed by a *cheap, fail-closed
  review* — the unverified-term report puts every capitalised term the
  detector did not touch in front of the lawyer, who reviews anyway;
* **precision high enough that the LLM's answer stays useful** — the
  *public-body over-redaction* metric: a memo in which every mention
  of the Commission or the DMA reads `Org7` is not "safe", it is
  useless;
* **review cost bounded** — of the order of ten items per page, a
  minute of attention.

Would a lawyer accept "100 % recall at any cost" — a 300 B model, or a
system that redacts half the words? No. A 300 B model at one page per
ten seconds on a €50,000 server is not the answer when a 0.5 B encoder
plus rules plus a review report reaches recall 0.998 on the tuning set;
and a system that over-redacts destroys the reason for sending the
document to an LLM at all. What the lawyer accepts is (i) a review
step — there is one anyway, it is the job — and (ii) false positives
up to the point where the answer degrades. The operating point is
therefore: **recall ≥ 0.99 by machine, precision ≥ 0.85, public-body
over-redaction ≤ 5 %, ≤ 10 review items per page, ≥ 1 page/s on the
majority tier.**

## Supply: what each rung of the size ladder buys

Measured on the benchmark corpus with the same harness, one runner per
process, on an Apple M2 with 8 GB (a deliberately modest machine — the
majority tier). *This section is filled from `benchmark/results/`;
the numbers below are the current run.*

<!-- LADDER_TABLE -->

<!-- LADDER_CHART -->

### Reading the curve

<!-- LADDER_READING -->

## The efficient point

<!-- CONCLUSION -->
