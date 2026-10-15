---
title: Review before send
layout: default
---

# Review before send

*Design for the screen a lawyer sees after Jude has redacted a document
and before anything is sent to an outside LLM. Written 15 October 2026
from the winning proposal of a four-way design round ("What leaves — a
residual-risk ledger as the review step"), with the ideas the three
judges asked to graft from the other three, and with every gap they
found in all four. This is the plan the team builds from.*

Contents: 1 Why the review carries the recall · 2 Principles · 3 The
screens · 4 Interactions and keys · 5 The flow and its time budget ·
6 What the matter remembers · 7 Data model · 8 Streamlit now, React/Tauri
later · 9 Metrics · 10 Risks and open questions · 11 Résumé pour Etienne.

---

## 1. Why the review step carries the recall

On the held-out split of the benchmark — twenty-five documents never
consulted while tuning — Jude's detector reaches recall 0.89 and
precision 0.64 (`benchmark-pii-models.html`, *The generalisation gap*).
Recall 0.89 means 142 of 1,627 gold identifiers reached the redacted
text in clear. They fall in five classes the taxonomy counts exactly:
28 registry numbers (`0712.445.303`, `HRB 71244`), 29 reference formats
the regex has not seen (`A/26/02371`, `LH/2026/0583-TRV`), 25 bare short
forms of organisations (`Valdoire` after *Valdoire Holdings NV*), 36
surname-only repeats (`Herbiet` ×3, `Thonnard`), and 24 postcode-and-city
lines and venues (`1040 Brussels`, `Hotel Löwenkranz`). The rules alone
sit at recall 0.57 with precision 0.95; the neural layers buy 32 points
of recall for 31 points of precision. No version of the detector will
reach 1, and `towards-recall-one.html` says where the guarantee has to
live instead: in a review that is cheap, exhaustive and fail-closed. The
lawyer is the last filter; the detector exists to make that filter
affordable.

Today's filter is not affordable and not exhaustive. The review panel
(`src/jude/ui/app.py`, `_render_review_panel`, lines 502–617) shows a
10-page document — about 30,000 characters — in a 320-pixel `<pre>` and
a 320-pixel text area, side by side; the unverified-term report
(`src/jude/review.py`) adds up to 80 checkbox rows, and each "Redact
selected & re-check" re-runs the whole detector (5.5 s a page with
`jude-full`). The report puts 50 of the 142 misses in front of the
reviewer at 22 items per 1.8-page document — the other 110 are numbers,
lower-case domains and all-caps short forms the capitalisation heuristic
cannot list (§7 of the benchmark). On the other side, 30 % of the 496
whitelisted public-sphere mentions (*Auditorat*, *Cour des marchés*,
*ONSS*) are hidden, 13 published citations are typed as live case
references, and 46 bare short forms are given the wrong type; none of
that can be undone from the panel. The objective of `efficiency-frontier.html`
is recall → 1 *by the human* at a bounded cost — about ten items a page,
a minute of attention a page — with precision high enough that the
answer stays useful. This document designs the step that meets it: a
queue of everything Jude did not decide, a proposal on every item, one
key per decision, nothing undecided allowed to leave, and a matter that
remembers so the tenth document costs a tenth of the first.

## 2. Principles

1. **Fail-closed.** Every item in the queue carries a proposal; the
   proposal is *hide* unless a rule says the term is public. Nothing
   undecided can be approved; there is no "acknowledge and continue",
   no cross-page "accept all", and a keep without a named reason lasts
   one turn only. The gate is state-based: closing a dialog never
   approves.
2. **Inspect in place.** Decisions are taken on the item, with its
   context, not on two scroll boxes. The document is on screen as a
   coloured map in the Word legend the reviewer already uses
   (`annotation-protocol.html`); the queue is the work surface. A
   decision re-applies `redact()` to the stored spans — never a
   detector re-run.
3. **Group by entity, then by shape.** Thirty-seven spans on a page are
   twenty-two surfaces and one question each; four invoice numbers of
   one shape are one question. Same-entity proposals come first,
   because every link removes items downstream.
4. **Remember per matter.** Hide, keep, same-as, type, shape, codename
   policy and generalisation are each a row next to the pseudonym
   dictionary; the next document of the matter asks only what is new,
   and the header says so in one line.
5. **Show what leaves — all of it.** The approval is a signature on a
   manifest: this turn, the earlier turns re-sent as context (the
   lawyer's and the model's), attachment names, smart-mode tags, Jude's
   fixed instructions, the resolved destination host and model, with
   the SHA-256 of the exact request bytes, written to the local record
   *before* the network call and re-verified at send time.
6. **Everything on the lawyer's machine, measured, not asserted.** The
   status line "nothing has left your computer" is backed by a local
   count of outbound connections, and every outbound call — LLM,
   Wikipedia lookup, model download — passes through one gate that
   refuses hosts outside the approved one.
7. **Plain words, two languages, a third ready.** Hide / Keep / Same as
   / Mark, never ORG or spaCy in the main surface; every string comes
   from one table with `en`, `fr` and an empty `nl` column from the
   first commit; keys are printed on the buttons and identical in both
   languages.

## 3. The screens

Layout: `st.set_page_config(layout="wide")` as today. Column widths are
45 / 55 for the document map and the queue. All wireframes are the
English UI; the French strings are in §4.

### Screen 0 — Preparing (nothing has left)

Replaces the chat input while `prepare_turn` runs. Today the lawyer
sees a spinner (`app.py` 756–774); with `jude-full` on a 10-page
document that is 55 s of silence, long enough to click again or close
the tab and lose the session.

```
┌ Jude · Kestrel / Zeta · strict · claude-sonnet-4-5 @ api.anthropic.com ─────────────────────┐
│                                                                                              │
│  Preparing your text for review — nothing has left your computer.                            │
│  Outbound connections this session: 0                                                        │
│                                                                                              │
│  spa-excerpt.docx   10 pages · 30 412 characters read                                        │
│     not read, therefore not sent: 3 comments · 2 tracked changes · 1 image (OCR is off)       │
│                                                                                              │
│  ▮▮▮▮▮▮▮▮▮▮▮▮░░░░░░░░  finding names and references (pass 2 of 2)             ~18 s left     │
│  Readers running: rules · your dictionary · firm list · spaCy (fr, en) · GLiNER small        │
│                                                                                              │
│  Then: a list of what Jude did not decide, for you to confirm — about 10 items a page.       │
│                                                                                              │
│                                  [ Esc  Cancel — keep my text ]                              │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

What is on it: a progress bar with the stage name (pass 1, pass 2, item
builder) and the time estimate from the size ladder (1.0 s/page without
GLiNER, 1.8 s/page with GLiNER small, 5.5 s/page `jude-full`,
`efficiency-frontier.html`); the attachments with pages and characters
*read* and what the adapter did **not** read (comments, tracked changes,
images without OCR, footnotes) — the lawyer must know what did not go as
well as what did; the list of readers (detectors) that actually ran, so
a silently absent GLiNER is visible rather than a 0.89 review that is
really a 0.57 one; and the outbound-connection counter from the network
gate (§7, `network_log`). Esc cancels and returns the typed text to a
text area to copy (Streamlit's `st.chat_input` has no `value` parameter,
so the input cannot be pre-filled; the React/Tauri app restores it).

### Screen 0b — Lookups gate (only when Wikipedia enrichment is ticked)

Today the Wikipedia lookup fires inside `redact()` during
`prepare_turn` (`src/jude/redact.py` 64–68, via `chat.py` 120–127,
toggled at `app.py` 241–254): canonical names leave the machine before
any approval. The lookups move behind their own gate, before the review
queue, because the tags they produce are text that must be reviewed.

```
┌ BEFORE REVIEW · Look up 4 names on Wikipedia?                                                ┐
│ You ticked "Enrich smart-mode context from Wikipedia". That sends these names, in clear, to  │
│ wikipedia.org, which logs your address and the query:                                        │
│   [x] Kestrel Foods NV   [x] Zeta Holdings Ltd   [ ] Thomas Herbiet   [x] Cour des marchés   │
│ Untick a name to skip it. Nothing else is sent.                                              │
│                  [ Send these 3 names to Wikipedia ]        [ Skip — review without tags ]   │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

Each confirmed lookup writes an `approvals` row with `endpoint_host =
'en.wikipedia.org'` and the list of names: the same record as a send,
because it is one.

### Screen 1 — The review queue

