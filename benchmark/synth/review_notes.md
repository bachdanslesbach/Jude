# Review notes — synthetic batch doc_021 … doc_035

Judged on the `text` field only (not the annotations). Scores 1–5; language scored for FR/NL only. "Sensitivity" = no real private individual, live matter or real private company as a party. Word counts are whitespace tokens.

## Summary table

| id | genre | lang | words | realism | consistency | language | sensitivity |
|---|---|---|---|---|---|---|---|
| doc_021 | board minutes | en | 886 | 4 | 4 | — | pass |
| doc_022 | accord de confidentialité | fr | 875 | 4 | 3 | 5 | pass |
| doc_023 | Form CO excerpt | en | 878 | 4 | 5 | — | pass |
| doc_024 | note interne après inspection | fr | 884 | 4 | 4 | 5 | pass |
| doc_025 | leniency marker request | en | 894 | 4 | 5 | — | pass |
| doc_026 | antwoord op verzoek om inlichtingen | nl | 876 | 4 | 4 | 5 | pass |
| doc_027 | SPA excerpt | en | 877 | 4 | 4 | — | pass |
| doc_028 | email thread | en | 835 | 5 | 5 | — | pass |
| doc_029 | verzoek tot arbitrage (CEPANI) | nl | 880 | 4 | 5 | 5 | pass |
| doc_030 | mémo RGPD / AIPD | fr | 886 | 4 | 5 | 5 | pass |
| doc_031 | DD red-flag report | en | 891 | 4 | 5 | — | pass |
| doc_032 | conclusions | fr | 888 | 3 | 4 | 5 | pass |
| doc_033 | dadingsovereenkomst | nl | 872 | 4 | 5 | 5 | pass |
| doc_034 | state aid complaint | en | 896 | 4 | 5 | — | pass |
| doc_035 | data room index | en | 822 | 4 | 4 | — | pass |

Read first: **032, 022, 035, 024, 026** (substantive legal or structural fixes). Then the batch-level rename pass (see end).

---

## doc_021 — board minutes (en)

1. "the Board paper with Annexes 1 to 4 had been circulated" vs. annex list ending "5. Financing memorandum (Lambrechts)" — make it "Annexes 1 to 5" or drop Annex 5.
2. "Apologies: Mrs. Hilde Peeters" — every other woman is "Ms."; harmonise.
3. "remedy commitment is capped at the divestment of Feldmann's primer line at Wrocław" while the only affected market is offshore primers *in Belgium* — add "which supplies the Belgian market" or move the line to Düsseldorf.
4. "RPR Antwerp" — Belgian practice: "RPR Antwerpen, afdeling Antwerpen" (or "RLE Antwerp" in English); also 2600 is Berchem, fine but say "2600 Berchem (Antwerp)".
5. Purchase price EUR 186,500,000 and long-stop 31 March 2027 are identical to doc_027 — change one deal's numbers (see batch notes).

## doc_022 — accord de confidentialité (fr)

1. Role of the « Conseil » is muddled: art. 1.2 defines Delvaux & Marchetti as counsel to the *Bénéficiaire*, but art. 2.3 has it approve the clean team "pour la Partie Divulgatrice", art. 3.2 has it coordinate the *seller's* data room, art. 8.1 copies it on both parties' notices. Either make it the Partie Divulgatrice's counsel (and move it out of « Représentants ») or make it a neutral "Conseil de la Data Room".
2. "l'Opération notifiée par Meridian au titre de l'article 6, paragraphe 1, point b), du règlement (CE) n° 139/2004" — 6(1)(b) is the decision basis, not the notification basis: "notifiée … au titre de l'article 4 … et déclarée compatible au titre de l'article 6, paragraphe 1, point b)".
3. "inscrite à la Banque-Carrefour des Entreprises," — no BCE number; a Belgian drafter would add "sous le numéro 0xxx.xxx.xxx".
4. "Dossier suivi par : Van den Broeck / Lambrechts" — Lambrechts is the client's data-room contact, not a fee-earner; replace with a second lawyer of the Conseil.
5. "informations commercialement sensibles au sens des articles 101 et 102 TFUE" — clean-team clauses cite 101 only; drop "et 102". (IBAN in an NDA penalty clause is a benchmark artefact; tolerable.)

