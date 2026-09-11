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


# Batch 2 (doc_036–045)

Judged on the `text` field only, same rules as batch one: scores 1–5, language scored for FR only, word counts are whitespace tokens. "Sensitivity" = no real private individual, live matter or real private company as a party; `pass*` = passes once the flagged real-name collision (found by web check, see the section) is renamed in Word. Checksums, weekdays and cross-document reuse were verified by script against the ten specs and doc_001–035.

## Summary table

| id | genre | lang | words | realism | consistency | language | sensitivity |
|---|---|---|---|---|---|---|---|
| doc_036 | lettre de licenciement pour motif grave | fr | 890 | 4 | 5 | 5 | pass* (Tilkin) |
| doc_037 | merger-control advice memo | en | 896 | 5 | 5 | — | pass |
| doc_038 | conclusions devant la Chambre contentieuse (APD) | fr | 868 | 4 | 4 | 5 | pass |
| doc_039 | extrait de contrat de franchise | fr | 900 | 4 | 5 | 5 | pass* (brand) |
| doc_040 | internal investigation interview notes | en | 880 | 5 | 5 | — | pass |
| doc_041 | shareholders' agreement excerpt | en | 893 | 4 | 4 | — | pass (rename Quillon) |
| doc_042 | cartel settlement submission | en | 878 | 4 | 5 | — | pass |
| doc_043 | lettre de mise en demeure | fr | 880 | 4 | 5 | 5 | pass* (Delfosse, Bastin) |
| doc_044 | fil d'e-mails avocat–client | fr | 890 | 5 | 5 | 5 | pass (rename Sécurilex) |
| doc_045 | escrow agreement excerpt | en | 889 | 3 | 4 | — | pass |

Read first: **045, 043, 042, 036, 039, 041** (substantive legal fixes and confirmed real-name collisions). Then the batch-level rename/renumber pass (end).

---

## doc_036 — lettre de licenciement pour motif grave (fr)

Art. 35 timing is right (knowledge Fri 4 Sept → congé Tue 8 Sept is the third jour ouvrable, Saturday counting); every dated weekday label is correct.

1. **Sensitivity.** "Maître Sébastien Tilkin (Tilkin Avocats SRL, Rue des Brasseurs 12, 4000 Liège" — a real Liège firm (Bottin – Tilkin – Bodarwé, rue Saint-Pierre) and a Liège huissier Tilkin exist. Rename the worker's counsel and firm (and the e-mail domain), e.g. "Maître Sébastien Warnant, Warnant Avocats SRL".
2. "Monsieur Damien Massart, gérant de Vesdre Instruments SRL" — an SRL has no gérant under the CSA (art. 5:70): "administrateur".
3. "la réparation intégrale de son préjudice, notamment sur pied de l'article VI.104 du Code de droit économique" claimed against the worker *and* Vesdre — VI.104 binds enterprises; against the worker the basis is art. 18 LCT (dol / faute lourde): "à Vesdre Instruments SRL sur pied de l'article VI.104 CDE et à vous-même sur pied de l'article 18 de la loi du 3 juillet 1978".
4. "PAR RECOMMANDÉ ET EN MAIN PROPRE" → "EN MAINS PROPRES".
5. "Copie est adressée à votre conseil …" (§6) and "Copie : Maître Tilkin." (foot) say the same thing — keep one. First names "Xavier" (also 044) and "Grégory" (also 043) recur in the batch.

## doc_037 — merger-control advice memo (en)

Best document of the batch with 040 and 044: the Art. 1(3) arithmetic (limb (c) fails on NL/FR), the IV.7 / §35 GWB / §9 KartG tests, Illumina/Grail (C-611/22 P and C-625/22 P, 3 Sept 2024) and the 15-working-day count that skips 11 November all hold.