```
┌ Kestrel / Zeta · strict · claude-sonnet-4-5 @ api.anthropic.com · 10 p · 30 412 chars · ~7 600 tok ┐
│ Nothing has left your computer (0 connections).  To decide 23 of 97 ▮▮▮▮▮▮▮░░░  Risk ● MEDIUM (3 ¶)│
│ Scope: whole document ▾   First document of this matter — Jude knows nothing about it yet;        │
│ every decision here is kept; the next document asks only what is new.                             │
├─────────────────────────────────────────────┬─────────────────────────────────────────────────────┤
│ DOCUMENT  (colour = what will happen)       │ TO DECIDE · page 3 / 10          ⏎ accept   ↑↓ move │
│ ▌1.  SHARE PURCHASE AGREEMENT               │                                                     │
│ ▌    between [Kestrel Foods NV→Org1] and    │ SAME ENTITY?                                        │
│ ▌    [Zeta Holdings Ltd→Org2], registered   │ ▶ Herbiet ×3 — same person as Person2 (Thomas       │
│ ▌    under ⟦HRB 71244⟧ …                    │   Herbiet)?          ¶3 "…the Seller's CFO, ⟦Herbiet⟧…"│
│ ▌                                           │   proposal: YES → hidden as Person2      [S] [H] [K]│
│ ▌3.  The Seller ([Thomas Herbiet→Person2])  │                                                     │
│ ▌    … ⟦Herbiet⟧ confirmed on 12 March 2026 │ REFERENCES AND NUMBERS                              │
│ ▌    that the price of EUR 186,500,000 …    │   HRB 71244   registry number ×2   ¶1 ¶9            │
│ ▌                                           │   "…GmbH, ⟦HRB 71244⟧, Amtsgericht Köln…"            │
│ ▌    the ⟦Auditorat⟧ and the ⟦Cour des      │   proposal: HIDE as Registry number     [H] [K] [T] │
│ ▌    marchés⟧ …                             │   F26-11xx    4 invoice numbers, one shape          │
│ ▌    Our ref. ⟦LH/2026/0583-TRV⟧            │   proposal: HIDE all 4 (ruling 7)       [H] [K] [T] │
│ ▌                                           │                                                     │
│ legend ■Person ■Organisation ■Place         │ NAMES AND TERMS                                     │
│        ■Reference ■Registry number          │   Auditorat   public body? ×4                       │
│        ░ public, kept   ⟦ ⟧ to decide       │   proposal: KEEP (public)   [K] [⇧K matter] [H]     │
│        ▌ gutter = paragraph risk ● ● ○      │   Thonnard    surname? ×3   "…Mr. ⟦Thonnard⟧ confirmed…"│
│                                             │   proposal: HIDE as Person              [H] [K] [T] │
│                                             │   … 5 more on this page                             │
│                                             │                                                     │
│                                             │ CONFIRM — found by a rule or your dictionary (9)    │
│                                             │   [Org1 ×12] [Person2 ×6] [Email1] [Iban1] [Case1] …│
│                                             │   ⇧⏎ confirm these 9                                │
│                                             │ ▸ Hidden on a guess alone (9) — check that none is  │
│                                             │   a public body; K keeps it                         │
├─────────────────────────────────────────────┴─────────────────────────────────────────────────────┤
│ [M] Mark a term Jude did not see…   [U] Undo   [L] Legend   [Esc] Back to editing                 │
│                                       Approve & send: not yet — 23 items still to decide          │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Header strip.** Matter, mode, model and the *resolved* destination
host (what the client will actually connect to, after `ANTHROPIC_BASE_URL`
and `HTTPS_PROXY` are read — today `AnthropicClient` is built with no
`base_url`, `anthropic_client.py` 27, so the SDK honours both silently);
size in pages, characters and tokens; the outbound-connection count;
progress "to decide N of M"; the worst paragraph risk. The **scope**
control restricts the turn to a paragraph range ("¶ 3–7 and my
question"): everything outside the range leaves neither the machine nor
the queue — the cheapest privacy lever on a 40-page brief. On the first
document of a matter the banner says that Jude knows nothing yet and
that every decision is kept; on later documents it says why the list is
short: *"4 new names, that is all — 52 terms hidden by your earlier
decisions [show anyway]"*.

**Blocking strip** (red, above the queue, only when needed). Approve
stays disabled with the reason and a one-click fix:

```
│ ⛔ Cannot send yet: spa-scan.pdf produced 0 characters for 6 pages — scanned? [Enable OCR] [Remove]│
│ ⛔ Cannot send yet: the tag for Org1 contains its own name ("Kestrel …")           [Edit tag]      │
│ ⛔ Cannot send yet: smart mode on a cloud endpoint without attestation   [Switch to local] [Attest]│
```

Issues: an attachment that produced fewer than 200 characters per page
(a scanned PDF with OCR off is indistinguishable from an empty one —
`PdfAdapter.read` defaults to `enable_ocr=False`); a `<could not read …>`
placeholder (`chat.py` 86–90); a smart-mode tag containing the canonical
name (`risk.py` 151–154); a SECRET detection; smart mode + cloud + no
attestation (`app.py` 738–748); a destination host that is not the one
the matter names; a required reader (GLiNER, spaCy model for the
document's language) that failed to load.

**Left: the document map.** The whole raw text as `st.html`, every span
coloured in the Word legend (yellow person, green organisation,
turquoise place, pink reference, violet registry/account, grey = public
kept), undecided items boxed `⟦ ⟧`, the current item outlined, each
span underlined in a type-specific style so colour is not the only
encoding, a `title=` tooltip with surface, type, pseudonym, which reader
found it and its confidence (`Detection.source` / `confidence`,
`types.py` 38–48). A left gutter bar coloured by the paragraph's risk
score (`risk.py` `_split_paragraphs`, scoring mentioned entities only —
see §10). A toggle **Original | As the model will read it** swaps the
text under the same marks; in the outgoing view the originals appear
only as tooltips, never in the text.

**Right: the queue**, one page of ten items, exactly one current item.
Four groups, in this order on every page:

* **Same entity?** — a bare surname against a PERSON entity, a short
  form against an ORG, a defined alias in parentheses, two surfaces the
  alias lookup refused as ambiguous (`store.py` 351–353). Proposal: the
  link. Decided first because each one removes items from the groups
  below.
* **References and numbers** — identifier-shaped tokens, digit runs of
  six or more with separators, prefix+number forms (`HRB 71244`), bare
  domains, attachment file names, postcode-and-city lines, grouped by
  shape into one item. Proposal: HIDE as Registry number / Reference /
  Place / Attachment, except a statute number or a published citation
  shape (KEEP, ruling 2).
* **Names and terms** — the capitalised terms of `review.unverified_terms`,
  with a proposal from shape: honorific + token → Person; legal-form
  suffix → Organisation; venue or street word → Place; whitelist
  near-match, institution noun (`patterns.py` `_INSTITUTION_NOUNS`),
  role phrase or all-caps heading line → KEEP. A first `Project X` in
  the matter raises one item: *"Is the codename itself confidential in
  this matter?"* (ruling 1), answered once.
* **Confirm** — detections whose source is deterministic (regex,
  pattern, known, dictionary, firm list; `_SOURCE_PRIORITY` in
  `detect/__init__.py` 22–31) or whose entity the lawyer already
  confirmed in this matter, shown as chips with counts. These are not
  questions; Shift+Enter confirms the chips of the current page in one
  stroke. Attention goes where the uncertainty is.

Below the groups, collapsed: **Hidden on a guess alone (N)** — spans
whose only source is spaCy, GLiNER or the privacy filter, with K to keep
and Shift+K to keep for the matter. Optional, because hiding is the
safe direction; this is where the 30 % public-sphere over-redaction is
corrected and learned. Smart-mode tags filled in this turn appear here
too, as text that leaves.

Each item shows: surface, shape guess in words, count, paragraph
numbers, up to three contexts (`UnverifiedTerm.context`), the proposal,
and the keys as buttons. The footer carries the M, U, L and Esc actions
and the disabled Approve with the count that blocks it.

### Screen 2 — Re-identification signals (second phase of the queue)

Once every term is decided, the queue column lists paragraphs instead
of terms: only those that contain a pseudonym *and* a date, currency
figure, bare large number, percentage or case citation
(`risk.py` `_gather_paragraphs_containing`, extended), worst first.

```
┌ SIGNALS — kept by default; listed because a pseudonym shares the paragraph      2 of 5 ¶ left ┐
│                                                                                                │
│ ¶ 3   ● HIGH (4)   Org1, Person2                           [read ¶3 as the model will see it]  │
│   EUR 186,500,000     amount      proposal: KEEP                                   [K] [G] [H] │
│   31 March 2027       date        proposal: KEEP                                   [K] [G]     │
│   Case T-274/01       citation    proposal: KEEP (published = public, ruling 2)    [K] [H]     │
│                                                                                                │
│ ¶ 7   ● MEDIUM (2)  Org2                                                                       │
│   218,400 data subjects  count    proposal: KEEP                                   [K] [G]     │
│   0712.445.303        registry    already HIDDEN as Reg1                                       │
│                                                                                                │
│ ○ 9 paragraphs carry dates or amounts with no pseudonym nearby: not listed                     │
│                                                                                                │
│ Why this list: a pseudonym next to a unique figure can be re-identified — a price that was in  │
│ the press names the deal whatever we call the parties. Dates and amounts are not identifiers   │
│ (annotation protocol); G rewrites one as an approximation, H removes it from the analysis.     │
│                                                                                                │
│ Sensitive matter: OFF — on, G becomes the proposal in HIGH paragraphs       [toggle · ⇧S]      │
│                           [ ⏎ accept proposal ]   [ ⇧⏎ accept all 5 on this page ]            │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

