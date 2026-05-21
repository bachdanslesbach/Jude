"""Build gold-annotated benchmark documents.

Each document is defined as (text, list-of-(text, type)) tuples. The
helper finds the character offsets of each annotation in the text and
writes the JSON in the schema expected by GoldDocument.

Run: python -m benchmark._build_corpus
"""

from __future__ import annotations

import json
import re
from pathlib import Path

CORPUS_DIR = Path(__file__).parent / "corpus"


def _spans(text: str, annotations: list[tuple[str, str]]) -> list[dict]:
    """Find all occurrences of each annotation, return GoldSpan dicts.

    De-duplicates: when a shorter annotation occurrence is fully
    contained inside a longer annotation occurrence (e.g. "Lumen
    Reality" inside "Lumen Reality SARL" at the same character
    positions), only the longer form is kept. This is correct because
    the benchmark uses lenient overlap: a prediction of "Lumen Reality"
    will be credited as a TP against the longer gold span. Keeping
    both would produce phantom false-negatives.
    """

    candidates = []
    for surface, type_ in annotations:
        for m in re.finditer(re.escape(surface), text):
            candidates.append({
                "start": m.start(),
                "end": m.end(),
                "type": type_,
                "text": surface,
            })

    # Drop any candidate strictly contained in a longer candidate of the
    # same type at overlapping char positions.
    kept = []
    for c in candidates:
        contained = any(
            o is not c
            and o["type"] == c["type"]
            and o["start"] <= c["start"]
            and c["end"] <= o["end"]
            and (o["end"] - o["start"]) > (c["end"] - c["start"])
            for o in candidates
        )
        if not contained:
            kept.append(c)
    kept.sort(key=lambda s: (s["start"], -(s["end"] - s["start"])))
    return kept


def doc_term_sheet_en():
    text = """\
PROJECT AURORA — DRAFT TERM SHEET
PRIVILEGED & CONFIDENTIAL — Working Draft of 12 March 2026

Parties:
  - Buyer: Acme Solutions SA, a Belgian société anonyme headquartered in Brussels.
  - Seller: Lumen Reality SARL, a French société à responsabilité limitée at 22 rue de Rivoli, 75001 Paris.

Counsel:
  - For the buyer: Maître Sophie Martin (sophie.martin@example-law.eu, +33 1 44 55 66 77).
  - For the seller: Dr. James Chen (j.chen@example-cabinet.fr).

The Buyer proposes to acquire 100% of Lumen Reality SARL for €450,000,000, payable in cash on closing. The transaction will be subject to clearance under Regulation (EU) 139/2004 and notification under the Digital Markets Act if applicable. The European Commission has been pre-notified.

Escrow account: BNP Paribas, IBAN FR76 3000 4000 5000 0123 4567 890.

The matter has been assigned reference Case T-203/24 internally."""
    annotations = [
        ("Acme Solutions SA", "ORG"),
        ("Brussels", "LOC"),
        ("Lumen Reality SARL", "ORG"),
        ("rue de Rivoli", "LOC"),
        ("Paris", "LOC"),
        ("Sophie Martin", "PERSON"),
        ("sophie.martin@example-law.eu", "EMAIL"),
        ("+33 1 44 55 66 77", "PHONE"),
        ("James Chen", "PERSON"),
        ("j.chen@example-cabinet.fr", "EMAIL"),
        ("BNP Paribas", "ORG"),
        ("FR76 3000 4000 5000 0123 4567 890", "IBAN"),
        ("Case T-203/24", "CASE_REF"),
        ("Lumen Reality", "ORG"),  # second mention shorter
    ]
    return {
        "id": "doc_001_term_sheet_en",
        "title": "Project Aurora — Draft term sheet (English)",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Fictional M&A term sheet. SHOULD redact: client names "
            "(Acme, Lumen Reality), counsel names + contacts, addresses, "
            "IBAN, internal case ref. SHOULD NOT redact: European "
            "Commission, Digital Markets Act, Regulation (EU) 139/2004, "
            "Buyer/Seller/Counsel labels."
        ),
    }


def doc_credit_facility_en():
    text = """\
MEMORANDUM — €750M REVOLVING CREDIT FACILITY

To: Christian Hartmann (c.hartmann@ubs-legal.ch, +41 44 234 5678)
From: Anne-Sophie Lefèvre, External Counsel
Subject: Pioneer Industries SA / UBS — proposed pricing terms

Dear Christian,

Pioneer Industries SA, a Luxembourg société anonyme, has requested a €750,000,000 multi-currency revolving credit facility from UBS. Pricing on the term sheet is SOFR + 175 bps, stepping down to 125 bps at investment grade. Disbursement will route through IBAN LU60 0030 1234 5678 9000.

The Bundeskartellamt and the Autorité de la concurrence have been notified. The European Banking Authority has issued no objection to the proposed structure under the leveraged-transactions guidance. We expect closing by Q3 2026.

The matter ID for our records is M-2026-PIO-001.

Please call me at +33 1 53 89 76 21 if you have questions.

Best regards,
Anne-Sophie Lefèvre
a.lefevre@example-swiss-legal.ch"""
    annotations = [
        ("Christian Hartmann", "PERSON"),
        ("Christian", "PERSON"),  # salutation reference to the same person
        ("c.hartmann@ubs-legal.ch", "EMAIL"),
        ("+41 44 234 5678", "PHONE"),
        ("Anne-Sophie Lefèvre", "PERSON"),
        ("Pioneer Industries SA", "ORG"),
        ("UBS", "ORG"),
        ("Luxembourg", "LOC"),
        ("LU60 0030 1234 5678 9000", "IBAN"),
        ("+33 1 53 89 76 21", "PHONE"),
        ("a.lefevre@example-swiss-legal.ch", "EMAIL"),
    ]
    return {
        "id": "doc_002_credit_facility_en",
        "title": "Pioneer Industries / UBS — Credit facility memo",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Counsel-to-counsel memorandum on a syndicated facility. "
            "SHOULD redact: lawyer names + contacts, borrower (Pioneer "
            "Industries SA), arranger (UBS, since here it's a party not a "
            "regulator). SHOULD NOT redact: Bundeskartellamt, Autorité "
            "de la concurrence, European Banking Authority — these are "
            "regulators in plain references. The matter ID M-2026-PIO-"
            "001 is internal but not necessarily PII; conservative "
            "annotation excludes it."
        ),
    }


def doc_solaris_jv_fr():
    text = """\
NOTE CONFIDENTIELLE — TotalEnergies SE / Mediterranean Solar Group

Bruxelles, le 8 avril 2026

À : Pierre Dubois (p.dubois@example-cabinet-fr.fr, +33 1 53 89 76 21)
De : Maria Rodríguez

Objet : Coentreprise photovoltaïque en Afrique du Nord

Cher Pierre,

TotalEnergies SE et Mediterranean Solar Group SARL envisagent une coentreprise dans laquelle TotalEnergies détiendrait 60% du capital. L'engagement total d'investissement est de 1.200.000.000 €. Le siège de Mediterranean Solar Group se trouve à Casablanca.

L'Autorité de la concurrence française a été informée. La Commission européenne examinera l'opération si les seuils de la Regulation (EC) 139/2004 sont atteints. L'ADEME et la BEI sont susceptibles de co-financer la phase de construction.

Le compte de séquestre est ouvert à BIL : IBAN LU28 0019 4006 4475 0000.

Les contrats définitifs devraient être signés à Casablanca le 30 septembre 2026. Mon adresse pour le courrier confidentiel : Maria Rodríguez, 14 boulevard Haussmann, 75009 Paris.

Bien à vous,
Maria Rodríguez (m.rodriguez@example-cabinet.fr)"""
    annotations = [
        ("Pierre Dubois", "PERSON"),
        ("p.dubois@example-cabinet-fr.fr", "EMAIL"),
        ("+33 1 53 89 76 21", "PHONE"),
        ("Maria Rodríguez", "PERSON"),
        ("TotalEnergies SE", "ORG"),
        ("TotalEnergies", "ORG"),  # short form
        ("Mediterranean Solar Group SARL", "ORG"),
        ("Mediterranean Solar Group", "ORG"),  # short form
        ("Casablanca", "LOC"),
        ("LU28 0019 4006 4475 0000", "IBAN"),
        ("BIL", "ORG"),
        ("14 boulevard Haussmann", "LOC"),
        ("Paris", "LOC"),
        ("m.rodriguez@example-cabinet.fr", "EMAIL"),
    ]
    return {
        "id": "doc_003_solaris_jv_fr",
        "title": "Projet Solaris — Note JV (French)",
        "language": "fr",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Working memo on a North-Africa solar JV. SHOULD redact: "
            "lawyer names + contacts, parties (TotalEnergies, "
            "Mediterranean Solar Group), city addresses, IBAN, BIL "
            "(named as the depository bank, hence party-adjacent). "
            "SHOULD NOT redact: Autorité de la concurrence, Commission "
            "européenne, Regulation (EC) 139/2004, ADEME, BEI."
        ),
    }


