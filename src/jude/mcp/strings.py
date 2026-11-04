"""Every string the plugin shows or returns, in one table.

Three audiences, three rules:

* ``STRINGS`` — what the lawyer reads in the Jude window and what the
  model receives as a ``next`` hint or a static error. Every key has an
  ``en`` and a ``fr`` text and an ``nl`` column that is empty until
  someone translates it (review-ux principle 7).
* ``TOOL_DESCRIPTIONS`` and ``INSTRUCTIONS`` — the coaching the model
  reads in ``tools/list``. English only, static, no placeholders: the
  model must never be asked to guess a matter, a file or a real name.

Nothing in this module is ever formatted with document content. Error
strings are static on purpose: an error that echoed its input would be
the one channel through which a file name could reach the model.
"""

from __future__ import annotations

LANGS: tuple[str, ...] = ("en", "fr", "nl")

STRINGS: dict[str, dict[str, str]] = {
    # ----- hints returned to the model ("next") -----
    "next.prepared": {
        "en": (
            "Jude opened its window on the user's computer. Tell the user to choose "
            "the matter and the document there, review and approve, then tell you "
            "they have approved. Then call fetch_approved once; if the status is not "
            "released, stop and wait for the user."
        ),
        "fr": (
            "Jude a ouvert sa fenêtre sur l'ordinateur de l'utilisateur. Demandez-lui "
            "d'y choisir le dossier et le document, de relire et d'approuver, puis de "
            "vous dire qu'il a approuvé. Appelez ensuite fetch_approved une fois ; si "
            "le statut n'est pas released, arrêtez-vous et attendez l'utilisateur."
        ),
        "nl": "",
    },
    "next.already_open": {
        "en": (
            "A review is already open in the Jude window; it belongs to the conversation "
            "that started it. Ask the user to finish or cancel it there. If the window is "
            "not visible, the user can run `jude mcp open` in a terminal."
        ),
        "fr": (
            "Une relecture est déjà ouverte dans la fenêtre Jude ; elle appartient à la "
            "conversation qui l'a démarrée. Demandez à l'utilisateur de la terminer ou de "
            "l'annuler là. Si la fenêtre n'est pas visible, l'utilisateur peut lancer "
            "`jude mcp open` dans un terminal."
        ),
        "nl": "",
    },
    "next.no_browser": {
        "en": (
            "The window could not be opened automatically; ask the user to run "
            "`jude mcp open` in a terminal."
        ),
        "fr": (
            "La fenêtre n'a pas pu être ouverte automatiquement ; demandez à "
            "l'utilisateur de lancer `jude mcp open` dans un terminal."
        ),
        "nl": "",
    },
    "next.not_yet": {
        "en": (
            "Not approved yet. Tell the user Jude is waiting in its window and stop "
            "until they say they have approved."
        ),
        "fr": (
            "Pas encore approuvé. Dites à l'utilisateur que Jude attend dans sa "
            "fenêtre et arrêtez-vous jusqu'à ce qu'il dise avoir approuvé."
        ),
        "nl": "",
    },
    "next.approved": {
        "en": "Approved in Jude; call fetch_approved now to receive the text.",
        "fr": "Approuvé dans Jude ; appelez fetch_approved maintenant pour recevoir le texte.",
        "nl": "",
    },
    "next.final": {
        "en": (
            "This review is closed; nothing was shared. Call prepare_document again "
            "if the user wants to start over."
        ),
        "fr": (
            "Cette relecture est close ; rien n'a été partagé. Appelez de nouveau "
            "prepare_document si l'utilisateur veut recommencer."
        ),
        "nl": "",
    },
    "next.already_released": {
        "en": (
            "The text of this review was already handed to you once; use the copy "
            "you received."
        ),
        "fr": (
            "Le texte de cette relecture vous a déjà été transmis une fois ; utilisez "
            "la copie que vous avez reçue."
        ),
        "nl": "",
    },
    # ----- static errors returned to the model -----
    "err.unknown_review": {
        "en": "Unknown review. Use the review_id returned by prepare_document.",
        "fr": "Relecture inconnue. Utilisez le review_id renvoyé par prepare_document.",
        "nl": "",
    },
    "err.not_released": {
        "en": (
            "No released text for this review; show_answer needs the review_id of a "
            "document you received through fetch_approved."
        ),
        "fr": (
            "Aucun texte transmis pour cette relecture ; show_answer exige le "
            "review_id d'un document reçu via fetch_approved."
        ),
        "nl": "",
    },
    "err.refused": {
        "en": (
            "The approved text could not be verified against its record and was not "
            "released."
        ),
        "fr": (
            "Le texte approuvé n'a pas pu être vérifié par rapport à son "
            "enregistrement et n'a pas été transmis."
        ),
        "nl": "",
    },
    "err.busy": {
        "en": (
            "Jude is busy with another review or answer; ask the user to finish or "
            "cancel in the Jude window, then try again."
        ),
        "fr": (
            "Jude est occupé par une autre relecture ou réponse ; demandez à "
            "l'utilisateur de terminer ou d'annuler dans la fenêtre Jude, puis "
            "réessayez."
        ),
        "nl": "",
    },
    "err.too_long_answer": {
        "en": "The answer is too long to show (over 400 000 characters); split it.",
        "fr": (
            "La réponse est trop longue pour être affichée (plus de 400 000 caractères) ; "
            "découpez-la."
        ),
        "nl": "",
    },
    "err.internal_tool": {
        "en": "Jude could not complete this call; the user can run `jude mcp doctor`.",
        "fr": "Jude n'a pas pu terminer cet appel ; l'utilisateur peut lancer `jude mcp doctor`.",
        "nl": "",
    },
    "err.unknown_argument": {
        "en": (
            "Unexpected argument. prepare_document takes no arguments; fetch_approved takes "
            "review_id and wait_seconds; show_answer takes review_id and text. Never pass a "
            "matter, a file name or a path: the user chooses them in the Jude window."
        ),
        "fr": (
            "Argument inattendu. prepare_document ne prend aucun argument ; fetch_approved "
            "prend review_id et wait_seconds ; show_answer prend review_id et text. Ne "
            "passez jamais de dossier, de nom de fichier ou de chemin : l'utilisateur les "
            "choisit dans la fenêtre Jude."
        ),
        "nl": "",
    },
    # ----- the window -----
    "ui.nothing_left": {
        "en": "Nothing has left your computer.",
        "fr": "Rien n'a quitté votre ordinateur.",
        "nl": "",
    },
    "ui.status.handed_once": {
        "en": "One text has been handed to Claude. Record:",
        "fr": "Un texte a été transmis à Claude. Enregistrement :",
        "nl": "",
    },
    "ui.ledger_ref": {"en": "record", "fr": "enregistrement", "nl": ""},
    "ui.zr_tag": {"en": "ZR", "fr": "ZR", "nl": ""},
    "ui.lang.en": {"en": "EN", "fr": "EN", "nl": ""},
    "ui.lang.fr": {"en": "FR", "fr": "FR", "nl": ""},
    "ui.start_from_claude": {
        "en": "No review is open. Start one from Claude.",
        "fr": "Aucune relecture n'est ouverte. Démarrez-en une depuis Claude.",
        "nl": "",
    },
    "ui.choose_matter": {
        "en": "Choose the matter",
        "fr": "Choisissez le dossier",
        "nl": "",
    },
    "ui.matter": {"en": "Matter", "fr": "Dossier", "nl": ""},
    "ui.continue": {"en": "Continue", "fr": "Continuer", "nl": ""},
    "ui.change_matter": {"en": "Change matter", "fr": "Changer de dossier", "nl": ""},
    "ui.no_matters": {
        "en": "No matter yet. Create one with `jude matter create` or in the Jude UI.",
        "fr": "Aucun dossier. Créez-en un avec `jude matter create` ou dans l'interface Jude.",
        "nl": "",
    },
    "ui.choose_file": {
        "en": "Choose the document",
        "fr": "Choisissez le document",
        "nl": "",
    },
    "ui.file_hint": {
        "en": (
            "A .txt, .md, .docx, .pdf or .xlsx file, up to 50 MiB and 150 000 characters "
            "(about 50 pages). It is read here and never sent as a file; a longer "
            "document must be split first."
        ),
        "fr": (
            "Un fichier .txt, .md, .docx, .pdf ou .xlsx, jusqu'à 50 Mio et 150 000 "
            "caractères (environ 50 pages). Il est lu ici et jamais envoyé comme fichier ; "
            "un document plus long doit d'abord être découpé."
        ),
        "nl": "",
    },
    "ui.prepare": {"en": "Prepare", "fr": "Préparer", "nl": ""},
    "ui.preparing": {
        "en": "Preparing the document. Nothing has left your computer.",
        "fr": "Préparation du document. Rien n'a quitté votre ordinateur.",
        "nl": "",
    },
    "ui.phase.reading": {
        "en": "Reading the document",
        "fr": "Lecture du document",
        "nl": "",
    },
    "ui.phase.loading_models": {
        "en": "Loading the language models (10–30 s after a pause)",  # noqa: RUF001
        "fr": "Chargement des modèles de langue (10–30 s après une pause)",  # noqa: RUF001
        "nl": "",
    },
    "ui.phase.detecting": {
        "en": "Finding names and references",
        "fr": "Recherche des noms et références",
        "nl": "",
    },
    "ui.phase.rendering": {
        "en": "Preparing the text",
        "fr": "Préparation du texte",
        "nl": "",
    },
    "ui.what_leaves": {
        "en": "What leaves your computer",
        "fr": "Ce qui quitte votre ordinateur",
        "nl": "",
    },
    "ui.destination": {
        "en": (
            "To: Claude Desktop, through a local pipe on this computer. Jude makes no "
            "network call; Claude Desktop sends the text below to Anthropic."
        ),
        "fr": (
            "Vers : Claude Desktop, par un canal local sur cet ordinateur. Jude ne fait "
            "aucun appel réseau ; Claude Desktop envoie le texte ci-dessous à Anthropic."
        ),
        "nl": "",
    },
    "ui.warn.comments": {
        "en": (
            "The document contains review comments. Jude does not read them, so they are "
            "not in the text below and will not reach Claude; remove them in Word if they "
            "matter."
        ),
        "fr": (
            "Le document contient des commentaires de révision. Jude ne les lit pas : ils "
            "ne sont pas dans le texte ci-dessous et n'iront pas à Claude ; supprimez-les "
            "dans Word s'ils comptent."
        ),
        "nl": "",
    },
    "ui.warn.tracked_changes": {
        "en": (
            "The document contains tracked changes. Jude reads the text as accepted; the "
            "deleted and inserted passages are not shown below."
        ),
        "fr": (
            "Le document contient des modifications suivies. Jude lit le texte comme "
            "accepté ; les passages supprimés et insérés n'apparaissent pas ci-dessous."
        ),
        "nl": "",
    },
    "ui.warn.metadata": {
        "en": "The file's properties (author, title…) are not part of the text and do not leave.",
        "fr": (
            "Les propriétés du fichier (auteur, titre…) ne font pas partie du texte et ne "
            "partent pas."
        ),
        "nl": "",
    },
    "ui.warn.image_pages": {
        "en": (
            "Some pages are images without text; they were not read. OCR is off in the "
            "plugin; `jude redact --ocr` in a terminal reads them."
        ),
        "fr": (
            "Certaines pages sont des images sans texte ; elles n'ont pas été lues. L'OCR "
            "est désactivée dans le plugin ; `jude redact --ocr` dans un terminal les lit."
        ),
        "nl": "",
    },
    "ui.languages": {"en": "Languages seen:", "fr": "Langues vues :", "nl": ""},
    "ui.undetermined": {"en": "undetermined", "fr": "indéterminé", "nl": ""},
    "ui.risk.lead": {
        "en": "Re-identification signals",
        "fr": "Signaux de ré-identification",
        "nl": "",
    },
    "ui.risk.low": {"en": "LOW", "fr": "FAIBLE", "nl": ""},
    "ui.risk.medium": {"en": "MEDIUM", "fr": "MOYEN", "nl": ""},
    "ui.risk.high": {"en": "HIGH", "fr": "ÉLEVÉ", "nl": ""},
    "ui.risk.none": {
        "en": "No structural re-identification signal found.",
        "fr": "Aucun signal structurel de ré-identification.",
        "nl": "",
    },
    "ui.risk.language_unmodelled": {
        "en": (
            "Some paragraphs are in a language Jude has no model for; names there were "
            "checked by the rules and GLiNER only:"
        ),
        "fr": (
            "Certains paragraphes sont dans une langue pour laquelle Jude n'a pas de "
            "modèle ; les noms y ont été vérifiés par les règles et GLiNER seulement :"
        ),
        "nl": "",
    },
    "ui.invisible_chars": {
        "en": (
            "This text contains characters that are invisible on screen (zero-width, "
            "direction or tag characters). They leave with the text."
        ),
        "fr": (
            "Ce texte contient des caractères invisibles à l'écran (largeur nulle, "
            "direction, étiquettes). Ils partent avec le texte."
        ),
        "nl": "",
    },
    "ui.show_invisible": {"en": "Show them", "fr": "Les afficher", "nl": ""},
    "ui.hide_invisible": {"en": "Hide them", "fr": "Les masquer", "nl": ""},
    "ui.show_original": {
        "en": "Show the original (stays here)",
        "fr": "Afficher l'original (reste ici)",
        "nl": "",
    },
    "ui.show_leaving": {
        "en": "Show the text that leaves",
        "fr": "Afficher le texte qui part",
        "nl": "",
    },
    "ui.hidden": {"en": "hidden", "fr": "masqués", "nl": ""},
    "ui.pseudonyms": {"en": "pseudonyms", "fr": "pseudonymes", "nl": ""},
    "ui.kept_visible": {"en": "kept visible", "fr": "laissés visibles", "nl": ""},
    "ui.chars": {"en": "characters", "fr": "caractères", "nl": ""},
    "ui.col_in_document": {"en": "In the document", "fr": "Dans le document", "nl": ""},
    "ui.col_sent_as": {"en": "Sent as", "fr": "Envoyé comme", "nl": ""},
    "ui.col_kind": {"en": "Kind", "fr": "Nature", "nl": ""},
    "ui.col_count": {"en": "Occurrences", "fr": "Occurrences", "nl": ""},
    "ui.keep": {"en": "Keep", "fr": "Garder", "nl": ""},
    "ui.hide": {"en": "Hide", "fr": "Masquer", "nl": ""},
    "ui.kept_marker": {"en": "(kept visible)", "fr": "(laissé visible)", "nl": ""},
    "ui.new": {"en": "new", "fr": "nouveau", "nl": ""},
    "ui.user_marked": {"en": "marked by you", "fr": "marqué par vous", "nl": ""},
    "ui.mark": {"en": "Mark", "fr": "Marquer", "nl": ""},
    "ui.mark_hint": {
        "en": "A term Jude missed — exactly as written in the document",
        "fr": "Un terme que Jude a manqué — tel qu'écrit dans le document",
        "nl": "",
    },
    "ui.kind.PERSON": {"en": "person", "fr": "personne", "nl": ""},
    "ui.kind.ORG": {"en": "organisation", "fr": "organisation", "nl": ""},
    "ui.kind.LOC": {"en": "place", "fr": "lieu", "nl": ""},
    "ui.kind.EMAIL": {"en": "e-mail", "fr": "courriel", "nl": ""},
    "ui.kind.PHONE": {"en": "phone", "fr": "téléphone", "nl": ""},
    "ui.kind.IBAN": {"en": "bank account", "fr": "compte bancaire", "nl": ""},
    "ui.kind.CASE_REF": {"en": "case reference", "fr": "référence d'affaire", "nl": ""},
    "ui.kind.URL": {"en": "web address", "fr": "adresse web", "nl": ""},
    "ui.kind.SECRET": {"en": "secret", "fr": "secret", "nl": ""},
    "ui.kind.OTHER": {"en": "other", "fr": "autre", "nl": ""},
    "ui.exact_text": {
        "en": "The exact text that leaves, as Claude will read it",
        "fr": "Le texte exact qui part, tel que Claude le lira",
        "nl": "",
    },
    "ui.sha": {"en": "sha256 of this text", "fr": "sha256 de ce texte", "nl": ""},
    "ui.attest": {
        "en": (
            "I have read the list and the text above. This exact text may be handed "
            "to Claude when Claude asks for it; the record is written on this computer "
            "first."
        ),
        "fr": (
            "J'ai lu la liste et le texte ci-dessus. Ce texte exact peut être transmis "
            "à Claude quand Claude le demandera ; l'enregistrement est écrit d'abord sur "
            "cet ordinateur."
        ),
        "nl": "",
    },
    "ui.after_approve": {
        "en": (
            "Once you approve, Claude can collect this exact text the moment it asks for "
            "it, once; you can withdraw here until it does."
        ),
        "fr": (
            "Dès l'approbation, Claude peut prendre ce texte exact au moment où il le "
            "demande, une fois ; vous pouvez le retirer ici jusque-là."
        ),
        "nl": "",
    },
    "ui.approve": {"en": "Approve", "fr": "Approuver", "nl": ""},
    "ui.cancel": {"en": "Cancel", "fr": "Annuler", "nl": ""},
    "ui.text_changed": {
        "en": "The text changed since you read it. Read it again, then approve.",
        "fr": "Le texte a changé depuis votre lecture. Relisez-le, puis approuvez.",
        "nl": "",
    },
    "ui.smart_fallback": {
        "en": (
            "This matter asks for smart mode, but its zero-retention attestation does not "
            "name Claude Desktop: strict mode is used for this document."
        ),
        "fr": (
            "Ce dossier demande le mode smart, mais son attestation sans conservation ne "
            "désigne pas Claude Desktop : le mode strict est utilisé pour ce document."
        ),
        "nl": "",
    },
    "ui.approved_title": {
        "en": "Approved. Claude has not collected the text yet.",
        "fr": "Approuvé. Claude n'a pas encore pris le texte.",
        "nl": "",
    },
    "ui.step_approved": {
        "en": "You approved this exact text. Record written on this computer:",
        "fr": "Vous avez approuvé ce texte exact. Enregistrement écrit sur cet ordinateur :",
        "nl": "",
    },
    "ui.step_tell": {
        "en": "Tell Claude, in the chat:",
        "fr": "Dites à Claude, dans la conversation :",
        "nl": "",
    },
    "ui.nudge_phrase": {"en": "Approved in Jude.", "fr": "Approuvé dans Jude.", "nl": ""},
    "ui.copy": {"en": "Copy", "fr": "Copier", "nl": ""},
    "ui.no_session": {
        "en": (
            "This tab has no Jude session. Open the window again from Claude, or run "
            "`jude mcp open` in a terminal."
        ),
        "fr": (
            "Cet onglet n'a pas de session Jude. Rouvrez la fenêtre depuis Claude, ou "
            "lancez `jude mcp open` dans un terminal."
        ),
        "nl": "",
    },
    "ui.step_tell_why": {
        "en": "Claude cannot see this window; your message tells it the text is ready.",
        "fr": (
            "Claude ne voit pas cette fenêtre ; c'est votre message qui lui dit que le "
            "texte est prêt."
        ),
        "nl": "",
    },
    "ui.step_collect": {
        "en": "Claude collects the text once. This page then says \"Collected\".",
        "fr": "Claude prend le texte une fois. Cette page dira alors « Pris ».",
        "nl": "",
    },
    "ui.approved_window": {
        "en": (
            "Claude may collect it from now on; the approval lapses after 30 minutes and "
            "nothing leaves."
        ),
        "fr": (
            "Claude peut le prendre dès maintenant ; l'approbation s'éteint après 30 "
            "minutes et rien ne part."
        ),
        "nl": "",
    },
    "ui.withdraw": {
        "en": "Withdraw approval — possible until Claude collects",
        "fr": "Retirer l'approbation — possible jusqu'à ce que Claude prenne le texte",
        "nl": "",
    },
    "ui.too_late": {
        "en": (
            "Claude collected the text before you withdrew; the record below is the one "
            "that counts."
        ),
        "fr": (
            "Claude a pris le texte avant votre retrait ; l'enregistrement ci-dessous fait "
            "foi."
        ),
        "nl": "",
    },
    "ui.released_title": {
        "en": "Collected by Claude at",
        "fr": "Pris par Claude à",
        "nl": "",
    },
    "ui.copy_answer": {"en": "Copy", "fr": "Copier", "nl": ""},
    "ui.expires_in": {
        "en": "This review closes after 20 minutes without you —",
        "fr": "Cette relecture se ferme après 20 minutes sans vous —",
        "nl": "",
    },
    "ui.answers_title": {
        "en": "Claude's answers, with the real names (shown only here)",
        "fr": "Les réponses de Claude, avec les vrais noms (affichées ici seulement)",
        "nl": "",
    },
    "ui.no_answer_yet": {
        "en": "No answer shown yet. Ask Claude to show its answer in Jude.",
        "fr": (
            "Aucune réponse affichée pour l'instant. Demandez à Claude d'afficher sa réponse "
            "dans Jude."
        ),
        "nl": "",
    },
    "ui.answer_warning": {
        "en": (
            "Text written by the model. Jude only replaced the pseudonyms it had "
            "issued for this document; read it as you would any draft."
        ),
        "fr": (
            "Texte écrit par le modèle. Jude n'a remplacé que les pseudonymes qu'il "
            "avait émis pour ce document ; lisez-le comme tout brouillon."
        ),
        "nl": "",
    },
    "ui.legend": {"en": "Legend", "fr": "Légende", "nl": ""},
    "ui.unknown_pseudonym": {
        "en": "Unknown pseudonym, not issued for this document (left as written):",
        "fr": "Pseudonyme inconnu, non émis pour ce document (laissé tel quel) :",
        "nl": "",
    },
    "ui.closed_cancelled": {
        "en": "Cancelled. Nothing was shared.",
        "fr": "Annulé. Rien n'a été partagé.",
        "nl": "",
    },
    "ui.closed_withdrawn": {
        "en": "Withdrawn. Nothing was shared.",
        "fr": "Retiré. Rien n'a été partagé.",
        "nl": "",
    },
    "ui.closed_expired": {
        "en": "Expired. Nothing was shared.",
        "fr": "Expiré. Rien n'a été partagé.",
        "nl": "",
    },
    "ui.closed_failed": {
        "en": "Jude could not prepare this document. Nothing was shared.",
        "fr": "Jude n'a pas pu préparer ce document. Rien n'a été partagé.",
        "nl": "",
    },
    "ui.error.models_missing": {
        "en": (
            "Jude cannot prepare documents yet: a language component is not installed "
            "for the Jude that Claude Desktop runs."
        ),
        "fr": (
            "Jude ne peut pas encore préparer de documents : un composant de langue n'est "
            "pas installé pour le Jude que Claude Desktop lance."
        ),
        "nl": "",
    },
    "ui.error.component_missing": {
        "en": (
            "A Jude component for this file type is not installed for the Jude that "
            "Claude Desktop runs."
        ),
        "fr": (
            "Un composant Jude pour ce type de fichier n'est pas installé pour le Jude "
            "que Claude Desktop lance."
        ),
        "nl": "",
    },
    "ui.missing.spacy_en": {
        "en": "English language model (en_core_web_lg)",
        "fr": "Modèle de langue anglais (en_core_web_lg)",
        "nl": "",
    },
    "ui.missing.spacy_fr": {
        "en": "French language model (fr_core_news_md)",
        "fr": "Modèle de langue français (fr_core_news_md)",
        "nl": "",
    },
    "ui.missing.spacy_nl": {
        "en": "Dutch language model (nl_core_news_md)",
        "fr": "Modèle de langue néerlandais (nl_core_news_md)",
        "nl": "",
    },
    "ui.missing.gliner": {
        "en": "GLiNER weights (urchade/gliner_small-v2.1), not in the local cache",
        "fr": "Poids GLiNER (urchade/gliner_small-v2.1), absents du cache local",
        "nl": "",
    },
    "ui.missing.gliner_package": {
        "en": "GLiNER package: `pip install \"jude[gliner]\"`",
        "fr": "Paquet GLiNER : `pip install \"jude[gliner]\"`",
        "nl": "",
    },
    "ui.missing.pdf": {
        "en": "PDF reader: `pip install \"jude[pdf]\"`",
        "fr": "Lecteur PDF : `pip install \"jude[pdf]\"`",
        "nl": "",
    },
    "ui.missing.xlsx": {
        "en": "Excel reader: `pip install \"jude[xlsx]\"`",
        "fr": "Lecteur Excel : `pip install \"jude[xlsx]\"`",
        "nl": "",
    },
    "ui.missing.command": {
        "en": (
            "In a terminal: `jude mcp doctor --as-desktop --fix`. It downloads once, from "
            "the terminal; Jude never downloads while running as a plugin."
        ),
        "fr": (
            "Dans un terminal : `jude mcp doctor --as-desktop --fix`. Le téléchargement se "
            "fait une fois, depuis le terminal ; Jude ne télécharge jamais quand il tourne "
            "comme plugin."
        ),
        "nl": "",
    },
    "ui.error.needs_ocr": {
        "en": (
            "This PDF is a scan without a text layer. OCR is off in the plugin; run "
            "`jude redact --ocr` in a terminal, then prepare the result."
        ),
        "fr": (
            "Ce PDF est un scan sans couche texte. L'OCR est désactivée dans le plugin ; "
            "lancez `jude redact --ocr` dans un terminal, puis préparez le résultat."
        ),
        "nl": "",
    },
    "ui.error.too_long": {
        "en": (
            "The document is longer than 150 000 characters (about 50 pages): split it in "
            "Word and prepare the parts one by one."
        ),
        "fr": (
            "Le document dépasse 150 000 caractères (environ 50 pages) : découpez-le dans "
            "Word et préparez les parties une à une."
        ),
        "nl": "",
    },
    "ui.error.no_text": {
        "en": "No text could be read from the document.",
        "fr": "Aucun texte n'a pu être lu dans le document.",
        "nl": "",
    },
    "ui.error.unreadable": {
        "en": "The document could not be read.",
        "fr": "Le document n'a pas pu être lu.",
        "nl": "",
    },
    "ui.error.internal": {
        "en": "Jude recorded the detail locally; run `jude mcp doctor`.",
        "fr": "Jude a enregistré le détail localement ; lancez `jude mcp doctor`.",
        "nl": "",
    },
    "ui.error.stale_page": {
        "en": "This page was out of date and has been refreshed.",
        "fr": "Cette page n'était plus à jour et a été rafraîchie.",
        "nl": "",
    },
    "ui.error.refused": {
        "en": "The approved text did not match its record and was not released.",
        "fr": (
            "Le texte approuvé ne correspondait pas à son enregistrement et n'a pas été "
            "transmis."
        ),
        "nl": "",
    },
    "ui.error.unsupported_suffix": {
        "en": "Only .txt, .md, .docx, .pdf and .xlsx files are accepted.",
        "fr": "Seuls les fichiers .txt, .md, .docx, .pdf et .xlsx sont acceptés.",
        "nl": "",
    },
    "ui.error.oversize": {
        "en": "The file is larger than 50 MiB.",
        "fr": "Le fichier dépasse 50 Mio.",
        "nl": "",
    },
    "ui.error.unknown_entity": {
        "en": "That item is no longer in the list.",
        "fr": "Cet élément n'est plus dans la liste.",
        "nl": "",
    },
    "ui.error.not_found": {
        "en": "That term does not appear in the document exactly as written.",
        "fr": "Ce terme n'apparaît pas dans le document tel qu'écrit.",
        "nl": "",
    },
    "ui.error.expired": {
        "en": "This review expired. Start again from Claude.",
        "fr": "Cette relecture a expiré. Recommencez depuis Claude.",
        "nl": "",
    },
    "ui.error.generic": {
        "en": "Jude could not do that. Try again.",
        "fr": "Jude n'a pas pu faire cela. Réessayez.",
        "nl": "",
    },
    "banner.server_gone": {
        "en": "Jude is no longer running. Close this tab and start again from Claude.",
        "fr": "Jude ne tourne plus. Fermez cet onglet et recommencez depuis Claude.",
        "nl": "",
    },
}