1. "Section 35(2) GWB does not exempt" — since 2013 §35(2) only covers public-sector mergers (kommunale Gebietsreform) and cooperative bank groupings; the carve-out a German practitioner checks is the de minimis market clause: "the de minimis market clause of Section 36(1) sentence 2 no. 2 GWB does not apply".
2. "runs from receipt by the Austrian Federal Competition Authority (the "BWB") and the Federal Cartel Prosecutor" — the filing goes to the BWB alone, which forwards it to the Bundeskartellanwalt: "runs from receipt by the BWB (Section 11 KartG)".
3. "Dhaenens has confirmed that the Seller accepts" sits between "Mr. Wim Dhaenens" and "Mr. Dhaenens indicates" in the same paragraph — off-register mid-paragraph; keep the surname-only trap in the timetable line or write "Mr. Dhaenens has confirmed".
4. Five phone numbers with "555" (+32 2 555 62 10 / 62 19 / 62 27, +32 3 555 29 84, +32 9 555 38 06); "555 62" recurs in 038 and 042 — re-roll (batch note 3).
5. "Rue Guimard 23, 1040 Brussels", "Dulle-Grietlaan 233, 9050 Gentbrugge", "Vaartkaai 62, 2170 Merksem" are real streets with plausible real occupants — check the numbers are vacant, as for "22 Bedford Row" in batch one. "Bonn" also hosts 038's processor.

## doc_038 — conclusions devant la Chambre contentieuse (fr)

LCA arts 98 and 100 §1 1°/2°, loi caméras art. 6 §2, EDPB Guidelines 3/2019, RGPD 12(3)/15(4), the DOS-2026-xxxxx docket format and the Rue de la Presse address are all correct.

1. §2.2 "pictogrammes et registre d'images sont conformes à l'arrêté royal du 8 mai 2018" vs §5 "remplacé les pictogrammes par le modèle de l'arrêté royal du 10 février 2008" — the 2018 AR governs the declaration and the register, the 2008 AR (as amended 28 May 2018) the pictogram; and compliant pictograms would not need replacing. In 2.2: "pictogrammes conformes à l'arrêté royal du 10 février 2008 et registre conforme à l'arrêté royal du 8 mai 2018"; in 5: "actualisé les pictogrammes (modèle 2018)".
2. "Optiwacht Sicherheitstechnik GmbH, établie à Bonn … qui en assure la maintenance et l'hébergement" — a Bonn installer hosting the CCTV of a Jambes garde-meubles is odd (and Bonn recurs in 037); make it a Belgian or Dutch processor, or add "hébergement dans l'Union".
3. "Madame, Monsieur," to the Chambre contentieuse → "Monsieur le Président," (or "Madame, Monsieur les Membres de la Chambre contentieuse,").
4. "Chaussée de Marche 412, 5100 Jambes" — house number 412 also in 039 ("Chaussée de Louvain 412"); change one.
5. "Mme Laurence Godefroid" — the surname is 043's street ("Rue Godefroid 64", a real Namur street); rename the complainant (e.g. "Mme Laurence Hubaux"). Phones "+32 81 555 40 78 / 555 62 93": see batch note 3.

## doc_039 — extrait de contrat de franchise (fr)

X.27/X.28 (DIP 17 Aug → signature 22 Sept, > 1 month), VBER 2022 art. 4(b)(i) and 5(3), the Charleroi ring of communes and the 7-year term arithmetic are correct.

1. **Sensitivity.** "marque verbale Benelux « BOUCHÉE DOUBLE »" — a real Brussels culinary studio "Bouchée Double" (and a 2025 gastronomy platform "Bouchées Doubles") exist in the same sector; rename the brand (e.g. « DOUBLE FOURNÉE »), incl. the domain bouchee-double.example.be.
2. "représentée par son gérant, M. Nicolas Rimaldi" and 7.2 "cessation des fonctions de M. Rimaldi en qualité de gérant" — SRL under the CSA: "administrateur" (twice); a Brussels-drafted contract would not use the old term.
3. 7.2 "résilier avec effet immédiat en cas de faillite, de réorganisation judiciaire" — a clause triggered by the opening of a PRJ is ineffective (art. XX.56 §2 CDE); drop "de réorganisation judiciaire" or add "dans les limites de l'article XX.56 CDE".
4. "Réf. : MV/26/2318 — Dossier suivi par : Marlière / Kesteloot" at the head of a signed contract — a fee-earner line belongs on a draft; label the excerpt "Projet" or keep the reference in 9.2 only (same pattern in 041, 045; batch note 1).
5. "35.000 €" is also 044's budget total; first name "Nicolas" also 044 — vary.