KEEP is always the default: in a competition or damages matter the
figure *is* the legal question, and a tool that offers to change the
facts will not be trusted. GENERALISE is a proposal only when the
matter is marked sensitive and the paragraph scores HIGH. A generalised
figure is **not** rehydrated in the answer — the lawyer reads what the
model reasoned on, and the chat bubble says "1 figure generalised".
Shift+Enter is allowed here because every item's proposal is KEEP (the
text is unchanged); the exception is a HIGH paragraph in a sensitive
matter, whose items must be taken one by one. Generalisation ships in
v2 (§8); in v1 the G key is absent and this screen is a list of
paragraphs to read.

### Screen 3 — What leaves (the gate)

A modal (`st.dialog`) that opens only when the queue is empty and no
blocking issue remains. Dismissing it returns to the queue; it never
approves.

```
┌ WHAT LEAVES YOUR COMPUTER                                       ⌘⏎ Approve & send    Esc Back ┐
│ To: api.anthropic.com (resolved now · no proxy) · claude-sonnet-4-5 · cloud · strict          │
│     + Jude's fixed instructions to the model (1 212 chars)                           [view]   │
│ Readers that ran on this turn: rules · your dictionary · firm list · spaCy fr/en · GLiNER small│
│                                                                                               │
│ 1  THIS TURN   30 412 chars · ~7 600 tokens · scope: whole document                           │
│    hidden        41 names/references → 23 pseudonyms (Org 9 · Person 11 · Case 2 · Reg 1)     │
│    kept          14 terms you chose to leave visible: Auditorat, Cour des marchés, Art. X.36…  │
│    kept together ¶3: Org1 + EUR 186,500,000 + 31 March 2027  ● MEDIUM     [read ¶3 as sent]   │
│    attachment    spa-excerpt.docx → name hidden as Attachment1 · 10 pages read                │
│                  not read, therefore not sent: 3 comments · 2 tracked changes · 1 image        │
│    still useful? 0.8 pseudonyms per 100 words · 0 public bodies hidden · 9 hidden on a guess   │
│                                                                                               │
│ 2  RE-SENT AS CONTEXT   6 earlier messages · 12 380 chars · approved 14:02, 14:09, 14:21      │
│    ⚠ your message of 14:02 contains "Thonnard" in clear — you hid it today.                   │
│    ⚠ the model's reply of 14:03 names "Kestrel" — it guessed. Re-redacted before re-sending.   │
│    [Re-redact history before sending]   (recommended; "Thonnard" already left at 14:02)       │
│                                                                                               │
│ 3  RESIDUAL RISK   ● MEDIUM — Org1: amount + date in ¶3 · Person2: date in ¶3                 │
│    [Run local second reader (Ollama, ~90 s, nothing leaves)]                                  │
│    last run: "parties: a Belgian food group, a UK holding; identifying detail: the price"      │
│                                                                                               │
│ ▸ Show the exact text that leaves (30 412 chars, as the model will read it)                   │
│ request sha256 7f3a…c91e — the bytes the client will send · verified again at send time       │
│                                                                                               │
│ Approving as: Etienne Perrin (this Mac) · prepared by: you · 6 min 12 s of review             │
│ "I reviewed the 97 items listed and the 3 paragraphs marked MEDIUM or HIGH. The exact text    │
│  was shown to me." — recorded on this machine with the hash; nothing is sent until you press. │
│                          [ ⌘⏎  Approve & send ]            [ Esc  Back to review ]            │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

Sections, top to bottom: the **destination** as the client resolved it
now, with the model and mode, and Jude's fixed system prompt
(`llm/base.py` `JUDE_SYSTEM_PROMPT`, prepended by both clients) with a
viewer — payload part 1, which no screen shows today; the **readers**
that ran; **this turn** with counts and lists, the attachments (read and
not read), the *kept together* line (the joint view of what is kept in
one paragraph — a public body plus a published citation plus a date can
identify a matter together even when each is public alone) and the
*still useful?* line (pseudonym density, public bodies hidden, spans
hidden on a neural guess alone) so precision has a reading too; the
**re-sent context** — every earlier message, the lawyer's *and the
model's*, with two warnings: a surface the lawyer has since hidden
appears in clear in an earlier turn (late correction), and an earlier
*reply* names an entity or looks like a re-identification (the model's
replies are stored as `redacted_text` and re-sent every turn, `chat.py`
159–162; today nobody reads them); the **residual risk** per entity and
the optional local second reader (lever 4 of `towards-recall-one.html`;
it never gates); the exact text, collapsed; the **two hashes** — of the
canonical message list and of the serialised request body the client
will put on the wire; the **approver** (OS user and the name set once in
settings), who prepared the session if it was handed over, the review
time; and the **attestation sentence**, which says exactly what was done
and nothing more: items reviewed, risk paragraphs read, exact text
shown. "Read in full" is claimed only when the lawyer opened the full
text and, in the desktop app, scrolled it to the end; the Streamlit
version records `text_opened`, never `text_read`.

### Screen 4 — Item detail (T)

A popover over the queue for the current item.

```
┌ Thonnard — surname?  ×3                              type: [1] Person [2] Organisation [3] Place┐
│                                                            [4] Reference [5] Registry number    │
│ ¶3  "…Mr. ⟦Thonnard⟧ confirmed on 12 March 2026 that…"                                          │
│ ¶5  "…⟦Thonnard⟧'s e-mail of 2 April…"                                                          │
│ ¶9  "…counsel for ⟦Thonnard⟧…"                                                                  │
│                                                                                                │
│ Looks like a surname used after first mention. Same person as someone already hidden?          │
│   [ — no — ▾ ]  Person2 (Thomas Herbiet) · Person3 (Luc Roelandts)   → adds a form, no new      │
│                                                                        pseudonym               │
│ If HIDDEN, Jude will also hide in this matter: "Thonnard's" · "THONNARD" · "T. Thonnard"        │
│   [x] hide these forms too                                                                     │
│ If KEPT:  (•) this turn only   ( ) for this matter, as: [1] role [2] public body [3] heading    │
│                                                        [4] published citation [5] other → once │
│                                                                                                │
│ Why Jude did not decide: not in the matter dictionary, no honorific, spaCy and GLiNER silent.  │
│ Proposal source: capitalised single word repeated mid-sentence → identifier shape.             │
│                        [ H  Hide ]      [ K  Keep ]      [ U  Undo last ]      [ Esc ]         │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

For a number the popover offers a **shape rule** with a preview:

```
│ 0712.445.303 — registry number?  ×1                                                            │
│ Shape \d{4}\.\d{3}\.\d{3} also matches in this document: 0845.112.907 (¶12) · 0401.336.221 (¶14)│
│   [x] hide every number of this shape in this matter (3 now, and in later documents)           │
```

One registry number becomes a rule for the matter (learning-first's
SHAPE), typed Registry number (`EntityType.IBAN` until a `REGISTRY_ID`
type exists, ruling 3) — but only after the lawyer has seen the matches
it will take, because an auto-derived `[A-Z]{3} \d{5}` on a financial
document over-matches in the fail-closed direction and eats precision
matter-wide.

Also in the popover: the propagation forms (surname, possessive,
all-caps, initials — lever 2), each untickable and stored with its
origin; the keep scope with a required kind (an unnamed reason —
"other" — is this turn only, never permanent); and for a codename item,
the matter policy: *"hide codenames in this matter"* flips
`Matter.redact_codenames` from where the word sits, not from the
sidebar.

**State D.** When the lawyer presses K on a surface whose pseudonym has
already been sent in this conversation, the popover says so and offers
two choices: *keep from the next conversation* (default — the model
never sees `Org2` and *Valdoire SA* side by side in one context window;
stored with `effective_from_conversation`) or *keep anyway, in this one
too* (logged). The opposite case — a name that left in clear earlier and
is hidden now — is stated honestly: *"left unredacted in your message of
13:40"*, with the incident path of Screen 6 one click away.

### Screen 5 — Matter memory (extends `pages/2_Entities.py`)