def doc_brussels_letter_nl():
    text = """\
GEACHTE COLLEGA,

Hierbij bevestigen wij ons advies inzake het geschil tussen onze cliënt Vermeer Logistics BVBA en de tegenpartij De Smet & Zonen NV. Het dossier wordt behandeld door de Belgische Mededingingsautoriteit onder kenmerk C2026-001.

Onze contactgegevens:
- Maître Jan Peeters, j.peeters@example-be-legal.be, +32 2 555 0123
- Adres kantoor: Wetstraat 16, 1040 Brussel.

De zaak verwijst naar Case C-403/19 voor de jurisdictiekwestie. Wij verwachten dat de Europese Commissie geen actie zal ondernemen onder de Digital Markets Act.

Het cliëntenrekening voor de afhandeling: BE68 5390 0754 7034.

Met vriendelijke groet,
Jan Peeters"""
    annotations = [
        ("Vermeer Logistics BVBA", "ORG"),
        ("De Smet & Zonen NV", "ORG"),
        ("Jan Peeters", "PERSON"),
        ("j.peeters@example-be-legal.be", "EMAIL"),
        ("+32 2 555 0123", "PHONE"),
        ("Wetstraat 16", "LOC"),
        ("Brussel", "LOC"),
        ("Case C-403/19", "CASE_REF"),
        ("BE68 5390 0754 7034", "IBAN"),
    ]
    return {
        "id": "doc_004_brussels_letter_nl",
        "title": "Brussels-bar advice letter (Dutch)",
        "language": "nl",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Dutch counsel-to-counsel letter. SHOULD redact: client / "
            "counterparty names, lawyer name + contacts, office address, "
            "case ref C-403/19 (a citation but Belgian internal "
            "reference here), IBAN. SHOULD NOT redact: Belgische "
            "Mededingingsautoriteit, Europese Commissie, Digital "
            "Markets Act."
        ),
    }


def doc_supply_agreement_en():
    text = """\
LONG-TERM SUPPLY AGREEMENT — DRAFT v3

Parties:
  Supplier: Acme Mining Holdings Ltd, a Cayman exempted company.
  Offtaker: Bavarian Steel Holdings AG, Munich.

Counsel:
  Dr. Markus Weber (m.weber@example-de.de, +49 89 1234 5678) — for Acme Mining Holdings Ltd.
  Lars Andersson (l.andersson@example-svensk-juridik.se) — for Bavarian Steel Holdings AG.

The agreement contemplates supply of approximately 8.4 million metric tonnes of iron ore concentrates over 5 years. Aggregate contract value: USD 2,300,000,000. Pricing follows the Platts IODEX 65% Fe Index.

Competition / antitrust:
The Bundeskartellamt has been informed. The Swiss COMCO is unlikely to take an interest. Article 101 TFEU applies; vertical block exemption Regulation (EU) 2022/720 may be relevant.

Sanctions:
The Supplier confirms compliance with OFAC, EU sanctions (Council Regulation (EU) 833/2014), and SECO requirements.

Wire instructions:
Beneficiary: Acme Mining Holdings Ltd
IBAN: DE89 3704 0044 0532 0130 00
SWIFT/BIC: COBADEFFXXX

Signed at Hamburg on 15 May 2026."""
    annotations = [
        ("Acme Mining Holdings Ltd", "ORG"),
        ("Bavarian Steel Holdings AG", "ORG"),
        ("Munich", "LOC"),
        ("Markus Weber", "PERSON"),
        ("m.weber@example-de.de", "EMAIL"),
        ("+49 89 1234 5678", "PHONE"),
        ("Lars Andersson", "PERSON"),
        ("l.andersson@example-svensk-juridik.se", "EMAIL"),
        ("DE89 3704 0044 0532 0130 00", "IBAN"),
        ("Hamburg", "LOC"),
    ]
    return {
        "id": "doc_005_supply_agreement_en",
        "title": "Iron-ore supply agreement (English)",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Long-term commodity supply agreement. SHOULD redact: "
            "supplier / offtaker names, counsel names + contacts, IBAN, "
            "city refs that locate parties (Munich = offtaker HQ, "
            "Hamburg = signing place). SHOULD NOT redact: "
            "Bundeskartellamt, Swiss COMCO, OFAC, SECO, Article 101 "
            "TFEU, Regulation (EU) 2022/720, Council Regulation (EU) "
            "833/2014."
        ),
    }


def doc_employment_dispute_en():
    text = """\
MEMORANDUM — PRIVILEGED & CONFIDENTIAL
Re: Harrington v. Northbridge Analytics Ltd — wrongful dismissal claim

Prepared by: Eleanor Whitfield, Counsel for the Claimant
Date: 21 May 2026

1. Background

Our client, Mr. Daniel Harrington, was employed as Senior Quantitative Analyst by Northbridge Analytics Ltd (HQ at 14 Cornhill, London EC3V 3ND) from 3 February 2019 until his summary dismissal on 11 March 2026. Mr. Harrington reported to the firm's CTO, Ms. Priya Subramanian, and previously to former CTO Marcus Goldberg, who left Northbridge in late 2024.

2. The dismissal

On 11 March 2026 Mr. Harrington received a one-line email from HR (sent by Ms. Olivia Tran, head of People Ops, olivia.tran@northbridge-analytics.co.uk) terminating his employment for "irreconcilable performance differences", with no PIP, no warning, and no right of appeal. We say this is a plain breach of the contractual disciplinary procedure and an unfair dismissal under the Employment Rights Act 1996.

3. Comparators

Two colleagues recently raised parallel grievances: Mr. Karim El-Sayed (now at a competitor) and Ms. Hannah Vogel. Both have confirmed they will give witness statements. We hold their contact details on file.

4. Next steps

We propose to file the ET1 next week under tribunal reference NBA-2026-014. The settlement window before issue closes on 6 June 2026. Please call me on +44 20 7946 2231 or write to e.whitfield@example-uk-law.co.uk.

The Information Commissioner's Office has not been involved; no GDPR complaint has been lodged."""
    annotations = [
        ("Harrington", "PERSON"),
        ("Northbridge Analytics Ltd", "ORG"),
        ("Northbridge Analytics", "ORG"),
        ("Northbridge", "ORG"),
        ("Eleanor Whitfield", "PERSON"),
        ("Daniel Harrington", "PERSON"),
        ("Mr. Harrington", "PERSON"),
        ("14 Cornhill", "LOC"),
        ("London EC3V 3ND", "LOC"),
        ("Priya Subramanian", "PERSON"),
        ("Marcus Goldberg", "PERSON"),
        ("Olivia Tran", "PERSON"),
        ("olivia.tran@northbridge-analytics.co.uk", "EMAIL"),
        ("Karim El-Sayed", "PERSON"),
        ("Hannah Vogel", "PERSON"),
        ("NBA-2026-014", "CASE_REF"),
        ("+44 20 7946 2231", "PHONE"),
        ("e.whitfield@example-uk-law.co.uk", "EMAIL"),
    ]
    return {
        "id": "doc_006_employment_dispute_en",
        "title": "Harrington v. Northbridge — wrongful dismissal memo",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Internal counsel memo on a wrongful dismissal claim. "
            "SHOULD redact: claimant, employer, all named individuals "
            "(current/former execs, HR contact, comparator witnesses), "
            "office address, internal tribunal reference, counsel "
            "contact info. SHOULD NOT redact: Employment Rights Act "
            "1996 (statute), Information Commissioner's Office (UK DPA, "
            "regulator), GDPR (regulation). 'CTO' is a role label."
        ),
    }