## doc_040 — internal investigation interview notes (en)

Nothing substantive to fix: the Breda → 15 April announcement sequence, the litigation hold → group exit (24 → 26 Aug), Horizontal Guidelines ch. 6, the BCA's 2020 leniency guidelines, Art. 12 Reg. 1/2003 and the closing "not verbatim; not read back" are all right.

1. "Ms. Rasquin gave the Upjohn warning" / "Litigation hold of 24 August 2026" — US vocabulary in a Belgian firm's notes; acceptable in international practice, but "explained that the Firm acts for the Company only" and "document preservation notice" read more Brussels.
2. "+49 171 5539 2846" — German 0171 mobiles carry seven digits after the prefix: "+49 171 553 9284".
3. "Real risk that Griesbacher approaches the Belgian Competition Authority first" — with Dutch and German meetings and effect on trade, the first port of call would be the Commission: "approaches the Commission or a national authority first".
4. "Zwartebeekstraat 41, 2800 Mechelen" vs 045's "Zwartzustersvest 141, 2800 Mechelen" — two Mechelen seats with near-identical street strings; move Pentaflex (e.g. Lier).
5. "Wouter Deneckere", "Saskia Verlinden", "Tobias Eyckmans" — Wouter appears in four documents (040, 041, 042, 045), Saskia in 045, Tobias in 041; rename.

## doc_041 — shareholders' agreement excerpt (en)

Capital table (24,000 × EUR 1,000; 12,000 / 9,600 / 2,400), Art. 7:195 blocked account, 7:78, Art. 4 → 6(1)(b) condition (the batch-one 022 error is not repeated), bindende derdenbeslissing and the Lux Class A/B managers are correct.

1. 2.2 "as confirmed in the Expert's report under Article 7:197 of the Code" covers only Vlietmolen's extrusion line, while 2.3 issues the Founder's 2,400 shares "against the contribution in kind of the Halyard know-how and the domain name" — that contribution also needs the 7:197 report and a value: "…together with the Founder's contribution in kind valued at EUR 2,400,000, in the Expert's report under Article 7:197".
2. 8.1 "declaring the formation of Zwalmveld Bioplastics NV as a full-function joint venture" — the Company already exists (enterprise number, seat, Founder); what is notified is the acquisition of joint control: "declaring the acquisition of joint control over the Company by Vlietmolen and the Investor (a full-function joint venture)…"; add that the Art. 1 thresholds are met on the two shareholders' group turnover.
3. 10.1 "the Enterprise Court of Brussels (Dutch-speaking division)" — a separate court, not a division: "the Dutch-speaking Enterprise Court of Brussels" (as 045 has it).
4. "Drafted by Tanghe Sabbe Advocaten BV … our ref. TS/2026/HAL/0731 (Vereecke / Tanghe)" on an execution version — delete or move to a cover e-mail; "0731" ≈ 044's "PJ/2026/07731".
5. "Quillon Growth Equity ("QGE")" — "Quillon Partners" is a real investment advisory firm; rename. "Bavo" (also 042), "Tobias" (040), "Wouter" (040/042/045) recur; "Dated 3 September 2026" is also 045's signing date.

## doc_042 — cartel settlement submission (en)

The point-20 checklist (liability, facts/qualification/role/duration, maximum fine, procedural confirmations, language), points 17/27/29/32, Art. 10a(2) and 15(1a) Reg. 773/2004, Art. 6(6) Dir. 2014/104 and the Leniency Notice second-applicant band are all correct; the surname-only trap sits in a quoted footnote, as batch one recommended.

