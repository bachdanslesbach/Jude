#!/bin/zsh
# Double-clic depuis le Finder : réintègre les .docx relus, re-score, affiche le résultat.
cd "$(dirname "$0")/.." || exit 1
source .venv/bin/activate
python scripts/review_ingest.py
echo
echo "Vous pouvez fermer cette fenêtre."