def doc_patent_litigation_en():
    text = """\
IN THE UNITED STATES DISTRICT COURT FOR THE DISTRICT OF DELAWARE

Helios Photonics Inc., Plaintiff,
v.
Lumen Optical Systems Corp., Defendant.

Civil Action No. 1:26-cv-00489-RGA

PLAINTIFF'S OPENING BRIEF ON CLAIM CONSTRUCTION (excerpt)

Plaintiff Helios Photonics Inc. ("Helios"), a Delaware corporation with its principal place of business at 2200 Greenfield Drive, San Jose, California 95110, brings this action against Lumen Optical Systems Corp. ("Lumen"), a Cayman exempted company with its US office in Austin, Texas. The dispute concerns U.S. Patent No. 11,482,917 ("the '917 patent") covering tunable laser modulation in optical transceivers.

The named inventor, Dr. Anika Krishnamurthy, is Helios's Chief Scientist. Dr. Krishnamurthy will testify that her June 2018 lab notebook (Helios Bates HEL-NB-00231) discloses every limitation of claim 1 well before Lumen's earliest priority date.

Lumen's lead engineer on the accused product line is Mr. Jonas Sandström, formerly of Helios's R&D team. Mr. Sandström left Helios in November 2020, three months before Lumen filed its competing application. We will present forensic evidence that Mr. Sandström downloaded 412 confidential design files to a personal device the week of his departure.

Counsel for Helios: Rebecca Lin (rlin@example-patent-firm.com, +1 415 555 0188), with co-counsel Dr. Stefan Müller appearing pro hac vice.

Lumen is represented by Wilkerson Stone LLP. The USPTO concurrently has the related IPR2025-00712 under consideration."""
    annotations = [
        ("Helios Photonics Inc.", "ORG"),
        ("Helios Photonics", "ORG"),
        ("Helios", "ORG"),
        ("Lumen Optical Systems Corp.", "ORG"),
        ("Lumen Optical Systems", "ORG"),
        ("Lumen", "ORG"),
        ("1:26-cv-00489-RGA", "CASE_REF"),
        ("2200 Greenfield Drive", "LOC"),
        ("San Jose", "LOC"),
        ("Austin", "LOC"),
        ("Anika Krishnamurthy", "PERSON"),
        ("Dr. Krishnamurthy", "PERSON"),
        ("Jonas Sandström", "PERSON"),
        ("Mr. Sandström", "PERSON"),
        ("Rebecca Lin", "PERSON"),
        ("rlin@example-patent-firm.com", "EMAIL"),
        ("+1 415 555 0188", "PHONE"),
        ("Stefan Müller", "PERSON"),
        ("Wilkerson Stone LLP", "ORG"),
        ("IPR2025-00712", "CASE_REF"),
    ]
    return {
        "id": "doc_007_patent_litigation_en",
        "title": "Helios v. Lumen — patent claim-construction brief",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "US patent litigation pleading. SHOULD redact: both parties "
            "and all short forms, civil action number (party-specific), "
            "inventor and ex-employee names, opposing firm (Wilkerson "
            "Stone LLP), counsel contacts, addresses pinning the "
            "parties, IPR docket. SHOULD NOT redact: Delaware (state-"
            "of-incorporation descriptor), Cayman (incorporation "
            "descriptor), USPTO (regulator), 'California', 'Texas' here "
            "are state names tied to party HQs — annotate the city, "
            "not the state, to keep it lenient. The patent number is a "
            "public document identifier, not PII."
        ),
    }


def doc_regulatory_submission_en():
    text = """\
SUBMISSION TO THE BUNDESKARTELLAMT
Case file B6-127/26 — Proposed acquisition of MeridianMedia GmbH by Polaris Broadcasting AG

Filed by: Dr. Friedrich Albrecht, Partner, on behalf of Polaris Broadcasting AG
Date: 21 May 2026
Contact: f.albrecht@example-de-kartell.de / +49 30 2576 4400

1. Notifying party

Polaris Broadcasting AG ("Polaris"), a Berlin-headquartered Aktiengesellschaft (Karl-Liebknecht-Straße 8, 10178 Berlin), proposes to acquire 100% of the share capital of MeridianMedia GmbH ("MeridianMedia"), a Hamburg-based regional broadcaster controlled by the Henkel-Vorwerk family trust.

2. The target

MeridianMedia operates 14 regional FM radio licences and a streaming service (MeridianFM+) with approximately 2.1 million monthly active listeners. Its CEO, Ms. Renate Hofmann, will remain in post for an 18-month transition period under a side letter dated 14 May 2026.

3. Competition assessment

Polaris and MeridianMedia do not currently compete in any product market. Polaris is active only in television; MeridianMedia is radio-only. We submit that no horizontal overlap arises. Vertical concerns are limited because Polaris's content-licensing business sells to all radio broadcasters on FRAND terms.

The transaction has no EU dimension under the EU Merger Regulation (Regulation (EC) 139/2004); turnover thresholds are not met. The Autorité de la concurrence and the ACM have been informally apprised but no parallel filing is required.

4. Escrow

The purchase-price escrow is held at Deutsche Bank under IBAN DE12 5001 0517 5407 3249 31. Total consideration: EUR 184,500,000.

Please direct further questions to the undersigned."""
    annotations = [
        ("B6-127/26", "CASE_REF"),
        ("MeridianMedia GmbH", "ORG"),
        ("MeridianMedia", "ORG"),
        ("Polaris Broadcasting AG", "ORG"),
        ("Polaris", "ORG"),
        ("Friedrich Albrecht", "PERSON"),
        ("f.albrecht@example-de-kartell.de", "EMAIL"),
        ("+49 30 2576 4400", "PHONE"),
        ("Berlin", "LOC"),
        ("Karl-Liebknecht-Straße 8", "LOC"),
        ("10178 Berlin", "LOC"),
        ("Hamburg", "LOC"),
        ("Henkel-Vorwerk", "PERSON"),
        ("MeridianFM+", "ORG"),
        ("Renate Hofmann", "PERSON"),
        ("Deutsche Bank", "ORG"),
        ("DE12 5001 0517 5407 3249 31", "IBAN"),
    ]
    return {
        "id": "doc_008_regulatory_submission_en",
        "title": "Polaris / MeridianMedia — Bundeskartellamt filing",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Merger filing to a national authority. SHOULD redact: "
            "notifying party + target + all short forms, counsel name "
            "+ contacts, target CEO, family trust name, both party "
            "addresses, escrow bank, IBAN, case file ref (party-"
            "specific). SHOULD NOT redact: Bundeskartellamt, Autorité "
            "de la concurrence, ACM, EU Merger Regulation, Regulation "
            "(EC) 139/2004. 'Aktiengesellschaft' is a corporate-form "
            "label."
        ),
    }


def doc_witness_statement_en():
    text = """\
WITNESS STATEMENT OF MS. CARMEN ORTIZ-VALDEZ

I, Carmen Ortiz-Valdez, of 47 Elm Street, Apt 3B, Boston, Massachusetts 02114, will say as follows:

1. I am 39 years old and I am a former Senior Procurement Manager at Cascadia Technologies LLC. I worked there from January 2020 until I resigned on 8 April 2026.

2. My direct manager throughout was Mr. Wesley Tan, Vice-President of Procurement. Mr. Tan reported to the CFO, Ms. Patricia Almgren.

3. On 12 February 2026 at approximately 14:30, Mr. Tan called me into his office. Also present was Mr. Devlin O'Connor from the legal team. Mr. Tan asked me to "find a way" to award the Q2 components contract to Vertex Microsystems LLP without running the competitive RFP that company policy required. I refused.

4. Vertex Microsystems LLP is, to my knowledge, partly owned by Mr. Tan's brother-in-law, Mr. Aleksander Petrov. Mr. Petrov is listed as a 24% shareholder according to the public Delaware filing I retrieved on 10 March 2026.

5. After I refused, my access to the procurement system was suspended within 48 hours. On 1 April 2026 I was placed on "performance review". On 8 April 2026 I resigned.

6. I have provided copies of the relevant emails (including Mr. Tan's message of 13 February 2026 from wesley.tan@cascadia-tech.com) to my attorney, Ms. Hilda Brennan of Brennan & Park LLP.

7. The matter has been referred internally as Case CT-WB-026 by Cascadia's outside counsel.

Signed: Carmen Ortiz-Valdez
Dated: 15 May 2026
Reachable at: c.ortiz.valdez@example-mail.com / +1 617 555 0142"""
    annotations = [
        ("Carmen Ortiz-Valdez", "PERSON"),
        ("47 Elm Street", "LOC"),
        ("Boston", "LOC"),
        ("Cascadia Technologies LLC", "ORG"),
        ("Cascadia Technologies", "ORG"),
        ("Cascadia", "ORG"),
        ("Wesley Tan", "PERSON"),
        ("Mr. Tan", "PERSON"),
        ("Patricia Almgren", "PERSON"),
        ("Devlin O'Connor", "PERSON"),
        ("Vertex Microsystems LLP", "ORG"),
        ("Vertex Microsystems", "ORG"),
        ("Aleksander Petrov", "PERSON"),
        ("Mr. Petrov", "PERSON"),
        ("wesley.tan@cascadia-tech.com", "EMAIL"),
        ("Hilda Brennan", "PERSON"),
        ("Brennan & Park LLP", "ORG"),
        ("CT-WB-026", "CASE_REF"),
        ("c.ortiz.valdez@example-mail.com", "EMAIL"),
        ("+1 617 555 0142", "PHONE"),
    ]
    return {
        "id": "doc_009_witness_statement_en",
        "title": "Ortiz-Valdez — whistleblower witness statement",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Witness statement with rich PII. SHOULD redact: witness + "
            "her home address + her contact details, employer + "
            "subsidiary mentions, every named individual (managers, "
            "third-party relative, attorney, opposing-firm partner), "
            "third-party supplier company, witness's outside counsel "
            "firm, internal case ref. SHOULD NOT redact: 'Delaware' "
            "(a US-state descriptor for the filing jurisdiction, not "
            "a party identifier), 'Senior Procurement Manager', "
            "'Vice-President', 'CFO' (role labels), 'Massachusetts' "
            "(state-level, leave city for redaction)."
        ),
    }


