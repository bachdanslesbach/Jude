# Public split — excerpts of real published documents

The answer to "it is all synthetic": excerpts (450–900 words) of real
judgments and decisions, annotated **as if they were a client's
confidential file** — the parties, their counsel, judges and officials
named in a public capacity, the document's own case number, registry
numbers and party addresses are gold; courts, authorities, statutes,
cited precedents and the court's own address are public. The task is
"what must Jude find", not "what must leave the machine" — nothing in
these documents is confidential.

Each record in `benchmark/corpus/doc_1NN_*.json` carries
`split: "public"` and a `provenance` block (source, URL, court, date,
licence, attribution). Raw excerpts and metadata live in `raw/`.

## How the gold was made

Two agents annotated every excerpt blind, from the same policy
(`benchmark/synth/POLICY_QUESTIONS.md`, rulings of 13 October 2026);
a third compared the two sets, settled each disagreement with a written
reason appended to the record's `notes` (an *ADJUDICATION* paragraph),
and re-ran the validator. Agreement before adjudication: 21/21, 34/82,
25/27, 18/18, 24/24, 43/45, 22/24, 35/39, 34/72, 15/15, 13/13, 46/56,
50/79, 21/23 surfaces (doc_101 … doc_114) — the disagreements are almost
all about which *public* mentions to list, not about what is gold.
Questions the policy does not settle are collected as items 8–17 of
`POLICY_QUESTIONS.md` for the lawyer's ruling. Pre-highlighted Word
copies are in `review/` (gitignored), like the other splits.

## Documents