# Keys the server may hand to the model as a ``next`` hint or a ToolError.
MODEL_KEYS: tuple[str, ...] = tuple(
    k for k in STRINGS if k.startswith("next.") or k.startswith("err.")
)

TOOL_DESCRIPTIONS: dict[str, str] = {
    "prepare_document": (
        "Start a Jude review so the user can hand you one document from their own "
        "computer with the confidential names replaced by pseudonyms such as Org1 or "
        "Person2. Takes no arguments: the user chooses the matter and the document in "
        "the Jude window on their computer, so never ask the user which matter or "
        "which file, and never ask them to paste the document into the chat. Returns "
        "a review_id and a status. The document itself arrives later, through "
        "fetch_approved, only after the user has approved it in the Jude window."
    ),
    "fetch_approved": (
        "Collect the approved, pseudonymized text of a review started with "
        "prepare_document. Call it only after the user says they have approved in "
        "the Jude window. It waits up to wait_seconds (between 5 and 30) and returns "
        "the text once the review is released. The text is handed out once, so keep "
        "the copy you receive. If the status is not released, stop and wait for the "
        "user to say they have approved; call this at most three times for one "
        "approval, never in a loop."
    ),
    "show_answer": (
        "Show your answer about an approved document to the user in the Jude window, "
        "where Jude puts the real names back locally. Pass the review_id of the "
        "document you received through fetch_approved and the full text of your "
        "answer, using the pseudonyms exactly as you received them (Org1, Person2). "
        "Returns only a status and a character count: the real names never come back "
        "to you."
    ),
}