def doc_expert_economist_en():
    text = """\
EXPERT REPORT OF PROFESSOR EMIL HAUKSSON
Market definition and competitive effects in Case M.10987 — Brightline / Verdant Holdings

Prepared at the request of: Counsel for Brightline Industries plc
Submitted to: DG Competition, European Commission
Date: 21 May 2026

I. Qualifications

I, Emil Hauksson, am Professor of Industrial Economics at the University of Reykjavík. My CV is at Annex A. I have previously testified before the Bundeskartellamt, the CMA, and the EU General Court. I am instructed by Brightline's counsel, Ms. Yuki Tanaka of Hartford & Mead LLP.

II. Assignment

I was asked to assess (i) the relevant product market for industrial polymer adhesives in the EEA, and (ii) whether the proposed acquisition of Verdant Holdings BV by Brightline Industries plc raises competition concerns in that market.

III. Data sources

I rely principally on (a) confidential transaction data produced by Brightline, (b) the Verdant Holdings sales ledger 2021–2025 produced by Verdant under the confidentiality undertaking, (c) Eurostat trade statistics, and (d) a market-research report by IHS Markit dated October 2025.

IV. Conclusions

I find that the relevant market is industrial polymer adhesives sold to OEM automotive customers within the EEA. On 2024 figures, Brightline's share is [REDACTED in published version; ~14% combined]. The merged entity faces strong remaining competitors, including 3M, Henkel, and two Asian entrants. The Herfindahl-Hirschman Index post-merger is approximately 1,450 — below the Commission's safe-harbour threshold of 2,000 for non-coordinated effects.

I accordingly find no significant impediment to effective competition arising from the transaction.

Contact: emil.hauksson@example-uni-rey.is / +354 555 7821."""
    annotations = [
        ("Emil Hauksson", "PERSON"),
        ("M.10987", "CASE_REF"),
        ("Brightline / Verdant Holdings", "ORG"),
        ("Brightline Industries plc", "ORG"),
        ("Brightline Industries", "ORG"),
        ("Brightline", "ORG"),
        ("University of Reykjavík", "ORG"),
        ("Yuki Tanaka", "PERSON"),
        ("Hartford & Mead LLP", "ORG"),
        ("Verdant Holdings BV", "ORG"),
        ("Verdant Holdings", "ORG"),
        ("Verdant", "ORG"),
        ("3M", "ORG"),
        ("Henkel", "ORG"),
        ("emil.hauksson@example-uni-rey.is", "EMAIL"),
        ("+354 555 7821", "PHONE"),
    ]
    return {
        "id": "doc_010_expert_economist_en",
        "title": "Brightline / Verdant — economist expert report",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Economist report for an EU merger case. SHOULD redact: "
            "expert name + contact + affiliation, both parties + short "
            "forms, the M.xxxxx case ref (party-specific Commission "
            "case number), instructing counsel name + firm, named "
            "third-party competitors (3M, Henkel — they're undertakings, "
            "not regulators). SHOULD NOT redact: DG Competition, "
            "European Commission, Bundeskartellamt, CMA, EU General "
            "Court, EEA, Eurostat — all public bodies/datasets. IHS "
            "Markit is a market-research provider; arguably PII-"
            "adjacent but commonly cited, so we DO redact it as a "
            "named commercial entity that could identify the matter."
        ),
    }


def doc_sanctions_memo_en():
    text = """\
INTERNAL MEMO — CONFIDENTIAL
Subject: Sanctions screening hit — counterparty Severnaya Logistika OOO

To: General Counsel, Faraday Energy SE
From: Aisha Ndiaye, Head of Trade Compliance
Date: 21 May 2026
Internal ref: FE-COMP-2026-088

1. Background

In connection with the proposed crude charter under master agreement with Severnaya Logistika OOO (registered in Murmansk, beneficial owner Mr. Vsevolod Kuznetsov), our screening tool flagged a 92% name match against the OFAC SDN list updated 14 May 2026. The flagged entry relates to "Severnaya Logistics LLC" with an associated address in Saint Petersburg.

2. Diligence performed

We obtained the counterparty's certificate of incorporation, current TIN, and a sworn ownership statement from Mr. Kuznetsov. We separately ran the entity through the EU Consolidated Sanctions List, the UK OFSI list, and the Swiss SECO list. No exact match was found on EU or UK lists. The SECO list returned a single low-confidence hit.

3. Legal analysis

Outside counsel — Mr. Ronan Fitzgerald of Fitzgerald Maloney & Partners, Dublin — advises that the SDN flag is likely a false positive based on common Russian-language naming conventions. However, he recommends we obtain an OFAC interpretive guidance letter before any payment instruction is issued.

4. Recommendation

Defer the transaction pending OFAC clearance. Suspend the wire instruction (intended IBAN: NL91 ABNA 0417 1643 00, beneficiary Severnaya Logistika OOO) until clearance is received. Notify our relationship bank, ING, in writing.

Contact: a.ndiaye@faraday-energy.example.eu, +49 40 5559 6677."""
    annotations = [
        ("Severnaya Logistika OOO", "ORG"),
        ("Severnaya Logistika", "ORG"),
        ("Faraday Energy SE", "ORG"),
        ("Faraday Energy", "ORG"),
        ("Aisha Ndiaye", "PERSON"),
        ("FE-COMP-2026-088", "CASE_REF"),
        ("Murmansk", "LOC"),
        ("Vsevolod Kuznetsov", "PERSON"),
        ("Mr. Kuznetsov", "PERSON"),
        ("Severnaya Logistics LLC", "ORG"),
        ("Saint Petersburg", "LOC"),
        ("Ronan Fitzgerald", "PERSON"),
        ("Fitzgerald Maloney & Partners", "ORG"),
        ("Dublin", "LOC"),
        ("NL91 ABNA 0417 1643 00", "IBAN"),
        ("ING", "ORG"),
        ("a.ndiaye@faraday-energy.example.eu", "EMAIL"),
        ("+49 40 5559 6677", "PHONE"),
    ]
    return {
        "id": "doc_011_sanctions_memo_en",
        "title": "Faraday Energy — sanctions screening memo",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Internal compliance memo on a sanctions hit. SHOULD "
            "redact: own client (Faraday Energy SE), counterparty + "
            "near-match alias, all named individuals (compliance "
            "officer, UBO, outside counsel), city refs locating "
            "parties, outside firm, relationship bank (ING is the "
            "client's bank here = party-adjacent), internal ref, "
            "intended IBAN. SHOULD NOT redact: OFAC, SDN list, EU "
            "Consolidated Sanctions List, UK OFSI, SECO — all "
            "official sanctions instruments / regulators."
        ),
    }