| Id | Lang | Source | Court / authority | Date | Words | Gold | Public |
|---|---|---|---|---|---|---|---|
| `doc_101` [Central Térmica de Temane SA & Anor v Banco Santander SA](https://caselaw.nationalarchives.gov.uk/ewhc/comm/2026/2587) | EN | Find Case Law | Commercial Court (KBD) | 2026-10-13 | 849 | 46 | 74 |
| `doc_102` [Intralinks Inc v Nexans SA](https://caselaw.nationalarchives.gov.uk/ewhc/comm/2026/2355) | EN | Find Case Law | London Circuit Commercial Court (KBD) | 2026-09-17 | 787 | 39 | 74 |
| `doc_103` [Glencore Energy UK Ltd v Prax Lindsey Oil Refinery Ltd](https://caselaw.nationalarchives.gov.uk/ewhc/ch/2026/2394) | EN | Find Case Law | Chancery Division, Insolvency and Companies List | 2026-09-21 | 873 | 43 | 65 |
| `doc_104` [NoCopyrightSounds Ltd v AEI Music Ltd & Anor](https://caselaw.nationalarchives.gov.uk/ewhc/ch/2026/2360) | EN | Find Case Law | Chancery Division, Intellectual Property List | 2026-09-15 | 781 | 41 | 38 |
| `doc_105` [Rasmala Trade Finance Fund v Trafigura Pte Ltd](https://caselaw.nationalarchives.gov.uk/ewca/civ/2026/1259) | EN | Find Case Law | Court of Appeal (Civil Division) | 2026-10-07 | 719 | 59 | 51 |
| `doc_106` [Sandoz, Inc. v. United Therapeutics Corp.](https://www.govinfo.gov/content/pkg/USCOURTS-ca3-24-03146/pdf/USCOURTS-ca3-24-03146-0.pdf) | EN | govinfo | US Court of Appeals, Third Circuit | 2026-10-07 | 774 | 88 | 27 |
| `doc_107` [Trustees Main/270, LLC v. ApplianceSmart, Inc.](https://www.govinfo.gov/content/pkg/USCOURTS-ca6-25-03889/pdf/USCOURTS-ca6-25-03889-0.pdf) | EN | govinfo | US Court of Appeals, Sixth Circuit | 2026-10-07 | 886 | 86 | 32 |
| `doc_108` [AlexSam, Inc. v. Simon Property Group, L.P.](https://www.govinfo.gov/content/pkg/USCOURTS-ca13-25-01138/pdf/USCOURTS-ca13-25-01138-0.pdf) | EN | govinfo | US Court of Appeals, Federal Circuit | 2026-10-05 | 860 | 87 | 68 |
| `doc_109` [International Tools Service s.a. c. H. et Horelec s.a.](https://juportal.be/content/ECLI:BE:CASS:2023:ARR.20230223.1F.3/FR) | FR | JUPORTAL | Cour de cassation, 1re ch. (1F) | 2023-02-23 | 878 | 14 | 64 |
| `doc_110` [Ville de Virton c. Trema Architecture s.r.l.](https://juportal.be/content/ECLI:BE:CASS:2025:ARR.20250313.1F.1/FR) | FR | JUPORTAL | Cour de cassation, 1re ch. (1F) | 2025-03-13 | 845 | 20 | 66 |
| `doc_111` [C. G. c. État belge](https://juportal.be/content/ECLI:BE:CASS:2025:ARR.20250116.1F.1/FR) | FR | JUPORTAL | Cour de cassation, 1re ch. (1F) | 2025-01-16 | 541 | 17 | 43 |
| `doc_112` [ABC-2026-CC-22 — Rossel / IPM](https://www.abc-bma.be/sites/default/files/content/download/files/ABC-2026-CC-22%20PUB%20FIN_0.pdf) | FR | ABC/BMA | Collège de la concurrence | 2026-07-03 | 860 | 87 | 77 |
| `doc_113` [ABC-2026-RPR-27-AUD — RFB e.a. c. URBSFA](https://www.abc-bma.be/sites/default/files/content/download/files/ABC-2026-RPR-27-AUD%20PUB.pdf) | FR | ABC/BMA | Auditorat | 2026-08-13 | 875 | 64 | 79 |
| `doc_114` [ABC-2026-CCS-24-AUD — RMGA / Pierre-Joël / AAG](https://www.abc-bma.be/sites/default/files/content/download/files/ABC-2026-CCS-24-AUD_pub.pdf) | FR | ABC/BMA | Auditorat | 2026-07-09 | 632 | 33 | 93 |

14 documents, 8 EN / 6 FR, 724 gold spans, 851 public mentions.
"Gold" counts every occurrence (a party named twelve times is twelve
spans); the Cour de cassation already anonymises natural persons, which
is why its FR excerpts carry few gold spans and many public ones.

## Sources and licences

| Source | Language | What | Licence / attribution |
|---|---|---|---|
| [Find Case Law](https://caselaw.nationalarchives.gov.uk) (The National Archives) | EN | England & Wales judgments (Commercial Court, Chancery, Court of Appeal), LegalDocML `data.xml` | Open Justice Licence / OGL v3 — "Contains public sector information licensed under the Open Government Licence v3.0"; judgments published by The National Archives |
| [govinfo](https://www.govinfo.gov) (US GPO) | EN | US federal court opinions, USCOURTS collection (PDF, text layer via PyMuPDF) | US Government work, public domain (17 U.S.C. § 105) |
| [JUPORTAL](https://juportal.be) (SPF Justice) | FR | Arrêts de la Cour de cassation de Belgique (natural persons already anonymised by the court) | Public case-law database of the Belgian federal judiciary; reproduction with attribution |
| [Autorité belge de la concurrence](https://www.abc-bma.be/fr/decisions) | FR | Decisions (merger control, antitrust), public versions (PDF, text layer via PyMuPDF) | Official publications of the authority; reproduction with attribution |

Not used: EUR-Lex and Curia (serve empty pages to automated clients),
CourtListener (full text needs an API token), EDGAR (blocks undeclared
tools), BAILII (terms forbid automated access), Légifrance/Judilibre
(API key).

## Fetching etiquette

A declared user agent naming the project and nothing else —
`JudeBenchmark/0.8 (https://github.com/bachdanslesbach/Jude)` — at most
a dozen requests per source per batch, one second apart; excerpts only,
never whole collections. One collector in this batch put a personal
e-mail address in its user agent when probing JUPORTAL; the metadata
files record a placeholder instead, and the string above is the rule
from now on. JUPORTAL's ECLI numbering is sparse: the next batch should
follow the *Publication(s) liée(s)* links printed on fetched pages
rather than probe dates (9 of 12 probes returned 404 this time).