```
┌ MATTER MEMORY · Kestrel / Zeta   [Hidden 23] [Kept 14] [Rules 2] [Generalised 1] [Approvals 7] [Incidents 0]┐
│ KEPT — never asked again in this matter                                                                │
│  Auditorat           public body        14 Oct · doc 1    [revert → hide]   [propose to firm list]     │
│  Cour des marchés    public body        14 Oct · doc 1    [revert]          [propose]                  │
│  the Buyer           role               14 Oct · doc 1    [revert]      re-asks if seen with a suffix  │
│  C-746/21 P          published citation 14 Oct · doc 2    [revert]                                     │
│  Project Sable       codename — this matter does NOT hide codenames (ruling 1)  [hide codenames here]  │
│ HIDDEN — the dictionary                                                                                │
│  Org1    Kestrel Foods NV   forms: Kestrel Foods · KFN · Kestrel (surname rule)   by: rule + you       │
│  Person2 Thomas Herbiet     forms: Herbiet (you) · Herbiet's · T. Herbiet (initials)   risk last: MED  │
│ RULES — shapes you hid once, applied to every match                                                    │
│  \d{4}\.\d{3}\.\d{3}  registry number   6 matches in 3 documents   [revoke]                            │
│ APPROVALS                                                                                              │
│  14 Oct 14:02  "SPA review"  7 600 tok  api.anthropic.com  sha 7f3a…  97 items · 14 kept · 6 min 12 s  │
│  14 Oct 14:09  "SPA review"  1 200 tok  api.anthropic.com  sha 02b8…  ⚠ late correction: Thonnard      │
│ Pace: 41 decisions/min on doc 2 — your usual is 18.   Queue: doc 1 97 · doc 2 41 · doc 3 22  [details]│
│ [Export memory (.json, confidential)]  [Export kept terms as whitelist proposals]  [Your firm's list →]│
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Six tabs: Hidden (the existing dictionary with merge), Kept (per-matter
keep list with kind, origin, revert, and *propose to firm list* for
kinds that are true everywhere), Rules (shape rules with their match
counts), Generalised, Approvals (one row per send: hash, host, counts,
human seconds, late corrections), Incidents. The pace line compares
decisions per minute on this matter with the lawyer's own history, and
the queue-size line shows the curve that must fall. Exports reuse
`export_matter_json` (`store.py` 580–644) bumped to version 2.

### Screen 6 — Incident record (from an approval row)

When a surface is found to have left in clear — a late correction, a
reply that named a party, a term the lawyer notices afterwards — the
tool must produce the record a lawyer needs for the file, the
bâtonnier or the DPO, not just a counter.

```
┌ INCIDENT · "Thonnard" left in clear                                            matter Kestrel / Zeta ┐
│ What left     "Thonnard" (a person, hidden since 14 Oct 14:31 as Person4)                            │
│ When          14 Oct 14:02 (your message, approval #12, sha 7f3a…) · re-sent 14:09 and 14:21 as       │
│               context (approvals #13, #14)                                                           │
│ Where to      api.anthropic.com · claude-sonnet-4-5 · zero-retention: attested by you on 2 Oct       │
│ Also exposed  the model's reply of 14:03 repeats the surname once                                    │
│ Done since    history re-redacted at 14:31; nothing containing "Thonnard" will be re-sent             │
│ To do         [ ] deletion request to the provider — draft with message ids and timestamps  [draft]   │
│               [ ] note for the Art. 458 file                                                 [export]│
│ [Export incident record (.md + .json)]                                            [Close]            │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Screen 7 — Your firm (standing hide rules, once per machine)

The firm's own name, address, lawyers, e-mail domain and reference
format appear on every letter of every matter and tie each matter to
the firm. All four proposals learned per matter and none asked once.
A one-time page, reachable from the sidebar and from the first review:

```
┌ YOUR FIRM — hidden in every matter, on this machine                                            ┐
│ Firm name        Lefèvre Hardy & Partners   also: LH&P · Lefèvre Hardy      hidden as Org0      │
│ Address lines    Avenue des Arts 46, 1000 Bruxelles                                             │
│ People           Me Etienne Perrin · Me Anne Hardy · (add)                                      │
│ E-mail domain    @lhp.be                                                                        │
│ Reference shape  LH/\d{4}/\d{4}-[A-Z]{3}    preview: LH/2026/0583-TRV ✓                         │
│ Hiding is the safe direction: these rules only ever hide. Nothing here is shared with anyone.   │
│                                                                   [Save]  [Skip for now]        │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Applied by a `FirmDetector` at dictionary priority in every matter. A
*firm keep list* (public bodies, roles, citations promoted from matter
keep lists) is a separate, later feature with a conflict check (§6);
the two must never be one table.

## 4. Interactions and the keyboard map

The current item is application state, not DOM focus: one item is
current (the first undecided on the page), keys act on it and advance.
Every key is also a button that prints the key, so the mouse path is
the test path (`streamlit.testing.v1.AppTest`). Streamlit 1.57.0
supports `st.button(shortcut=…)` with single alphanumerics, Enter, Esc,
arrows, PageUp/PageDown and the Shift / Mod modifiers, and reserves
**C** and **R** (`streamlit/elements/widgets/button.py`, *shortcut*
docstring) — hence H for Hide. Keys are the same in both languages;
the verb beside the key changes.

| Key | Where | Does | English label | French label |
|---|---|---|---|---|
| Enter | queue, signals | Accept the proposal on the current item, advance | Accept | Accepter |
| Shift+Enter | Confirm chips; signals page with only KEEP proposals | Confirm every chip / accept every KEEP on this page; never on a *to decide* item, never across pages | Confirm page | Confirmer la page |
| ↑ ↓ | queue | Move the cursor within the page | — | — |
| PageDown / PageUp | queue | Next / previous page of ten (forward only once the page is decided) | Next page | Page suivante |
| H | item | Hide as the proposed type; derives propagation forms; re-applies `redact()` incrementally | Hide | Masquer |
| Shift+H | item | Hide, type picker first | Hide as… | Masquer comme… |
| K | item, chip, signal | Keep, this turn (`scope = once`) | Keep | Garder |
| Shift+K | item, chip | Keep for this matter — kind picker 1–5; kind 5 "other" falls back to once | Keep for this matter | Garder pour ce dossier |
| S | same-entity item | Same as… — picker of candidates; Enter confirms; adds a surface form, no new pseudonym | Same as… | Même entité que… |
| A | item showing a sibling form | Also hide the sibling shown in context (`F26-1190` beside `F26-1183`; *Herbiet* beside *Thomas Herbiet*) | Also hide | Masquer aussi |
| T | item | Detail popover (Screen 4): occurrences, type, same-as, propagation, keep scope, shape rule, why | Details | Détails |
| 1–5 | a picker | Person / Organisation / Place / Reference / Registry number — or keep kind role / public body / heading / published citation / other | — | — |
| G | signal (v2) | Generalise — cycles the proposals (amount → order of magnitude; date → month-year → `[date]`; percent → band); Enter fixes | Generalise | Généraliser |
| M | footer | Mark a term Jude did not see: a text input; Enter finds every occurrence (case-insensitive) and opens the type picker — the Streamlit substitute for select-text-and-hide | Mark a term | Marquer un terme |
| U | anywhere in the review | Undo the last decision (a `superseded_by` link, never a delete); Shift+U redo | Undo | Annuler la dernière décision |
| L | anywhere | Legend overlay: colours, keys, the three kinds of mark | Legend | Légende |
| Shift+S | signals | Toggle *sensitive matter* | Sensitive matter | Dossier sensible |
| Esc | popover → queue → chat | Close the popover; then *back to editing* (session stays open) | Back | Retour |
| Mod+Enter | the gate only | Approve & send (Cmd on macOS, Ctrl elsewhere; Streamlit prints the right one) | Approve & send | Approuver et envoyer |

Not keys, deliberately: *Discard review*, *Re-redact history*, *Run
local second reader*, *Enable OCR*, *Send names to Wikipedia* — each is
a button that names what it does.

**Click paths.** Click an item or its boxed span in the map → the detail
popover. Click a decided span → the same popover with *change decision*.
Click a chip → Keep / Keep for matter / Details. Click a paragraph in
the signals list → the paragraph in outgoing form. Hover a span → the
tooltip.

**What a decision does, in code.** `ReviewSession.decide()` appends a
`review_decisions` row, updates the entity dictionary (`create_entity`,
`add_surface_form`, `merge_entities` — `store.py` 362–493 — with
`decided_by = 'review'`), recomputes the effective span list (base
detections ∪ user spans − kept spans, replayed in decision order) and
calls `redact()` on it — milliseconds, never a detector run; today's
"Redact selected & re-check" (`app.py` 674–686) re-runs `prepare_turn`
and the whole pipeline. The `st.fragment` around the queue reruns only
the queue and the map.

**The trigger.** Send in the chat → `prepare_turn` runs locally →
`review_sessions` row with status `open` (today the `PreparedTurn` lives
only in `st.session_state` under `pending_review_<conv>`, `app.py`
462–464 and 773, and a browser refresh destroys twenty minutes of
decisions) → Screen 0 → optionally 0b → Screen 1. *Back to editing*
leaves the session `open`, listed under the conversation as *review in
progress*; a refresh or a restart resumes it. *Discard review* sets
`discarded`; entities created meanwhile stay in the dictionary (as
today, `chat.py` 107–108), listed under *Hidden on a guess alone* until
confirmed.

**The gate.** Queue empty, no blocking issue → Screen 3. Mod+Enter →
`ReviewSession.approve()` writes the `approvals` row (both hashes,
resolved host, model, counts, approver, attestation kind) **before** any
network call, flips the session to `approved`, then
`commit_streaming_turn` receives an `ApprovedPayload`, asks the client
to rebuild the request, compares the body hash and the host, refuses on
any mismatch (another tab, the CLI or the Entities page may have changed
the dictionary in between), sends, flips to `sent`. After the stream
ends the **reply scan** runs the detection pipeline and a surface-form
sweep over the model's reply; a canonical name, a stored surface form
or an identifier-shaped new term in the reply is recorded in
`messages.reply_scan_json`, shown as a chip on the bubble, and surfaced
on the next manifest. The chat bubble of a sent turn carries *approved
14:02 · sha 7f3a… · 97 items · 14 kept*, which opens the stored
manifest; the existing *View what the LLM actually saw* expander
(`app.py` 704–706) remains and shows the coloured outgoing text.

**Re-redact history.** Rewrites `messages.redacted_text` of earlier user
*and assistant* turns through the current dictionary, stores the
original under `redacted_text_before`, sets `reredacted_at`, logs
`history.reredact`, and records in the approval that the surface had
already left at the earlier timestamp.

## 5. The review flow, with a time budget

A page is 3,000 characters (`efficiency-frontier.html`, *Units*); the
document is a 10-page `.docx` of about 30,000 characters with a
question typed under it. Times are reading-speed estimates to be
replaced by the telemetry of §9; the first document of a matter is the
expensive one, and the design says so on screen rather than hiding it.

| Step | What happens | Machine | Attention, 1st document | Attention, 3rd document |
|---|---|---|---|---|
| 0 Trigger | Attach, type the question, Send | 0 | 0 | 0 |
| 1 Prepare | Two-pass detection (`redact_two_pass`), item builder (< 1 s), Screen 0 | 10 s no GLiNER · 18 s GLiNER small · 55 s `jude-full` | 0 | 0 |
| 2 Header | Destination, scope, size, "to decide N", worst risk, the first-document banner | — | 5 s | 5 s |
| 3 Blocking issues | Usually none; a scanned PDF, a leaking tag, a read error — one click each | — | 0–15 s | 0 |
| 4 Same entity? | ~4 surname / short-form / alias proposals, Enter or S | — | 16 s | 4 s |
| 5 References and numbers | 15–25 raw tokens grouped by shape into 8–12 items × 2.5 s; a statute or a published citation flipped to K | — | 25 s | 8 s |
| 6 Names and terms | Today 22 items on a 1.8-page document ≈ 12 a page → ~120 raw on 10 pages; links, the line-break fix and shape grouping bring it to 60–90 *to decide* items × 3 s; public bodies and roles go to Shift+K once | — | 180–270 s | 20 items → 60 s |
| 7 Confirm chips | Deterministic hits and confirmed entities, ~30 on a first document, ~60 on later ones; glance + Shift+Enter per page | — | 10 s | 20 s |
| 8 Signals | 3–8 paragraphs with a pseudonym and a figure, 5 s each; KEEP by default | — | 20–40 s | 10 s |
| 9 Spot-read | The 2–3 MEDIUM/HIGH paragraphs in outgoing form — the "read before you send" of the threat model, focused on where the risk is | — | 40–60 s | 20 s |
| 10 Second reader (optional) | Ollama on the redacted payload, lever-4 question; never gates | 60–120 s when used | 0 | 0 |
| 11 Manifest | Destination, this turn, context, risk, hashes, approver, Mod+Enter | — | 20–30 s | 15 s |
| 12 Record, verify, send | `approvals` row, rebuild + hash check, stream, reply scan | ~1 s + stream | 0 | 0 |
| **Total** | | **≈ 1 min** | **≈ 5½–7½ min** | **≈ 2½ min** |

Tenth document of the same matter: about 90 s of attention — a handful
of new names, the chips, one or two paragraphs, the manifest. The
demand-side budget is about ten items a page and a minute of attention
a page, i.e. ≤ 10 minutes for 10 pages: the first document lands inside
it, not at half of it; the third lands at a quarter. Items per page:
8–12 on a first document (the upper end is above the ≤ 10 target and is
measured, §9), ≤ 4 on the third, ≤ 2 on the tenth.

What the lawyer does *not* do in this flow: read 30,000 characters.
The attestation sentence says so (Screen 3). Proof-reading a page takes
about two minutes; a lawyer who wants that reads the outgoing view and
the record says `text_read` only when the desktop app saw the scroll
reach the end.

## 6. What is remembered per matter — and why the tenth document costs less

| Decision | Where it lives | Who consults it | Effect on the next document |
|---|---|---|---|
| Hide | `entities` + `surface_forms` (existing), stamped `decided_by`, `review_session_id`; derived forms with `derived_from` (surname, possessive, all-caps, initials, suffix-stripped) | `DictionaryDetector` at priority 1 on every turn | A surname hidden on document 1 is a Confirm chip on document 2, never a question. Closes the 36 surname-only and 25 short-form held-out misses |
| Same as | `review_decisions(kind='same_as')` + `add_surface_form` / `merge_entities` | dictionary; the ledger | The link is recorded as a decision, not only as a form, so the ledger shows who linked what |
| Keep | `matter_keep_terms(form, normalized, kind, scope, effective_from_conversation)` | `review.unverified_terms` (never re-listed); `redact()` beside `is_public_no_redact` (`redact.py` 47–49); the DictionaryDetector skips the form | *Auditorat* kept once stays visible in the matter; the 30 % public-sphere over-redaction costs one Shift+K per matter |
| Keep, once | `review_decisions(scope='once')` only | the pace line; the nudge | Not remembered — a one-off stays a one-off. The second *keep once* on the same surface makes the item propose Shift+K |
| Re-ask trigger | `matter_keep_terms.reask_on` (suffix / honorific / alias) | item builder | A kept role or defined term that later appears with *SA*, *Me* or a defined-alias parenthesis is asked once more — the guard against *Valdoire the product* becoming *Valdoire SA the party* |
| Type correction | `entities.entity_type` updated, new pseudonym from the new type's counter, old never reused (`store.py` 721–742) | redaction | The 46 ORG↔PERSON confusions are asked once per surface per matter; the ledger shows both pseudonyms |
| Shape rule | `matter_shape_rules(pattern, entity_type)` | a `ShapeDetector` at pattern priority | One registry number → every sibling in the matter; previewed before it is saved |
| Codename policy | `matters.redact_codenames` (exists) | `PatternDetector`, `SpacyDetector` | Asked once, on the first *Project X*, where the word sits |
| Sensitivity | `matters.sensitivity` | signals defaults, second-reader recommendation; the hook for lever 7 *paranoid mode* | — |
| Generalisation (v2) | `matter_generalisations(original, replacement)` | a post-redaction rewrite on every later turn | The model sees the same approximation every time; never rehydrated |
| Approval | `approvals` | the ledger; the incident record; the export | The lawyer's own record of what left, when, where |
| Firm identity | `firm_hide_terms` (machine-wide) | `FirmDetector` in every matter | The letterhead never enters a queue |
| Settings | `settings` | UI | language, approver name, page size, canary opt-in |

**The curve.** The queue on document *n* contains only surfaces that
are new to the matter. Expected on 10-page documents of one matter:
80–120 items on the first (97 in the wireframe), 30–50 on the third,
10–20 on the tenth — the same parties, the same public bodies, the same
headings, the same reference shapes. The header says why the list is
short so the lawyer trusts it. The curve is a metric (§9): a matter
whose third queue is not smaller than its first means the keep list or
the propagation is not firing.

**Firm-wide keep list (later, explicit).** Kinds *public body*, *role*
and *published citation* repeated in two or more matters may be
proposed for a machine-wide keep list, under a conflict check against
every surface form of every entity in every matter on the machine;
never PERSON, never a shape, never anything hidden anywhere. Exported
as grey-list candidates for Jude's bundled whitelist (lever 8). A keep
is right in one matter and wrong in the next (*Martin* the word, *Martin*
the surname), which is why promotion is a proposal with a button, not
a side-effect.

## 7. Data-model changes

All additions are idempotent: `CREATE TABLE IF NOT EXISTS` in `SCHEMA`
and the `PRAGMA table_info` → `ALTER TABLE ADD COLUMN` pattern of
`_migrate_v2` (`store.py` 120–134). The database stays one file,
`~/.jude/jude.db`, confidential as today (`store.py` 98–102).

```sql
-- One row per Send; replaces the Streamlit-only pending_review_<conv> blob.
CREATE TABLE IF NOT EXISTS review_sessions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    matter_id TEXT NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('open','ready','approved','sent','discarded')),
    raw_text TEXT NOT NULL,
    redacted_text TEXT NOT NULL,
    scope_json TEXT,                       -- null = whole turn; else {"paragraphs":[3,7]}
    base_detections_json TEXT NOT NULL,    -- what the pipeline found, before any decision
    segments_json TEXT,                    -- [[raw_s, raw_e, red_s, red_e, entity_id], …]
    history_message_ids_json TEXT NOT NULL,
    attachments_json TEXT,                 -- [{name, pages, chars, not_read:{comments:3,…}}]
    detectors_json TEXT NOT NULL,          -- readers that ran, with model names and versions
    prepared_by TEXT,                      -- OS user who pressed Send
    prepare_ms INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN (
        'same_entity','term','identifier','number','domain','postcode_city','venue',
        'attachment_name','codename_policy','smart_tag','hidden_model_only','confirm',
        'signal_amount','signal_date','signal_number','signal_percent','signal_citation')),
    surface TEXT NOT NULL,
    normalized TEXT NOT NULL,
    count INTEGER NOT NULL,
    occurrences_json TEXT NOT NULL,        -- [[start,end], …] in raw_text
    paragraph_indexes_json TEXT,
    group_key TEXT,                        -- shape group: "F26-11xx"
    risk_score INTEGER,
    source TEXT,                           -- DetectionSource of the span, if any
    proposal TEXT NOT NULL CHECK (proposal IN ('hide','keep','link','generalise')),
    proposed_type TEXT,                    -- EntityType
    proposal_reason TEXT,                  -- one line, shown in the popover
    link_entity_id INTEGER REFERENCES entities(id),
    page_no INTEGER NOT NULL,
    position INTEGER NOT NULL,
    canary INTEGER NOT NULL DEFAULT 0      -- §9: a re-asked known item, disclosed afterwards
);
CREATE INDEX IF NOT EXISTS idx_review_items_session ON review_items(session_id, page_no, position);