def doc_engagement_letter_en():
    text = """\
ENGAGEMENT LETTER

Between:
  Client: BluePine Capital Partners LP, with offices at 540 Madison Avenue, 18th Floor, New York, NY 10022 ("Client")
  Counsel: Reinhart Voss & Klein, Avenue Louise 250, 1050 Brussels ("RVK" or "the Firm")

Dated: 21 May 2026
Matter ID: RVK-2026-BPC-014

1. Scope

The Firm is engaged to advise the Client on EU-law aspects of its proposed minority investment in NordVent Holdings AS (Oslo). The engagement covers (i) merger-control analysis, (ii) FDI screening across France, Germany and Italy, and (iii) coordination with local counsel in Norway.

2. Lead attorneys

The matter will be led by Maître Charlotte Beaumont (c.beaumont@rvk-law.example.be, direct line +32 2 555 4470). Day-to-day work will be supervised by senior associate Dr. Henrik Olsson. Junior associates may be assigned as workload requires.

3. Fees

Our standard hourly rates apply: Partners EUR 950–1,250, Counsel EUR 750–900, Senior Associates EUR 550–700, Associates EUR 350–490. Fees are billed monthly. A retainer of EUR 75,000 is payable on signature to RVK's client account, IBAN BE63 0689 9999 9999, BIC GKCCBEBB.

4. Conflicts

The Firm has performed a conflicts check and is not aware of any impediment. The Client confirms that it does not regard any of the Firm's other current clients listed in Annex 1 as adverse parties.

5. Confidentiality

The engagement is subject to professional secrecy under Belgian law and Article 458 of the Belgian Penal Code.

Acknowledged:
For the Client: Vivian Park, Managing Partner, BluePine Capital Partners LP
For RVK: Charlotte Beaumont"""
    annotations = [
        ("BluePine Capital Partners LP", "ORG"),
        ("BluePine Capital Partners", "ORG"),
        ("BluePine Capital", "ORG"),
        ("540 Madison Avenue", "LOC"),
        ("New York", "LOC"),
        ("Reinhart Voss & Klein", "ORG"),
        ("RVK", "ORG"),
        ("Avenue Louise 250", "LOC"),
        ("Brussels", "LOC"),
        ("RVK-2026-BPC-014", "CASE_REF"),
        ("NordVent Holdings AS", "ORG"),
        ("NordVent Holdings", "ORG"),
        ("Oslo", "LOC"),
        ("Charlotte Beaumont", "PERSON"),
        ("c.beaumont@rvk-law.example.be", "EMAIL"),
        ("+32 2 555 4470", "PHONE"),
        ("Henrik Olsson", "PERSON"),
        ("BE63 0689 9999 9999", "IBAN"),
        ("Vivian Park", "PERSON"),
    ]
    return {
        "id": "doc_012_engagement_letter_en",
        "title": "BluePine / RVK — engagement letter",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Standard client engagement letter. SHOULD redact: client "
            "+ short forms + HQ address, firm + abbreviation + office "
            "address, target company + short form + HQ city, lead and "
            "supervising attorneys + contact, internal matter ID, "
            "firm client-account IBAN, client signatory. SHOULD NOT "
            "redact: 'Belgian law', 'France', 'Germany', 'Italy', "
            "'Norway' (general jurisdictional references at country "
            "level — not pinning the party). Article 458 Belgian Penal "
            "Code is a statute reference."
        ),
    }


def doc_settlement_offer_en():
    text = """\
By email only.

From: Maximilian Voss, Partner, Voss Lambrechts Avocats
To: Imogen Ashworth, Partner, Ashworth & Holm Solicitors
Cc: client teams
Date: 21 May 2026
Re: Crestwood Marine Insurance Co. / Tidewater Logistics Ltd — without prejudice settlement proposal

Dear Imogen,

I write further to our call of Monday on the long-running coverage dispute between our respective clients arising out of the loss of the M/V Aurelia in the Bay of Biscay (the underlying matter is your firm's ref AHS-2024-117).

On instructions from Crestwood Marine Insurance Co., I am authorised to make the following without-prejudice offer in full and final settlement of all claims:

(a) Crestwood will pay EUR 14,750,000 to Tidewater Logistics Ltd within 30 days of execution of a mutually acceptable settlement deed;
(b) Each party will bear its own costs;
(c) The settlement will include the cross-claims by Mr. Diego Ferreira (the master of the vessel at the time of the casualty) and by Ms. Lucia Marchetti, the cargo surveyor instructed by Tidewater.

Payment, if accepted, will be made to Tidewater's account at Banco Santander, IBAN ES79 2100 0813 6101 2345 6789, by reference WP-CREST-TLW-2026.

This offer remains open until close of business on 4 June 2026, after which we reserve all rights, including to issue proceedings before the Commercial Court of London under our coverage's English-law and jurisdiction clause.

Best regards,
Maximilian Voss
m.voss@voss-lambrechts.example.lu
+352 27 86 1199"""
    annotations = [
        ("Maximilian Voss", "PERSON"),
        ("Voss Lambrechts Avocats", "ORG"),
        ("Imogen Ashworth", "PERSON"),
        ("Ashworth & Holm Solicitors", "ORG"),
        ("Crestwood Marine Insurance Co.", "ORG"),
        ("Crestwood Marine Insurance", "ORG"),
        ("Crestwood", "ORG"),
        ("Tidewater Logistics Ltd", "ORG"),
        ("Tidewater Logistics", "ORG"),
        ("Tidewater", "ORG"),
        ("M/V Aurelia", "ORG"),
        ("AHS-2024-117", "CASE_REF"),
        ("Diego Ferreira", "PERSON"),
        ("Lucia Marchetti", "PERSON"),
        ("Banco Santander", "ORG"),
        ("ES79 2100 0813 6101 2345 6789", "IBAN"),
        ("WP-CREST-TLW-2026", "CASE_REF"),
        ("m.voss@voss-lambrechts.example.lu", "EMAIL"),
        ("+352 27 86 1199", "PHONE"),
    ]
    return {
        "id": "doc_013_settlement_offer_en",
        "title": "Crestwood / Tidewater — without-prejudice settlement offer",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Counsel-to-counsel settlement letter. SHOULD redact: both "
            "lawyers + their firms + contact info, both client parties "
            "+ short forms, vessel name (uniquely identifies the "
            "matter), individual witnesses (vessel master, surveyor), "
            "opposing-firm internal reference, payment IBAN + reference. "
            "SHOULD NOT redact: 'Bay of Biscay' (geographical, not "
            "pinning a party), 'Commercial Court of London' (court "
            "name), 'English law' (jurisdiction descriptor)."
        ),
    }


def doc_compliance_investigation_en():
    text = """\
INTERNAL COMPLIANCE INVESTIGATION — SUMMARY OF FINDINGS
Project Lighthouse — Reference: ALCYONE-IC-2026-04

Investigators: Sarah Whitcombe (Head of Internal Audit), Dr. Bastien Levaillant (Outside Counsel, Levaillant Partners)
Period reviewed: 1 January 2024 to 31 March 2026
Subject: Allegations of facilitation payments in the Casablanca branch of Alcyone Pharmaceuticals SA

1. Mandate

Alcyone Pharmaceuticals SA ("Alcyone") commissioned this review following an anonymous hotline report received on 12 February 2026 alleging that the head of the Casablanca branch, Mr. Hicham Bensalem, had authorised cash payments of approximately EUR 90,000 in aggregate to local customs officials to expedite shipment of cold-chain pharmaceutical products.

2. Methodology

We reviewed 2,418 expense entries, 412 vendor master records, and 87 emails identified by keyword search. Interviews were conducted (in person or by video) with 11 employees, including Ms. Fatima El-Idrissi (Finance Manager, Casablanca), Mr. Omar Belhaj (Logistics Lead), and former branch controller Ms. Joëlle Dupont (now resident in Marseille).

3. Findings

We find substantial corroboration of the hotline allegation. Twelve expense entries between March 2024 and November 2025 follow a recurring pattern: cash withdrawals of MAD 80,000–95,000 from the branch petty-cash account at Banque Populaire (account holder Alcyone Maghreb SARL, IBAN MA64 0123 4567 8901 2345 6789 01), each followed within 48 hours by customs clearance of consignments that had been administratively delayed.

4. Reporting obligations

We recommend self-reporting to the U.S. Department of Justice under the FCPA Corporate Enforcement Policy, and to the French Parquet National Financier under the loi Sapin II. The board's Audit & Risk Committee should convene by 5 June 2026.

Contact: bastien.levaillant@example-lev-part.fr / +33 1 87 23 99 44."""
    annotations = [
        ("ALCYONE-IC-2026-04", "CASE_REF"),
        ("Sarah Whitcombe", "PERSON"),
        ("Bastien Levaillant", "PERSON"),
        ("Levaillant Partners", "ORG"),
        ("Casablanca", "LOC"),
        ("Alcyone Pharmaceuticals SA", "ORG"),
        ("Alcyone Pharmaceuticals", "ORG"),
        ("Alcyone", "ORG"),
        ("Hicham Bensalem", "PERSON"),
        ("Fatima El-Idrissi", "PERSON"),
        ("Omar Belhaj", "PERSON"),
        ("Joëlle Dupont", "PERSON"),
        ("Marseille", "LOC"),
        ("Banque Populaire", "ORG"),
        ("Alcyone Maghreb SARL", "ORG"),
        ("MA64 0123 4567 8901 2345 6789 01", "IBAN"),
        ("bastien.levaillant@example-lev-part.fr", "EMAIL"),
        ("+33 1 87 23 99 44", "PHONE"),
    ]
    return {
        "id": "doc_014_compliance_investigation_en",
        "title": "Alcyone — internal FCPA / loi Sapin investigation",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Internal anti-bribery investigation summary. SHOULD "
            "redact: client + subsidiary entity + all short forms, "
            "every named individual (investigators, suspect manager, "
            "interviewees, former employee), branch banking IBAN + "
            "bank, outside counsel firm + contact, internal investigation "
            "ref, cities (Casablanca = subsidiary's location, Marseille "
            "= ex-employee's residence). SHOULD NOT redact: U.S. "
            "Department of Justice (regulator), FCPA, French Parquet "
            "National Financier (public prosecutor), loi Sapin II "
            "(statute)."
        ),
    }