INSTRUCTIONS: str = (
    "Jude keeps the user's confidential documents on their own computer and lets them "
    "hand you one document at a time with the names replaced by pseudonyms.\n"
    "Flow: (1) When the user wants you to read, summarise or analyse a document, call "
    "prepare_document with no arguments, then tell the user to choose the matter and the "
    "document in the Jude window, review it and approve. (2) When the user says "
    "'Approved' or 'Approved in Jude', call fetch_approved with the review_id. If the "
    "status is released, the text is in the result. Otherwise stop and wait until the "
    "user says they have approved; do not call it in a loop. (3) Write your answer with "
    "the pseudonyms exactly as received and call show_answer with the review_id so the "
    "user reads it with the real names in the Jude window.\n"
    "Never try to guess the real names behind the pseudonyms, never ask the user which "
    "matter or which file to use, and never ask them to paste the document into the chat. "
    "If prepare_document returns status other_review_open, the window already has a review "
    "from another conversation: tell the user to finish or cancel it there and do not call "
    "fetch_approved."
)

TOOL_NAMES: tuple[str, ...] = ("prepare_document", "fetch_approved", "show_answer")


def text(key: str, lang: str = "en") -> str:
    """Return ``STRINGS[key]`` in ``lang``, falling back to English when the
    column is empty (the ``nl`` column, until it is translated)."""

    entry = STRINGS[key]
    value = entry.get(lang) or ""
    return value or entry["en"]