CREATE TABLE IF NOT EXISTS review_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    item_id INTEGER REFERENCES review_items(id) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK (decision IN ('hide','keep','link','retype','generalise','mark','shape')),
    scope TEXT NOT NULL CHECK (scope IN ('once','matter')),
    entity_type TEXT,
    entity_id INTEGER REFERENCES entities(id),
    link_entity_id INTEGER REFERENCES entities(id),
    keep_kind TEXT CHECK (keep_kind IN ('role','public_body','heading','published_citation','other')),
    replacement TEXT,
    propagate_json TEXT,                   -- forms added by this decision, with derived_from
    via TEXT NOT NULL CHECK (via IN ('key','click','page_accept','proposal')),
    ms_since_previous INTEGER,
    superseded_by INTEGER REFERENCES review_decisions(id),   -- undo chain; never DELETE
    decided_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matter_keep_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id TEXT NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    form TEXT NOT NULL,
    normalized TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('role','public_body','heading','published_citation')),
    entity_type_hint TEXT,
    reask_on TEXT NOT NULL DEFAULT 'suffix,honorific,alias',  -- re-ask triggers, comma list or ''
    effective_from_conversation TEXT REFERENCES conversations(id),  -- State D
    origin_session_id TEXT REFERENCES review_sessions(id),
    revoked_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (matter_id, normalized)
);
CREATE INDEX IF NOT EXISTS idx_keep_matter_norm ON matter_keep_terms(matter_id, normalized);