def doc_corporate_restructuring_opinion_en():
    text = """\
LEGAL OPINION — CORPORATE RESTRUCTURING
Re: Internal reorganisation of the Halcyon Industries group

Addressed to: The Board of Directors, Halcyon Industries Holdings Ltd
Issued by: Pemberton Cross LLP, 10 Old Bailey, London EC4M 7NG
Date: 21 May 2026
Our ref: PC-2026-HII-RESTR

1. Instructions

We were instructed by Halcyon Industries Holdings Ltd ("HIH"), through its CFO Mr. Reginald Caulfield, to advise on the proposed migration of the group's Jersey-incorporated treasury vehicle, Halcyon Treasury Ltd, to an Irish private limited company.

2. Steps

The reorganisation proceeds as follows:

(a) On 1 July 2026, Halcyon Treasury Ltd will be re-domiciled to Ireland under Part 17 of the Irish Companies Act 2014, becoming Halcyon Treasury Designated Activity Company ("HTreas DAC");

(b) On 15 July 2026, HIH will transfer its 100% shareholding in HTreas DAC to a newly-formed Dutch intermediate holding company, Halcyon Treasury Holdings BV, registered office Strawinskylaan 3127, 1077 ZX Amsterdam;

(c) Halcyon Treasury Holdings BV will be capitalised by way of a EUR 480 million equity injection from HIH funded through a debt-push-down structure.

3. Stamp-duty and consents

Stamp duty considerations under the UK Stamp Act 1891 are addressed at paragraph 14 below. Lender consent has been obtained from the syndicate led by Standard Chartered (relationship banker: Mr. Trevor Akinyemi, t.akinyemi@example-sc-bank.com).

4. Conclusion

In our opinion, subject to the assumptions in Annex B, the transaction is enforceable as a matter of English, Irish, Dutch and Jersey law.

Signed by:
Hugo Pemberton, Senior Partner (h.pemberton@pemberton-cross.example.uk, +44 20 7000 4242)"""
    annotations = [
        ("Halcyon Industries Holdings Ltd", "ORG"),
        ("Halcyon Industries Holdings", "ORG"),
        ("Halcyon Industries", "ORG"),
        ("Pemberton Cross LLP", "ORG"),
        ("Pemberton Cross", "ORG"),
        ("10 Old Bailey", "LOC"),
        ("London EC4M 7NG", "LOC"),
        ("PC-2026-HII-RESTR", "CASE_REF"),
        ("HIH", "ORG"),
        ("Reginald Caulfield", "PERSON"),
        ("Halcyon Treasury Ltd", "ORG"),
        ("Halcyon Treasury Designated Activity Company", "ORG"),
        ("HTreas DAC", "ORG"),
        ("Halcyon Treasury Holdings BV", "ORG"),
        ("Halcyon Treasury Holdings", "ORG"),
        ("Halcyon Treasury", "ORG"),
        ("Strawinskylaan 3127", "LOC"),
        ("Amsterdam", "LOC"),
        ("Standard Chartered", "ORG"),
        ("Trevor Akinyemi", "PERSON"),
        ("t.akinyemi@example-sc-bank.com", "EMAIL"),
        ("Hugo Pemberton", "PERSON"),
        ("h.pemberton@pemberton-cross.example.uk", "EMAIL"),
        ("+44 20 7000 4242", "PHONE"),
    ]
    return {
        "id": "doc_015_corporate_restructuring_en",
        "title": "Halcyon Industries — restructuring opinion",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Cross-border corporate-restructuring opinion. SHOULD "
            "redact: client group + holding + all subsidiaries (Jersey "
            "treasury, Irish DAC, Dutch holdco) + short forms, issuing "
            "law firm + address, addressee CFO, lender (Standard "
            "Chartered = party-adjacent, named relationship bank) + "
            "relationship banker, partner signatory + contact, "
            "internal matter ref, Amsterdam registered-office "
            "address. SHOULD NOT redact: 'Jersey', 'Ireland', 'Dutch', "
            "'English', 'Irish Companies Act 2014', 'UK Stamp Act "
            "1891' (jurisdictions and statutes)."
        ),
    }


def doc_tax_memo_en():
    text = """\
TAX STRUCTURING MEMORANDUM — DRAFT
Privileged & Confidential
Project Codename: GINKGO

To: Vanessa Krüger (CFO), Helix Biotech Group AG
From: Dr. Akira Watanabe, Hamilton Reeves Tax LLP
Date: 21 May 2026
Matter ID: HRT-2026-GINKGO-01

Executive summary

This memo outlines a tax-efficient route for routing royalty income from Helix Biotech Group AG's US-resident subsidiary, Helix Biotech Inc., through a Luxembourg principal company to the Swiss parent. Annual royalty stream: USD 220 million.

Proposed structure

1. Establish Helix Royalty SCSp, a Luxembourg special limited partnership, with Helix Biotech Group AG as the limited partner (99.99%) and a Luxembourg-resident GP, Helix GP Sarl, as the unlimited partner (0.01%).

2. License the patent portfolio (currently held by the Swiss parent in Zug) to Helix Royalty SCSp for an upfront fee of USD 35 million. The license is sub-licensable to Helix Biotech Inc. (Cambridge, Massachusetts).

3. Royalty flow: Helix Biotech Inc. → Helix Royalty SCSp → Helix Biotech Group AG. Withholding-tax leakage: 0% under the US-Luxembourg treaty and the Lux-Swiss treaty (subject to the LOB clauses).

BEPS / Pillar Two considerations

Helix Biotech Group AG is in scope for Pillar Two (consolidated revenue ~EUR 1.4bn). The Luxembourg sub-jurisdictional top-up tax (QDMTT) will apply and is expected to neutralise any GILTI-style attribution from the Swiss tax administration. We are coordinating with the OECD secretariat's guidance under the GloBE Model Rules.

Banking
Initial capitalisation will route through BCEE: IBAN LU93 0019 4001 0000 4000.

Please call me on +41 44 555 6677 with any questions.

Akira Watanabe
a.watanabe@hamilton-reeves.example.ch"""
    annotations = [
        ("Vanessa Krüger", "PERSON"),
        ("Helix Biotech Group AG", "ORG"),
        ("Helix Biotech Group", "ORG"),
        ("Helix Biotech", "ORG"),
        ("Akira Watanabe", "PERSON"),
        ("Hamilton Reeves Tax LLP", "ORG"),
        ("HRT-2026-GINKGO-01", "CASE_REF"),
        ("Helix Biotech Inc.", "ORG"),
        ("Helix Royalty SCSp", "ORG"),
        ("Helix GP Sarl", "ORG"),
        ("Zug", "LOC"),
        ("Cambridge", "LOC"),
        ("BCEE", "ORG"),
        ("LU93 0019 4001 0000 4000", "IBAN"),
        ("+41 44 555 6677", "PHONE"),
        ("a.watanabe@hamilton-reeves.example.ch", "EMAIL"),
    ]
    return {
        "id": "doc_016_tax_memo_en",
        "title": "Helix Biotech — cross-border royalty tax memo",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Cross-border tax structuring memo. SHOULD redact: client "
            "CFO + group + every group entity (US sub, Lux SCSp, Lux "
            "GP) + short forms, advising tax firm + contact, internal "
            "matter ref, party-locating cities (Zug = Swiss parent's "
            "location, Cambridge = US sub's location), Luxembourg "
            "bank (BCEE) and IBAN. SHOULD NOT redact: Pillar Two, "
            "GloBE, BEPS (OECD frameworks), OECD secretariat, GILTI "
            "(US tax concept), 'Swiss tax administration' (regulator), "
            "tax-treaty references, Luxembourg/Swiss/US as jurisdictional "
            "descriptors."
        ),
    }


