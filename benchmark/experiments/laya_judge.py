"""Can a typed-decision model (Laya) serve as Jude's redact/keep judge?

usage: laya_experiment.py [limit|balanced:N] [torch|mlx] [A|B|C]

For every candidate (gold span, public mention, whitelisted mention,
Jude false positive) on the held-out split, ask one question with the
sentence as state. Report accuracy by source and language, latency,
calibration, and a threshold sweep.
"""

import collections
import json
import random
import sys
import time
from pathlib import Path

S = Path(__file__).parent  # expects decision_set.jsonl next to this file
rows = [json.loads(l) for l in (S / "decision_set.jsonl").read_text(encoding="utf-8").splitlines()]
sel = sys.argv[1] if len(sys.argv) > 1 else "all"
backend = sys.argv[2] if len(sys.argv) > 2 else "torch"
variant = sys.argv[3] if len(sys.argv) > 3 else "A"

if sel.startswith("balanced:"):
    n = int(sel.split(":")[1])
    rnd = random.Random(7)
    red = [r for r in rows if r["expected"] == "REDACT"]
    keep = [r for r in rows if r["expected"] == "KEEP"]
    rnd.shuffle(red); rnd.shuffle(keep)
    rows = red[: n // 2] + keep[: n // 2]
    rnd.shuffle(rows)
elif sel != "all":
    rows = rows[: int(sel)]

# --- question variants ------------------------------------------------------
VARIANTS = {
    # A: long criteria, state = {sentence, expression}
    "A": lambda r: ({"sentence": r["context"], "expression": r["text"]}, {
        "verdict": {
            "type": "choice",
            "instructions": (
                "This expression appears in a legal working document that a lawyer wants to send to an "
                "outside AI service. Professional secrecy requires hiding anything that identifies a client, "
                "a counterparty, a private individual, or the matter. Should the expression be redacted "
                "(replaced by a pseudonym) or kept as it is?"
            ),
            "criteria": {
                "redact": ("a private company, law firm, bank, deal codename, private individual, a party's "
                           "address or city, an internal file reference, a registration number"),
                "keep": ("a public institution, regulator, court, statute, treaty article, published judgment, "
                         "country, or a generic role such as 'the Buyer', 'our client', 'the undersigned'"),
            },
        }}),
    # B: yes/no (noul), expression first
    "B": lambda r: ({"expression": r["text"], "context": r["context"]}, {
        "private": {
            "type": "noul",
            "instructions": (
                f"In the context, is the expression \"{r['text']}\" the name of a private company, "
                "a private individual, a private address, a deal codename or an internal reference "
                "(something that identifies a client, a counterparty or a matter) — as opposed to a "
                "public institution, court, regulator, statute, published judgment, country or generic role?"
            ),
        }}),
    # C: compact choice, expression embedded in the instruction, three-way (public / role / private)
    "C": lambda r: ({"text": r["context"]}, {
        "kind": {
            "type": "choice",
            "instructions": f"What is \"{r['text']}\" in this text?",
            "criteria": {
                "private_party": "a private company, firm, bank, individual, address, codename or file reference",
                "public_body": "a public institution, court, regulator, statute, treaty, published judgment or country",
                "role_or_term": "a generic role or defined term (the Buyer, our client, the Firm, the undersigned)",
            },
        }}),
}
make = VARIANTS[variant]

t0 = time.time()
if backend == "mlx":
    import laya_mlx as laya
    agent = laya.load("aac6fef/laya-mlx")
    ask = lambda state, q: agent.predict(state, q)  # noqa: E731
else:
    from laya import Router
    router = Router(preload=True)
    ask = lambda state, q: router.predict(state, q)  # noqa: E731
print(f"backend {backend} variant {variant}: loaded in {time.time()-t0:.1f}s; {len(rows)} items", flush=True)


def parse(result):
    answers = result.get("answers", result)
    name = next(iter(answers))
    ans = answers[name]
    if variant == "B":
        p = ans.get("probability", ans.get("p", ans.get("value")))
        if isinstance(p, dict):
            p = p.get("true", p.get("yes"))
        p = float(p) if p is not None else None
        return ("REDACT" if (p or 0) >= 0.5 else "KEEP"), p
    probs = ans.get("probabilities") or {}
    if variant == "C":
        p = probs.get("private_party")
        return ("REDACT" if ans.get("choice") == "private_party" else "KEEP"), p
    return ans.get("choice", "").upper(), probs.get("redact")


out = []
t0 = time.time()
for i, r in enumerate(rows):
    state, q = make(r)
    res = ask(state, q)
    if i == 0:
        print("RAW:", json.dumps(res, ensure_ascii=False)[:300], flush=True)
    label, p = parse(res)
    out.append({**r, "pred": label, "p_redact": p})
dt = time.time() - t0
print(f"{len(rows)} questions in {dt:.1f}s = {1000*dt/len(rows):.0f} ms/question", flush=True)
(S / f"laya_{backend}_{variant}_{sel.replace(':', '')}.jsonl").write_text(
    "\n".join(json.dumps(o, ensure_ascii=False) for o in out), encoding="utf-8")


def acc(items):
    ok = sum(1 for o in items if o["pred"] == o["expected"])
    return ok, len(items), (ok / len(items) if items else float("nan"))


print("\n== accuracy by source ==")
for src in ("gold", "public_span", "whitelist", "jude_fp"):
    items = [o for o in out if o["source"] == src]
    if items:
        ok, n, a = acc(items)
        print(f"  {src:12s} expected {items[0]['expected']:6s} {ok:4d}/{n:<4d} = {a:.3f}")
print("== by language ==")
for lang in ("en", "fr"):
    for exp in ("REDACT", "KEEP"):
        sub = [o for o in out if o["doc"].endswith("_" + lang) and o["expected"] == exp]
        if sub:
            ok, n, a = acc(sub)
            print(f"  {lang} {exp:6s} {ok:4d}/{n:<4d} = {a:.3f}")
print("== by gold type (REDACT items) ==")
for t in ("PERSON", "ORG", "LOC", "CASE_REF"):
    sub = [o for o in out if o["source"] == "gold" and o["type"] == t]
    if sub:
        ok, n, a = acc(sub)
        print(f"  {t:9s} {ok:4d}/{n:<4d} = {a:.3f}")
ok, n, a = acc(out)
red = [o for o in out if o["expected"] == "REDACT"]
keep = [o for o in out if o["expected"] == "KEEP"]
bal = 0.5 * (acc(red)[2] + acc(keep)[2]) if red and keep else float("nan")
print(f"== overall {ok}/{n} = {a:.3f}; balanced accuracy {bal:.3f} ==")

ps = [o for o in out if isinstance(o.get("p_redact"), (int, float))]
if ps and red and keep:
    print("== calibration (p_redact bin → share actually REDACT, n) ==")
    bins = collections.defaultdict(list)
    for o in ps:
        bins[min(int(o["p_redact"] * 5), 4)].append(o["expected"] == "REDACT")
    for b in sorted(bins):
        v = bins[b]
        print(f"  [{b/5:.1f}–{(b+1)/5:.1f})  actual REDACT {sum(v)/len(v):.2f}  n={len(v)}")
    # AUC (rank-based): does the score separate the classes at all?
    pr = sorted(o["p_redact"] for o in ps if o["expected"] == "REDACT")
    pk = sorted(o["p_redact"] for o in ps if o["expected"] == "KEEP")
    import bisect
    wins = sum(bisect.bisect_left(pk, x) + 0.5 * (bisect.bisect_right(pk, x) - bisect.bisect_left(pk, x)) for x in pr)
    print(f"== AUC {wins / (len(pr) * len(pk)):.3f} ==")
    print("== sweep: threshold on p_redact → REDACT recall / KEEP accuracy ==")
    for th in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
        rr = sum(1 for o in pr if o >= th) / len(pr)
        ka = sum(1 for o in pk if o < th) / len(pk)
        print(f"  th {th:.1f}: REDACT recall {rr:.3f}   KEEP accuracy {ka:.3f}   balanced {(rr+ka)/2:.3f}")

print("\n== sample errors ==")
errs = [o for o in out if o["pred"] != o["expected"]]
for o in errs[:14]:
    p = o.get("p_redact")
    print(f"  [{o['source']:11s} exp {o['expected']:6s} p={p if p is None else round(p, 2)}] {o['text']!r}  ⟵ {o['context'][:80]!r}")