CREATE TABLE IF NOT EXISTS matter_shape_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id TEXT NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    pattern TEXT NOT NULL,                 -- derived: digits→\d, letters→[A-Z], separators kept
    example TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    origin_session_id TEXT REFERENCES review_sessions(id),
    revoked_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (matter_id, pattern)
);

CREATE TABLE IF NOT EXISTS matter_generalisations (          -- v2
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id TEXT NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('amount','date','number','percent','duration','postcode')),
    original TEXT NOT NULL,
    normalized TEXT NOT NULL,
    replacement TEXT NOT NULL,
    origin_session_id TEXT REFERENCES review_sessions(id),
    created_at TEXT NOT NULL,
    UNIQUE (matter_id, normalized)
);

-- Written BEFORE any network call; one row per send and per Wikipedia lookup batch.
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES review_sessions(id),
    conversation_id TEXT,
    matter_id TEXT NOT NULL,
    purpose TEXT NOT NULL CHECK (purpose IN ('llm_turn','wikipedia_lookup','local_check')),
    payload_sha256 TEXT NOT NULL,          -- canonical JSON of system + messages
    request_sha256 TEXT,                   -- bytes of the serialised request body the client sends
    endpoint TEXT NOT NULL,                -- 'anthropic' | 'ollama' | 'wikipedia'
    endpoint_host TEXT NOT NULL,           -- resolved at approval; re-checked at send
    proxy_host TEXT,                       -- HTTPS_PROXY if any, or null
    model TEXT,
    mode TEXT,
    zero_retention INTEGER,
    scope_json TEXT,
    n_hidden INTEGER, n_kept INTEGER, n_generalised INTEGER, n_signals_kept INTEGER,
    n_items INTEGER, n_confirm_chips INTEGER,
    worst_risk TEXT,
    kept_together_json TEXT,               -- paragraphs with ≥2 kept quasi-identifiers
    history_message_ids_json TEXT,
    late_corrections INTEGER NOT NULL DEFAULT 0,
    reply_flags INTEGER NOT NULL DEFAULT 0, -- earlier replies that named someone
    detectors_json TEXT,
    attestation TEXT NOT NULL CHECK (attestation IN ('items_reviewed','items_reviewed_text_opened','items_reviewed_text_read')),
    approver_os_user TEXT NOT NULL,
    approver_name TEXT,                    -- from settings.approver_name
    prepared_by TEXT,
    local_check_json TEXT,
    human_ms INTEGER, machine_ms INTEGER,
    ui_lang TEXT,
    verified_at_send INTEGER,              -- 1 when the rebuilt request matched; 0 = refused
    approved_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id TEXT NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    surface TEXT NOT NULL,
    entity_id INTEGER REFERENCES entities(id),
    approval_ids_json TEXT NOT NULL,       -- every send that carried it in clear
    message_ids_json TEXT NOT NULL,
    first_left_at TEXT NOT NULL,
    endpoint_host TEXT NOT NULL,
    model TEXT,
    zero_retention INTEGER,
    discovered_at TEXT NOT NULL,
    discovered_how TEXT CHECK (discovered_how IN ('late_correction','reply_scan','manual')),
    history_reredacted_at TEXT,
    deletion_request_drafted_at TEXT,
    deletion_request_sent_at TEXT,
    note TEXT
);

-- Machine-wide, hide-only: the firm's own identity (§3, Screen 7).
CREATE TABLE IF NOT EXISTS firm_hide_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK (kind IN ('firm_name','lawyer','address','email_domain','reference_shape')),
    form TEXT, normalized TEXT, pattern TEXT,
    entity_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Every outbound connection the process makes, through jude.net (§8).
CREATE TABLE IF NOT EXISTS network_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    approval_id INTEGER REFERENCES approvals(id),
    host TEXT NOT NULL,
    purpose TEXT NOT NULL CHECK (purpose IN ('llm','wikipedia','model_download','other')),
    allowed INTEGER NOT NULL,              -- 0 = refused by the gate
    bytes_out INTEGER,
    ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,                  -- ui_lang ('en'|'fr'|'nl'), approver_name, review_page_size,
    value TEXT                             -- local_check_model, canary_rate, firm_setup_done
);

ALTER TABLE messages ADD COLUMN approval_id INTEGER REFERENCES approvals(id);
ALTER TABLE messages ADD COLUMN payload_sha256 TEXT;
ALTER TABLE messages ADD COLUMN detections_json TEXT;      -- colour the bubble; find clear surfaces
ALTER TABLE messages ADD COLUMN segments_json TEXT;        -- redraw the exact outgoing text
ALTER TABLE messages ADD COLUMN reply_scan_json TEXT;      -- for assistant turns
ALTER TABLE messages ADD COLUMN redacted_text_before TEXT; -- set by history re-redaction
ALTER TABLE messages ADD COLUMN reredacted_at TEXT;

ALTER TABLE matters ADD COLUMN sensitivity TEXT NOT NULL DEFAULT 'normal';   -- 'normal' | 'sensitive'
ALTER TABLE matters ADD COLUMN review_page_size INTEGER NOT NULL DEFAULT 10;
-- matters.redact_codenames stays as is (store.py 131–134).

ALTER TABLE entities ADD COLUMN decided_by TEXT NOT NULL DEFAULT 'detector';  -- 'detector'|'user'|'review'|'firm'
ALTER TABLE entities ADD COLUMN review_session_id TEXT;
ALTER TABLE entities ADD COLUMN confirmed_at TEXT;          -- first time a lawyer confirmed it