def doc_data_breach_notification_en():
    text = """\
DATA BREACH NOTIFICATION — DRAFT FOR DPA SUBMISSION

Notification to the Autoriteit Persoonsgegevens
Article 33 GDPR — Notification of a personal data breach
Date: 21 May 2026

1. Controller details

Name of controller: Stedelijk Verzekeringen NV
Registered office: Beursplein 5, 1012 JW Amsterdam
DPO: Mr. Roeland van der Meer (r.vandermeer@stedelijk-verz.example.nl, +31 20 555 0099)
Reference: SV-DPO-IR-2026-007

2. Nature of the breach

On 18 May 2026 at approximately 03:14 CET, an unauthorised actor obtained access to a Stedelijk Verzekeringen NV customer-data export hosted in an Azure blob storage container. The container had been temporarily reconfigured with public-read access on 14 May 2026 by a contractor, Mr. Lennart Voskamp of Voskamp ICT BV, in connection with an analytics integration project.

3. Personal data concerned

Approximately 218,400 data subjects, primarily Dutch and Belgian retail life-insurance customers. Categories: full name, date of birth, postal address, BSN (national identification number), policy number, and inception/renewal dates. No financial-account data was exposed.

4. Likely consequences

Risk of identity theft and targeted phishing. The breach satisfies the Article 33(1) threshold ("likely to result in a risk to the rights and freedoms of natural persons").

5. Measures taken

Container access revoked at 09:42 CET on 18 May 2026 by our infrastructure lead, Ms. Jasmijn Beekhuis. The Belgian counterpart authority, the Autorité de protection des données (APD), and the Information Commissioner's Office (for affected Dutch nationals resident in the UK) will be informed in parallel.

6. External counsel

We are advised by Ms. Anne Vermeulen of Vermeulen & Partners, Brussels (a.vermeulen@vermeulen-partners.example.be)."""
    annotations = [
        ("Stedelijk Verzekeringen NV", "ORG"),
        ("Stedelijk Verzekeringen", "ORG"),
        ("Stedelijk", "ORG"),
        ("Beursplein 5", "LOC"),
        ("Amsterdam", "LOC"),
        ("Roeland van der Meer", "PERSON"),
        ("r.vandermeer@stedelijk-verz.example.nl", "EMAIL"),
        ("+31 20 555 0099", "PHONE"),
        ("SV-DPO-IR-2026-007", "CASE_REF"),
        ("Lennart Voskamp", "PERSON"),
        ("Voskamp ICT BV", "ORG"),
        ("Jasmijn Beekhuis", "PERSON"),
        ("Anne Vermeulen", "PERSON"),
        ("Vermeulen & Partners", "ORG"),
        ("Brussels", "LOC"),
        ("a.vermeulen@vermeulen-partners.example.be", "EMAIL"),
    ]
    return {
        "id": "doc_017_data_breach_notification_en",
        "title": "Stedelijk Verzekeringen — DPA breach notification",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "GDPR Article 33 breach notification to a national DPA. "
            "SHOULD redact: controller + short forms + registered "
            "office, DPO + contact, internal ref, third-party "
            "contractor + firm, internal infrastructure-lead employee, "
            "outside counsel + firm + office city + contact. SHOULD "
            "NOT redact: Autoriteit Persoonsgegevens, Autorité de "
            "protection des données / APD, Information Commissioner's "
            "Office (all DPAs are public regulators), GDPR Article 33, "
            "'Dutch', 'Belgian' (descriptors), Azure (a public-knowledge "
            "Microsoft cloud product; Microsoft is in the gatekeeper "
            "list and IS redactable in principle — but 'Azure blob "
            "storage container' here is a generic technical reference, "
            "so we omit it; Jude is expected to leave it alone)."
        ),
    }


def doc_cease_and_desist_en():
    text = """\
CEASE AND DESIST — TRADE MARK INFRINGEMENT

From: Margaret Holloway, Partner, Holloway IP Partners
        margaret.holloway@hollowayip.example.com / +1 212 555 7799
To: The CEO and General Counsel, Pinegrove Coffee Roasters LLC
       1188 Cascade Way, Portland, OR 97209

By email and certified mail
Date: 21 May 2026
Our reference: HIP-NOTUSE-2026-0098

Dear Sir/Madam,

We act for Northwind Coffee Company Inc. ("Northwind"), proprietor of US Trademark Registration No. 5,123,456 for the word mark "NORTHWIND" in International Class 30, registered 4 August 2018 and in continuous use since 2009.

It has come to our client's attention that Pinegrove Coffee Roasters LLC has, since approximately February 2026, been marketing a single-origin espresso blend under the name "NORTHWIND RESERVE" through its retail outlets in Portland, Seattle and online via your website pinegrove-coffee.example.com. We enclose at Annex A photographs and online listings evidencing this use.

Your conduct constitutes (i) infringement of the registered mark under 15 U.S.C. § 1114, (ii) false designation of origin under § 1125(a), and (iii) unfair competition under Oregon common law.

We accordingly demand that you:

1. Immediately cease all use of "NORTHWIND" or any confusingly similar mark in connection with coffee or related goods;
2. Withdraw all infringing inventory by 4 June 2026;
3. Provide a sworn accounting of all sales of the "NORTHWIND RESERVE" product to date.

Should you fail to comply by the stated deadline, our client will file suit in the United States District Court for the District of Oregon, seeking injunctive relief, treble damages, and attorneys' fees.

This letter is sent without prejudice to all rights of Northwind, including the right to commence proceedings without further notice.

Yours faithfully,
Margaret Holloway
Holloway IP Partners"""
    annotations = [
        ("Margaret Holloway", "PERSON"),
        ("Holloway IP Partners", "ORG"),
        ("margaret.holloway@hollowayip.example.com", "EMAIL"),
        ("+1 212 555 7799", "PHONE"),
        ("Pinegrove Coffee Roasters LLC", "ORG"),
        ("Pinegrove Coffee Roasters", "ORG"),
        ("Pinegrove", "ORG"),
        ("1188 Cascade Way", "LOC"),
        ("Portland", "LOC"),
        ("HIP-NOTUSE-2026-0098", "CASE_REF"),
        ("Northwind Coffee Company Inc.", "ORG"),
        ("Northwind Coffee Company", "ORG"),
        ("Northwind", "ORG"),
        ("Seattle", "LOC"),
        ("pinegrove-coffee.example.com", "URL"),
    ]
    return {
        "id": "doc_018_cease_and_desist_en",
        "title": "Northwind / Pinegrove — IP cease-and-desist",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Trade-mark cease-and-desist letter. SHOULD redact: "
            "sending lawyer + firm + contact, addressee party + HQ "
            "address, addressee retail-city refs (Portland, Seattle), "
            "client party + short forms, infringing-product website "
            "URL, internal matter ref. SHOULD NOT redact: 'Oregon' "
            "(state descriptor for the choice-of-law clause), 15 "
            "U.S.C. § 1114 / § 1125 (statutes), 'United States "
            "District Court for the District of Oregon' (a court), "
            "'NORTHWIND RESERVE' (the disputed mark — note: this "
            "names the infringing brand variant. Conservative call: "
            "leave it; it's the subject-matter of the dispute, not "
            "the party identifier. Borderline.)"
        ),
    }


