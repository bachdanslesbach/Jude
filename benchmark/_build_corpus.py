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


def main():
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    docs = [
        doc_term_sheet_en(),
        doc_credit_facility_en(),
        doc_solaris_jv_fr(),
        doc_brussels_letter_nl(),
        doc_supply_agreement_en(),
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