ALTER TABLE surface_forms ADD COLUMN derived_from TEXT NOT NULL DEFAULT 'detector';
-- 'detector' | 'user' | 'surname' | 'possessive' | 'allcaps' | 'initials' | 'suffix_stripped' | 'merge'
```

`audit_log` (`store.py` 58–64) keeps its shape; new action names:
`review.open`, `review.decide`, `review.undo`, `review.approve`,
`review.refused_at_send`, `review.discard`, `keep.add`, `keep.revert`,
`shape.add`, `shape.revoke`, `generalise.add`, `history.reredact`,
`reply.flag`, `incident.open`, `incident.export`, `lookup.approve`,
`settings.set`. `export_matter_json` bumps `version` to 2 and includes
keep terms, shape rules, generalisations, approvals and incidents (not
`network_log`).

**Code changes implied, not schema.**

* `src/jude/review_session.py` — framework-free `ReviewSession`:
  `open(conversation, prepared, history, destination)`, `items(page)`,
  `current()`, `decide(item_id, decision, **kw)`, `undo()`,
  `blocking_issues()`, `manifest()`, `approve(approver) → ApprovedPayload`,
  `discard()`. The Streamlit page and the future desktop app are both
  thin clients of it; tests exercise it directly.
* `src/jude/review/items.py` — the item builder: `unverified_terms`
  gains digit-bearing tokens (`\d{6,}` with separators, `[A-Z]{2,4}\.? ?\d{4,}`),
  postcode-and-city lines, venue words, attachment names, a `keep_terms`
  argument, and the one-line fix `_PHRASE_RE` `\s+` → `[ \t]+` so a term
  cannot span a line break (today `Bruxelles\n\nLiège` is one item);
  `_noise_for`'s `lru_cache` key must include the keep-list version.
* `src/jude/review/proposals.py` — the proposal engine (shape, honorific,
  suffix, whitelist near-match, institution noun, role, heading).
* `src/jude/review/hotkeys.py` — `HOTKEYS`, a data table both front
  ends read.
* `src/jude/ui/i18n.py` — `t(key)` over a table with `en`, `fr`, `nl`
  columns (`nl` empty, falls back to `en`); widgets keyed by stable ids.
* `risk.py` — paragraph-level signal extraction (bare large numbers and
  percentages join `_CURRENCY_RE` / `_DATE_RE`), the *kept together*
  score, and the smart-tag signal only for entities mentioned in the
  text (`_score_one`, 106–119).
* `redact.py` — `redact()` returns the segment map it already computes
  while building `out_parts` (76–83); `force_redact_span` (159–178)
  backs the M key.
* `llm/base.py` — `LLMClient.build_request(system, messages, mode) →
  PreparedRequest(host, proxy, model, body: bytes, sha256)` and
  `send_prepared(req)`; `commit_streaming_turn(conversation, approved:
  ApprovedPayload, …)` rebuilds, compares `sha256` and `host`, refuses
  on mismatch.
* `src/jude/net.py` — one `guarded_session(phase, approval_id)` through
  which every HTTP call goes; phase `review` allows only `127.0.0.1`,
  phase `send` allows only the approved host; every call is a
  `network_log` row; refusals raise. `jude ui` already passes
  `--browser.gatherUsageStats=false` (`cli.py` 363); the UI asserts it
  at startup and shows the connection counter. Model weights are
  fetched only by an explicit `jude models pull`, never during a review
  (`HF_HUB_OFFLINE=1` otherwise).
* `chat.py` — attachments are written to a private per-process
  directory (`tempfile.mkdtemp(dir=jude_home()/'tmp')`, mode 0700)
  instead of `/tmp/jude_chat_<original filename>` (`chat.py` 68), with
  the original name never used as a path; the adapters return what they
  did not read.
* `cli.py` — `jude redact` writes files with no review at all (`cli.py`
  94–135); it gains `--unreviewed` as a required flag for that path and
  `jude review --approve` for a reviewed one.

## 8. Streamlit now / React–Tauri later

**Doable now**, on the installed Streamlit 1.57.0 (Python 3.14): keys as
`st.button(shortcut=…)`; the whole queue in one `st.fragment` so a key
reruns only the queue and the map (today every checkbox tick reruns the
page and 80 rows × 2 widgets are instantiated, `app.py` 646–661);
`st.dialog` for the gate and the popovers, state-based; `st.pills` /
`st.segmented_control` for the type and keep-kind pickers; `st.badge`
for risk; `st.progress` and `st.status` for Screen 0; `st.html` for the
coloured map with `title=` tooltips; `st.data_editor` for the keep list;
`AppTest` for the tests, because every key is a button. The current
item as app state rather than DOM focus is what makes keys work without
a custom component. A fragment rerun costs 100–300 ms per key — fine
for a hundred items, not snappy.

**Not possible in Streamlit, deferred to React/Tauri**: selecting text
in the map and hiding it (no selection events; M with a text input is
the substitute, and it is the weak point of v1 — the lower-case domain
the eye catches must be retyped); linked scrolling of original and
outgoing views; scroll-to-current-span in `st.html` (only through a
sandboxed `components.html` iframe, not planned); scroll tracking for
`text_read`; a pre-filled chat input after *Back to editing*; sub-100 ms
keys; a native print-to-PDF of the manifest; the OS keychain for the API
key (today pasted into process memory, `app.py` 802–844); a shell-level
allow-list that makes "nothing has left" a property of the application
rather than of the Python process.

**What survives the move unchanged**: `ReviewSession` and its tables,
the item kinds and proposals, `HOTKEYS`, the manifest fields and both
hashes, `jude.net`, the i18n table. The Streamlit page is a renderer
calling `session.decide()`, `session.manifest()`, `session.approve()`;
the desktop app calls the same module over a local IPC and adds the
selection-to-hide inspector on the document itself.

**Test migration (a prerequisite, budgeted).** `tests/test_ui_app.py`
selects widgets by English label (`test_review_panel_lists_unverified_terms`,
218–240, expects an expander containing "unverified term" and a
checkbox labelled with the term). Two languages and buttons instead of
checkboxes break it on the first commit. Step one, before any screen:
give every widget a stable `key`, select by key in tests, run the suite
in `en` with one `fr` smoke test. About a day for the ~120 strings in
`app.py` and `pages/2_Entities.py`.

**Build order.**

* **v1 — the gate and the queue (3–4 weeks).** i18n table and key-based
  tests; `ReviewSession`, `review_sessions`, `review_items`,
  `review_decisions`, `matter_keep_terms`, `approvals`, `settings`;
  item builder with numbers, postcodes, venues, attachment names,
  same-entity proposals and the `_PHRASE_RE` fix; Screens 0, 1 (four
  groups, chips, *hidden on a guess*), 3, 4 (without shape rules and G);
  blocking strip including the empty-attachment check; `build_request`
  + double hash + refuse-on-mismatch; `jude.net` with the connection
  counter; Wikipedia gate 0b; private attachment directory; reply scan
  stored and shown as a chip; approver and attestation in the row;
  Screen 7 *Your firm*; `jude redact --unreviewed`.
* **v2 — memory and repair (3 weeks).** Signals screen with G and
  `matter_generalisations`; shape rules with preview; re-ask triggers;
  State D; history re-redaction including replies; Screen 5 tabs
  Approvals and Incidents, Screen 6 incident export; local second
  reader; the pace line and the canary (opt-in); scope control (send
  only ¶ n–m); firm keep-list proposals with the conflict check.
* **Later — the desktop app.** The same `ReviewSession` behind a local
  IPC; the document as the surface (select → hide, click → inspector,
  linked views, `text_read`); OS allow-list; keychain; print the
  manifest.

## 9. Metrics

**Benchmark** (extend `benchmark/run.py::_attach_review_metric`,
209–230, and `benchmark/analyze.py`):

1. *Misses surfaced by the review* — `misses_surfaced / misses`, today
   50/142 on the held-out split. Target ≥ 0.90 with the new item builder
   in place of `unverified_terms`; the residual reported by type, since
   it is the only true leakage class.
2. *Where the misses land* — the share of gold misses in the mandatory
   queue, in the optional *hidden on a guess* list, and in neither.
   Release gate: 0 in neither. Baseline with gold spans as detections
   (the noise floor of a perfect detector): 15.1 items a page held-out,
   8.5 dev, 28.2 on `doc_035_data_room_index_en`.
3. *Items per page* — `items / (chars ÷ 3,000)`, split by group. Target
   ≤ 10 on the first document of a matter, *to decide* ≤ 6; ≤ 4 on the
   third, measured by replaying a synthetic matter (three to ten
   documents sharing parties, built with `benchmark/synth.py`) through
   the keep list, the dictionary and the shape rules before counting.
4. *Proposal accuracy* in two halves — fail-closed recall: the share of
   gold identifiers among queue items whose proposal is HIDE or LINK,
   must be 1.00 (release gate); proposal precision: the share of grey
   (public) spans among items whose proposal is KEEP, target ≥ 0.85 so
   Enter is right most of the time.
5. *Public-body over-redaction after review under "accept every
   proposal"* — the existing column recomputed on the text that would
   leave; target ≤ 5 % (the operating point) against 22–26 % before
   review.
6. *Replay* — derive decisions from the gold of the first half of a
   document's paragraphs (hide gold, keep grey), score the second half:
   target −70 % items and 100 % of repeat identifiers (surnames, short
   forms) caught by propagation.
7. *Signals coverage* — on synthetic documents carrying a press-known
   amount or date next to a party, the share listed on Screen 2; target
   1.00 for amounts of ≥ 7 significant digits in HIGH paragraphs.
8. *Simulated review seconds per page* — Σ(items × measured constant per
   group) as a column of the size ladder, so a detector change is judged
   by review cost, not F1 alone.
9. *Baseline first* — time from panel open to Approve on five 10-page
   documents by the same lawyer on today's panel, then on v1: the only
   honest "faster" claim.

**On-device telemetry** (rows in `review_decisions`, `approvals`,
`review_sessions`, `network_log`; never transmitted; the lawyer may
export a matter-free aggregate):

* human seconds per page split from machine seconds (`approvals.human_ms`,
  `machine_ms`, `review_sessions.prepare_ms`); target ≤ 60 s a page;
* decisions per minute and flips versus accepted proposals
  (`ms_since_previous`, `via`): a pace above the lawyer's own median × 2
  is shown as a nudge on the memory page; a confirm-rate above 95 % on
  *to decide* items means they are mis-tiered and should become chips,
  not that the lawyer should slow down; the flip rate is the field proxy
  for proposal precision;
* queue size per document across a matter — must fall;
* late corrections and reply flags (`approvals.late_corrections`,
  `reply_flags`) — each is an observed miss; the number the lawyer most
  wants at zero;
* regret rate — decisions superseded within 7 days ÷ decisions taken,
  by kind (a high rate on keep-for-matter means the kind picker is too
  easy);
* the canary (opt-in, `settings.canary_rate`): in one review in N, a
  surface the dictionary already caught deterministically is re-asked
  as a *to decide* item with the correct proposal; whether the lawyer
  hid or kept it is recorded and disclosed to the lawyer at the end of
  the review ("one of the 97 items was a test; you caught it"). The only
  objective measure of human recall in production, shown to nobody else;
* blocking issues raised and resolved by type; sessions discarded or
  left open; `approvals.verified_at_send = 0` (must be 0 in normal use —
  any non-zero means a concurrent writer); `network_log` rows with
  `allowed = 0` (must be 0 — a refused call is a bug or an intrusion).

**Headless tests** (`AppTest`, the `tests/test_ui_app.py` pattern):
replay a 10-page corpus document through Send → queue → manifest with a
stub client; assert Approve is absent while items remain; assert the
`approvals` row exists before the stub is called and that the stub
received bytes whose SHA-256 equals `approvals.request_sha256`; assert
a mismatch refuses and sends nothing; assert the queue on a second
replay of the same matter is smaller; assert a decision survives a
simulated refresh; assert no `network_log` row has a host other than the
stub's during the review phase.

## 10. Risks, and open questions for Etienne

**Risks the design accepts and watches.**

* *Rubber-stamping.* Pages of ten confirmed with Enter can become
  reflexive. No cross-page accept, Shift+Enter only on chips, the flip
  count per page, the pace line against the lawyer's own history, the
  canary. The design cannot make a lawyer read; it can make not-reading
  visible to them.
* *Precision collapse if every proposal is accepted.* Default-HIDE would
  turn headings and defined terms into `Org9` and `efficiency-frontier.html`
  is explicit that an over-redacted memo is useless. The proposal engine
  marks whitelist near-matches, institution nouns, roles and all-caps
  heading lines as KEEP; metric 5 gates the release.
* *Queue inflation from numbers.* A financial document carries dozens;
  grouping by shape and the per-page budget metric are the answer, and
  if the first-document figure stays above 10 a page the shape grouping
  is tightened before the detector is touched.
* *History already sent.* A surname missed on turn 1 and hidden on turn
  3 left in clear; the manifest says so and the incident record is the
  honest output. The design repairs what can be repaired (nothing
  containing the surface is re-sent) and records the rest.
* *Pseudonym churn.* A type change or a late link allocates a new
  pseudonym; earlier turns keep the old one (counters never reuse,
  `store.py` 721–742). The model sees a renamed entity across turns;
  the ledger shows both; changes are encouraged before the first send.
* *Streamlit limits.* M instead of selection; 100–300 ms per key; no
  scroll tracking. Isolated in the renderer; removed by the desktop app.
* *Key mnemonics.* H, K, S, A, M, U are English letters under French
  verbs; the key is printed on every button and L shows the legend.
* *The local second reader.* A 4 B model scores F1 0.54 on extraction
  and redacts 46 % of public bodies when told not to (benchmark §6). It
  is one more reader, never clearance, never a gate.
* *The record is evidence.* Approvals, decisions, incidents and hashes
  in `~/.jude/jude.db` are the lawyer's own records (`threat-model.html`,
  *Subpoena of you*); they contain real names; the export warnings
  (`app.py` 308–310) extend to them.

**Open questions — each answerable in one line.**

1. Approver identity in v1: is the OS user name plus a name typed once
   in settings enough, or do you want a per-machine passphrase at the
   Approve click?
2. Hand-off: should a matter be able to require that the person who
   approves is not the person who prepared (four-eyes), or is recording
   both names enough?
3. Canary: opt-in per matter with disclosure after each review — yes,
   or never?
4. Generalise (G): defer to v2 as planned, or drop it entirely and keep
   Screen 2 as a reading list?
5. Shift+Enter on Confirm chips (deterministic hits only): acceptable,
   or must every item be one key?
6. The firm list (Screen 7): should the firm's own name be hidden by
   default in every matter, or asked per matter?
7. Wikipedia lookups: keep them behind the 0b gate, or remove the
   feature until the desktop app?
8. `jude redact` without review: require `--unreviewed`, or remove the
   command's write path?
9. Sensitive matter: a per-matter flag as designed, or the default for
   every strict-mode matter?
10. History re-redaction: rewrite the model's stored replies as well as
    your turns — yes?
11. The attestation sentence: approve the two wordings ("items reviewed
    and risk paragraphs read, exact text shown" / "… read in full"), or
    rewrite them?
12. Scope control ("send only ¶ 3–7"): v1 or v2?
13. Retention: do approvals, incidents and the network log live as long
    as the matter, or should a matter's deletion purge them too?
14. NL: translate the strings table now, or ship the empty column?
15. Codename question on the first *Project X* of a matter, where the
    word sits — yes?
16. Model weights: bundle them in the installer so no download ever
    happens after setup, or keep an explicit `jude models pull`?

## 11. Résumé pour Etienne

**Ce que ce document décide.** Aujourd'hui, quand vous cliquez sur
*Envoyer*, Jude vous montre deux petites boîtes côte à côte (le texte
original et le texte masqué) et une liste de cases à cocher. Pour un
document de dix pages, c'est illisible : trente mille caractères dans
une fenêtre de dix lignes. Et le détecteur laisse passer environ un
identifiant sur dix (recall 0,89 sur les documents jamais vus) : des
numéros de registre, des références de dossier, des noms de famille
cités seuls, des codes postaux suivis d'une ville. Aucun modèle
n'attrapera tout. La garantie, c'est donc *vous*, et le travail de Jude
est de rendre votre relecture courte et sûre.

**Comment ça marchera.** Après *Envoyer*, Jude prépare le texte sur
votre machine (dix secondes à une minute selon le modèle) en affichant
ce qu'il fait et le compteur « connexions sortantes : 0 ». Puis il vous
présente une **liste de ce qu'il n'a pas su décider**, dix éléments par
page, chacun avec une proposition : *masquer* sauf si une règle dit que
c'est public (une juridiction, une loi, un rôle). Une touche par
décision : **H** masquer, **K** garder, **S** même personne que…,
**M** marquer un terme que Jude n'a pas vu, **U** annuler. Les noms
trouvés par une règle sûre ou déjà connus du dossier sont des pastilles
à confirmer d'un coup ; les noms trouvés par le modèle seul sont des
questions, une par une. À gauche, le document coloré avec les couleurs
du surligneur Word que vous connaissez — c'est une carte, pas une
lecture.

**Rien ne part sans votre signature sur l'exact contenu.** Quand tout
est décidé, un écran *Ce qui quitte votre ordinateur* liste : la
destination réelle (l'adresse du serveur, le modèle), votre texte masqué
avec ce qui est masqué, gardé et laissé ensemble dans un même
paragraphe (un montant et une date à côté d'un pseudonyme peuvent
ré-identifier), les six messages précédents qui repartent comme
contexte — y compris les réponses du modèle, que personne ne relit
aujourd'hui — les pièces jointes et ce que Jude n'a *pas* pu lire
(commentaires, images sans OCR), et une empreinte (hash) des octets
exacts qui vont partir. Vous approuvez avec Cmd+Entrée. L'enregistrement
(qui a approuvé, quoi, quand, vers où) est écrit sur votre disque
*avant* l'envoi, et Jude vérifie au moment d'envoyer que rien n'a
changé. La phrase d'approbation dit exactement ce que vous avez fait :
« j'ai relu les 97 éléments listés et les paragraphes à risque ; le
texte exact m'a été montré » — pas « j'ai tout lu », sauf si vous l'avez
fait.

**Le dossier se souvient.** Chaque décision est gardée dans le dossier :
un nom masqué une fois l'est partout ensuite ; *Auditorat* gardé une
fois n'est plus jamais demandé ; un numéro de registre peut devenir une
règle pour tous les numéros de même forme. Le premier document d'un
dossier coûte six à sept minutes de votre attention ; le troisième
environ deux minutes et demie ; le dixième une minute et demie. L'écran
vous dit pourquoi la liste est courte, pour que vous lui fassiez
confiance.

**Si quelque chose a fuité quand même** (un nom gardé puis masqué plus
tard, une réponse du modèle qui devine une partie), Jude produit la
fiche dont vous avez besoin pour le bâtonnier ou le DPO : ce qui est
parti, quand, vers quel serveur, et un brouillon de demande de
suppression au fournisseur.

**Ce que je vous demande.** Seize questions à la section 10, chacune
répond en une ligne. Les plus importantes : qui signe l'approbation
(nom d'utilisateur suffit ?) ; acceptez-vous de confirmer d'un coup les
pastilles trouvées par des règles sûres ; faut-il un « test
d'attention » optionnel ; le nom du cabinet doit-il être masqué par
défaut dans tous les dossiers.

**Ce qui est une hypothèse.** Les temps sont des estimations de vitesse
de lecture, remplacées par les mesures locales dès la première semaine
d'usage ; les volumes (environ cent éléments sur un premier document de
dix pages) viennent du benchmark et seront vérifiés sur le vôtre.