def doc_antitrust_complaint_en():
    text = """\
COMPLAINT UNDER ARTICLE 7(2) REGULATION 1/2003
Submitted to the European Commission, DG Competition

Complainant: Velora Streaming Services Ltd
Date: 21 May 2026
Counsel: Maître Étienne Garnier, Garnier Vasseur SCP

I. Identity of the complainant

Velora Streaming Services Ltd ("Velora") is an Irish-incorporated audio-streaming company headquartered at 16 Sir John Rogerson's Quay, Dublin 2, Ireland. Velora has approximately 4.6 million monthly active users across the EEA. Its CEO is Ms. Sinéad Brennan; its Head of Public Policy and the primary point of contact for this submission is Mr. Théo Roussel (t.roussel@velora.example.ie, +353 1 555 0011).

II. The respondent

The complaint is directed against Apple Inc. ("Apple") in its capacity as DMA-designated gatekeeper for the App Store. The conduct under complaint relates to Apple's commission structure, anti-steering provisions, and selective enforcement of in-app-purchase requirements against Velora's iOS application.

III. Conduct complained of

Velora alleges that, since the entry into force of the DMA on 7 March 2024, Apple has:

(a) continued to apply a 27% commission to "linked-out" payment transactions, contrary to Article 5(4) DMA;
(b) imposed onerous "scare-screen" warnings on Velora users following a linked-out checkout flow, in breach of Article 6(13) DMA; and
(c) selectively rejected Velora's iOS app updates in February and April 2026 on pretextual grounds, despite materially identical updates being approved for competitor apps.

Velora has documented 47 specific incidents. Affidavits from Velora's product manager, Mr. Hideo Nakamura, and senior engineer Ms. Wiktoria Lewandowska are attached as Annex 3.

IV. Relief sought

Velora respectfully requests that the Commission (i) open formal proceedings under Article 20 DMA, (ii) impose interim measures, and (iii) consider penalties under Article 30 DMA.

Counsel contact: e.garnier@garnier-vasseur.example.fr / +33 1 56 90 22 14."""
    annotations = [
        ("Velora Streaming Services Ltd", "ORG"),
        ("Velora Streaming Services", "ORG"),
        ("Velora", "ORG"),
        ("Étienne Garnier", "PERSON"),
        ("Garnier Vasseur SCP", "ORG"),
        ("16 Sir John Rogerson's Quay", "LOC"),
        ("Dublin", "LOC"),
        ("Sinéad Brennan", "PERSON"),
        ("Théo Roussel", "PERSON"),
        ("t.roussel@velora.example.ie", "EMAIL"),
        ("+353 1 555 0011", "PHONE"),
        ("Apple Inc.", "ORG"),
        ("Apple", "ORG"),
        ("Hideo Nakamura", "PERSON"),
        ("Wiktoria Lewandowska", "PERSON"),
        ("e.garnier@garnier-vasseur.example.fr", "EMAIL"),
        ("+33 1 56 90 22 14", "PHONE"),
    ]
    return {
        "id": "doc_019_antitrust_complaint_en",
        "title": "Velora v. Apple — DMA complaint to the Commission",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "DMA complaint to DG COMP. SHOULD redact: complainant + "
            "short forms, complainant HQ address, complainant CEO and "
            "policy contact + contact info, counsel + firm + contact, "
            "complainant's named product manager and engineer "
            "(witness affidavits), Apple Inc. and 'Apple' (a "
            "DMA-designated gatekeeper that IS in the known_entities "
            "whitelist with redact:true — it's a real party here, "
            "so Jude should still redact it). SHOULD NOT redact: "
            "European Commission, DG Competition, DMA, Regulation "
            "1/2003, Article references, 'Irish' (jurisdictional "
            "descriptor), 'iOS' (Apple's platform; arguably "
            "Apple-adjacent but a generic platform name; conservative "
            "call: leave it)."
        ),
    }


def doc_insolvency_update_en():
    text = """\
INSOLVENCY UPDATE MEMORANDUM
Re: In the matter of Avenir Retail Holdings SA (in administration)

To: Creditors' Committee
From: Insolvency Administrator: Mr. Théodore Lacombe, Lacombe Restructuring Avocats
Date: 21 May 2026
Court reference: T.Comm.Bxl 2025/A/4408

1. Procedural posture

Avenir Retail Holdings SA ("Avenir") was placed in judicial reorganisation by the Tribunal de l'entreprise francophone de Bruxelles on 14 November 2025. The conversion to formal administration was ordered on 12 March 2026 following the failure of the proposed continuation plan. The court appointed the undersigned as administrator pursuant to Book XX of the Belgian Code of Economic Law.

2. Asset realisations

Since the last update of 15 April 2026:

(a) Sale of the Avenir Lyon distribution centre (registered address: 84 avenue Tony Garnier, 69007 Lyon) completed on 30 April 2026 for EUR 23,400,000 to LogiSud Investissements SAS. Net proceeds, after secured-creditor payouts to KBC, have been credited to the administration account at Belfius (IBAN BE74 0682 7777 0001).

(b) Discussions are ongoing with two potential buyers for the Avenir-branded e-commerce platform: a strategic buyer represented by Ms. Alexandra Petrescu (a.petrescu@strategicbuyer.example.eu) and a financial sponsor represented by Mr. Eitan Bar-Levav.

(c) The previously-reported tax dispute with the Belgian SPF Finances remains unresolved. The Belgian Court of Cassation is scheduled to hear the related appeal on 18 September 2026.

3. Employment

Of the 412 former Avenir employees, 287 have been transferred to acquirers under article 61 CCT 32bis. The remaining 125 staff received their final settlement on 30 April 2026, signed off by HR director Ms. Ingrid Vanderbeke.

4. Next steps

The administrator will convene the next creditors' committee on 11 June 2026 at the Brussels offices of Lacombe Restructuring Avocats, Boulevard du Régent 47, 1000 Brussels.

Contact: t.lacombe@lacombe-restructuring.example.be / +32 2 555 8800."""
    annotations = [
        ("Avenir Retail Holdings SA", "ORG"),
        ("Avenir Retail Holdings", "ORG"),
        ("Avenir", "ORG"),
        ("Théodore Lacombe", "PERSON"),
        ("Lacombe Restructuring Avocats", "ORG"),
        ("T.Comm.Bxl 2025/A/4408", "CASE_REF"),
        ("84 avenue Tony Garnier", "LOC"),
        ("Lyon", "LOC"),
        ("LogiSud Investissements SAS", "ORG"),
        ("LogiSud Investissements", "ORG"),
        ("KBC", "ORG"),
        ("Belfius", "ORG"),
        ("BE74 0682 7777 0001", "IBAN"),
        ("Alexandra Petrescu", "PERSON"),
        ("a.petrescu@strategicbuyer.example.eu", "EMAIL"),
        ("Eitan Bar-Levav", "PERSON"),
        ("Ingrid Vanderbeke", "PERSON"),
        ("Boulevard du Régent 47", "LOC"),
        ("Brussels", "LOC"),
        ("t.lacombe@lacombe-restructuring.example.be", "EMAIL"),
        ("+32 2 555 8800", "PHONE"),
    ]
    return {
        "id": "doc_020_insolvency_update_en",
        "title": "Avenir Retail Holdings — administrator's update",
        "language": "en",
        "text": text,
        "gold_spans": _spans(text, annotations),
        "notes": (
            "Insolvency administrator's update to creditors' committee. "
            "SHOULD redact: debtor + short forms, administrator + firm "
            "+ Brussels office address + contact, court file ref, sold "
            "distribution-centre address + city, buyer (LogiSud), "
            "secured creditor (KBC, here a party), administration bank "
            "(Belfius) + IBAN, named potential buyers and their "
            "representatives, HR director. SHOULD NOT redact: 'Tribunal "
            "de l'entreprise francophone de Bruxelles' (a Belgian "
            "court), 'Belgian Code of Economic Law' (statute), 'SPF "
            "Finances' (Belgian tax administration / regulator), "
            "'Belgian Court of Cassation' (court — in whitelist as "
            "'Cour de cassation (Belgium)'), 'CCT 32bis' (collective "
            "bargaining instrument / statute)."
        ),
    }


def main():
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    docs = [
        doc_term_sheet_en(),
        doc_credit_facility_en(),
        doc_solaris_jv_fr(),
        doc_brussels_letter_nl(),
        doc_supply_agreement_en(),
        doc_employment_dispute_en(),
        doc_patent_litigation_en(),
        doc_regulatory_submission_en(),
        doc_witness_statement_en(),
        doc_expert_economist_en(),
        doc_sanctions_memo_en(),
        doc_engagement_letter_en(),
        doc_settlement_offer_en(),
        doc_compliance_investigation_en(),
        doc_corporate_restructuring_opinion_en(),
        doc_tax_memo_en(),
        doc_data_breach_notification_en(),
        doc_cease_and_desist_en(),
        doc_antitrust_complaint_en(),
        doc_insolvency_update_en(),
    ]
    for doc in docs:
        path = CORPUS_DIR / f"{doc['id']}.json"
        path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  wrote {path}  ({len(doc['gold_spans'])} gold spans)")


if __name__ == "__main__":
    main()