1. "enterprise number 0682.315.402" fails mod 97 → "0682.315.420".
2. "By hand and by secure e-mail" — settlement submissions are lodged via eLeniency: "Submitted via eLeniency; hard copy by hand" (same slip as batch-one 025).
3. "quoted at paragraph 148 of the summary of objections" / "as presented in the summary of objections of 2 July 2026" — not a Settlement Notice term; the Commission discloses the "essential elements" at settlement meetings (point 16): "the Commission's presentation of the essential elements of the case at the settlement meeting of 2 July 2026 (point 16 of the Settlement Notice)".
4. §12 "In that event the acknowledgements above shall be deemed withdrawn" — "that event" has no antecedent after 11(c): "Should the statement of objections or the final decision not reflect this submission, the acknowledgements…".
5. "+32 2 555 62 39" shares "555 62" with 037/038; "Céline" (043), "Harriet" (045), "Wouter" (040/041/045), "Bavo" (041), "Breda" (040) recur — rename/renumber. Verify "Case AT.41786" (and 045's "M.12917") against the case register at release.

## doc_043 — lettre de mise en demeure (fr)

Arithmetic (4 invoices = 96,720.50; +160 +9,672.05 = 106,552.55), loi du 2 août 2002 arts 5–6, art. 1798 aCC action directe, competence of tribunal de l'entreprise de Liège, division Huy (Amay) and the agréation point are correct; excellent Belgian French ("TVAC", "agréation", "sans reconnaissance préjudiciable").

1. "facture n° F26-1183 … : 41.140,00 € TVAC" (×4) — works on immovable property between VAT-registered contractors are reverse-charged (AR n° 1, art. 20): a subcontractor's invoices carry no VAT. Write "HTVA (TVA autoliquidée par le cocontractant)" on the four lines; the totals can stay.
2. **Sensitivity.** "Maître Sandrine Delfosse, Delfosse & Coibion, Rue des Vennes 27, 4020 Liège" — "Avocats Delfosse" is a real Liège firm (founded 1920) active in construction and liability law: rename (e.g. "Maître Sandrine Gilon, Gilon & Coibion"). "HENNEQUIN & BASTIN AVOCATS SRL" — a Maître Hélène Bastin practises at the Namur bar: rename the second partner. "Tôleries Havelange SA … Andenne" — Andenne has real Havelange family businesses (Scierie Havelange): rename or move the seat.
3. "À l'attention de Monsieur Grégory Marbaix, gérant" → "administrateur" (SRL, CSA).
4. "IBAN BE50 7320 4471 9053" passes the ISO mod-97 check but fails the Belgian BBAN check digit → "BE49 7320 4471 9071".
5. "Nos réf. : CH/2026/1362-TOH" ≈ 038's "PW/2026/1364-STM"; "Rue Godefroid 64" = 038's complainant surname and shares the house number with 044's "Rue de la Sablière 64" — re-roll.

## doc_044 — fil d'e-mails avocat–client (fr)

Best French document: X.36–X.38 handled correctly (the point batch-one 032 missed), Cass. 10 sept. 1971 (Pas., 1972, I, 28) accurate, art. 156 loi du 4 avril 2014, arts 735/747 CJ, the 24 € fonds d'aide juridique, the 12,100 € TVAC provision and the weekday chain (Mon 7 → Tue 8 → Wed 9 → Thu 10) all hold; the IBAN sits where it belongs.

1. "IBAN BE72 7320 5581 9046" — ISO check passes, Belgian BBAN check digit fails → "BE85 7320 5581 9006".
2. "Sécurilex Assurances SA" — one letter from Securex, a real Belgian provider of protection juridique: rename (e.g. "Juridis Protect SA").
3. 10 Sept "Camille vous envoie ce matin la convention d'honoraires et le projet de citation" after 8 Sept "projet de citation ci-joint" → "le projet de citation revu".
4. "Le gérant de HIB, Ludovic Quertinmont" — tolerable in the client's register (SRL → administrateur); leave or fix with the others.
5. "PJ/2026/07731" ≈ 041's "TS/2026/HAL/0731"; "Rue de la Sablière 64, 1400 Nivelles" — Nivelles is also 024's raided site and "64" is 043's house number; first names "Nicolas" (039) and "Xavier" (036) recur — vary.

## doc_045 — escrow agreement excerpt (en)

1. "for EUR 58,400,000 … Completion is conditional on the European Commission declaring the concentration compatible … (Case M.12917)" — a wind-farm target sold for EUR 58.4 m cannot reach the Art. 1 EUMR turnover floors (the target itself needs EUR 250 m / 100 m EU-wide turnover); a Brussels reader stops here. Either replace the condition with the Belgian FDI screening (cooperation agreement of 30 Nov 2022; Interfederal Screening Committee — apt for a UK buyer of Belgian energy assets) or make the deal ten times larger.
2. "notified the concentration on 21 August 2026 …; a decision is expected by 23 October 2026" — Phase I is 25 working days: 25 September 2026 (23 October ≈ 45 WD; with commitments 35 WD → 9 October). Fix the date if the EU condition stays.
3. "Cnockaert Wynants Advocaten BV — Our ref.: CW-26-1447/ESC (Cnockaert / Wynants)" in the title block of an execution version — delete or move to a cover note (as 039, 041).
4. "conventional sequestrator (séquestre conventionnel) … Articles 1956 to 1958 of the old Belgian Civil Code" — a French term in an otherwise Dutch-language notarial setting (derdenrekening, bedrijfsrevisor): "(sekwester / séquestre conventionnel)"; art. 1956 presumes a "chose contentieuse", so add "by analogy".
5. "58,400,000" equals doc_026's turnover figure "58.400.000 EUR"; "Dated 3 September 2026" also 041; long-stop "26 February 2027" also 037 and 044; "Zwartzustersvest 141, 2800 Mechelen" ≈ 040's "Zwartebeekstraat 41, 2800 Mechelen"; "Wouter", "Saskia", "Harriet" recur — vary. Otherwise sound: Art. 7:93 CSA, ING/BBRUBEBB, the Dutch-speaking Enterprise Court and "Commercial Court in London" (the 027 fix applied).

---

## Batch-level observations

**1. Reference-number fingerprint — mostly fixed, template still visible.** Batch one's "0417" token is gone: the 19 references carry distinct digit runs. Two near-pairs remain (043 "CH/2026/1362-TOH" vs 038 "PW/2026/1364-STM"; 041 "TS/2026/HAL/0731" vs 044 "PJ/2026/07731"), and the shape "AA/2026/dddd-XXX" (initials / year / four digits / three-letter codename) is used by five firms (037, 038, 040, 042, 043), while three contracts carry a "(Surname / Surname)" fee-earner tag (039, 041, 045). Vary the shapes.

**2. Cross-document name reuse — surnames fixed, first names and cities not.** No surname of batch two recurs within the batch or in doc_001–035 (script-checked; batch one's Lambrechts/Meridian problem is solved), and the five codenames (Sarment, Bramble, Halyard, Cinnabar, Sorbier) are unique. First names cluster instead: Wouter ×4 (040, 041, 042, 045), Saskia, Tobias, Bavo, Harriet, Céline, Nicolas, Xavier, Grégory ×2 each. Geography clusters: three Namur firms at 5000 Namur (038, 043, 044), Mechelen ×2 (040, 045), Breda ×2 (040, 042), Bonn ×2 (037, 038), 1040 Brussels ×2 (037, 045), Nivelles (044 + 024). "Godefroid" is a surname in 038 and a (real) street in 043.

**3. Numeric duplicates.** House number 412 (038, 039), 62/63/64 clusters (Rue des Trois Fontaines 62 / Vaartkaai 62; Kapellestraat 63 / boulevard 63 / Rue Pépin 63; Rue Godefroid 64 / Rue de la Sablière 64); phone group "555 62" in 037, 038, 042 (nine "555" numbers in the batch, all in 037/038/042 — the FR letters from Huy, Namur and Liège use genuine zone codes and read better); EUR 58,400,000 (045) = doc_026's turnover; 218,400 (043) = doc_017's data-subject count; 35,000 (039, 044); long-stop 26 Feb 2027 (037, 044, 045); signing date 3 Sept 2026 (041, 045); 10 September 2026 is "today" in six of ten (036, 038, 040, 042, 043, 044), as 11 September was in batch one.

**4. Checksums — recurred.** One of thirteen enterprise numbers fails mod 97 (042: 0682.315.402 → 0682.315.420). All six IBANs pass the ISO mod-97 check, but two fail the Belgian BBAN check digit (043 → BE49 7320 4471 9071; 044 → BE85 7320 5581 9006); batch one's 035 (BE72 7340 8812 5507) has the same latent defect — the first report validated ISO only. Add the BBAN check to the validator.

**5. Calendar — fixed.** Every 2026 date is a weekday and all ~25 stated weekday labels (036, 037, 040, 043, 044) are correct; 036's three-working-day count and 037's 15-working-day count (skipping 11 November) are right. The only weekend dates are real statute dates (loi du 3 décembre 2017, AR du 10 février 2008). The one calendar error is legal, not weekday: 045's Phase I date.

**6. IBANs as benchmark artefacts — fixed.** Each IBAN now sits where a practitioner puts it: final pay (036), royalties clause (039), blocked capital account (041), payment paragraph of a demand letter (043), fee e-mail (044), escrow-account definition (045).

**7. Surname-only in formal filings — fixed.** 042 puts "Vezzani"/"Blancquaert" inside a quoted message in a footnote and 038 puts "Godefroid" in a quoted e-mail subject, as recommended; the internal notes (040) and e-mails (044) use bare names naturally. One mild lapse: 037's mid-paragraph "Dhaenens has confirmed".

**8. Language.** FR (036, 038, 039, 043, 044) is native Belgian legal French: "sur pied de", "pécule de vacances de sortie", "C4", "Dimona OUT", "TVAC", "agréation", "sans reconnaissance préjudiciable", "débats succincts", "indemnité de procédure", "Chère Maître", "Bien à vous", "le grief manque en fait" — no calques found. Two nits: "en main propre" (036), and "gérant" for an SRL in 036, 039, 043, 044 — pre-CSA vocabulary ("administrateur"); acceptable in a client's e-mail (044), a slip in a Brussels-drafted contract (039).

**9. Legal substance — stronger than batch one, one structural slip.** Right: 037's thresholds and referral analysis; 042's point-20 checklist; 043's action directe and 2002 law; 044's X.36–X.38 and Cass. 1971; 036's art. 35 timing; 038's LCA arts 98/100; 039's VBER 4(b)(i)/5(3); 041's 7:195/7:197 and Art. 4 → 6(1)(b); 045's 7:93 and court names (the 027 "Commercial Court of London" fix applied). Wrong or loose: 045's EU clearance condition on a EUR 58 m deal and its Phase I date; 043's "TVAC" on reverse-charged construction invoices; 042's "summary of objections" and hand delivery instead of eLeniency (025's slip repeated); 041's court name and 7:197 coverage; 037's §35(2) GWB; 038's pictogram decree; 039's PRJ termination trigger.

**10. Sensitivity — web-checked this time; several real-name collisions.** None is a real individual named as a party, so nothing fails outright, but rename before release: Tilkin (036 — real Liège law firm and huissier), Delfosse (043 — real Liège firm in construction/liability law), Bastin (043 — real Namur avocate), Bouchée Double (039 — real Brussels culinary studio), Sécurilex ≈ Securex (044 — real insurer, same product), Quillon ≈ Quillon Partners (041), Havelange family businesses in Andenne (043). All other invented companies, firms, notaries and competitors (Hesbaye Capteurs, Vesdre Instruments, Stockerie Mosane, Sablieux, Rimaldi Lunch, Optiwacht, Pentaflex Conveyor Belts, Terhaegen, Waelkens Sensortechniek, Scheldeboord Invest, Zwalmveld, Vlietmolen, Kempische Windkracht, Vaerenbergh, Thistlewood, Dorimont, HIB, Merckaert, Orvalline, Griesbacher, Rondelaar, Ziegelhoff, Perlati, Fenwright, BBP, ECMF, Quintard Lemahieu, Piérard Willems, Rousselot & Wanlin, Duvivier Hasselbrink, Ravaillé Deblonde, Marlière & Kesteloot, Cnockaert Wynants, Tanghe Sabbe, Meulebroeck Dhaenens, Verbiest & Callewaert, Descheemaeker & Vranckx) returned no match. Verify AT.41786 and M.12917 against the Commission's case register at release.

**11. Regenerate vs. fix.** Nothing needs regeneration. The only paragraph-level rewrite is 045's condition (recital (B) and clause 2.3); everything else — the three checksums, the seven renames, "TVAC", "gérant", the reference and phone re-roll — is a Word-level edit.