## doc_023 — Form CO excerpt (en)

1. Section layout follows the 2004 form: in Reg. 2023/914 Annex I turnover is Section 4, not "3.3 Union dimension"; either renumber or label the draft "abridged structure for pre-notification".
2. "Ashcombe has confirmed that neither MPCP nor the Seller…" — bare surname is off-register in a Form CO ("Mr Ashcombe"); if the surname-only trap must stay, move it to a footnote.
3. "The three-year non-compete given by the Seller" — the Seller is a PE fund; a financial seller giving a three-year non-compete is unusual (Ancillary Restraints Notice para 20: goodwill + know-how). Make it two years or have MPCP's portfolio company give it.
4. "22 Bedford Row, London WC1R 4EB" — Bedford Row is barristers' chambers territory; a real set may sit at that number. Use a non-existent number (e.g. 122).
5. "Corvane" is also the codename in doc_034 — rename one.

## doc_024 — note interne après inspection (fr)

1. "L'affaire porte la référence MEDE-I-26/0031" — BMA format for an ex officio investigation is "MEDE-I/O-26/0031" (cf. doc_026's correct "MEDE-P/K-26/0031").
2. 11 September 2026 is a Friday, so "Reprise annoncée demain à 08h30" and "Demain 08h30 : présence … à Nivelles" put the second raid day on a Saturday; date the raid Tuesday 8 or Wednesday 9 September.
3. "07h55 — Arrivée … de six inspecteurs" — art. IV.41 §3 CDE confines perquisitions to 8h–18h; say "07h55 — Arrivée … ; les inspecteurs attendent 08h00 pour entamer les opérations".
4. "Projet Héron" is also the codename in doc_022; "Julie Lambrechts", "Sofie Deprez", "Delcourt" recur across the batch — rename.
5. "(e) Un recours contre le mandat et les saisies devant la Cour des marchés" — add the legal basis a partner would expect ("art. IV.79 CDE") or soften to "les voies de recours (Cour des marchés) seront examinées".

## doc_025 — leniency marker request (en)

1. "(ii) nothing be disclosed … before the Applicant has been heard on the scope of any inspection" — an applicant is not consulted on inspection scope; rephrase: "before the Applicant has been informed, so that it can ensure its cooperation during any inspection".
2. "By hand and by secure email" — since 2019 the channel is eLeniency; "Submitted via eLeniency; hard copy by hand".
3. "referred to within the Firm as Project Lantern" — a firm would not disclose its internal codename to DG COMP; either drop "within the Firm" or make Lantern the Applicant's own internal review name.
4. "Meridiaan" is also the party name in doc_029 and doc_031 — rename.
5. Para 9: after the ECN sentence, add one line that the CMA application is outside the ECN (post-Brexit) to avoid the implication that Art. 11 allocation covers the UK.

## doc_026 — antwoord op verzoek om inlichtingen (nl)

1. "Wij verwijzen naar het arrest … Intel, C-413/14 P" cited for *buyer power / no dominance* — Intel is about exclusivity rebates and the AEC test; cite it under point 3.2 (kortingen) or replace here with Hoffmann-La Roche / Post Danmark I on dominance.
2. "De prijslijsten van Pakdistri Benelux BV worden door de distributeur zelf vastgesteld en gepubliceerd op kesterbeek.example.com" — an independent distributor's prices on the supplier's own domain undercuts the no-RPM argument; use pakdistri.example.com or drop "gepubliceerd op…".
3. "Nordic Wrap Ltd" for Scandinavia — use a Nordic legal form (AB/AS/ApS).
4. "Louizalaan 331, 1050 Brussel" is also the address of Dhondt & Castellane in doc_027; "Noorderlaan 118" vs "Noorderlaan 42" in doc_027 — change one.
5. "Mevr. Nathalie Ryckaert, Auditeur" — invented official; verify against the current BMA Auditoraat staff list before publication.

## doc_027 — SPA excerpt (en)

1. Purchase price EUR 186,500,000 and Long Stop Date 31 March 2027 duplicate doc_021 — change to e.g. EUR 172,000,000 / 30 April 2027.
2. "Mr. Koen Vermeire, General Counsel" (7.1(a)) then "Mr. Koen Vermeire, Director" (signature block); "Ms. Priya Ramaswamy, Head of Legal" then "Director" — either give both titles ("Director and General Counsel") or use different signatories.
3. "the Commercial Court of London" — "the Commercial Court in London" / "the courts of England and Wales".
4. "Seller's Solicitors means Dhondt & Castellane BV" — fine in an English-law SPA, but "BV" for a Belgian firm is odd next to "Solicitors"; "Dhondt & Castellane BV, advocaten" reads better.
5. "Meridian Thermal Systems NV" — fifth use of Meridian/Meridiaan in the batch; rename.

## doc_028 — email thread (en)

1. "Solvane Packaging Group N.V." collides with "Solvane Industrial Holdings BV" in doc_021 — rename one.
2. "Ms. Okafor," from a Head of Integration to her own GC is stiff for an internal mail; "Adaeze," or "Dear Adaeze,".
3. Nothing else: Altice C-746/21 P, Art. 9(2)(a), Art. 7(3) and the timeline (14:32 → 17:05 → 22:47 → 07:52, weekdays correct) all hold. Best document of the batch.

## doc_029 — verzoek tot arbitrage CEPANI (nl)

1. "ingeschreven in de Kruispuntbank van Ondernemingen onder nummer 0745.612.338" — fails the mod-97 check; use e.g. 0745.612.365 (or any number whose last two digits = 97 − (first eight mod 97)).
2. "vertegenwoordigd door Mr. Bram Verhulst en Meester Lore De Coninck" — one convention per line ("Mr. … en Mr. …").
3. Same fact pattern as doc_032 (German supplier "Hallstein … GmbH" terminates a Belgian exclusive distributor; indemnities under the 1961 regime) — rename the supplier at least, or regenerate one of the two (see batch notes).
4. "volgens vaste rechtspraak van het Hof van Cassatie moeten ook arbiters ze toepassen" — add a date (e.g. "Cass. 28 juni 1979") or soften to "rechtspraak"; the point is contested after 2023.
5. Optional: the CEPANI filing fee paid from the "derdenrekening" — fine; but the IBAN in a request for arbitration is an artefact a reader will notice.

## doc_030 — mémo RGPD / AIPD (fr)

1. "Le Comité européen de la protection des données (lignes directrices WP248 rev.01)" — WP248 is a Groupe 29 document endorsed by the CEPD: "les lignes directrices WP248 rev.01 du Groupe de travail « Article 29 », entérinées par le CEPD".
2. "Nos honoraires … sont à régler sur le compte du Cabinet auprès de KBC (IBAN …)" — fee/IBAN paragraph does not belong in an advice memo; move to a covering letter or footnote "voir note d'honoraires jointe".
3. "respecter la CCT n° 81 du 26 avril 2002" — CCT 81 covers network communication data; scanners/badges are only partly in scope; add "dans la mesure où des données de communication électroniques en réseau sont traitées" or cite CCT n° 39 (nouvelles technologies) for the consultation duty.
4. "Delcourt" (also doc_024), "Vandermeulen" (also doc_033), "Peeters" (also 021, 032) — rename.
5. Phone "+32 3 555 08 41" is the same local number as doc_034's "+32 2 555 08 41" — vary.

## doc_031 — DD red-flag report (en)

1. "The German subsidiary's shareholder list has not been filed with the commercial register since 2019" — a Gesellschafterliste is only refiled on a change; say "the list on file (2019) does not reflect the 2023 transfer".
2. "processed on servers located in Aalst without a documented intra-group data transfer agreement (GDPR — Amber)" — intra-EU, no transfer issue; "without an intra-group processing agreement (Art. 28 GDPR)".
3. "Corvina Capital Partners" — sixth Corv- name (Corvane, Corvalis, Corvid, Corvina, Corvane, Corvus); rename.
4. "Meridiaan Packaging NV" / "MERIDIAAN" word mark — see Meridiaan collisions (025, 029).
5. "Hexaform Moulds BV v. Meridiaan Packaging NV before the Brussels Enterprise Court" — MPN sits in Aalst (ondernemingsrechtbank Gent, afdeling Dendermonde); keep Brussels only if you add "under the jurisdiction clause of the supply agreement".

## doc_032 — conclusions (fr)

1. The legal basis a Brussels practitioner expects is missing: termination of an exclusive concession of indefinite duration with effect in Belgium is governed by art. X.35–X.40 CDE (ex-loi du 27 juillet 1961); the heads claimed ("indemnité compensatoire de préavis", "investissements non amortis") are precisely X.36/X.37. Add a section B bis citing X.36 and X.37 before the abus de droit / VI.104 arguments.
2. "R.G. n° A/26/02371" while "La citation a été signifiée le 12 juin 2025" — a 2025 citation gets a 2025 roll number: "A/25/02371".
3. "distribue depuis 2009" vs. "la rupture brutale d'une relation de neuf années" — 2009→2025 is sixteen years; write "relation de seize années (contrat du 14 mars 2016 succédant à un contrat de 2009)" or change 2009 to 2016.
4. "l'indemnité de procédure liquidée à 12.000 €" — claims total 1,180,600 €, above the 1,000,000 € bracket; check the indexed base amount for that bracket (higher than 12,000 €).
5. "Hallstein" duplicates doc_029's supplier; "Maître Sophie Deprez" vs "Sofie Deprez" (GC in doc_024); "Monsieur Peeters"; "Vandersmissen" (also 035) — rename. Also "Nos réf. : VD/2024/0187" predates the 2025 dispute — "VD/2025/0187".

## doc_033 — dadingsovereenkomst (nl)

1. "Opgemaakt te Antwerpen op 27 juni 2026" — a Saturday; use 26 or 29 June 2026.
2. "rekeningnummer BE71 0961 2345 6769 bij KBC" — KBC accounts carry bank code 73x/74x (as in every other document); use e.g. BE-- 7340 …, recomputing the check digits.
3. "Mr. Karolien Wouters … Meester Bram Deleu" — pick one convention.
4. "Sofie Verhaeghe" collides with "Verhaeghe Lindqvist Advocaten" (doc_031); "Vandermeulen" with doc_030 — rename.
5. Nothing substantive otherwise: art. 35 AOW, cao 109, arts 2044/2052 oud BW, C4, RSZ/FOD, rol-doorhaling all correct; RRN checksum and parity (even = female) valid.

## doc_034 — state aid complaint (en)

1. "enterprise number 0799.412.658" — fails the mod-97 check; use e.g. 0799.412.638 (verify).
2. Art. 24(2) complaints must use the form in Annex IV to Reg. (EC) No 794/2004; add "The completed complaint form is at Annex 0" (or lodge it "together with the form").
3. "MCS's 2024 accounts … show negative equity of EUR 6.4 million at 31 December 2023" — the loan was signed 18 December 2024, so the relevant filed accounts are FY2023: "MCS's accounts for the financial year 2023, filed with the National Bank of Belgium in July 2024 (note 12)".
4. "L'Echo of 9 December 2024 quotes Coppieters as saying" — bare surname off-register in a Commission filing ("Mr Coppieters").
5. "Project Corvane" duplicates doc_023's notifying party; "+32 2 555 08 41" duplicates doc_030 — vary.

## doc_035 — data room index (en)

1. Items 5.1 and 5.2 contradict each other: 5.1 asks the BCA whether the *Belgian* thresholds apply, 5.2 records "Pre-notification contact with the European Commission … under the EU Merger Regulation" — one-stop-shop means only one applies, and a vendor cannot pre-notify. Replace 5.2 with "Merger control assessment memorandum (Vendor's counsel) — 2 April 2026 — L2".
2. "2.3 Escrow account details: BE72 …, held with KBC in the name of ACP" — an escrow account is in the escrow agent's name and is not open before signing; make it "Proposed escrow bank and draft escrow agreement — L2".
3. "Benelux word mark HELLEBORE, registration no. 1094 7712" — BOIP numbers are 7 digits: "1094771".
4. "5.4 Environmental permit … issued 2019, valid until 2039" — Flemish omgevingsvergunningen issued since 2018 are of indefinite duration; "issued 2019 (indefinite duration)".
5. Dockets "A/24/03117" (here), "A/25/03127" (031), "A/25/03417" (027) are near-identical; "Joris Lambrechts", "Vandersmissen", "Ardenne" recur — rename/renumber.

---

## Batch-level observations

**1. Reference-number fingerprint — fix before any training/scoring.** "0417" appears in the matter reference of 10 of 15 documents (RW/GAN/2026/0417, VD/2026/0417-SAB, RD-2026-0417/CONC, VAP/COMP/2026-0417, HV/2026/0417-KVN, VDC/2026/0417-BV, VDA/2026/0417, HV-2026-0417, DP/2026/0417, VO/2026/EIF-0417). Court dockets cluster on 031xx/034xx. A detector can learn the token; a reviewer will see a template. Re-roll every reference with distinct digits.

**2. Cross-document name reuse — a rename pass is needed.** Meridian/Meridiaan is a party in five documents (022, 025, 027, 029, 031); the Corv- family in six (023 Corvane, 024 Corvalis, 027 Corvid, 031 Corvina, 034 Corvane, 035 Corvus); Hallstein in 029 and 032; Solvane in 021 and 028; Projet Héron in 022 and 024. Surnames: Lambrechts (021, 022, 024, 026, 032, 035), Deprez (024, 031, 032 — "Sofie"/"Sophie"), Peeters (021, 030, 032), Delcourt (024, 030), Vandermeulen (030, 033), Verhaeghe (031, 033), Verhaegen (022, 023), Vandersmissen (032, 035), Ardenne (026, 035). Addresses: Louizalaan 331 (026, 027), Noorderlaan (026, 027), Industrieweg/Industrielaan/rue de l'Industrie in five documents, Düsseldorf as a seat in four. This matters for a held-out split with a known-entity detector: entities learned on one document will fire on another. Run a uniqueness check against doc_001–020 as well.

**3. Numeric duplicates.** EUR 186,500,000 and long-stop 31 March 2027 in both 021 and 027; local phone number 555 08 41 in 030 and 034. Vary.

**4. Checksums.** Two enterprise numbers fail mod-97 (029: 0745.612.338; 034: 0799.412.658). All IBANs, the other KBO numbers and the RRN validate; KBC IBANs consistently use 734x/735x except 033 (0961).

**5. Calendar.** 11 September 2026 is a Friday and is "today" in six documents; it breaks 024 (raid resumes "demain" = Saturday). 033 is signed on a Saturday. Email weekdays in 028 are correct.

**6. IBANs as benchmark artefacts.** NDA penalty clause (022), advice memo fee paragraph (030), dispositif of conclusions (032), data-room index (035), raid chronology (024): a practitioner would not put an IBAN there. Acceptable for the benchmark, but each costs a realism point; if a document is regenerated, put the IBAN in a payment schedule or cover letter instead.

**7. Register of surname-only traps.** Bare surnames are natural in internal memos (024, 031, 028) and jarring in formal filings (023 "Ashcombe has confirmed", 034 "quotes Coppieters"). Keep the trap but place it in a footnote or a quoted press line.

**8. Language.** FR (022, 024, 030, 032) and NL (026, 029, 033) are native-level Belgian legal drafting: "tribunal de l'entreprise", "ondernemingsrechtbank", "dading", "verbrekingsvergoeding", "marge semi-brute", "se porte fort", "Cour des marchés", "Marktenhof", "gérante" for Geschäftsführerin all correct; no calques found. Only nit: "Mr." and "Meester" mixed within one line (029, 033).

**9. Legal substance.** Mostly sound (Art. 7:96 CCA, Art. IV.7 thresholds arithmetic in 026, Reference Rate margins and NoA paras 89–96 in 034, SCC module 3 and the 10 July 2023 DPF decision in 030, Altice in 028, eleven-month indemnity in 033). The three real slips: 032 omits art. X.35–X.40 CDE; 026 cites Intel for the wrong proposition; 022 cites Art. 6(1)(b) as the notification basis. 035's regulatory folder is internally contradictory.

**10. Regenerate vs. fix.** Nothing must be regenerated for sensitivity; all fifteen pass (verify the invented BMA auditeur in 026 and the proposed arbitrator in 029 against real staff/arbitrator lists, and change "22 Bedford Row"). Consider regenerating **one of 029/032** with a different scenario (agency, franchise, or a supply dispute) — the batch currently carries the same German-supplier/Belgian-distributor termination twice under the same supplier name. Everything else is a Word-level fix.
